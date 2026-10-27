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
With --wfcd <folder of WFCD/warframe-items data/json> it also writes (used for polarity, drain, capacity and stats):
  mst:       mod name -> [polarity, base drain, max rank, compatibility, type, {stat: value at max rank}] (Warframe mods: stat keys; weapon mods: labels)
  frames:    Warframe name -> [health, shield, armor, energy, sprint speed (rank 30), aura polarity, [innate polarities]]
  weapons:   weapon name -> [kind, type, [innate polarities], exilus polarity, stance polarity]
  arc:       Arcane name -> type
"""
import argparse
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from build_vendors import fetch


STAT_KEYS = {"Health": "health", "Shield Capacity": "shield", "Armor": "armor", "Energy Max": "energy",
             "Sprint Speed": "sprint", "Ability Duration": "duration", "Ability Efficiency": "efficiency",
             "Ability Range": "range", "Ability Strength": "strength"}
MOD_TYPES = {"Warframe Mod": "W", "Primary Mod": "P", "Shotgun Mod": "G", "Secondary Mod": "S", "Melee Mod": "M",
             "Stance Mod": "T"}


def wfcd(folder: Path) -> dict:
    """Polarity, drain and stats from the community-maintained WFCD/warframe-items data."""
    def load(name):
        return json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    mst = {}
    for m in load("Mods"):
        kind = MOD_TYPES.get(m.get("type"))
        name = m.get("name")
        if not kind or not name or "baseDrain" not in m:
            continue
        lim = int(m.get("fusionLimit") or 0)
        if name in mst and mst[name][2] >= lim:
            continue
        stats = {}
        levels = m.get("levelStats") or []
        if kind == "W" and levels:
            for line in levels[-1].get("stats", []):
                hit = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)%\s*([A-Za-z ]+)", line.strip())
                if hit and hit.group(3).strip() in STAT_KEYS:
                    key = STAT_KEYS[hit.group(3).strip()]
                    stats[key] = round(stats.get(key, 0) + (1 if hit.group(1) == "+" else -1) * float(hit.group(2)) / 100, 4)
        if kind in "PGSM" and levels:                    # weapon mods: percentage stats by (plain) label, for the bonus recap
            for line in levels[-1].get("stats", []):
                hit = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)%\s*(.+)", re.sub(r"<[^>]+>", "", line).strip())
                if hit:
                    label = re.sub(r"\s*\(.*?\)", "", hit.group(3)).strip()
                    stats[label] = round(stats.get(label, 0) + (1 if hit.group(1) == "+" else -1) * float(hit.group(2)) / 100, 4)
        mst[name] = [m.get("polarity") or "", int(m["baseDrain"]), lim, m.get("compatName") or "", kind, stats]
    frames = {}
    for w in load("Warframes"):
        if w.get("type") == "Warframe" and w.get("name"):
            frames[w["name"]] = [w.get("health", 0), w.get("shield", 0), w.get("armor", 0), w.get("power", 0),
                                 w.get("sprintSpeed", 1), w.get("aura") or "", w.get("polarities") or []]
    weapons = {}
    for fn, kind in (("Primary", "primary"), ("Secondary", "secondary"), ("Melee", "melee")):
        for w in load(fn):
            if w.get("name") and w.get("type") not in ("Zaw Component",):
                weapons[w["name"]] = [kind, w.get("type") or "", w.get("polarities") or [], w.get("exilusPolarity") or "",
                                      w.get("stancePolarity") or ""]
    arc = {a["name"]: a.get("type", "") for a in load("Arcanes") if a.get("name")}
    return {"mst": mst, "frames": frames, "weapons": weapons, "arc": arc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("loadout_data.json")))
    ap.add_argument("--wfcd", default="", help="folder with the WFCD/warframe-items data/json files")
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
    if a.wfcd:
        out.update(wfcd(Path(a.wfcd)))
        out["source"] += " + WFCD/warframe-items"
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(mods)} mods, {len(arcanes)} arcanes, {len(abilities)} abilities, {len(suits)} warframes -> {a.out}")


if __name__ == "__main__":
    main()
