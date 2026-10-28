#!/usr/bin/env python3
"""Generates challenges.json: names and descriptions of Nightwave's challenges and of the 1999 Calendar's challenges, for the
Activities overlay (the world state only gives their game paths).

Source: https://github.com/calamity-inc/warframe-public-export-plus (ExportNightwave, ExportChallenges, dict.en).
Usage:  python build_challenges.py [--out challenges.json] [--cache download_folder]
  nightwave: path -> [name, description, standing, kind (daily / weekly / elite)]
  calendar:  path -> [name, description]"""
import argparse
import json
import re
import tempfile
from pathlib import Path

from build_vendors import fetch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("challenges.json")))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    lang = fetch("dict.en", cache)
    clean = lambda s: re.sub(r"<[^>]+>\s*", "", s or "").strip()

    def text(key, count):
        return clean(lang.get(key, "")).replace("|COUNT|", f"{count:,}" if isinstance(count, int) else str(count))
    nw = {}
    for path, c in (fetch("ExportNightwave", cache).get("challenges") or {}).items():
        kind = {"Daily": "daily", "Weekly": "weekly", "WeeklyHard": "elite"}.get(path.split("/")[-2], "weekly")
        nw[path] = [text(c.get("name"), c.get("required", 1)), text(c.get("description"), c.get("required", 1)),
                    int(c.get("standing") or 0), kind]
    cal = {}
    for path, c in fetch("ExportChallenges", cache).items():
        if "/Calendar1999/" in path and isinstance(c, dict):
            cal[path] = [text(c.get("name"), c.get("requiredCount", 1)), text(c.get("description"), c.get("requiredCount", 1))]
    Path(a.out).write_text(json.dumps({"nightwave": nw, "calendar": cal}, ensure_ascii=False, separators=(",", ":")),
                           encoding="utf-8")
    print(f"{len(nw)} Nightwave challenges, {len(cal)} calendar challenges -> {a.out}")


if __name__ == "__main__":
    main()
