#!/usr/bin/env python3
"""Generates vendors.json: the items sold by every Warframe vendor/syndicate (English names), with standing costs.

Source: https://github.com/calamity-inc/warframe-public-export-plus (converted official game data).
Usage:  python build_vendors.py [--out vendors.json] [--cache download_folder]
The program then matches the names to tradable warframe.market items (only items that exist on the
market appear in the price list). Baro Ki'Teer is not in this data: see vendors.py.
"""
import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://raw.githubusercontent.com/calamity-inc/warframe-public-export-plus/senpai/"
NAME_FILES = ["ExportUpgrades", "ExportWarframes", "ExportWeapons", "ExportResources", "ExportGear",
              "ExportCustoms", "ExportSentinels", "ExportFlavour", "ExportKeys", "ExportFusionBundles"]
VENDOR_PREFIX = "/Lotus/Types/Game/VendorManifests/"

REGION = {"Deimos": "Deimos", "Duviri": "Duviri", "EntratiLabs": "Cavia", "Events": "Event",
          "FocusSchools": "Focus", "GameModes": "Game modes", "Hubs": "Hub", "Kahl": "Kahl",
          "Ostron": "Cetus", "Solaris": "Fortuna", "Tau": "Tau", "TheHex": "1999", "Zariman": "Zariman"}
OVERRIDE = {   # clearer names for the main vendors
    "Hubs/TeshinHardModeVendorManifest": "Teshin (Steel Path)",
    "Duviri/AcrithisVendorManifest": "Acrithis (Duviri)",
    "Kahl/ChipperVendorManifest": "Chipper (Kahl)",
    "TheHex/AmirNightwaveVendorManifest": "Amir (1999 Nightwave)",
    "Solaris/NightcapVendorManifest": "Nightcap (Fortuna)",
    "Solaris/DebtTokenVendorManifest": "Debt-Token vendor (Fortuna)",
    "EntratiLabs/EntratiLabVendorManifest": "Cavia (Entrati Lab)",
    "EntratiLabs/EntratiLabsArcaneShopManifest": "Cavia · Arcane",
    "Zariman/ArchimedeanVendorManifest": "Archimedean (Zariman)",
    "Hubs/IronwakeFlawedModVendorManifest": "Ironwake (Flawed mods)",
    "Hubs/IronwakeDondaVendorManifest": "Ironwake (Donda)",
    "Deimos/HivemindCommisionsManifestNecromech": "Deimos · Necromech",
}


def fetch(name, cache: Path):
    f = cache / f"{name}.json"
    if not f.exists():
        r = requests.get(BASE + f"{name}.json", timeout=120)
        r.raise_for_status()
        f.write_bytes(r.content)
    return json.loads(f.read_text(encoding="utf-8"))


def words(s: str) -> str:
    s = re.sub(r"(Vendor)?(Products)?Manifest", "", s)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    return s.strip()


def vendor_name(key: str) -> str:
    short = key[len(VENDOR_PREFIX):]
    if short.startswith("Events/RadioLegion"):
        return "Nightwave (Nora)"                      # all seasons together
    if short in OVERRIDE:
        return OVERRIDE[short]
    parts = short.split("/")
    region = REGION.get(parts[0], parts[0])
    return f"{region} · {words(parts[-1])}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("vendors.json")))
    ap.add_argument("--cache", default=None, help="folder where downloads are saved (default: temporary)")
    ap.add_argument("--report", action="store_true", help="print name coverage")
    a = ap.parse_args()
    cache = Path(a.cache) if a.cache else Path(tempfile.mkdtemp(prefix="wfvendors_"))
    cache.mkdir(parents=True, exist_ok=True)

    lang = fetch("dict.en", cache)
    names = {}                                         # uniqueName -> English name
    for fn in NAME_FILES:
        for path, e in fetch(fn, cache).items():
            if isinstance(e, dict) and lang.get(e.get("name", "")):
                names.setdefault(path, lang[e["name"]])
    recipes = fetch("ExportRecipes", cache)

    def resolve(store_item: str):
        """Returns 'Name' or ['Name Blueprint', 'Name'] for blueprints, None if unknown."""
        path = store_item.replace("/StoreItems", "", 1)
        if path in names:
            return names[path]
        rec = recipes.get(path)
        if rec and rec.get("resultType") in names:
            base = names[rec["resultType"]]
            return [f"{base} Blueprint", base]
        return None

    vendors, total, missing = {}, 0, []

    def add(vendor: str, store_item: str, standing=None, rank=None):
        """Adds an entry; `standing` = standing cost (None if it is not paid in standing)."""
        nonlocal total
        total += 1
        r = resolve(store_item)
        if r is None:
            missing.append(store_item)
            return
        lst = vendors.setdefault(vendor, {})
        key = json.dumps(r, ensure_ascii=False)
        e = lst.setdefault(key, {"n": r})
        if standing:                                   # the same entry can appear twice: keep the cheapest
            if "s" not in e or standing < e["s"]:
                e["s"], e["r"] = int(standing), int(rank or 0)

    for key, v in fetch("ExportVendors", cache).items():
        for it in v.get("items", []):
            syn = it.get("syndicate") or {}
            add(vendor_name(key), it.get("storeItem", ""), syn.get("standingCost"), syn.get("minRank"))
    for sid, s in fetch("ExportSyndicates", cache).items():
        if sid.startswith("RadioLegion"):
            continue
        vname = lang.get(s.get("name", ""), sid)
        for f in s.get("favours", []):
            add(vname, f.get("storeItem", ""), f.get("standingCost"), f.get("requiredLevel"))

    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "source": "calamity-inc/warframe-public-export-plus",
           "vendors": {k: list(v.values()) for k, v in sorted(vendors.items()) if v}}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_items = sum(len(v) for v in out["vendors"].values())
    print(f"{len(out['vendors'])} vendors, {n_items} entries -> {a.out} (names resolved: {total - len(missing)}/{total})")
    if a.report:
        for k, v in out["vendors"].items():
            print(f"  {len(v):4d}  {k}")
        print("unresolved, examples:", missing[:12])


if __name__ == "__main__":
    sys.exit(main())
