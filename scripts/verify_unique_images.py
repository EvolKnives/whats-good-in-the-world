#!/usr/bin/env python3
"""Verify every story primary image is unique by MD5 and exists on disk."""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEEK = ROOT / "data" / "week.json"
LIVE = "https://evolknives.github.io/whats-good-in-the-world/"


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    data = json.loads(WEEK.read_text())
    by_id: dict[str, dict] = {}
    for s in (data.get("stories") or []) + (data.get("pool") or []):
        by_id[s["id"]] = s

    prim: dict[str, list] = defaultdict(list)
    missing = []
    for sid, s in by_id.items():
        imgs = s.get("images") or []
        if not imgs:
            missing.append((sid, "(no images)"))
            continue
        path = ROOT / imgs[0]
        if not path.exists():
            missing.append((sid, imgs[0]))
            continue
        prim[md5_file(path)].append((sid, imgs[0]))

    dups = {h: v for h, v in prim.items() if len(v) > 1}
    print(f"stories={len(by_id)} unique_primary_hashes={len(prim)} dup_groups={len(dups)}")
    if missing:
        print("MISSING:")
        for sid, p in missing:
            print(f"  {sid} -> {p}")
    if dups:
        print("DUPLICATES:")
        for h, v in dups.items():
            print(f"  {h}: {v}")

    check_live = "--live" in sys.argv
    live_fail = []
    if check_live:
        ua = {"User-Agent": "WhatsGoodBot/1.0 verify"}
        for sid, s in sorted(by_id.items()):
            for img in s.get("images") or []:
                url = LIVE + img
                req = urllib.request.Request(url, method="HEAD", headers=ua)
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        code = resp.status
                except urllib.error.HTTPError as e:
                    code = e.code
                except Exception as e:
                    code = str(e)
                ok = code == 200
                mark = "OK" if ok else "FAIL"
                print(f"  {mark} {code} {img}")
                if not ok:
                    live_fail.append((img, code))

    if missing or dups or live_fail:
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
