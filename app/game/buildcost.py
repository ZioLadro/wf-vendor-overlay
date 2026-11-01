"""What a planned build (or a whole planned loadout) costs you: Endo and credits to rank the mods, platinum for what you do
not own, counting what you own (the game file read by the Builds tab).

Mods: fusing a mod from rank r to r + 1 costs 10 x k x 2^r Endo and about 483 x k x 2^r credits, k = 1 Common, 2
Uncommon, 3 Rare, 4 Legendary (Primed, Umbral, Archon...): a Rare mod to rank 5 costs 930 Endo, a Primed mod to rank 10
40,920. A mod you own at a lower rank only needs the ranks it lacks; one you do not own is bought unranked (its rank 0
price) and ranked, or bought already at its top rank when that costs less platinum than the Endo is worth to you.
Arcanes: no Endo; a rank r Arcane is (r + 1)(r + 2) / 2 copies, so the copies you lack are bought (rank 0 price each),
or one already maxed (its max-rank price) when that is cheaper.
A mod or Arcane counts once even when several pieces of the loadout use it: in the game the same copy can be equipped on
every item. Rivens are not counted (each is unique)."""
from app.game import arcanes as A
from app.game import buildcalc as BC
from app.game import loadouts as LO

RARITY_K = {"C": 1, "U": 2, "R": 3, "L": 4}
CREDITS_PER_ENDO = 48.3                 # the game's credit cost of a fusion is about 48.3 credits per Endo


def rarity(name: str) -> str:
    r = LO.data().get("rarity", {}).get(name)
    if r:
        return r
    if name.startswith(("Primed ", "Umbral ", "Archon ")):
        return "L"
    return "R"


def endo(name: str, frm: int, to: int) -> int:
    """Endo to rank a mod from rank frm to rank to."""
    if to <= frm:
        return 0
    k = RARITY_K.get(rarity(name), 3)
    return 10 * k * ((1 << to) - (1 << max(0, frm)))


def credits(name: str, frm: int, to: int) -> int:
    return int(round(endo(name, frm, to) * CREDITS_PER_ENDO))


def needed(pieces: dict, all_configs: bool = False) -> dict:
    """{name: {"rank": highest rank wanted, "arcane": bool, "items": [planned items using it]}} of a loadout's mods
    and Arcanes. pieces: {kind: planner piece}; only the shown configuration of each piece unless all_configs."""
    out = {}
    for kind, p in (pieces or {}).items():
        if not p or not p.get("item"):
            continue
        cfgs = p.get("configs") or []
        use = cfgs if all_configs else cfgs[p.get("cfg", 0):p.get("cfg", 0) + 1]
        for c in use:
            for m in c.get("mods") or []:
                if not m or not m[0] or (len(m) > 2 and m[2]):
                    continue                              # empty slot or a Riven
                name, rank = m[0], int(m[1] or 0)
                e = out.setdefault(name, {"rank": 0, "arcane": A.is_arcane(name), "items": []})
                e["rank"] = max(e["rank"], rank)
                if p["item"] not in e["items"]:
                    e["items"].append(p["item"])
    return out


def cost(pieces: dict, owned: dict, price_of=lambda name: (None, None), all_configs: bool = False) -> dict:
    """The loadout's cost. owned: loadouts.owned_mods(); price_of(name) -> (rank 0 price, max-rank price) or Nones.
    Returns {"rows": [...], "endo", "credits", "plat", "plat_max", "missing", "unpriced", "owned"} where each row is
    {"name", "arcane", "rank", "max", "items", "have_n", "have_rank", "status": "ok" | "rank" | "buy",
     "endo", "credits", "plat" (unranked copies bought and ranked), "plat_max" (bought at the top rank instead),
     "buy_copies" (Arcanes: copies to buy), "choice": "unranked" | "maxed"}."""
    rows = []
    tot = {"endo": 0, "credits": 0, "plat": 0, "plat_max": 0, "missing": 0, "unpriced": 0, "owned": 0}
    for name, need in sorted(needed(pieces, all_configs).items(), key=lambda kv: kv[0].lower()):
        have = (owned or {}).get(name) or {}
        n, hr = int(have.get("n", 0) or 0), int(have.get("rank", 0) or 0)
        rank = need["rank"]
        p0, pm = price_of(name)
        row = {"name": name, "arcane": need["arcane"], "rank": rank, "items": need["items"], "have_n": n,
               "have_rank": hr, "endo": 0, "credits": 0, "plat": None, "plat_max": None, "buy_copies": 0,
               "choice": "", "price": p0, "price_max": pm}
        if need["arcane"]:
            top = A.max_rank(name)
            row["max"] = top
            have_c = int(have.get("c", n) or 0)
            want = A.copies(rank)
            lack = max(0, want - have_c)
            row["buy_copies"] = lack
            if lack == 0:
                row["status"] = "ok"
            else:
                row["status"] = "buy" if have_c == 0 else "rank"
                row["plat"] = None if p0 is None else p0 * lack
                if rank == top and pm is not None:
                    row["plat_max"] = pm
                row["choice"] = "maxed" if (row["plat_max"] is not None and (row["plat"] is None
                                                                            or row["plat_max"] < row["plat"])) else "unranked"
        else:
            info = BC.mod_info(name)
            top = info[2] if info else rank
            row["max"] = top
            if n > 0 and hr >= rank:
                row["status"] = "ok"
            elif n > 0:
                row["status"] = "rank"
                row["endo"], row["credits"] = endo(name, hr, rank), credits(name, hr, rank)
            else:
                row["status"] = "buy"
                row["endo"], row["credits"] = endo(name, 0, rank), credits(name, 0, rank)
                row["plat"] = p0
                if rank > 0 and rank == top and pm is not None:
                    row["plat_max"] = pm
                row["choice"] = "unranked"
        rows.append(row)
        if row["status"] == "ok":
            tot["owned"] += 1
            continue
        if row["status"] == "buy" or (row["arcane"] and row["buy_copies"]):
            tot["missing"] += 1
            if row["plat"] is None and row["plat_max"] is None:
                tot["unpriced"] += 1
        tot["endo"] += row["endo"]
        tot["credits"] += row["credits"]
        if row["choice"] == "maxed":
            tot["plat"] += row["plat_max"] or 0
            tot["plat_max"] += row["plat_max"] or 0
        else:
            tot["plat"] += row["plat"] or 0
            # buying it maxed instead (no Endo): the alternative total
            tot["plat_max"] += (row["plat_max"] if row["plat_max"] is not None else (row["plat"] or 0))
    return dict(tot, rows=rows)


def wish_entries(rows: list, slug_of) -> list:
    """The missing mods and Arcanes as entries for Quantframe's wish list (its Live Scraper places want-to-buy orders):
    [{"slug", "name", "rank", "qty"}]. Mods: one unranked copy (or one at the top rank when that was the cheaper
    choice); Arcanes: the copies you lack, unranked."""
    out = []
    for r in rows:
        if r["status"] == "ok" or (r["status"] == "rank" and not r["arcane"]):
            continue
        slug = slug_of(r["name"])
        if not slug:
            continue
        if r["arcane"]:
            if r["choice"] == "maxed":
                out.append({"slug": slug, "name": r["name"], "rank": r["max"], "qty": 1})
            else:
                out.append({"slug": slug, "name": r["name"], "rank": 0, "qty": max(1, r["buy_copies"])})
        else:
            maxed = r["choice"] == "maxed"
            out.append({"slug": slug, "name": r["name"], "rank": r["max"] if maxed else 0, "qty": 1})
    return out
