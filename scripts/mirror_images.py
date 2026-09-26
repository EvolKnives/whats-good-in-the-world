#!/usr/bin/env python3
"""Download + compress story images into images/<story-id>-<n>.{jpg|webp}."""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WEEK = ROOT / "data" / "week.json"
OUT = ROOT / "images"
MAX_W = 1200
JPEG_Q = 80
WEBP_Q = 78
UA = (
    "Mozilla/5.0 (compatible; WhatsGoodBot/1.0; +https://evolknives.github.io/"
    "whats-good-in-the-world/)"
)

# Soft Wikimedia / public alternatives when primary URL fails
ALTERNATES: dict[str, list[str]] = {
    "nasa-and-ibm-open-source-an-ai-model-for-mapping": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/FullMoon2010.jpg/1280px-FullMoon2010.jpg",
    ],
    "portland-s-springwater-wetlands-wins-national-fl": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Wetland.jpg/1280px-Wetland.jpg",
    ],
    "oregon-state-chemists-invent-a-greener-way-to-se": [
        "https://commons.wikimedia.org/wiki/Special:FilePath/Idrossido_di_rame.jpg?width=1280",
    ],
    "portland-monarchs-get-digital-trackers-you-can-f": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Danaus_plexippus_MHNT.jpg/1280px-Danaus_plexippus_MHNT.jpg",
    ],
    "ai-helps-find-scents-that-steer-bees-away-from-p": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Apis_mellifera_-_Carduus_crispus_-_Keila.jpg/1280px-Apis_mellifera_-_Carduus_crispus_-_Keila.jpg",
    ],
    "partners-launch-research-to-bring-sea-otters-bac": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Sea_otter_cropped.jpg/1280px-Sea_otter_cropped.jpg",
    ],
    "chinook-salmon-reclaim-most-of-their-historic-kl": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Chinook_salmon.jpg/1280px-Chinook_salmon.jpg",
    ],
    "getty-brings-reynolds-portrait-of-mai-to-los-ang": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Portrait_of_Omai_by_Sir_Joshua_Reynolds.jpg/1024px-Portrait_of_Omai_by_Sir_Joshua_Reynolds.jpg",
    ],
    "iron-canyon-fish-passage-reopens-8-5-miles-of-co": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Salmon_jumping.jpg/1280px-Salmon_jumping.jpg",
    ],
    "open-source-orca-turns-everyday-radios-into-scie": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Amateur_radio_station.jpg/1280px-Amateur_radio_station.jpg",
    ],
    "olive-ridley-turtles-nest-on-the-u-s-west-coast-": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Habalikhati_Island_Turtle_Site.jpg/1280px-Habalikhati_Island_Turtle_Site.jpg",
    ],
    "xerces-maps-a-statewide-oregon-pollinator-conser": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Monarch_Butterfly_Danaus_plexippus_Male_2664px.jpg/1280px-Monarch_Butterfly_Danaus_plexippus_Male_2664px.jpg",
    ],
    "smithsonian-s-african-american-history-museum-ma": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/NMAAHC.jpg/1280px-NMAAHC.jpg",
    ],
    "free-digital-twin-lets-anyone-explore-assisi-s-g": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Assisi_Panorama.jpg/1280px-Assisi_Panorama.jpg",
    ],
    "thailand-eliminates-rubella-as-a-public-health-p": [
        "https://commons.wikimedia.org/wiki/Special:FilePath/MMR_vaccine.jpg?width=1280",
    ],
    "nasa-prithvi-ai-in-orbit": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/ISS_after_completion.jpg/1280px-ISS_after_completion.jpg",
    ],
    "nasa-galapagos-tortoises-satellite": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Galapagos_tortoise_Santa_Cruz.jpg/1280px-Galapagos_tortoise_Santa_Cruz.jpg",
    ],
    "noaa-indian-river-lagoon-restore": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Lagoon.jpg/1280px-Lagoon.jpg",
    ],
    "oregon-zoo-sihek-palmyra": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Todiramphus_cinnamominus.jpg/1024px-Todiramphus_cinnamominus.jpg",
    ],
    "met-3d-models-open-access": [
        "https://images.metmuseum.org/CRDImages/dp/web-large/DT1567.jpg",
    ],
    "met-gilded-predator-moche": [
        "https://images.metmuseum.org/CRDImages/ao/web-large/DT4655.jpg",
    ],
    "usgs-landsat-next-free-data": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Landsat_8_first_light_image.jpg/1280px-Landsat_8_first_light_image.jpg",
    ],
    "nasa-eyes-free-solar-system": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Solar_sys.jpg/1280px-Solar_sys.jpg",
    ],
    "nga-always-free-admission": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/National_Gallery_of_Art.jpg/1280px-National_Gallery_of_Art.jpg",
    ],
    "esa-earth-observation-open": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Sentinel-2.jpg/1280px-Sentinel-2.jpg",
    ],
    "data-gov-open-datasets": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Data_visualization_process_v1.png/1280px-Data_visualization_process_v1.png",
    ],
    "huggingface-nasa-models": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Open_science_logo.svg/1024px-Open_science_logo.svg.png",
    ],
}


