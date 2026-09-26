#!/usr/bin/env python3
"""Replace duplicate primary images so every story has unique content-hash hero."""
from __future__ import annotations

import hashlib
import io
import json
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WEEK = ROOT / "data" / "week.json"
OUT = ROOT / "images"
MAX_W = 1200
JPEG_Q = 80
WEBP_Q = 78
UA = (
    "WhatsGoodBot/1.0 (educational; +https://github.com/EvolKnives/"
    "whats-good-in-the-world)"
)

# Keepers: leave existing primary as-is (on-topic or unique already).
# Everyone else listed in REPLACE gets a fresh download.

REPLACE: dict[str, str] = {
    # Blue Marble cluster (keep nasa-earthdata-open)
    "chinook-salmon-reclaim-most-of-their-historic-kl":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d8/Chinook_Salmon_Adult_Male.jpg/1280px-Chinook_Salmon_Adult_Male.jpg",
    "nasa-galapagos-tortoises-satellite":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/17/20180809-Gal%C3%A1pagos_giant_tortoise_eating_leaves_%289960%29.jpg/1280px-20180809-Gal%C3%A1pagos_giant_tortoise_eating_leaves_%289960%29.jpg",
    "nps-cuyahoga-habitat-day":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/9d/Illuminating_the_Ledges_%28Cuyahoga_Valley_National_Park%29.jpg/1280px-Illuminating_the_Ledges_%28Cuyahoga_Valley_National_Park%29.jpg",
    "marsh-billings-forest-fest":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/97/Marsh-Billings-Rockefeller_National_Historical_Park%2C_Vermont_LOC_2003620566.jpg/1280px-Marsh-Billings-Rockefeller_National_Historical_Park%2C_Vermont_LOC_2003620566.jpg",
    "usgs-landsat-next-free-data":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/69/Elephant_Island_by_Landsat_8.jpeg/1280px-Elephant_Island_by_Landsat_8.jpeg",
    "fws-refuge-volunteer-habitat":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/67/Sharps_Fire_Planting_and_Habitat_Restoration_%281%29_%2848942546271%29.jpg/1280px-Sharps_Fire_Planting_and_Habitat_Restoration_%281%29_%2848942546271%29.jpg",
    "smithsonian-open-access":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c0/Smithsonian_Building_NR.jpg/1280px-Smithsonian_Building_NR.jpg",
    "opb-oregon-science-desk":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c1/Crater_Lake_-_Oregon_-_panoramio.jpg/1280px-Crater_Lake_-_Oregon_-_panoramio.jpg",
    "oregon-state-newsroom-free":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/bf/Aerial_view_of_Oregon_State_University_campus_%286443595921%29.jpg/1280px-Aerial_view_of_Oregon_State_University_campus_%286443595921%29.jpg",
    "noaa-fisheries-habitat-stories":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6c/Mimic_goatfish_coral_reef_Howland_Island_2023.png/1280px-Mimic_goatfish_coral_reef_Howland_Island_2023.png",
    "nga-always-free-admission":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/29/East_Building_-_National_Gallery_of_Art.JPG/1280px-East_Building_-_National_Gallery_of_Art.JPG",
    "getty-open-content":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/79/Architectural_Detail_-_The_Getty_Center_-_Los_Angeles_-_California_-_USA_-_02_%2846447747094%29_%28cropped%29.jpg/1280px-Architectural_Detail_-_The_Getty_Center_-_Los_Angeles_-_California_-_USA_-_02_%2846447747094%29_%28cropped%29.jpg",
    "data-gov-open-datasets":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b8/Capitol_Dome_Restoration_-_West_Front_Early_April_%2813721830364%29.jpg/1280px-Capitol_Dome_Restoration_-_West_Front_Early_April_%2813721830364%29.jpg",
    "library-congress-free-exhibits":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a8/LOC_Main_Reading_Room_Highsmith.jpg/1280px-LOC_Main_Reading_Room_Highsmith.jpg",
    "bird-alliance-oregon":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/97/American_robin_%2871307%29.jpg/1280px-American_robin_%2871307%29.jpg",
    "xerces-pollinator-resources":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/50/Bombus_Bumblebee_%28Bestoevning%29.jpg/1280px-Bombus_Bumblebee_%28Bestoevning%29.jpg",
    "esa-earth-observation-open":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/23/Central-eastern_Brazil%2C_by_Copernicus_Sentinel-2A_satellite.jpg/1280px-Central-eastern_Brazil%2C_by_Copernicus_Sentinel-2A_satellite.jpg",
    # Pair losers / weak fits
    "noaa-wemo-open-source-r":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/2a/Big_wave_breaking_in_Santa_Cruz.jpg/1280px-Big_wave_breaking_in_Santa_Cruz.jpg",
    "nasa-eyes-free-solar-system":
        "https://commons.wikimedia.org/wiki/Special:FilePath/Solar_System_true_color.jpg?width=1280",
    "nasa-prithvi-ai-in-orbit":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/2c/Earth_and_international_space_station.jpg/1280px-Earth_and_international_space_station.jpg",
    "olive-ridley-turtles-nest-on-the-u-s-west-coast-":
        "https://commons.wikimedia.org/wiki/Special:FilePath/Lepidochelys_olivacea.jpg?width=1280",
    "uoregon-research-news":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/42/Anstett_Hall_on_the_University_of_Oregon_Campus_in_Eugene%2C_Oregon.jpg/1280px-Anstett_Hall_on_the_University_of_Oregon_Campus_in_Eugene%2C_Oregon.jpg",
    "met-3d-models-open-access":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/10/At_the_Metropolitan_Museum_of_Art%2C_New_York_2017_49_-_Marble_statue_of_a_lion.jpg/1280px-At_the_Metropolitan_Museum_of_Art%2C_New_York_2017_49_-_Marble_statue_of_a_lion.jpg",
    "oregon-zoo-sihek-palmyra":
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/4b/GuamMicronesianKingfisher_TodiramphusCinnamominusCinnamominus.jpg/1280px-GuamMicronesianKingfisher_TodiramphusCinnamominusCinnamominus.jpg",
}


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def md5_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, timeout: int = 60) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if len(data) < 500:
                print(f"  too small ({len(data)})", flush=True)
                return None
            return data
    except Exception as e:
        print(f"  FAIL fetch: {e}", flush=True)
        return None


