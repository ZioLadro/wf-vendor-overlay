"""Riven calculator: the range of every stat a Riven can roll, how good a rolled value is (a grade, S best to F worst), and
the odds of rolling the stats you want when you cycle it with Kuva.

The figures follow the game data (rivens.json) and the same model the rest of the program uses (rivens.py):
    value = 90 x base x disposition x M x (rank + 1) / 9 x roll,   roll from 0.9 to 1.1
M depends on how many positive / negative stats the Riven has (2+0: 0.99 · 2+1: 1.2375 positive, 0.495 negative ·
3+0: 0.75 · 3+1: 0.9375 positive, 0.75 negative); every weapon's disposition is 1.2 since Hotfix 44.1.3.
That is the model RivenLens (github.com/remesis/RivenLens, GPL-3.0) uses too, written as 10 x (rank + 1) x
disposition x 1.5 x attenuation; its grade scale is the one used here: the roll's distance from the average, -10 % to
+10 %, cut in eleven letters (S: +9.5 % or more · A+ · A · A- · B+ · B (about average) · B- · C+ · C · C- · F: -9.5 % or
less). For a negative stat a higher grade is a stronger penalty. This module is a separate implementation of those
published rules, not RivenLens code.

Cycling odds: a cycle picks one of the four layouts (2 or 3 positives, with or without a negative) with the same chance,
draws the positives among the stats the weapon can roll, and the negative among the negatives that are not one of the
positives. With a stat locked the layout stays as it is and only the other stats are drawn (a locked cycle costs twice
the Kuva). Each cycle costs 3,500 Kuva."""
import math
from itertools import combinations

from app.game import loadouts as LO
from app.game import rivens as R

TYPES = {"Rifle": "LotusRifle", "Shotgun": "LotusShotgun", "Pistol": "LotusPistol", "Melee": "PlayerMeleeWeapon",
         "Archgun": "LotusArchgun", "Kitgun": "LotusModularPistol", "Zaw": "LotusModularMelee"}
LAYOUTS = ((2, 0), (2, 1), (3, 0), (3, 1))
KUVA_PER_CYCLE = 3500
LOCKED_KUVA = 2
GRADES = (("S", 9.5), ("A+", 7.5), ("A", 5.5), ("A-", 3.5), ("B+", 1.5), ("B", -1.5), ("B-", -3.5), ("C+", -5.5),
          ("C", -7.5), ("C-", -9.5), ("F", -10.0))
GRADE_COLORS = {"S": "#39ff14", "A+": "#55ff00", "A": "#83ff00", "A-": "#b5ff00", "B+": "#eaff00", "B": "#ffe000",
                "B-": "#ffc400", "C+": "#ff9a00", "C": "#ff6b00", "C-": "#ff3b00", "F": "#ff1744", "?": "#9aa4b2"}


def type_path(rtype: str) -> str:
    return "/Lotus/Upgrades/Mods/Randomized/" + TYPES.get(rtype, "LotusRifle") + "RandomModRare"


def type_of(weapon: str) -> str:
    """The Riven type of a weapon (Rifle, Shotgun, Pistol, Melee, Archgun, Kitgun, Zaw), "" when not known."""
    w = LO.data().get("weapons", {}).get(weapon)
    if w:
        kind, wtype = w[0], w[1]
        if kind == "primary":
            return "Shotgun" if wtype == "Shotgun" else "Rifle"
        if kind == "secondary":
            return "Pistol"
        if kind == "melee":
            return "Melee"
        if kind == "archgun":
            return "Archgun"
    for x in _market_weapons():
        if R._norm(x.get("name")) == R._norm(weapon):
            t = str(x.get("type") or "").lower()
            return {"rifle": "Rifle", "shotgun": "Shotgun", "pistol": "Pistol", "melee": "Melee", "archgun": "Archgun",
                    "kitgun": "Kitgun", "zaw": "Zaw"}.get(t, "")
    return ""


def _market_weapons() -> list:
    """warframe.market's Riven weapon list (saved by the Riven flip scan), [] when it was never downloaded."""
    try:
        import json
        from app.trade import rivenmarket as M
        return json.loads(M.WEAPONS_FILE.read_text(encoding="utf-8")).get("data") or []
    except Exception:
        return []


