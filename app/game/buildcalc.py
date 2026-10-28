"""Build maths: slot polarities, mod drain, capacity and the Warframe stat recap (an approximation of the in-game screen).

Not counted: Arcanes, Archon Shards, Helminth, set bonuses, conditional or per-enemy effects, Warframe rank below 30.
Polarity of a slot: the one set by Forma in the game file, otherwise the Warframe's / weapon's innate one (the public data lists
the innate polarities in slot order, which is how they are assigned here)."""
import math

from app.game import loadouts as LO

AP = {"AP_ATTACK": "madurai", "AP_DEFENSE": "vazarin", "AP_TACTIC": "naramon", "AP_POWER": "zenurik", "AP_WARD": "unairu",
      "AP_UMBRA": "umbra", "AP_PRECEPT": "penjaga", "AP_ANY": "universal", "AP_UNIVERSAL": "universal"}
POLARITIES = ["madurai", "vazarin", "naramon", "zenurik", "unairu", "penjaga", "umbra", "universal"]
# capacity = the item's rank (30 at rank 30), doubled by an Orokin Reactor / Catalyst; an Aura adds its own.
# A "universal" slot (AP_ANY / AP_UNIVERSAL in the game file, e.g. after an Aura Forma) matches every mod polarity: checked on a
# real build, the game's total (60 + Aura 7 doubled = 74) only comes out that way.
STAT_ORDER = ("health", "shield", "armor", "energy", "sprint", "duration", "efficiency", "range", "strength")


def _plain(label: str) -> str:
    """A stat label without its parenthesis: 'Fire Rate (x2 for Bows)' -> 'Fire Rate'."""
    import re
    return re.sub(r"\s*\(.*?\)", "", label).strip()


def mod_info(name: str):
    """(polarity, base drain, max rank, compatibility, kind, stats) of a mod by name, or None."""
    row = LO.data().get("mst", {}).get(name)
    return tuple(row) if row else None


def innate(kind: str, item: str, roles: list) -> list:
    """Polarity ('' for none) of every slot the item has before any Forma."""
    d = LO.data()
    pols = [""] * len(roles)
    if kind == "warframe":
        fr = d.get("frames", {}).get(item)
        if fr:
            general = [i for i, r in enumerate(roles) if r == "general"]
            for slot, p in zip(general, fr[6]):
                pols[slot] = p
            for i, r in enumerate(roles):
                if r == "aura":
                    pols[i] = fr[5]
    elif kind in ("companion", "archwing"):
        c = d.get("companions" if kind == "companion" else "archwings", {}).get(item)
        innate_pols = (c[1] if kind == "companion" else c) if c else []
        general = [i for i, r in enumerate(roles) if r == "general"]
        for slot, p in zip(general, innate_pols or []):
            pols[slot] = p
    else:
        w = d.get("weapons", {}).get(item)
        if w:
            general = [i for i, r in enumerate(roles) if r == "general"]
            for slot, p in zip(general, w[2]):
                pols[slot] = p
            for i, r in enumerate(roles):
                if r == "exilus":
                    pols[i] = w[3]
                elif r == "stance":
                    pols[i] = w[4]
    return pols


def slot_polarities(kind: str, item: str, roles: list, forma: list | None) -> list:
    """forma: the game file's [{"Slot": 3, "Value": "AP_ATTACK"}, ...] (or {slot: polarity} for the planner)."""
    pols = innate(kind, item, roles)
    if isinstance(forma, dict):
        for slot, p in forma.items():
            if 0 <= int(slot) < len(pols):
                pols[int(slot)] = p
    else:
        for f in forma or []:
            try:
                slot = int(f.get("Slot"))
            except (TypeError, ValueError, AttributeError):
                continue
            if 0 <= slot < len(pols):
                pols[slot] = AP.get(f.get("Value"), "")
    return pols