def fetch(url: str, timeout: int = 45) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if len(data) < 200:
                return None
            return data
    except Exception as e:
        print(f"  FAIL fetch: {e}", flush=True)
        return None


def make_placeholder(path: Path, label: str) -> None:
    w, h = 1200, 750
    img = Image.new("RGB", (w, h), (232, 232, 237))
    draw = ImageDraw.Draw(img)
    # soft gradient bars
    for y in range(h):
        t = y / h
        c = int(232 - 18 * t)
        draw.line([(0, y), (w, y)], fill=(c, c, c + 2))
    draw.rounded_rectangle([40, 40, w - 40, h - 40], radius=24, outline=(200, 200, 205), width=2)
    text = "Photo coming soon"
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((w // 2 - 60, h // 2 - 8), text, fill=(120, 120, 128), font=font)
    img.save(path, "JPEG", quality=82, optimize=True)


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

    if webp_bytes and len(webp_bytes) < len(jpg_bytes) * 0.92:
        webp_path.write_bytes(webp_bytes)
        if jpg_path.exists():
            jpg_path.unlink()
        return webp_path

    jpg_path.write_bytes(jpg_bytes)
    if webp_path.exists():
        webp_path.unlink()
    return jpg_path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(WEEK.read_text())
    # Map unique URL -> first (story_id, index) for naming; then rewrite all refs
    url_to_local: dict[str, str] = {}
    failed: list[tuple[str, str, str]] = []
    mirrored = 0
    placeholders = 0

    # Collect unique URLs with preferred naming from first occurrence
    unique: list[tuple[str, int, str]] = []
    seen: set[str] = set()
    for key in ("stories", "pool"):
        for story in data.get(key) or []:
            sid = story.get("id") or "story"
            for i, url in enumerate(story.get("images") or []):
                if not url or url in seen:
                    continue
                seen.add(url)
                unique.append((sid, i, url))

    print(f"Unique images: {len(unique)}", flush=True)

    for sid, i, url in unique:
        base = OUT / f"{sid}-{i}"
        # skip if already have a local file for this base
        existing = None
        for ext in (".webp", ".jpg", ".jpeg", ".png"):
            p = base.with_suffix(ext)
            if p.exists() and p.stat().st_size > 500:
                existing = p
                break
        if existing:
            rel = f"images/{existing.name}"
            url_to_local[url] = rel
            print(f"SKIP existing {rel}", flush=True)
            mirrored += 1
            continue

        print(f"GET [{sid}-{i}] {url[:90]}...", flush=True)
        raw = fetch(url)
        source_used = url
        if raw is None:
            for alt in ALTERNATES.get(sid, []):
                print(f"  try alt: {alt[:90]}...", flush=True)
                raw = fetch(alt)
                if raw:
                    source_used = alt
                    break

        if raw is None:
            ph = base.with_suffix(".jpg")
            make_placeholder(ph, sid)
            rel = f"images/{ph.name}"
            url_to_local[url] = rel
            failed.append((sid, url, "placeholder"))
            placeholders += 1
            print(f"  PLACEHOLDER {rel}", flush=True)
            continue

        out = compress(raw, base)
        if out is None:
            ph = base.with_suffix(".jpg")
            make_placeholder(ph, sid)
            rel = f"images/{ph.name}"
            url_to_local[url] = rel
            failed.append((sid, url, "bad-decode-placeholder"))
            placeholders += 1
            print(f"  PLACEHOLDER {rel}", flush=True)
            continue

        rel = f"images/{out.name}"
        url_to_local[url] = rel
        mirrored += 1
        print(f"  OK {rel} ({out.stat().st_size // 1024} KB) via {source_used[:60]}", flush=True)
        time.sleep(0.15)

    # Rewrite all image arrays
    for key in ("stories", "pool"):
        for story in data.get(key) or []:
            imgs = story.get("images") or []
            new_imgs = []
            for u in imgs:
                if u in url_to_local:
                    new_imgs.append(url_to_local[u])
                elif isinstance(u, str) and u.startswith("images/"):
                    new_imgs.append(u)
                else:
                    # leave as-is only if somehow missed — shouldn't happen
                    new_imgs.append(u)
            story["images"] = new_imgs

    WEEK.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("---", flush=True)
    print(f"mirrored_ok={mirrored} placeholders={placeholders} unique={len(unique)}", flush=True)
    for sid, url, why in failed:
        print(f"FAILED {sid}: {why} :: {url[:100]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
