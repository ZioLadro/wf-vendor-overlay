#!/usr/bin/env python3
"""Generates weekly.json: the vendor offers with a purchase limit (most of them weekly), for the Weekly tab.

Source: https://github.com/calamity-inc/warframe-public-export-plus (ExportVendors and names).
Usage:  python tools/build_weekly.py [--out data/weekly.json] [--cache download_folder]
  vendors: manifest path -> {"name": vendor name, "items": [{"store": store item, "path": item path, "name": English name,
           "qty": quantity, "limit": purchases per period, "hours": period length, "cost": [[count, currency]],
           "cost_any": [[lowest, highest, currency]] (vendors whose prices are drawn per offer from a list, like
           Acrithis: one of these; a single entry is the price, e.g. 10 Pathos Clamps)}]}
Nightwave's seasonal vendors are left out."""
import argparse
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from build_vendors import NAME_FILES, VENDOR_PREFIX, fetch, vendor_name, words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "weekly.json"))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    lang = fetch("dict.en", cache)
    names = {}
    for fn in NAME_FILES:
        for path, e in fetch(fn, cache).items():
            if isinstance(e, dict) and lang.get(e.get("name", "")):
                names.setdefault(path, re.sub(r"<[^>]+>\s*", "", lang[e["name"]]).strip())
    recipes = fetch("ExportRecipes", cache)

    def name_of(path):
        if path in names:
            n = names[path]
            return n.title() if n.isupper() else n             # "PRIMARY ARCANE ADAPTER" -> "Primary Arcane Adapter"
        rec = recipes.get(path)
        if isinstance(rec, dict) and rec.get("resultType") in names:
            return names[rec["resultType"]] + " Blueprint"
        return words(path.rsplit("/", 1)[-1])

    out = {}
    for key, v in fetch("ExportVendors", cache).items():
        if "/RadioLegion" in key:
            continue
        bins = v.get("randomItemPricesPerBin") or []
        items = []
        for it in v.get("items", []):
            if not it.get("purchaseLimit") or not isinstance(it.get("durationHours", 0), (int, float)):
                continue                                  # no limit, or a commission that rotates every few hours
            store = it.get("storeItem", "")
            path = store.replace("/StoreItems", "", 1)
            cost = [[int(p.get("ItemCount") or 0), name_of(p.get("ItemType", ""))] for p in it.get("itemPrices") or []]
            for field, label in (("credits", "Credits"), ("platinum", "Platinum")):
                c = it.get(field)
                if isinstance(c, dict):                   # a random price in a range
                    c = c.get("minValue")
                if c:
                    cost.append([int(c), label])
            row = {"store": store, "path": path, "name": name_of(path), "qty": int(it.get("quantity") or 1),
                   "limit": int(it["purchaseLimit"]), "hours": int(it.get("durationHours") or 0), "cost": cost}
            b = it.get("bin")
            if not cost and isinstance(b, int) and b < len(bins) and bins[b]:
                # the price is drawn from the bin's list: one entry = that price (Acrithis: 10 Pathos Clamps)
                anyc = []
                for p in bins[b]:
                    c = p.get("count") or {}
                    lo, hi = (int(c.get("minValue") or 0), int(c.get("maxValue") or 0)) if isinstance(c, dict) else (int(c), int(c))
                    anyc.append([lo, hi, name_of(p.get("type", ""))])
                if len(anyc) == 1 and anyc[0][0] == anyc[0][1]:
                    row["cost"] = [[anyc[0][0], anyc[0][2]]]
                else:
                    row["cost_any"] = anyc
            items.append(row)
        if items:
            out[key] = {"name": vendor_name(key) if key.startswith(VENDOR_PREFIX) else words(key.rsplit("/", 1)[-1]),
                        "items": items}
    Path(a.out).write_text(json.dumps({"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                       "source": "calamity-inc/warframe-public-export-plus", "vendors": out},
                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} vendors, {sum(len(v['items']) for v in out.values())} limited offers -> {a.out}")


if __name__ == "__main__":
    main()