def weapons() -> list:
    """[(weapon name, Riven type)] of every weapon a Riven exists for, by name."""
    seen = {}
    for name, _dispo in R.data().get("weapons", {}).values():
        if name not in seen:
            ty = type_of(name)
            if ty:
                seen[name] = ty
    for x in _market_weapons():
        n = x.get("name")
        if n and n not in seen:
            ty = type_of(n)
            if ty:
                seen[n] = ty
    return sorted(seen.items(), key=lambda kv: kv[0].lower())


def stats(rtype: str) -> dict:
    """{tag: {"label", "base", "pct", "pos", "neg", "restr", "faction"}} a Riven type can roll."""
    out = {}
    for tag, v in (R.data()["types"].get(type_path(rtype)) or {}).items():
        out[tag] = {"label": v[4], "base": v[0], "pct": bool(v[3]), "pos": bool(v[5]) if len(v) > 5 else True,
                    "neg": bool(v[6]) if len(v) > 6 else True, "restr": v[7] if len(v) > 7 else "",
                    "faction": tag.endswith(R.TWO_DIGIT)}
    return out


PHYS = {"WeaponImpactDamageMod": "impact", "WeaponArmorPiercingDamageMod": "puncture", "WeaponSlashDamageMod": "slash"}


def pools(weapon: str, rtype: str) -> tuple:
    """(positive tags, negative tags) this weapon's Riven can roll: a physical damage stat only on weapons that deal
    that damage, no magazine / reload / ammo stats on the Grimoire."""
    st = stats(rtype)
    from app.trade.rivenmarket import weapon_stats
    ws = weapon_stats(weapon) or {}
    dmg = {k.lower(): float(v or 0) for k, v in (ws.get("dmg") or {}).items()}
    pos, neg = [], []
    for tag, s in st.items():
        if s["restr"] == "DamageTypes" and dmg and dmg.get(PHYS.get(tag, ""), 0) <= 0:
            continue
        if s["restr"] == "NotGrimoire" and "grimoire" in weapon.lower():
            continue
        if s["pos"]:
            pos.append(tag)
        if s["neg"]:
            neg.append(tag)
    return pos, neg


def mean_value(tag: str, rtype: str, layout: tuple, positive: bool, rank: int = 8) -> float | None:
    """The average value of a stat (roll 1.0) on this layout and rank, as the game shows it without the sign: a
    percentage (16.7 = 16.7 %) or, for faction damage, the multiplier's distance from x1 in percent."""
    s = stats(rtype).get(tag)
    mult = R.MULT.get(tuple(layout))
    if not s or not mult:
        return None
    m = mult[0] if positive else -mult[1]
    if not m:
        return None
    v = 90.0 * s["base"] * R.DISPOSITION * m * (rank + 1) / 9.0
    return v * 100.0 if s["pct"] else v


def value_range(tag: str, rtype: str, layout: tuple, positive: bool, rank: int = 8):
    """(lowest, highest) value (roll 0.9 and 1.1), None when the stat cannot be on that side."""
    v = mean_value(tag, rtype, layout, positive, rank)
    return None if v is None else (v * 0.9, v * 1.1)


def letter(quality_pct: float) -> str:
    """S … F from the roll's distance from the average (in %, -10 to +10)."""
    q = max(-10.0, min(10.0, quality_pct))
    return next((g for g, lo in GRADES if q >= lo), "F")


def grade(value: float, tag: str, rtype: str, layout: tuple, positive: bool, rank: int = 8, step: float = 0.1) -> dict:
    """How well a shown value rolled: {"grade", "quality" (% from the average), "low", "high" (the stat's range),
    "edge": the grade the value's rounding could also be, or "", "ok": False when the value is outside the range
    (wrong stat, rank or layout)}. Faction damage: the value as the multiplier's distance from 1 in % (x1.25 -> 25)."""
    mean = mean_value(tag, rtype, layout, positive, rank)
    if not mean:
        return {"grade": "?", "quality": None, "low": None, "high": None, "edge": "", "ok": False}
    v = abs(float(value))
    q = (v / mean - 1) * 100
    lo_q, hi_q = ((max(0.0, v - step / 2)) / mean - 1) * 100, ((v + step / 2) / mean - 1) * 100
    ok = lo_q <= 10 + 1e-6 and hi_q >= -10 - 1e-6
    g = letter(q)
    other = {letter(lo_q + 1e-6), letter(hi_q - 1e-6)} - {g}
    return {"grade": g if ok else "?", "quality": q, "low": mean * 0.9, "high": mean * 1.1,
            "edge": next(iter(other), "") if ok else "", "ok": ok}


