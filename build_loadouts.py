#!/usr/bin/env python3
"""Generates loadout_data.json: names the loadout view needs (from the public game data export).

Source: https://github.com/calamity-inc/warframe-public-export-plus (converted official game data).
Usage:  python build_loadouts.py [--out loadout_data.json] [--cache download_folder]
  mods:      mod path -> [English name, max rank]
  rarity:    English mod name -> C/U/R/L (for the Endo cost of ranking a mod up)
  arcanes:   arcane path -> [English name, max rank]
  arcrar:    English Arcane name -> C/U/R/L (which generic picture it gets)
  abilities: ability path -> English name (every Warframe's abilities)
  suits:     Warframe path -> [its 4 ability paths, in order]
  helminth:  generic Helminth ability path -> English name
"""
import argparse
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from build_vendors import fetch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("loadout_data.json")))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    lang = fetch("dict.en", cache)
    nm = lambda key: re.sub(r"<[^>]+>\s*", "", lang.get(key, "")).strip()
    mods, arcanes, abilities, suits, rarity, best, arcrar = {}, {}, {}, {}, {}, {}, {}
    for path, u in fetch("ExportUpgrades", cache).items():
        if isinstance(u, dict) and nm(u.get("name", "")):
            mods[path] = [nm(u["name"]), int(u.get("fusionLimit") or 0)]
            r = {"COMMON": "C", "UNCOMMON": "U", "RARE": "R", "LEGENDARY": "L"}.get(u.get("rarity"))
            lim = int(u.get("fusionLimit") or 0)
            if r and lim > 0 and lim >= best.get(nm(u["name"]), 0):          # same name, several versions: the full-rank one
                best[nm(u["name"])] = lim
                rarity[nm(u["name"])] = r
    for path, u in fetch("ExportArcanes", cache).items():
        if isinstance(u, dict) and nm(u.get("name", "")):
            arcanes[path] = [nm(u["name"]), int(u.get("fusionLimit") or 0)]
            r = {"COMMON": "C", "UNCOMMON": "U", "RARE": "R", "LEGENDARY": "L"}.get(u.get("rarity"))
            if r:
                arcrar[nm(u["name"])] = r
    for path, w in fetch("ExportWarframes", cache).items():
        ab = [x for x in (w.get("abilities") or []) if isinstance(x, dict) and x.get("uniqueName")]
        if len(ab) >= 4 and w.get("productCategory") == "Suits":
            suits[path] = [x["uniqueName"] for x in ab[:4]]
        for x in ab:
            if nm(x.get("name", "")):
                abilities[x["uniqueName"]] = nm(x["name"])
    helminth = {}
    for key, val in lang.items():
        m = re.fullmatch(r"/Lotus/Language/Suits/(Helminth\w+)Name", key)
        if m and val:
            helminth[m.group(1)] = nm(key)
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "source": "calamity-inc/warframe-public-export-plus", "mods": mods, "rarity": rarity, "arcrar": arcrar, "arcanes": arcanes,
           "abilities": abilities, "suits": suits, "helminth": helminth}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(mods)} mods, {len(arcanes)} arcanes, {len(abilities)} abilities, {len(suits)} warframes -> {a.out}")


if __name__ == "__main__":
    main()
