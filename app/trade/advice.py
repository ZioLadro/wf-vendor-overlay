"""What to do with the items you own: trade them for ducats, or sell them on the market.

Ducats  (prime parts only — they are the only items DE lets you trade for ducats):
    liquidity   = min(1, volume / advice_liquid_volume)        how easily it sells
    plat_eff    = price * liquidity                             what the platinum is realistically worth
    ratio       = ducats / max(plat_eff, 0.5)                   ducats gained per platinum given up
    -> "ducats" if ratio >= ducat_min_ratio, otherwise it is worth more as platinum.
    Every copy counts: total ducats = copies * ducats, platinum given up = copies * price.

Every advice also shows the trend (current price against the 30-day average); a price above that average is
pulled towards it by advice_trend_weight percent, so a short spike does not make an item look better than it is.

Selling (items that are not better as ducats):
    sellable    = min(copies, max(1, round(volume * 0.25)))     how many you can expect to sell in a day or so
    liquidity   = min(1, volume / volume_high)
    score       = price * sellable                              expected platinum (sellable already follows the volume)
    -> items under the minimum price or the minimum volume are left out.
Ranking up (mods you own that are not at max rank, to sell them at max rank):
    endo/credits to rank a copy from rank r to max M:  base * (2^M - 2^r)   (Endo base 10/20/30/40, Credits 483/966/1449/1932
                                                       for common/uncommon/rare/legendary)
    gain        = max-rank price - current price         platinum gained per copy
    sellable    = min(copies, max(1, round(volume * 0.25)))
    gain/price  = the current prices, but a price above its 30-day average is pulled towards it (advice_trend_weight %)
    score       = gain * sellable per 1000 Endo spent      "how well the Endo is paid" (sellable follows the volume)
    -> mods whose gain is under the minimum, or that trade less than the minimum volume, are left out.
Rows without a price or a volume cannot be rated; their slugs are returned so the prices can be fetched.
"""
from app.core.config import CFG


def eff_price(price, avgs):
    """Price used for the advice: when the current price is above the 30-day average (a spike that may not last) it is
    pulled towards the average by advice_trend_weight percent; a price below the average is left as it is."""
    if price is None or not avgs or avgs[1] is None:
        return price
    w = max(0, min(100, float(CFG["advice_trend_weight"]))) / 100
    return price * (1 - w) + avgs[1] * w if price > avgs[1] else price


def trend(price, avgs):
    """Current price against the 30-day average, in percent (None without data)."""
    if price is None or not avgs or not avgs[1]:
        return None
    return (price / avgs[1] - 1) * 100


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
        from app.trade.signals import expected_price
        p_eff = expected_price(p, r.get("avg"), r.get("ind"), r.get("bid")) * _liquidity(vol, scale)
        ratio = d / max(p_eff, 0.5)
        out.append({"slug": r["slug"], "name": r["name"], "n": n, "ducats": d, "total_ducats": n * d,
                    "price": p, "vol": vol, "plat_lost": n * p, "ratio": ratio, "ducat": ratio >= min_ratio,
                    "trend": trend(p, r.get("avg")), "avg": r.get("avg")})
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
        from app.trade.signals import expected_price, signal
        pe = expected_price(p, r.get("avg"), r.get("ind"), r.get("bid"))
        score = pe * sellable                    # expected platinum: `sellable` already follows the volume
        out.append({"slug": r["slug"], "name": r["name"], "n": n, "price": p, "vol": vol, "sellable": sellable,
                    "expected": p * sellable, "score": score, "ranked": r["ranked"],
                    "trend": trend(p, r.get("avg")), "avg": r.get("avg"), "ind": r.get("ind"), "bid": r.get("bid"),
                    "signal": signal(p, r.get("ind"))})
    out.sort(key=lambda x: (-x["score"], -x["vol"], x["name"].lower()))
    return out, list(dict.fromkeys(missing))


ENDO_BASE = {"C": 10, "U": 20, "R": 30, "L": 40}
CREDIT_BASE = {"C": 483, "U": 966, "R": 1449, "L": 1932}


def rankup_advice(rows):
    """rows: inventory.build_rows(). Returns (list of dicts sorted by score, missing slugs).
    Only mods (Arcanes cannot be ranked with Endo). Copies in a loadout are left out when the rows were built with
    exclude_installed."""
    from app.game import loadouts
    rarity = loadouts.data().get("rarity", {})
    out, missing = [], []
    min_gain, min_vol = float(CFG["rankup_min_gain"]), float(CFG["rec_min_volume"])
    high = CFG["volume_high"]
    for r in rows:
        if not r["ranked"] or r["category"] != "mod" or r["n"] <= 0:
            continue
        rar = rarity.get(r["name"])
        if not rar:
            continue
        p, pm, vol = r["price"], r["pmax"], r["vol"]
        if p is None or pm is None or vol is None:
            missing.append(r["slug"])
            continue
        gain = eff_price(pm, r.get("avgm")) - eff_price(p, r.get("avg"))
        if gain < min_gain or vol < min_vol:
            continue
        mx = r["max_rank"]
        sellable = min(r["n"], max(1, round(vol * 0.25)))
        lv = sorted(r["lv"][:r["n"]], reverse=True)[:sellable]       # the most ranked copies are the cheapest to finish
        steps = sum((1 << mx) - (1 << min(l, mx)) for l in lv)
        endo, credits = ENDO_BASE[rar] * steps, CREDIT_BASE[rar] * steps
        if endo <= 0:
            continue
        out.append({"slug": r["slug"], "name": r["name"], "n": r["n"], "rarity": rar, "price": p, "pmax": pm, "vol": vol,
                    "gain": round(gain, 1), "sellable": sellable, "trend": trend(pm, r.get("avgm")), "avg": r.get("avgm"), "endo": endo, "credits": credits, "total_gain": gain * sellable,
                    "score": gain * sellable / endo * 1000})        # platinum per 1000 Endo (sellable follows the volume)
    out.sort(key=lambda x: (-x["score"], -x["total_gain"], x["name"].lower()))
    return out, list(dict.fromkeys(missing))