def grade_riven(weapon: str, attrs: list, rank: int = 8) -> list:
    """Grades of a Riven's stats: attrs [{"tag" or "label", "value", "positive"}] -> [grade() + "tag", "label"]."""
    rtype = type_of(weapon)
    st = stats(rtype)
    by_label = {R._norm(s["label"]): tag for tag, s in st.items()}
    npos = sum(1 for a in attrs if a.get("positive", True))
    layout = (npos, len(attrs) - npos)
    out = []
    for a in attrs:
        tag = a.get("tag") if a.get("tag") in st else by_label.get(R._norm(a.get("label")))
        if not tag or a.get("value") is None:
            out.append({"grade": "?", "quality": None, "tag": tag, "label": a.get("label") or tag, "ok": False,
                        "low": None, "high": None, "edge": ""})
            continue
        v = float(a["value"])
        if st[tag]["faction"] and abs(v) < 3:          # shown as a multiplier (x1.25): its distance from 1, in %
            v = (v - 1) * 100
        g = grade(v, tag, rtype, layout, a.get("positive", True), rank)
        g.update(tag=tag, label=st[tag]["label"])
        out.append(g)
    return out


# ---------- cycling odds ----------
def _match(drawn, slots) -> bool:
    """Every wanted slot (a set of acceptable tags) gets its own drawn stat."""
    slots = [s for s in slots if s]
    if len(slots) > len(drawn):
        return False

    def assign(i, used):
        if i == len(slots):
            return True
        for j, tag in enumerate(drawn):
            if j not in used and tag in slots[i] and assign(i + 1, used | {j}):
                return True
        return False
    return assign(0, frozenset())


def odds(pos_pool: list, neg_pool: list, wanted: list, neg_mode: str = "any", neg_ok=(), layouts=None,
         lock: str = "", lock_layout: tuple | None = None) -> dict:
    """Chance that one cycle gives what you want.
    wanted: up to 3 sets of acceptable positive stats (one stat each, all different).
    neg_mode: "any" (whatever the negative), "none" (no negative), "good" (none, or one of neg_ok), "must" (one of neg_ok).
    layouts: the layouts that count ([(positives, negatives)], default all four); lock: a positive stat kept by locking
    it (the layout then stays lock_layout). Returns {"p", "rolls" (expected cycles), "kuva", "p50", "p90", "by_layout"}."""
    wanted = [set(w) for w in wanted if w]
    neg_ok = set(neg_ok)
    if lock:
        lay_w = {tuple(lock_layout or (3, 1)): 1.0}
    else:
        lay_w = {lay: 0.25 for lay in LAYOUTS}
    allowed = set(map(tuple, layouts)) if layouts else set(LAYOUTS)
    total, by = 0.0, {}
    for lay, w in lay_w.items():
        if lay not in allowed:
            continue
        k, has_neg = lay
        if neg_mode == "none" and has_neg:
            continue
        if neg_mode == "must" and not has_neg:
            continue
        pool = [t for t in pos_pool if t != lock]
        draws = k - (1 if lock else 0)
        if draws < 0 or draws > len(pool):
            continue
        n_comb = math.comb(len(pool), draws)
        p_lay = 0.0
        for combo in combinations(pool, draws):
            drawn = list(combo) + ([lock] if lock else [])
            if not _match(drawn, wanted):
                continue
            if not has_neg or neg_mode == "any":
                p_lay += 1.0
                continue
            negs = [t for t in neg_pool if t not in drawn]
            if not negs:
                continue
            p_lay += sum(1 for t in negs if t in neg_ok) / len(negs)
        p_lay /= n_comb
        by[lay] = p_lay
        total += w * p_lay
    cost = KUVA_PER_CYCLE * (LOCKED_KUVA if lock else 1)
    rolls = (1 / total) if total > 0 else math.inf

    def quant(c):
        if total <= 0:
            return math.inf
        if total >= 1:
            return 1
        return math.ceil(math.log1p(-c) / math.log1p(-total))
    return {"p": total, "rolls": rolls, "kuva": rolls * cost if total > 0 else math.inf, "p50": quant(0.5),
            "p90": quant(0.9), "by_layout": by, "cost": cost}
