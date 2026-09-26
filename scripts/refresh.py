#!/usr/bin/env python3
"""
Refresh data/week.json with a featured 15 plus a larger reusable pool.

Monday cron/routine friendly. Prefers USA stories (majority), with Oregon when
available (Portland, Oregon coast, Cascades, Willamette, Oregon nonprofits,
OSU/UO research, conservation, community, art, tech). Keep a little global
variety only as needed. Freely readable writeups — tech, space, AI-for-good,
open source, conservation, community, art-world wins, and recent human
achievements (records, maker builds, science milestones, community goals) —
over dense journal abstracts, controversy, or auction spectacle. Assigns impact 1–5 and stable ids.

Writes both `stories` (featured 15 for first paint / Monday label) and `pool`
(~30–45) so the site Refresh button can swap in a disjoint set of 15 client-side.
No API key required (DuckDuckGo HTML). Keeps prior file if too few candidates.
Monday deploy: run this script, then git commit + push so GitHub Pages updates.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "week.json"
UA = "WhatsGoodInTheWorldRefresh/1.4 (+local; positive-news curator)"
NEED = 15
POOL_TARGET = 40

# Prefer accessible newsy sources + tech/space/open-source; still allow WHO/uni
POSITIVE_QUERIES = [
    # USA-first (majority preference)
    "site:science.nasa.gov OR site:nasa.gov open source OR AI OR Artemis",
    "site:noaa.gov OR site:fisheries.noaa.gov habitat restoration OR recovery",
    "site:si.edu OR site:airandspace.si.edu OR site:nmaahc.si.edu free OR exhibition",
    "site:smithsonianmag.com conservation OR discovery USA",
    "site:techcrunch.com OR site:theverge.com useful OR open source OR accessibility",
    "open source tool OR software release GitHub university NASA OR MIT OR Stanford",
    "AI for good OR machine learning bees OR accessibility OR assistive USA",
    "USA conservation recovery wildlife sanctuary OR reintroduction OR fish passage",
    "site:fws.gov OR site:nps.gov restoration OR recovery habitat",
    "museum free exhibition OR heritage conservation Getty OR Met OR Smithsonian",
    # Oregon preference when available
    "Oregon Portland conservation OR restoration OR wetland OR salmon",
    "Oregon coast OR Cascades OR Willamette wildlife OR habitat OR otter",
    "site:oregonstate.edu OR site:uoregon.edu OR site:ohsu.edu research breakthrough OR discovery",
    "site:opb.org Oregon conservation OR science OR community",
    "Oregon nonprofit museum OR art OR pollinator OR monarch",
    # Human achievements (personal/team wins, records, maker builds, milestones)
    "athlete OR runner OR climber breaks record OR first person OR summit USA",
    "student inventor OR invention OR debuted OR launched open source USA OR Oregon",
    "community fundraiser reaches goal OR raised OR completed restoration USA",
    "wildlife rescued released OR habitat restored success OR fish passage complete",
    "accessibility win OR assistive technology debuted OR open source shipped GitHub",
    "NASA OR NOAA milestone OR first OR record OR completed mission",
    "Oregon Portland award OR completed OR milestone OR inventor OR graduated",
    "maker build completed OR open source release shipped university OR NASA",
    "site:reignfc.com OR site:nwslsoccer.com record OR milestone OR first",
    # Small global fill only
    "site:who.int verifies OR eliminates OR validates",
    "site:esa.int Earth observation OR open",
    "museum restoration OR free exhibition OR digital heritage conservation",
]

# Skip known paywall / contested / low-signal domains
BLOCK_HOSTS = re.compile(
    r"(nytimes\.com|wsj\.com|ft\.com|economist\.com|bloomberg\.com|"
    r"washingtonpost\.com|telegraph\.co\.uk|thetimes\.co\.uk|"
    r"foxnews\.com|breitbart\.com|dailymail\.co\.uk|nypost\.com)",
    re.I,
)

# Dense academic / clinical framing to downrank (not hard-block if newsy title)
DENSE_HINTS = re.compile(
    r"\b(epitope|senescent|nanoparticle|transcriptom|in vitro|"
    r"randomized controlled|meta-analysis|doi:|supplementary figure)\b",
    re.I,
)

NEG_HINTS = re.compile(
    r"\b(war|killed|murder|attack|scandal|corruption|shooting|"
    r"partisan|election fraud|lawsuit)\b",
    re.I,
)

POS_HINTS = re.compile(
    r"\b(recover|recovery|protect|protection|eliminate|eliminat|"
    r"restore|restoration|breakthrough|discover|hope|milestone|"
    r"success|return|rebound|open[- ]source|vaccine|conservation|"
    r"accessibility|tool|app|gadget|satellite|lunar|space|"
    r"AI|artificial intelligence|robot|software|free|"
    r"community|sanctuary|reintroduc|habitat|"
    r"museum|exhibition|gallery|fresco|mural|heritage|"
    r"street art|conservation studio|gigapixel)\b",
    re.I,
)

TECH_HINTS = re.compile(
    r"\b(open[- ]source|software|app|AI|artificial intelligence|"
    r"robot|satellite|NASA|ESA|lunar|space|gadget|tool|"
    r"Hugging Face|GitHub|accessibility|assistive)\b",
    re.I,
)

ART_HINTS = re.compile(
    r"\b(museum|gallery|exhibition|fresco|mural|heritage|"
    r"street art|conservator|restoration|gigapixel|"
    r"Tate|Louvre|Smithsonian|Met |MOCAA|ARTIST ROOMS|Getty)\b",
    re.I,
)

# Human achievement / personal-team wins (avoid war/politics/scandal via NEG_HINTS)
ACHIEVE_HINTS = re.compile(
    r"\b(achieved|achievement|record|broke record|first person|"
    r"milestone|completed|graduated|raised \$?\d|rescued|release(?:d)?|"
    r"restored habitat|won award|award[- ]winning|inventor|invented|"
    r"debuted|launched open[- ]source|climbed|summit|finished|"
    r"all[- ]time|career (?:high|record)|brace|hat[- ]trick|"
    r"fundraiser|goal (?:met|reached)|shipped|prototype|"
    r"world(?:'s)? first|for the first time)\b",
    re.I,
)

# Geographic preference: majority USA, boost Oregon
USA_HINTS = re.compile(
    r"\b(United States|U\.S\.?|USA|American|NASA|NOAA|Smithsonian|"
    r"California|Washington|Colorado|Texas|Alaska|Hawaii|Michigan|"
    r"New Jersey|Idaho|Georgia|Puerto Rico|"
    r"National Park|Fish and Wildlife|\.gov)\b",
    re.I,
)

OREGON_HINTS = re.compile(
    r"\b(Oregon|Portland|Salem|Eugene|Corvallis|Bend|Ashland|"
    r"Willamette|Cascades|Crater Lake|Columbia River|"
    r"Oregon coast|Newport|Astoria|Hood River|Klamath|"
    r"OSU|Oregon State|University of Oregon|UO |OHSU|"
    r"OPB|Xerces|Elakha|Johnson Creek|Sandy River)\b",
    re.I,
)

USA_HOSTS = (
    "nasa.gov", "noaa.gov", "si.edu", "smithsonianmag.com", "usgs.gov",
    "fws.gov", "nps.gov", "nih.gov", "energy.gov", "usda.gov",
    "edu", ".gov",
    "techcrunch.com", "theverge.com", "getty.edu", "metmuseum.org",
    "nga.gov", "npr.org", "opb.org",
)

OREGON_HOSTS = (
    "oregonstate.edu", "uoregon.edu", "ohsu.edu", "portland.gov",
    "oregon.gov", "opb.org", "oregonlive.com", "kgw.com",
    "birdallianceoregon.org", "xerces.org", "beecityusa.org",
    "wildnet.org", "aquarium.org", "elakha",
)


def prior_week_monday(today: date | None = None) -> date:
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7)


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def ddg_links(query: str, week_of: date) -> list[str]:
    q = f"{query} {week_of.year}-{week_of.month:02d}"
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q})
    try:
        html = fetch(url)
    except Exception as exc:
        print(f"search failed for {query!r}: {exc}", file=sys.stderr)
        return []
    links = re.findall(r'uddg=([^&"]+)', html)
    out: list[str] = []
    for enc in links:
        decoded = urllib.parse.unquote(enc)
        if not decoded.startswith("http"):
            continue
        if "duckduckgo.com" in decoded:
            continue
        host = urllib.parse.urlparse(decoded).netloc.lower()
        if BLOCK_HOSTS.search(host):
            continue
        out.append(decoded)
    return out


def meta(html: str, prop: str) -> str | None:
    patterns = [
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            return unescape(m.group(1).strip())
    return None


def page_title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    if not m:
        return None
    t = unescape(re.sub(r"\s+", " ", m.group(1)).strip())
    t = re.split(r"\s+[|\-—–]\s+", t)[0].strip()
    return t or None


def summarize(html: str) -> str:
    desc = meta(html, "og:description") or meta(html, "description") or ""
    desc = re.sub(r"\s+", " ", unescape(desc)).strip()
    if len(desc) < 40:
        paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)
        for p in paras[:10]:
            text = re.sub(r"<[^>]+>", " ", p)
            text = re.sub(r"\s+", " ", unescape(text)).strip()
            if len(text) > 80:
                desc = text
                break
    parts = re.split(r"(?<=[.!?])\s+", desc)
    summary = " ".join(parts[:3]).strip()
    if len(summary) > 420:
        summary = summary[:417].rsplit(" ", 1)[0] + "…"
    return summary


def source_name(url: str, html: str) -> str:
    site = meta(html, "og:site_name")
    if site:
        return site.strip()
    host = urllib.parse.urlparse(url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    return host.split(".")[0].replace("-", " ").title() if host else "Source"


def score_candidate(title: str, summary: str, url: str) -> float:
    blob = f"{title} {summary} {url}"
    if NEG_HINTS.search(blob) and not POS_HINTS.search(blob):
        return -1.0
    score = 0.0
    score += 1.5 * len(POS_HINTS.findall(blob))
    score -= 1.0 * len(NEG_HINTS.findall(blob))
    # Prefer digestible tech / accessible news over dense paper language
    score += 2.0 * len(TECH_HINTS.findall(blob))
    score += 2.0 * len(ART_HINTS.findall(blob))
    score += 2.0 * len(ACHIEVE_HINTS.findall(blob))
    if DENSE_HINTS.search(blob):
        score -= 2.5
    host = urllib.parse.urlparse(url).netloc.lower()
    preferred = (
        "nasa.gov", "noaa.gov", "si.edu", "esa.int", "who.int",
        "techcrunch.com", "theverge.com",
        "smithsonianmag.com", "mongabay.com", "cam.ac.uk", "colorado.edu",
        "mit.edu", "ucr.edu", "ibm.com", "huggingface.co", "github.com",
        "wildlife", "nationaltrust", "halotrust",
        "tate.org.uk", "asia.si.edu", "metmuseum.org", "getty.edu",
        "zeitzmocaa", "haltadefinizione", "nga.gov",
        "oregonstate.edu", "uoregon.edu", "ohsu.edu", "portland.gov",
        "opb.org", "fws.gov", "nps.gov",
    )
    if any(h in host for h in preferred):
        score += 2.5
    elif any(h in host for h in ("edu", "ac.uk", "gov", "int")):
        score += 1.5
    # Geographic preference: Oregon strongest, then USA majority
    if OREGON_HINTS.search(blob) or any(h in host for h in OREGON_HOSTS):
        score += 4.0
    elif USA_HINTS.search(blob) or any(h in host for h in USA_HOSTS):
        score += 2.5
    # Soft preference for news/blog paths over /articles/ journal URLs
    path = urllib.parse.urlparse(url).path.lower()
    if "/news" in path or "/blog" in path or "/smart-news" in path or "/feature-story" in path:
        score += 1.0
    if re.search(r"/articles/s\d+|doi\.org|abstract", path):
        score -= 1.5
    if 60 <= len(summary) <= 420:
        score += 1.0
    return score


def impact_from_score(score: float, rank: int) -> int:
    if rank == 0 and score >= 4:
        return 5
    if rank <= 1:
        return 5 if score >= 6 else 4
    if rank <= 4:
        return 4
    if rank <= 8:
        return 3
    if rank <= 12:
        return 2
    return 1


def harvest(week_of: date, need: int = NEED) -> list[dict]:
    seen: set[str] = set()
    candidates: list[tuple[float, dict]] = []

    for q in POSITIVE_QUERIES:
        for link in ddg_links(q, week_of)[:10]:
            key = urllib.parse.urlparse(link)._replace(query="", fragment="").geturl()
            if key in seen:
                continue
            seen.add(key)
            try:
                html = fetch(link)
            except Exception:
                continue
            low = html.lower()
            if "subscribe to continue" in low or "already a subscriber" in low:
                continue
            title = meta(html, "og:title") or page_title(html)
            if not title:
                continue
            summary = summarize(html)
            if len(summary) < 40:
                continue
            sc = score_candidate(title, summary, link)
            if sc < 0.5:
                continue
            images: list[str] = []
            og = meta(html, "og:image")
            if og and og.startswith("http"):
                images.append(og)
            story = {
                "title": title.strip(),
                "summary": summary,
                "source": source_name(link, html),
                "url": link,
                "impact": 3,
                "images": images[:2],
            }
            candidates.append((sc, story))

    candidates.sort(key=lambda x: x[0], reverse=True)
    picked: list[dict] = []
    titles_norm: list[str] = []
    tech_count = 0
    art_count = 0
    achieve_count = 0

    def blob_of(story: dict) -> str:
        return f"{story['title']} {story['summary']} {story.get('url', '')}"

    for sc, story in candidates:
        norm = re.sub(r"[^a-z0-9]+", "", story["title"].lower())[:48]
        if any(norm[:24] in t or t[:24] in norm for t in titles_norm):
            continue
        is_tech = bool(TECH_HINTS.search(blob_of(story)))
        is_art = bool(ART_HINTS.search(blob_of(story)))
        is_achieve = bool(ACHIEVE_HINTS.search(blob_of(story)))
        titles_norm.append(norm)
        story["impact"] = impact_from_score(sc, len(picked))
        picked.append(story)
        if is_tech:
            tech_count += 1
        if is_art:
            art_count += 1
        if is_achieve:
            achieve_count += 1
        if len(picked) >= need:
            break

    def boost_category(hint_re: re.Pattern, count: int, want: int, label: str) -> int:
        if count >= want:
            return count
        for sc, story in candidates:
            if count >= want:
                break
            if not hint_re.search(blob_of(story)):
                continue
            norm = re.sub(r"[^a-z0-9]+", "", story["title"].lower())[:48]
            if any(norm[:24] in t or t[:24] in norm for t in titles_norm):
                continue
            if len(picked) >= need:
                for i in range(len(picked) - 1, -1, -1):
                    # Prefer replacing items outside protected mix categories
                    pb = f"{picked[i]['title']} {picked[i]['summary']}"
                    if hint_re.search(pb):
                        continue
                    if label != "tech" and TECH_HINTS.search(pb):
                        continue
                    if label != "art" and ART_HINTS.search(pb):
                        continue
                    if label != "achieve" and ACHIEVE_HINTS.search(pb):
                        continue
                    story["impact"] = picked[i]["impact"]
                    picked[i] = story
                    titles_norm[i] = norm
                    count += 1
                    break
            else:
                story["impact"] = impact_from_score(sc, len(picked))
                picked.append(story)
                titles_norm.append(norm)
                count += 1
        return count

    # Second pass: keep tech, art, and achievements represented
    # Soft targets scale with need: ~5 tech / ~2 art / ~3–5 achieve in featured 15;
    # ~12 tech / ~5 art / ~10 achieve across a ~40 pool.
    want_tech = max(5, (need * 5) // 15)
    want_art = max(2, (need * 2) // 15)
    want_achieve = max(3, (need * 4) // 15)  # ~3–4 of 15; ~10 of 40
    tech_count = boost_category(TECH_HINTS, tech_count, want_tech, "tech")
    art_count = boost_category(ART_HINTS, art_count, want_art, "art")
    achieve_count = boost_category(ACHIEVE_HINTS, achieve_count, want_achieve, "achieve")

    # Third pass: prefer USA majority (soft replace non-US when USA candidates remain)
    def is_usa(story: dict) -> bool:
        b = blob_of(story)
        host = urllib.parse.urlparse(story.get("url", "")).netloc.lower()
        return bool(USA_HINTS.search(b) or OREGON_HINTS.search(b) or any(h in host for h in USA_HOSTS + OREGON_HOSTS))

    usa_count = sum(1 for s in picked if is_usa(s))
    want_usa = max(10, (need * 2) // 3)  # majority (~10 of 15)
    if usa_count < want_usa:
        for sc, story in candidates:
            if usa_count >= want_usa:
                break
            if not is_usa(story):
                continue
            norm = re.sub(r"[^a-z0-9]+", "", story["title"].lower())[:48]
            if any(norm[:24] in t or t[:24] in norm for t in titles_norm):
                continue
            # Replace weakest non-US from the end
            for i in range(len(picked) - 1, -1, -1):
                if is_usa(picked[i]):
                    continue
                story["impact"] = picked[i]["impact"]
                picked[i] = story
                titles_norm[i] = norm
                usa_count += 1
                break

    return picked


def slugify(title: str) -> str:
    s = re.sub(r"['’]", "", (title or "story").lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:48] or "story")


def ensure_ids(stories: list[dict]) -> list[dict]:
    seen: set[str] = set()
    for story in stories:
        base = slugify(str(story.get("id") or story.get("title") or "story"))
        sid = base
        n = 2
        while sid in seen:
            sid = f"{base}-{n}"
            n += 1
        story["id"] = sid
        seen.add(sid)
    return stories


def main() -> int:
    week_of = prior_week_monday()
    print(
        f"Refreshing featured {NEED} + pool (~{POOL_TARGET}) "
        f"for week of {week_of.isoformat()} …"
    )
    # Harvest a larger candidate set so Refresh can swap disjoint sets client-side
    harvested = harvest(week_of, need=POOL_TARGET)
    harvested = ensure_ids(harvested)

    # Merge with any prior pool entries that are still unique (keeps depth between Mondays)
    prior_pool: list[dict] = []
    if OUT.exists():
        try:
            prior = json.loads(OUT.read_text(encoding="utf-8"))
            prior_pool = list(prior.get("pool") or prior.get("stories") or [])
        except Exception:
            prior_pool = []

    by_id: dict[str, dict] = {}
    for story in ensure_ids(prior_pool) + harvested:
        by_id[story["id"]] = story
    pool = list(by_id.values())
    # Prefer freshly harvested order first
    fresh_ids = {s["id"] for s in harvested}
    pool.sort(key=lambda s: (0 if s["id"] in fresh_ids else 1, -float(s.get("impact") or 0)))
    pool = pool[: max(POOL_TARGET, NEED * 2)]
    pool = ensure_ids(pool)

    stories = pool[:NEED]
    min_keep = max(8, NEED // 2)
    if len(stories) < min_keep:
        print(
            f"Only found {len(stories)} candidates (need ≥{min_keep}); "
            "keeping previous week.json if present.",
            file=sys.stderr,
        )
        if OUT.exists():
            return 1
        if not stories:
            return 1

    payload = {
        "weekOf": week_of.isoformat(),
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stories": stories[:NEED],
        "pool": pool,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT} with {len(payload['stories'])} featured "
        f"+ {len(payload['pool'])} pool stories:"
    )
    for s in payload["stories"]:
        print(f"  [{s['impact']}] {s['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