def compress(raw: bytes, out_base: Path) -> Path | None:
    try:
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGB")
    except Exception as e:
        print(f"  FAIL decode: {e}", flush=True)
        return None

    if im.width > MAX_W:
        ratio = MAX_W / im.width
        im = im.resize((MAX_W, max(1, int(im.height * ratio))), Image.Resampling.LANCZOS)

    jpg_path = out_base.with_suffix(".jpg")
    webp_path = out_base.with_suffix(".webp")

    buf_j = io.BytesIO()
    im.save(buf_j, "JPEG", quality=JPEG_Q, optimize=True, progressive=True)
    jpg_bytes = buf_j.getvalue()

    webp_bytes = None
    try:
        buf_w = io.BytesIO()
        im.save(buf_w, "WEBP", quality=WEBP_Q, method=4)
        webp_bytes = buf_w.getvalue()
    except Exception:
        webp_bytes = None

    # Remove any prior primary with either extension
    for p in (jpg_path, webp_path):
        if p.exists():
            p.unlink()

    if webp_bytes and len(webp_bytes) < len(jpg_bytes) * 0.92:
        webp_path.write_bytes(webp_bytes)
        return webp_path

    jpg_path.write_bytes(jpg_bytes)
    return jpg_path


def collect_used_hashes(data: dict, skip_sids: set[str]) -> set[str]:
    used: set[str] = set()
    seen_ids: set[str] = set()
    for key in ("stories", "pool"):
        for story in data.get(key) or []:
            sid = story.get("id")
            if not sid or sid in seen_ids:
                continue
            seen_ids.add(sid)
            if sid in skip_sids:
                continue
            imgs = story.get("images") or []
            if not imgs:
                continue
            h = md5_file(ROOT / imgs[0])
            if h:
                used.add(h)
    return used


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(WEEK.read_text())
    used = collect_used_hashes(data, set(REPLACE))
    print(f"Existing unique primary hashes to avoid: {len(used)}", flush=True)

    ok = 0
    failed: list[str] = []
    updates: dict[str, str] = {}  # sid -> new relative path

    for sid, url in REPLACE.items():
        print(f"GET {sid}", flush=True)
        raw = fetch(url)
        if raw is None:
            failed.append(sid)
            time.sleep(0.5)
            continue
        h = md5_bytes(raw)
        if h in used:
            print(f"  COLLISION with existing hash {h} — skip", flush=True)
            failed.append(sid)
            continue
        base = OUT / f"{sid}-0"
        out = compress(raw, base)
        if out is None:
            failed.append(sid)
            continue
        out_h = md5_file(out)
        if out_h in used:
            print(f"  COLLISION after compress {out_h} — remove", flush=True)
            out.unlink(missing_ok=True)
            failed.append(sid)
            continue
        used.add(out_h)
        rel = f"images/{out.name}"
        updates[sid] = rel
        ok += 1
        print(f"  OK {rel} ({out.stat().st_size // 1024} KB) hash={out_h[:10]}", flush=True)
        time.sleep(0.4)

    # Rewrite primaries in stories + pool
    for key in ("stories", "pool"):
        for story in data.get(key) or []:
            sid = story.get("id")
            if sid not in updates:
                continue
            imgs = list(story.get("images") or [])
            if imgs:
                imgs[0] = updates[sid]
            else:
                imgs = [updates[sid]]
            story["images"] = imgs

    data["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    WEEK.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # Verify uniqueness
    by_id = {}
    for s in data["stories"] + data["pool"]:
        by_id[s["id"]] = s
    prim = defaultdict(list)
    for sid, s in by_id.items():
        p = s["images"][0]
        prim[md5_file(ROOT / p)].append((sid, p))

    unique = sum(1 for h, v in prim.items() if h and len(v) == 1)
    dups = {h: v for h, v in prim.items() if h and len(v) > 1}
    print("---", flush=True)
    print(f"replaced_ok={ok} failed={len(failed)} unique_primaries={unique}/{len(by_id)}", flush=True)
    if failed:
        print("FAILED:", ", ".join(failed), flush=True)
    if dups:
        print("STILL DUPLICATE:", flush=True)
        for h, v in dups.items():
            print(f"  {h}: {[s for s,_ in v]}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
