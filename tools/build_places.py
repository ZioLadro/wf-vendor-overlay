#!/usr/bin/env python3
"""Generates data/places.json: for the syndicate offerings sold by one specific NPC (Hok sells the Zaw parts and Exodia
arcanes at Cetus, Rude Zuud the kitgun parts at Fortuna…), which one. Read by app/game/places.py, which shows it in
Activities next to "Buy …".

The game data says which syndicate an offering belongs to, not which of its NPCs sells it, so the NPC is told by the
kind of item (its game path): RULES below, checked in order. Items no rule matches get the syndicate's own place
(places.DEFAULT). Names are written exactly as data/vendors.json writes them (blueprints as "<name> Blueprint").

Usage:  python tools/build_places.py [--out data/places.json] [--cache download_folder]"""
import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_vendors import fetch      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FISH = r"/Types/Items/Fish/|/FishBait/|FishingSpear|/Fishing/"
CONSERVATION = r"/Restoratives/Conservation/|/SentinelPrecepts/|CatbrowVampireDisinfect"
# syndicate tag -> [(regex on the store item path, place key)], first match wins
RULES = {
    "CetusSyndicate": [(r"/Weapons/Ostron/Melee/|/CosmeticEnhancers/", "hok"),
                       (FISH + r"|/Consumable/.*Spear", "hailuk"),
                       (r"EidolonRecipes|Nosam|MiningTool|/Gems/", "suumbaat"),
                       (CONSERVATION, "teasonai")],
    "SolarisSyndicate": [(r"/Weapons/SolarisUnited/|/CosmeticEnhancers/", "rudezuud"),
                         (r"MoaPetParts|SentinelRecipes", "legs"),
                         (FISH + r"|/Consumable/.*Spear|" + CONSERVATION, "business"),
                         (r"SolarisRecipes|PlasmaDrill|Sunpoint", "smokefinger")],
    "EntratiSyndicate": [(FISH + r"|/Consumable/.*Spear", "daughter"),
                         (CONSERVATION + r"|/Friendly/Pets/|ShipFeatureItems", "son"),
                         (r"DeimosRecipes", "otak"),
                         (r"/Weapons/Infested/|/Recipes/Weapons/|/Upgrades/Mods/", "father")],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "places.json"))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    g = json.loads((ROOT / "data" / "gamenames.json").read_text(encoding="utf-8"))
    names, recipes = g["names"], g["recipes"]

    def name_of(store_item):
        p = store_item.replace("/StoreItems", "", 1)
        if p in names:
            return names[p]
        if p in recipes:
            return f"{recipes[p]} Blueprint"
        return None

    out, n = {}, 0
    for sid, s in fetch("ExportSyndicates", cache).items():
        rules = RULES.get(sid)
        if not rules or not isinstance(s, dict):
            continue
        for f in s.get("favours", []):
            item = f.get("storeItem", "")
            name = name_of(item)
            if not name:
                continue
            key = next((k for rx, k in rules if re.search(rx, item)), None)
            if key:
                out.setdefault(sid, {})[name] = key
                n += 1
    Path(a.out).write_text(json.dumps({"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "items": out},
                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{n} offerings with a specific NPC -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
