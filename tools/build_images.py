#!/usr/bin/env python3
"""Generates images.json: item name -> picture file name on the WFCD image CDN (https://cdn.warframestat.us/img/<file>).

Source: WFCD/warframe-items (data/json, the "imageName" of every item). The program uses it for the Builds tab's pictures
(Warframes, weapons, companions, mods, Arcanes): one request per picture, before the Warframe wiki.
Usage:  python tools/build_images.py --wfcd <folder of warframe-items data/json> [--out data/images.json]"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

FILES = ("Warframes", "Primary", "Secondary", "Melee", "Arch-Gun", "Arch-Melee", "Archwing", "Sentinels", "SentinelWeapons",
         "Pets", "Mods", "Arcanes", "Resources", "Gear")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wfcd", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "images.json"))
    a = ap.parse_args()
    out = {}
    for f in FILES:
        p = Path(a.wfcd) / f"{f}.json"
        if not p.exists():
            continue
        for x in json.loads(p.read_text(encoding="utf-8")):
            name, img = x.get("name"), x.get("imageName")
            if isinstance(name, str) and isinstance(img, str) and img and name not in out:
                out[name] = img
    doc = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "source": "WFCD/warframe-items imageName",
           "cdn": "https://cdn.warframestat.us/img/", "images": dict(sorted(out.items()))}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} pictures -> {a.out}")


if __name__ == "__main__":
    main()
