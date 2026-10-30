#!/usr/bin/env python3
"""Generates data/rotations.json: what Ergo Glast (Tenet weapons) and Eleanor (Coda weapons) can offer, from DE's
vendor data (calamity-inc/warframe-public-export-plus, ExportVendors), with the seeds and cycles the vendors use
(as reconstructed by OpenWF's SpaceNinjaServer, serversideVendorsService.ts). See app/game/rotations.py.
Usage:  python tools/build_rotations.py [--out data/rotations.json] [--cache download_folder]"""
import argparse
import json
import re
import tempfile
from pathlib import Path

from build_vendors import fetch

VENDORS = {
    "tenet": {"manifest": "/Lotus/Types/Game/VendorManifests/Hubs/PerrinSequenceWeaponVendorManifest",
              "oid": "60ad3b6ec96976e97d227e19", "offset": 1744934400, "who": "Ergo Glast"},
    "coda": {"manifest": "/Lotus/Types/Game/VendorManifests/TheHex/InfestedLichWeaponVendorManifest",
             "oid": "67dadc30e4b6e0e5979c8d84", "offset": 1740960000, "who": "Eleanor"},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "rotations.json"))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    lang = fetch("dict.en", cache)
    weapons = fetch("ExportWeapons", cache)
    vend = fetch("ExportVendors", cache)
    nm = lambda key: re.sub(r"<[^>]+>\s*", "", lang.get(key, "")).strip()
    out = {"vendors": {}}
    for key, v in VENDORS.items():
        m = vend[v["manifest"]]
        items = []
        for it in m["items"]:
            path = it["storeItem"].replace("/Lotus/StoreItems/", "/Lotus/")
            w = weapons.get(path) or {}
            items.append({"path": path, "name": nm(w.get("name", "")) or path.rsplit("/", 1)[-1], "bin": it.get("bin", 0)})
        out["vendors"][key] = {"who": v["who"], "seed": int(v["oid"][16:], 16), "offset": v["offset"],
                               "cycle": 4 * 86400, "one_bin": bool(m.get("isOneBinPerCycle")),
                               "count": (m.get("numItems") or {}).get("minValue") or len(items), "items": items}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: [i["name"] for i in v["items"]] for k, v in out["vendors"].items()})


if __name__ == "__main__":
    main()
