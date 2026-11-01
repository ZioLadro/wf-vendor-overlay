"""Arcane Enhancements: ranks and copies, the slots an item has, what an Arcane does to the build's stats, and Vosfor.

Ranks (wiki "Arcane Enhancement"): ranking up consumes unranked copies of the same Arcane, one more copy for every rank, so
a rank r Arcane is made of (r + 1)(r + 2) / 2 copies: 1, 3, 6, 10, 15, 21. Most Arcanes stop at rank 5 (21 copies); the
Exodia, Virtuos, Pax and Residual ones at rank 3 (10 copies). No Endo and no credits are spent.

Slots: a Warframe has two Arcane slots, a primary or secondary weapon one (with its Arcane Adapter), a melee weapon one,
an Arch-gun two (one Primary and one Secondary Arcane). The same Arcane cannot be equipped twice on one item; Arcanes,
like mods, can be equipped on several items at once.

Effects: the game data has each Arcane's text at rank 0 and at its top rank ("On Kill: +30% Damage for 4s. Stacks up to
12x."). effects() reads the stats such a text gives with its condition met and every stack, scaled to the rank (a rank
r Arcane gives (r + 1) / (top + 1) of the top rank's value): the planner adds them to the build when "Arcane effects"
is on. Effects that need a choice or a target (on the next shot, against frozen enemies, healing, Overguard...) are not
counted; the tooltip lists them.

Vosfor (wiki "Vosfor"): Loid dissolves Arcanes into Vosfor (a fixed amount per copy, by Arcane) and sells collections of
3 random Arcanes for 200 Vosfor each (data/vosfor.json)."""
import json
import re

from app.core.paths import DATA
from app.game import loadouts as LO

TOP_RANK = 5


# ---------- ranks and copies ----------
def max_rank(name: str) -> int:
    for n, mx in LO.data().get("arcanes", {}).values():
        if n == name:
            return int(mx or TOP_RANK)
    return TOP_RANK


def copies(rank) -> int:
    """Copies a rank r Arcane is made of: 1, 3, 6, 10, 15, 21."""
    r = max(0, int(rank or 0))
    return (r + 1) * (r + 2) // 2


def rank_from_copies(n: int, top: int = TOP_RANK) -> int:
    """The highest rank n copies make."""
    r = 0
    while r < top and copies(r + 1) <= n:
        r += 1
    return r


def kind_of(name: str) -> str:
    """The game's Arcane type ("Warframe Arcane", "Primary Arcane"…), "" when not an Arcane."""
    return LO.data().get("arc", {}).get(name, "")


def is_arcane(name: str) -> bool:
    return bool(kind_of(name))


# ---------- slots ----------
SLOT_TYPES = {"warframe": [("Warframe Arcane",), ("Warframe Arcane",)],
              "primary": [("Primary Arcane",)], "secondary": [("Secondary Arcane",)], "melee": [("Melee Arcane",)],
              "archgun": [("Primary Arcane",), ("Secondary Arcane",)]}


def slot_candidates(kind: str, item: str, ordinal: int) -> list:
    """The Arcanes the game lets you put in an item's ordinal-th Arcane slot (0 = first). Shotgun and Bow Arcanes only on
    shotguns and bows; an Arch-gun's first slot takes Primary Arcanes, its second Secondary Arcanes."""
    slots = SLOT_TYPES.get(kind) or []
    if not slots:
        return []
    want = set(slots[min(ordinal, len(slots) - 1)])
    if kind == "primary":
        from app.game import buildcalc as BC
        ty = BC.item_type(item)
        if ty == "Shotgun":
            want.add("Shotgun Arcane")
        if ty == "Bow":
            want.add("Bow Arcane")
    return sorted(n for n, ty in LO.data().get("arc", {}).items() if ty in want)


# ---------- effects ----------
# words of the Arcane texts -> where they count: ("frame", stat key of buildcalc.STAT_ORDER) for a Warframe,
# ("weapon", bonus label of buildcalc.weapon_stats) for a weapon
FRAME_STATS = {"ability strength": "strength", "ability duration": "duration", "ability range": "range",
               "ability efficiency": "efficiency", "max health": "health", "health": "health", "armor": "armor",
               "shield capacity": "shield", "max shields": "shield", "energy max": "energy", "max energy": "energy",
               "maximum energy": "energy", "sprint speed": "sprint"}
