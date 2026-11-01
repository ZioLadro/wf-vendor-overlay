"""Vosfor calculator: how much Vosfor your Arcanes dissolve into, which Arcanes are best turned into Vosfor (little
platinum lost for a lot of Vosfor), and which of Loid's collections are worth buying.

Prices are warframe.market's (the rank 0 price of one copy; a ranked Arcane is worth its copies). A collection costs 200
Vosfor and gives 3 Arcanes, each slot rolled on its own: its expected value is 3 x the sum of (chance x price) of its
Arcanes, and the Vosfor you would get back by dissolving them is 3 x the sum of (chance x Vosfor). The "platinum per 100
Vosfor" of a collection is what 100 Vosfor are worth when spent there: dissolving an Arcane that sells for less than that
per 100 Vosfor it gives turns it into more platinum than selling it would."""
from app.game import arcanes as A

PACK_COST_DEFAULT = 200


def pack_cost() -> int:
    return int(A.vosfor_data().get("pack_cost") or PACK_COST_DEFAULT)


def pack_size() -> int:
    return int(A.vosfor_data().get("pack_size") or 3)


def _price(prices: dict, name: str):
    p = prices.get(name)
    return None if p is None else float(p)


def packs(prices: dict) -> list:
    """Loid's collections, best expected platinum first: [{"id", "name", "ev": expected platinum of one purchase,
    "ev_vosfor": Vosfor if its 3 Arcanes are dissolved again, "per100": platinum per 100 Vosfor spent, "best":
    (name, chance per pack, price) of the Arcane worth most, "legendary": chance of at least one Legendary,
    "known": share of the chance whose price is known, "rows": [(name, chance per slot, price, vosfor)]}].
    prices: {Arcane name: platinum of one rank 0 copy}."""
    out = []
    n, cost = pack_size(), pack_cost()
    for cid, c in (A.vosfor_data().get("collections") or {}).items():
        odds = A.pack_odds(cid)
        rows, ev, evv, known = [], 0.0, 0.0, 0.0
        for name, ch in sorted(odds.items(), key=lambda kv: -kv[1]):
            pr = _price(prices, name)
            y = A.vosfor_yield(name) or 0
            rows.append((name, ch, pr, y))
            if pr is not None:
                ev += ch * pr
                known += ch
            evv += ch * y
        leg = sum(ch for rar, ch, _names in c.get("pools") or [] if rar == "legendary")
        best = max(((r[0], 1 - (1 - r[1]) ** n, r[2]) for r in rows if r[2] is not None), key=lambda x: x[2],
                   default=None)
        # the Arcanes without a price count at the average of the priced ones (an estimate, flagged by "known")
        if 0 < known < 1:
            ev = ev / known
        out.append({"id": cid, "name": c.get("name") or cid, "ev": n * ev, "ev_vosfor": n * evv,
                    "per100": n * ev / cost * 100 if cost else 0.0, "best": best,
                    "legendary": 1 - (1 - leg) ** n, "known": known, "rows": rows})
    out.sort(key=lambda r: -r["ev"])
    return out


def best_rate(prices: dict) -> float:
    """Platinum 100 Vosfor are worth at the best collection (0 when no collection has prices)."""
    ps = [p for p in packs(prices) if p["known"] > 0.5]
    return max((p["per100"] for p in ps), default=0.0)


def mine(owned: dict, prices: dict, installed=frozenset()) -> list:
    """Your Arcanes that can be dissolved, the most Vosfor first: [{"name", "copies", "rank", "yield" (per copy),
    "vosfor" (all copies), "price" (one copy), "value" (all copies), "plat100" (platinum given up per 100 Vosfor),
    "advice": "dissolve" | "sell" | "keep" | "unknown", "installed": bool}].
    owned: {name: {"n", "c" (copies, ranked ones counted by what they are made of), "rank"}} (loadouts.owned_mods)."""
    rate = best_rate(prices)
    out = []
    for name, e in (owned or {}).items():
        y = A.vosfor_yield(name)
        if not A.is_arcane(name) or y is None:
            continue
        c = int(e.get("c", e.get("n", 0)) or 0)
        if c <= 0:
            continue
        pr = _price(prices, name)
        value = None if pr is None else pr * c
        plat100 = None if pr is None or not y else pr / y * 100
        inst = name in installed
        if inst:
            advice = "keep"                          # equipped: dissolving it empties the slot
        elif pr is None:
            advice = "unknown"                       # no price yet: update the prices
        else:                                        # selling gives less than the Vosfor buys at Loid's (or ~nothing)
            advice = "dissolve" if pr <= 2 or (rate and plat100 <= rate) else "sell"
        out.append({"name": name, "copies": c, "rank": int(e.get("rank") or 0), "yield": y, "vosfor": y * c,
                    "price": pr, "value": value, "plat100": plat100, "advice": advice, "installed": inst})
    out.sort(key=lambda r: (-r["vosfor"], r["name"]))
    return out


def cheapest(prices: dict, limit: int = 0) -> list:
    """Every Arcane that can be dissolved, the most Vosfor per platinum first: what to trade into Vosfor (or buy cheap
    to dissolve). [{"name", "yield", "price", "per_plat" (Vosfor per platinum), "plat100"}]; Arcanes without a price
    are left out."""
    out = []
    for name, y in (A.vosfor_data().get("yield") or {}).items():
        pr = _price(prices, name)
        if y is None or pr is None or pr <= 0:
            continue
        out.append({"name": name, "yield": y, "price": pr, "per_plat": y / pr, "plat100": pr / y * 100})
    out.sort(key=lambda r: -r["per_plat"])
    return out[:limit] if limit else out


def totals(rows: list) -> dict:
    """Your Arcanes together: Vosfor of all of them, of those advised to dissolve, and the collections they buy."""
    allv = sum(r["vosfor"] for r in rows)
    dis = sum(r["vosfor"] for r in rows if r["advice"] == "dissolve")
    lost = sum(r["value"] or 0 for r in rows if r["advice"] == "dissolve")
    cost = pack_cost()
    return {"all": allv, "dissolve": dis, "packs_all": allv // cost if cost else 0,
            "packs_dissolve": dis // cost if cost else 0, "plat_lost": lost}
