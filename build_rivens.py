#!/usr/bin/env python3
"""Generates rivens.json: what is needed to turn a riven's raw numbers into the stats shown in game.

Source: https://github.com/calamity-inc/warframe-public-export-plus (converted official game data).
Usage:  python build_rivens.py [--out rivens.json] [--cache download_folder]
  weapons: weapon path -> [English name, disposition]      (disposition = "omegaAttenuation" in the game data)
  types:   riven mod type -> {stat tag: [base value, prefix, suffix, is percentage (0/1), English label]}
"""
import argparse
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from build_vendors import fetch

RIVEN_TYPE = re.compile(r"/Lotus/Upgrades/Mods/Randomized/(Lotus|Player)\w*RandomModRare$")


def clean_label(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")                 # colour tags such as <DT_FIRE_COLOR>
    text = re.sub(r"\|val\|%?", "", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("rivens.json")))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    lang = fetch("dict.en", cache)
    weapons = {}
    for path, w in fetch("ExportWeapons", cache).items():
        if isinstance(w, dict) and isinstance(w.get("omegaAttenuation"), (int, float)) and lang.get(w.get("name", "")):
            weapons[path] = [lang[w["name"]], w["omegaAttenuation"]]
    types = {}
    for path, u in fetch("ExportUpgrades", cache).items():
        if not RIVEN_TYPE.search(path) or not isinstance(u, dict):
            continue
        stats = {}
        for e in u.get("upgradeEntries") or []:
            vals = e.get("upgradeValues") or []
            if not vals or "tag" not in e:
                continue
            text = lang.get(vals[0].get("locTag", ""), "")
            stats[e["tag"]] = [vals[0]["value"], lang.get(e.get("prefixTag", ""), ""), lang.get(e.get("suffixTag", ""), ""),
                               1 if "%" in text else 0, clean_label(text)]
        if stats:
            types[path] = stats
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "source": "calamity-inc/warframe-public-export-plus", "weapons": weapons, "types": types}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(weapons)} weapons, {len(types)} riven types -> {a.out}")


if __name__ == "__main__":
    main()
