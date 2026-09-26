#!/usr/bin/env python3
"""
Refresh data/week.json with 15 uplifting stories from the prior calendar week.

Monday cron/routine friendly. Prefers freely readable, accessible writeups —
tech products/tools, space, AI-for-good, open source, conservation, community —
over dense journal abstracts. Assigns impact 1–5. No API key required
(DuckDuckGo HTML). Keeps prior file if too few candidates.
Monday deploy: run this script, then git commit + push so GitHub Pages picks up data/week.json.
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
UA = "WhatsGoodInTheWorldRefresh/1.2 (+local; positive-news curator)"
NEED = 15

# Prefer accessible newsy sources + tech/space/open-source; still allow WHO/uni
POSITIVE_QUERIES = [
    "site:science.nasa.gov OR site:nasa.gov open source OR AI OR Artemis",
    "site:esa.int OR site:philab.esa.int Earth observation OR open",
    "site:techcrunch.com OR site:theverge.com useful OR open source OR accessibility",
    "site:who.int verifies OR eliminates OR validates",
    "open source tool OR software release GitHub university OR NASA",
    "conservation recovery wildlife sanctuary OR reintroduction",
    "AI for good OR machine learning bees OR accessibility OR assistive",
    "space mission OR lunar OR satellite open data positive",
    "community restoration OR habitat return wildlife trust",
    "site:news.mongabay.com OR site:smithsonianmag.com conservation",
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
    r"community|sanctuary|reintroduc|habitat)\b",
    re.I,
)

TECH_HINTS = re.compile(
    r"\b(open[- ]source|software|app|AI|artificial intelligence|"
    r"robot|satellite|NASA|ESA|lunar|space|gadget|tool|"
    r"Hugging Face|GitHub|accessibility|assistive)\b",
    re.I,
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
    blob = f"{title} {summary}"
    if NEG_HINTS.search(blob) and not POS_HINTS.search(blob):
        return -1.0
    score = 0.0
    score += 1.5 * len(POS_HINTS.findall(blob))
    score -= 1.0 * len(NEG_HINTS.findall(blob))
    # Prefer digestible tech / accessible news over dense paper language
    score += 2.0 * len(TECH_HINTS.findall(blob))
    if DENSE_HINTS.search(blob):
        score -= 2.5
    host = urllib.parse.urlparse(url).netloc.lower()
    preferred = (
        "nasa.gov", "esa.int", "who.int", "techcrunch.com", "theverge.com",
        "smithsonianmag.com", "mongabay.com", "cam.ac.uk", "colorado.edu",
        "mit.edu", "ucr.edu", "ibm.com", "huggingface.co", "github.com",
        "wildlife", "nationaltrust", "halotrust",
    )
    if any(h in host for h in preferred):
        score += 2.5
    elif any(h in host for h in ("edu", "ac.uk", "gov", "int")):
        score += 1.5
    # Soft preference for news/blog paths over /articles/ journal URLs
    path = urllib.parse.urlparse(url).path.lower()
    if "/news" in path or "/blog" in path or "/smart-news" in path:
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
    for sc, story in candidates:
        norm = re.sub(r"[^a-z0-9]+", "", story["title"].lower())[:48]
        if any(norm[:24] in t or t[:24] in norm for t in titles_norm):
            continue
        is_tech = bool(TECH_HINTS.search(f"{story['title']} {story['summary']} {story['url']}"))
        titles_norm.append(norm)
        story["impact"] = impact_from_score(sc, len(picked))
        picked.append(story)
        if is_tech:
            tech_count += 1
        if len(picked) >= need:
            break
    # Second pass: if tech under-represented, try to swap in remaining tech candidates
    if tech_count < 5:
        for sc, story in candidates:
            if len(picked) >= need and tech_count >= 5:
                break
            if not TECH_HINTS.search(f"{story['title']} {story['summary']} {story['url']}"):
                continue
            norm = re.sub(r"[^a-z0-9]+", "", story["title"].lower())[:48]
            if any(norm[:24] in t or t[:24] in norm for t in titles_norm):
                continue
            if len(picked) >= need:
                # replace lowest-impact non-tech
                for i in range(len(picked) - 1, -1, -1):
                    if not TECH_HINTS.search(f"{picked[i]['title']} {picked[i]['summary']}"):
                        story["impact"] = picked[i]["impact"]
                        picked[i] = story
                        titles_norm[i] = norm
                        tech_count += 1
                        break
            else:
                story["impact"] = impact_from_score(sc, len(picked))
                picked.append(story)
                titles_norm.append(norm)
                tech_count += 1
    return picked


def main() -> int:
    week_of = prior_week_monday()
    print(f"Refreshing {NEED} stories for week of {week_of.isoformat()} …")
    stories = harvest(week_of, need=NEED)

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
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(payload['stories'])} stories:")
    for s in payload["stories"]:
        print(f"  [{s['impact']}] {s['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