def fitted_polarities(kind: str, item: str, roles: list, forma, mods: list) -> list:
    """Slot polarities of a build read from the game file. The Forma'd slots are known; the item's innate polarities are
    not stored per slot anywhere public, so they are placed on the remaining slots where they save the most drain (players
    put matching mods on them, and the game never lets a build go over capacity: this placement is the one that fits)."""
    from itertools import permutations
    base = innate(kind, item, roles)
    general = [i for i, r in enumerate(roles) if r == "general"]
    wanted = [base[i] for i in general if base[i]]
    pols = [("" if roles[i] == "general" else base[i]) for i in range(len(roles))]
    fixed = set()
    for f in forma or []:
        try:
            slot = int(f.get("Slot"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= slot < len(pols):
            pols[slot] = AP.get(f.get("Value"), "")
            fixed.add(slot)
    free = [i for i in general if i not in fixed]
    k = min(len(wanted), len(free))
    if not k:
        return pols

    def cost(slot, pol):
        m = mods[slot] if slot < len(mods) else None
        info = mod_info(m[0]) if m and m[0] and not (len(m) > 2 and m[2]) else None
        if m and len(m) > 2 and m[2]:
            info = (m[2].get("polarity", ""), 10, 8, "", "R", {})
            m = (m[0], m[2].get("rank", 0))
        return drain(info, m[1], pol)[0] if info else 0
    best, best_cost = None, None
    for slots in permutations(free, k):
        c = sum(cost(s, p) - cost(s, "") for s, p in zip(slots, wanted[:k]))
        if best_cost is None or c < best_cost:
            best, best_cost = slots, c
    for s, p in zip(best, wanted[:k]):
        pols[s] = p
    return pols


def drain(info, rank, slot_pol: str):
    """(drain, state) of a mod at a rank in a slot; state: match, mismatch or '' (negative drain = Aura capacity)."""
    pol, base, mx = info[0], info[1], info[2]
    rank = mx if rank is None else max(0, min(int(rank), mx))
    d = base + rank if base >= 0 else base - rank
    if not slot_pol:
        return d, ""
    if slot_pol == pol or slot_pol == "universal":
        return (math.ceil(d / 2), "match") if d >= 0 else (d * 2, "match")
    return (d + math.ceil(d / 4), "mismatch") if d >= 0 else (-(abs(d) - round(abs(d) * 0.25)), "mismatch")


def evaluate(kind: str, item: str, roles: list, mods: list, pols: list, reactor: bool = True, level: int = 30) -> dict:
    """mods: per slot (name, rank or None) or None. Returns {"slots": [{"drain","state","pol","mpol"}], "total", "used", "free",
    "stats": {...} (Warframes only)}."""
    out, used, aura_bonus = [], 0, 0
    sums = {k: 0.0 for k in STAT_ORDER}
    bonus = {}                                   # weapons: label -> total percentage bonus of the mods and the Riven
    for i, role in enumerate(roles):
        m = mods[i] if i < len(mods) else None
        riven = m[2] if m and len(m) > 2 else None
        if riven and role != "arcane":           # a Riven: drain 10 + rank, its own polarity, its stats as they are
            info = (riven.get("polarity", ""), 10, 8, "", "R", {})
            m = (m[0], riven.get("rank", m[1]))
            for a in riven.get("attributes", []):
                if a.get("pct") and a.get("value") is not None:
                    lab = _plain(a["label"])
                    bonus[lab] = bonus.get(lab, 0) + a["value"] / 100
        else:
            info = mod_info(m[0]) if m and m[0] and role != "arcane" else None
        sp = pols[i] if i < len(pols) else ""
        if not info:
            out.append({"drain": None, "state": "", "pol": sp, "mpol": ""})
            continue
        dr, state = drain(info, m[1], sp)
        out.append({"drain": dr, "state": state, "pol": sp, "mpol": info[0]})
        if role == "aura" or dr < 0:
            aura_bonus += -dr
        else:
            used += dr
        mx = info[2] or 1
        rank = mx if m[1] is None else max(0, min(int(m[1]), mx))
        for k, v in info[5].items():
            if k in sums and kind == "warframe":
                sums[k] += v * (rank / mx)
            elif kind != "warframe" and not riven:
                bonus[k] = bonus.get(k, 0) + v * (rank / mx)
    total = max(0, min(40, int(level))) * (2 if reactor else 1) + aura_bonus
    res = {"slots": out, "total": total, "used": used, "free": total - used, "stats": {},
           "bonus": {k: round(v * 100, 1) for k, v in sorted(bonus.items(), key=lambda kv: -abs(kv[1])) if abs(v) > 1e-9}}
    fr = LO.data().get("frames", {}).get(item) if kind == "warframe" else None
    if fr:
        s = res["stats"]
        s["health"] = round(fr[0] * (1 + sums["health"]))
        s["shield"] = round(fr[1] * (1 + sums["shield"]))
        s["armor"] = round(fr[2] * (1 + sums["armor"]))
        s["energy"] = round(fr[3] * (1 + sums["energy"]))
        s["sprint"] = round(fr[4] * (1 + sums["sprint"]), 2)
        s["duration"] = round(max(12.5, 100 * (1 + sums["duration"])), 1)
        s["efficiency"] = round(min(175.0, max(25.0, 100 * (1 + sums["efficiency"]))), 1)
        s["range"] = round(max(10.0, 100 * (1 + sums["range"])), 1)
        s["strength"] = round(max(0.0, 100 * (1 + sums["strength"])), 1)
    return res


GENERIC = {"primary": {"Rifle": {"Rifle", "Assault Rifle", "PRIMARY"}, "Sniper": {"Sniper", "Rifle", "PRIMARY"},
                       "Bow": {"Bow", "Rifle", "PRIMARY"}, "Launcher": {"PRIMARY", "Rifle"}, "Shotgun": {"Shotgun"},
                       "Pistol": {"PRIMARY"}},
           "secondary": {"Pistol": {"Pistol", "Pistol (No Aoe)"}, "Dual Pistols": {"Pistol", "Pistol (No Aoe)"},
                         "Throwing": {"Thrown"}},
           "melee": {"Melee": {"Melee"}}}


def items(kind: str) -> list:
    """Names of the Warframes or weapons the planner offers for a kind."""
    d = LO.data()
    if kind == "warframe":
        return sorted(d.get("frames", {}))
    if kind == "companion":
        return sorted(d.get("companions", {}))
    if kind == "archwing":
        return sorted(d.get("archwings", {}))
    return sorted(n for n, w in d.get("weapons", {}).items() if w[0] == kind)


# mod slots the planner gives each kind (the game file's own layouts are in loadouts.LAYOUT)
PLAN_LAYOUT = {"companion": ["general"] * 10, "archwing": ["general"] * 8, "archmelee": ["general"] * 8}


def plan_roles(kind: str) -> list:
    return LO.LAYOUT.get(kind) or PLAN_LAYOUT.get(kind) or ["general"] * 8


def candidates(kind: str, item: str, role: str) -> list:
    """Names of the mods that fit a slot (the public data's compatibility field is rough: weapon-specific mods are matched by
    the weapon's name)."""
    mst = LO.data().get("mst", {})
    out = []
    if kind == "warframe":
        base = item.replace(" Prime", "").replace(" Umbra", "")
        for n, m in mst.items():
            if m[4] != "W":
                continue
            if role == "aura":
                ok = m[3] == "AURA"
            else:
                ok = m[3] in ("WARFRAME", item, base)
            if ok:
                out.append(n)
    elif kind in ("companion", "archwing", "archgun", "archmelee"):
        letter = {"companion": "C", "archwing": "A", "archgun": "R", "archmelee": "X"}[kind]
        fam = (LO.data().get("companions", {}).get(item) or ["", []])[0] if kind == "companion" else ""
        base = item.replace(" Prime", "").strip()
        words = {item.lower(), base.lower()} | {w.lower() for w in base.split()}
        fam_ok = {"sentinel": ("sentinel", "robotic"), "robotic": ("robotic", "moa", "hound"),
                  "beast": ("beast", "kubrow", "kavat", "claws", "vulpaphyla", "predasite", "helminth charger")}.get(fam, ())
        for n, m in mst.items():
            if m[4] != letter:
                continue
            compat = str(m[3]).strip().lower()
            if kind != "companion" or compat in ("companion",) or compat in fam_ok or compat in words:
                out.append(n)
    else:
        w = LO.data().get("weapons", {}).get(item)
        wtype = w[1] if w else ""
        generic = GENERIC.get(kind, {}).get(wtype, set())
        for n, m in mst.items():
            if role == "stance":
                if m[4] == "T":
                    out.append(n)
                continue
            if m[4] == "T":
                continue
            right = (m[4] == "P" and kind == "primary" and wtype != "Shotgun") or (m[4] == "G" and kind == "primary" and wtype == "Shotgun") \
                or (m[4] == "S" and kind == "secondary") or (m[4] == "M" and kind == "melee")
            if right and (m[3] in generic or m[3] == item):
                out.append(n)
    return sorted(out)


def arcane_candidates(kind: str) -> list:
    want = {"warframe": ("Warframe Arcane",), "primary": ("Primary Arcane", "Shotgun Arcane", "Bow Arcane"),
            "secondary": ("Secondary Arcane",), "melee": ("Melee Arcane",), "archgun": ("Primary Arcane",)}.get(kind, ())
    return sorted(n for n, ty in LO.data().get("arc", {}).items() if ty in want)
