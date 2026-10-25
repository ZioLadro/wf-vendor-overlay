"""What to do with the items you own: trade them for ducats, or sell them on the market.

Ducats  (prime parts only — they are the only items DE lets you trade for ducats):
    liquidity   = min(1, volume / advice_liquid_volume)        how easily it sells
    plat_eff    = price * liquidity                             what the platinum is realistically worth
    ratio       = ducats / max(plat_eff, 0.5)                   ducats gained per platinum given up
    -> "ducats" if ratio >= ducat_min_ratio, otherwise it is worth more as platinum.
    Every copy counts: total ducats = copies * ducats, platinum given up = copies * price.

Selling (items that are not better as ducats):
    sellable    = min(copies, max(1, round(volume * 0.25)))     how many you can expect to sell in a day or so
    liquidity   = min(1, volume / volume_high)
    score       = price * sellable * liquidity                  expected platinum, discounted by how rarely it trades
    -> items under the minimum price or the minimum volume are left out.
Rows without a price or a volume cannot be rated; their slugs are returned so the prices can be fetched.
"""
from config import CFG


def _liquidity(vol, scale):
    return 1.0 if vol is None else min(1.0, vol / max(1.0, float(scale)))


def ducat_advice(rows):
    """rows: inventory.build_rows(). Returns (list of dicts sorted by ratio, missing slugs)."""
    out, missing = [], []
    scale = CFG["advice_liquid_volume"]
    min_ratio = float(CFG["ducat_min_ratio"])
    for r in rows:
        d, n = r.get("ducats"), r["n"]
        if not d or n <= 0:
            continue
        p, vol = r["price"], r["vol"]
        if p is None or vol is None:
            missing.append(r["slug"])
            continue
        p_eff = p * _liquidity(vol, scale)
        ratio = d / max(p_eff, 0.5)
        out.append({"slug": r["slug"], "name": r["name"], "n": n, "ducats": d, "total_ducats": n * d,
                    "price": p, "vol": vol, "plat_lost": n * p, "ratio": ratio, "ducat": ratio >= min_ratio})
    out.sort(key=lambda x: (-x["ratio"], -x["total_ducats"], x["name"].lower()))
    return out, list(dict.fromkeys(missing))


def sell_advice(rows):
    """rows: inventory.build_rows(). Returns (list of dicts sorted by score, missing slugs)."""
    out, missing = [], []
    ducat_slugs = {x["slug"] for x in ducat_advice(rows)[0] if x["ducat"]}
    min_price, min_vol = float(CFG["sell_min_price"]), float(CFG["rec_min_volume"])
    high = CFG["volume_high"]
    for r in rows:
        n = r["n"]
        if n <= 0 or r["slug"] in ducat_slugs:
            continue
        p, vol = r["price"], r["vol"]
        if p is None or vol is None:
            missing.append(r["slug"])
            continue
        if p < min_price or vol < min_vol:
            continue
        sellable = min(n, max(1, round(vol * 0.25)))
        score = p * sellable * _liquidity(vol, high)
        out.append({"slug": r["slug"], "name": r["name"], "n": n, "price": p, "vol": vol, "sellable": sellable,
                    "expected": p * sellable, "score": score, "ranked": r["ranked"]})
    out.sort(key=lambda x: (-x["score"], -x["vol"], x["name"].lower()))
    return out, list(dict.fromkeys(missing))