WEAPON_STATS = {"critical chance": "Critical Chance", "critical damage": "Critical Damage", "status chance": "Status Chance",
                "multishot": "Multishot", "reload speed": "Reload Speed", "fire rate": "Fire Rate",
                "attack speed": "Attack Speed", "melee damage": "Melee Damage", "damage": "Damage",
                "headshot multiplier": "Headshot Multiplier", "weapon recoil": "Weapon Recoil",
                "corrosive damage": "Corrosive"}
# texts whose bonus does not hold for the build as a whole: one shot, one ability, one kind of enemy or attack
SKIP = re.compile(r"\bnext\b|heavy attack|against|on weak point hits|companion|allies|summon|overguard|"
                  r"to (primary|secondary|pistols|melee|sniper|shotguns)|primary weapons|secondary weapons|"
                  r"melee weapons|bleedout|revive|regen|recharge|life steal|parkour|resist", re.I)
_NUM = r"([+-]?\d[\d,]*(?:\.\d+)?)"


def _stat_name(text: str, table: dict):
    low = text.lower()
    for k in sorted(table, key=len, reverse=True):
        if re.search(r"\b" + re.escape(k) + r"\b", low):
            return table[k]
    return None


def _lines(text: str) -> list:
    """An Arcane text in parts that each hold one effect: the lines, and each line's sentences split on " and +"."""
    out = []
    for line in re.split(r"\s*/\s*|\n", text or ""):
        line = line.strip()
        if line:
            out.append(line)
    return out


def parse(text: str, kind: str) -> tuple:
    """({stat: value}, [texts not counted]) of one Arcane text (its top rank), as it applies to an item of `kind`
    ("warframe" or a weapon kind). Values: percentages as fractions (0.3 = +30 %), "flat:<stat>" for flat amounts."""
    table = FRAME_STATS if kind == "warframe" else WEAPON_STATS
    got, skipped = {}, []
    for line in _lines(text):
        if line.endswith(":") or line.lower().startswith("on ") and line.endswith(":"):
            continue                                    # "On Kill:" - the condition, taken as met
        if SKIP.search(line):
            skipped.append(line)
            continue
        stacks = re.search(r"stack(?:s|ing)? up to (\d+)\s*x", line, re.I)
        cap = re.search(r"up to (?:a maximum of )?\+?" + _NUM + r"\s*%", line, re.I)
        found = False
        for m in re.finditer(_NUM + r"\s*(%|x\b)?\s*(?:to )?([A-Za-z][A-Za-z ]+?)(?=\s+(?:for|per|and|on|while|when|,)|[.,]|$)",
                             line):
            num, unit, what = m.group(1), m.group(2), m.group(3)
            stat = _stat_name(what, table)
            if not stat:
                continue
            v = float(num.replace(",", ""))
            if unit == "%":
                v /= 100.0
                if stacks:
                    v *= int(stacks.group(1))
                if cap:
                    v = min(v, float(cap.group(1).replace(",", "")) / 100.0) if stacks else \
                        float(cap.group(1).replace(",", "")) / 100.0
                key = stat
            elif unit == "x":
                skipped.append(line)                      # "x2.5 Melee Damage", "+3x Final Critical Damage": special
                found = True
                break
            else:
                if kind != "warframe":
                    continue
                if stacks:
                    v *= int(stacks.group(1))
                key = "flat:" + stat
            got[key] = got.get(key, 0.0) + v
            found = True
        if not found and re.search(r"\d", line):
            skipped.append(line)
    return got, skipped


