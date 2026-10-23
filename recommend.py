"""What to buy with standing: ranks vendor items by the platinum they are worth per standing spent.

For every (item, vendor) pair with a standing cost and known market data:
    plat per 1000 standing = price / standing cost * 1000
    score                  = plat per 1000 standing * min(1, volume / volume_high)
The score discounts items that trade rarely: a high price is worthless if nobody buys.
Items traded less than `min_volume` times in 24 h, or cheaper than `min_price` platinum, are left out.
The price is the rank 0 one (what the vendor actually sells), not the max-rank one.
"""
from config import CFG


def recommend(rows, vendor=None, kind=None, min_volume=None, min_price=None, top=None):
    """rows: Market.snapshot(). Returns (picks, missing): `missing` lists the slugs of the standing items
    (within the filters) that have no price/volume yet, so they could not be rated."""
    min_volume = CFG["rec_min_volume"] if min_volume is None else min_volume
    min_price = CFG["rec_min_price"] if min_price is None else min_price
    top = CFG["rec_top"] if top is None else top
    target = max(1.0, float(CFG["volume_high"]))
    picks, missing = [], []
    for r in rows:
        if kind is not None and r["kind"] != kind:
            continue
        for e in r["standing"]:
            if vendor is not None and e["v"] != vendor:
                continue
            price, vol = r["price"], r["vol"]
            if price is None or vol is None:
                # never collected, or the volume is still missing -> cannot be rated yet
                # (price None with data collected = nobody is selling it online: just skip)
                if r["updated"] is None or (price is not None and vol is None):
                    missing.append(r["slug"])
                continue
            if vol < min_volume or price < min_price or e["s"] <= 0:
                continue
            ppk = price / e["s"] * 1000
            picks.append({"slug": r["slug"], "name": r["name"], "kind": r["kind"], "vendor": e["v"],
                          "cost": e["s"], "rank": e.get("r", 0), "price": price, "pmax": r["pmax"],
                          "vol": vol, "ppk": ppk, "score": ppk * min(1.0, vol / target)})
    picks.sort(key=lambda p: (-p["score"], -p["vol"], p["name"]))
    return picks[:top], list(dict.fromkeys(missing))
