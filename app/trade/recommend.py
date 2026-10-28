"""What to buy with standing: ranks vendor items by the platinum they can realistically bring you per day.

For every (item, vendor) pair with a standing cost and known market data:
    plat per 1000 standing = price / standing cost * 1000                       (the "Plat / 1k standing" column)
    price used             = the current price, or (when it is above its 30-day average: a spike) pulled towards that
                             average by advice_trend_weight percent, as in the inventory advice
    copies per day         = min(daily standing cap / standing cost,             what one day of standing buys
                                 max(1, volume * 0.25))                          what the market can absorb in a day
    score (~plat / day)    = price used * copies per day
The daily cap is 16,000 + 500 × Mastery Rank (26,000 if the rank is unknown). So a cheap item is no longer ranked first
just for its plat/standing if nobody would buy all the copies, and an item you cannot buy yet (your syndicate rank is
lower than the one it needs) counts half and is flagged.
Items traded less than `min_volume` times in 24 h, or cheaper than `min_price` platinum, are left out.
The price is the rank 0 one (what the vendor actually sells), not the max-rank one.
"""
from app.core.config import CFG

SELL_SHARE = 0.25        # share of the daily volume you can expect to sell yourself (same as the inventory advice)


def recommend(rows, vendor=None, kind=None, min_volume=None, min_price=None, top=None, per_vendor=None):
    """rows: Market.snapshot(). Returns (picks, missing): `missing` lists the slugs of the standing items
    (within the filters) that have no price/volume yet, so they could not be rated.
    per_vendor: keep only the N best items of EACH vendor (the best purchase at every vendor)."""
    min_volume = CFG["rec_min_volume"] if min_volume is None else min_volume
    min_price = CFG["rec_min_price"] if min_price is None else min_price
    top = CFG["rec_top"] if top is None else top
    from app.trade.advice import eff_price
    try:
        from app.game.standing import get_store
        store = get_store()
        mr = store.mr
    except Exception:
        store, mr = None, None
    cap = 16000 + 500 * int(mr) if mr is not None else 26000
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
            pe = eff_price(price, r.get("avg"))
            copies = min(cap / e["s"], max(1.0, vol * SELL_SHARE))
            pday = pe * copies
            f = store.get(e.get("t")) if store is not None and e.get("t") else None
            rank_short = bool(f and f.get("rank") is not None and f["rank"] < int(e.get("r") or 0))
            picks.append({"slug": r["slug"], "name": r["name"], "kind": r["kind"], "vendor": e["v"],
                          "cost": e["s"], "tag": e.get("t"), "rank": e.get("r", 0), "price": price, "pmax": r["pmax"],
                          "vol": vol, "ppk": ppk, "pday": pday, "copies": copies, "rank_short": rank_short,
                          "score": pday * (0.5 if rank_short else 1.0)})
    picks.sort(key=lambda p: (-p["score"], -p["vol"], p["name"]))
    if per_vendor:
        seen, kept = {}, []
        for p in picks:
            if seen.get(p["vendor"], 0) < per_vendor:
                seen[p["vendor"]] = seen.get(p["vendor"], 0) + 1
                kept.append(p)
        return kept, list(dict.fromkeys(missing))      # one list per vendor: `top` does not cut it
    return picks[:top], list(dict.fromkeys(missing))