def effects(name: str, rank, kind: str) -> dict:
    """What an Arcane of this rank does to an item of `kind`: {"pct": {stat: fraction}, "flat": {stat: amount},
    "bonus": {weapon label: fraction}, "skipped": [texts]}; empty dicts for Arcanes of another item kind."""
    out = {"pct": {}, "flat": {}, "bonus": {}, "skipped": []}
    texts = LO.data().get("mtext", {}).get(name)
    ty = kind_of(name)
    if not texts or not ty:
        return out
    if kind == "warframe" and ty != "Warframe Arcane":
        return out
    top = max_rank(name)
    k = (min(top, max(0, int(rank if rank is not None else top))) + 1) / (top + 1)
    got, skipped = parse(texts[-1], kind)
    out["skipped"] = skipped
    melee = kind in ("melee", "archmelee")
    for key, v in got.items():
        v *= k
        if key.startswith("flat:"):
            out["flat"][key[5:]] = out["flat"].get(key[5:], 0) + v
        elif kind == "warframe":
            out["pct"][key] = out["pct"].get(key, 0) + v
        else:
            if key == "Damage" and melee:
                key = "Melee Damage"
            if key == "Weapon Recoil":
                continue                                   # not shown in the planner's stats
            out["bonus"][key] = out["bonus"].get(key, 0) + v
    return out


def build_effects(arcanes, kind: str) -> dict:
    """The effects of an item's Arcanes together ([(name, rank)]): the same shape as effects(), plus "used": the names
    that changed a stat."""
    total = {"pct": {}, "flat": {}, "bonus": {}, "skipped": [], "used": []}
    for name, rank in arcanes:
        e = effects(name, rank, kind)
        changed = False
        for part in ("pct", "flat", "bonus"):
            for k, v in e[part].items():
                total[part][k] = total[part].get(k, 0) + v
                changed = True
        if changed:
            total["used"].append(name)
        total["skipped"] += [f"{name}: {s}" for s in e["skipped"]]
    return total


def describe(name: str, rank=None) -> str:
    """The Arcane's text at this rank for tooltips (rank 0 and top rank texts from the game data; between them the
    numbers are scaled)."""
    texts = LO.data().get("mtext", {}).get(name)
    if not texts:
        return ""
    top = max_rank(name)
    r = top if rank is None else max(0, min(top, int(rank)))
    if r == top:
        return texts[-1]
    if r == 0:
        return texts[0]
    k = (r + 1) / (top + 1)

    def scale(m):
        s = m.group(0)
        try:
            v = float(s.replace(",", "")) * k
        except ValueError:
            return s
        return f"{v:.3g}"
    # numbers of the top text that differ from the rank 0 text are the ones that grow with the rank
    t0, t1 = texts[0], texts[-1]
    n0, n1 = re.findall(r"\d[\d,]*(?:\.\d+)?", t0), re.findall(r"\d[\d,]*(?:\.\d+)?", t1)
    if len(n0) != len(n1):
        return t1
    parts, i = [], 0
    for a, b, m in zip(n0, n1, re.finditer(r"\d[\d,]*(?:\.\d+)?", t1)):
        parts.append(t1[i:m.start()])
        parts.append(b if a == b else scale(m))
        i = m.end()
    parts.append(t1[i:])
    return "".join(parts)


# ---------- Vosfor ----------
_vosfor = None


def vosfor_data() -> dict:
    global _vosfor
    if _vosfor is None:
        try:
            _vosfor = json.loads((DATA / "vosfor.json").read_text(encoding="utf-8"))
        except Exception:
            _vosfor = {"yield": {}, "collections": {}, "pack_cost": 200, "pack_size": 3}
    return _vosfor


def vosfor_yield(name: str):
    """Vosfor for dissolving one copy (rank 0) of this Arcane; None when it cannot be dissolved or is not known."""
    return vosfor_data().get("yield", {}).get(name)


def dissolve_value(name: str, rank=0, n=1):
    """Vosfor for dissolving n Arcanes of this rank: every copy a ranked Arcane is made of counts."""
    y = vosfor_yield(name)
    return None if y is None else y * copies(rank) * int(n)


def pack_odds(collection: str) -> dict:
    """{Arcane name: chance of one of the pack's slots} of a Loid collection (a rarity's chance shared equally)."""
    c = vosfor_data().get("collections", {}).get(collection) or {}
    out = {}
    for _rar, chance, names in c.get("pools") or []:
        for n in names:
            out[n] = out.get(n, 0) + chance / len(names)
    return out
