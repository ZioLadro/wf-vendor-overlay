"""Build maths: slot polarities, mod drain, capacity and the Warframe stat recap (an approximation of the in-game screen).

Not counted: Arcanes, Archon Shards, Helminth, set bonuses, conditional or per-enemy effects, Warframe rank below 30.
Polarity of a slot: the one set by Forma in the game file, otherwise the Warframe's / weapon's innate one (the public data lists
the innate polarities in slot order, which is how they are assigned here)."""
import math

from app.game import loadouts as LO

AP = {"AP_ATTACK": "madurai", "AP_DEFENSE": "vazarin", "AP_TACTIC": "naramon", "AP_POWER": "zenurik", "AP_WARD": "unairu",
      "AP_UMBRA": "umbra", "AP_PRECEPT": "penjaga", "AP_ANY": "universal", "AP_UNIVERSAL": ""}
POLARITIES = ["madurai", "vazarin", "naramon", "zenurik", "unairu", "penjaga", "umbra", "universal"]
# capacity = the item's rank (30 at rank 30), doubled by an Orokin Reactor / Catalyst; an Aura adds its own.
# A "universal" slot (AP_ANY in the game file: an Aura Forma) matches every mod polarity: checked on a real build, the game's
# total (60 + Aura 7 doubled = 74) only comes out that way. AP_UNIVERSAL is NOT that: the game writes it on slots without
# a polarity (an Exilus slot of a Cyte-09: Sure Footed rank 3 costs 9 there in the game, not 5), so it counts as none.
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
                elif r == "exilus" and len(fr) > 7:      # a few Warframes have one (Gauss, Hildryn, Baruuk…)
                    pols[i] = fr[7] or ""
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


def rank_factor(rank, mx) -> float:
    """How much of a mod's max-rank effect it gives at a rank: (rank + 1) / (max + 1), as in the game (Serration +15 %
    at rank 0, +165 % at rank 10). A mod without ranks gives all of it."""
    if not mx:
        return 1.0
    r = mx if rank is None else max(0, min(int(rank), int(mx)))
    return (r + 1) / (int(mx) + 1)


# what a Warframe gains by rank 30 over its rank-0 stats (the public data has rank 0): checked on Cyte-09 in the game,
# 225 / 135 / 180 -> 325 / 235 / 230
RANK_GAIN = {"health": 100, "shield": 100, "energy": 50}


def frame_base(item: str, level: int = 30) -> dict:
    """A Warframe's stats without mods at its rank (the gains spread evenly over the 30 ranks); {} if unknown."""
    fr = LO.data().get("frames", {}).get(item)
    if not fr:
        return {}
    k = max(0, min(30, int(level))) / 30
    out = {"health": fr[0] + RANK_GAIN["health"] * k, "shield": fr[1] + (RANK_GAIN["shield"] * k if fr[1] else 0),
           "armor": fr[2], "energy": fr[3] + RANK_GAIN["energy"] * k, "sprint": fr[4]}
    return {key: (round(v) if key != "sprint" else v) for key, v in out.items()}


# ---------- Archon Shards (Warframes) ----------
# what a shard adds (normal; Tauforged = x1.5), from the wiki's Archon Shard page. "pct": with the mods (additive);
# "flat": added after every other bonus (the Azure ones). Shards whose bonus is not a stat of the panel (casting speed,
# orbs, ability damage on statused enemies…) are listed, not counted.
SHARD_STATS = {"AbilityStrength": ("pct", "strength", 0.10), "AbilityDuration": ("pct", "duration", 0.10),
               "HealthMax": ("flat", "health", 150), "ShieldMax": ("flat", "shield", 150),
               "EnergyMax": ("flat", "energy", 50), "ArmourMax": ("flat", "armor", 150)}
# the shard choices of the planner: colour -> [(key, label)]
SHARD_CHOICES = {"RED": [("AbilityStrength", "Ability Strength +10%"), ("AbilityDuration", "Ability Duration +10%"),
                         ("CritDamageBoost", "Melee Critical Damage +25%"), ("PrimaryStatusChance", "Primary Status Chance +25%"),
                         ("SecondaryCritChance", "Secondary Critical Chance +25%")],
                 "BLUE": [("HealthMax", "Health +150"), ("ShieldMax", "Shield Capacity +150"), ("EnergyMax", "Energy Max +50"),
                          ("ArmourMax", "Armor +150"), ("HealthRegen", "Health Regeneration +5/s")],
                 "YELLOW": [("CastingSpeed", "Casting Speed +25%"), ("ParkourVelocity", "Parkour Velocity +15%"),
                            ("StartingEnergy", "Energy on Spawn +30%"), ("HealthOrbEffectiveness", "Health Orbs +100%"),
                            ("EnergyOrbEffectiveness", "Energy Orbs +50%")],
                 "GREEN": [("ToxinDamage", "Toxin Status Damage +30%"), ("CorrosiveStack", "Max Corrosion Stacks +2")],
                 "PURPLE": [("ElectricDamage", "Primary Electricity Damage +30%"), ("CritDamageBoostViolet", "Melee Critical Damage +25%")],
                 "ORANGE": [("BlastHealth", "Health per Blast kill +1")]}


def shard_bonus(shards, shield=True, energy=True) -> tuple:
    """({stat: percentage to add with the mods}, {stat: flat amount added at the end}) of a Warframe's Archon Shards.
    shield / energy False: the Warframe has no shields (Inaros, Nidus, Kullervo) / no energy (Hildryn, Lavos)."""
    pct, flat = {}, {}
    for s in shards or []:
        spec = SHARD_STATS.get(str(s.get("key") or ""))
        if not spec:
            continue
        how, stat, v = spec
        if (stat == "shield" and not shield) or (stat == "energy" and not energy):
            continue
        v *= 1.5 if s.get("tauforged") else 1.0
        (pct if how == "pct" else flat)[stat] = (pct if how == "pct" else flat).get(stat, 0) + v
    return pct, flat


def evaluate(kind: str, item: str, roles: list, mods: list, pols: list, reactor: bool = True, level: int = 30,
             locked: dict | None = None, shards=None) -> dict:
    """mods: per slot (name, rank or None) or None. Returns {"slots": [{"drain","state","pol","mpol"}], "total", "used", "free",
    "stats": {...} (Warframes only), "bonus": {label: %} and "elements": [(element, fraction)] in slot order (weapons)}.
    locked: {"exilus": True} when the Exilus slot has no adapter (its mod counts for nothing)."""
    locked = locked or {}
    elements, flat = [], {}
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
        f = rank_factor(m[1], info[2])
        if role == "exilus" and locked.get("exilus"):
            continue                              # an Exilus slot without its adapter: the mod does nothing
        for k, v in info[5].items():
            if k.endswith(" (flat)"):             # "+3 Range" (Primed Reach): added, not a percentage
                lab = k[:-7]
                flat[lab] = flat.get(lab, 0) + v * f
            elif k in sums and kind == "warframe":
                sums[k] += v * f
            elif kind != "warframe" and not riven:
                bonus[k] = bonus.get(k, 0) + v * f
                if k in ELEMENTS or k in COMBINED:
                    elements.append((k, v * f))
        if riven:
            for a in riven.get("attributes", []):
                lab = _plain(a.get("label", ""))
                if a.get("pct") and a.get("value") is not None and (lab in ELEMENTS or lab in COMBINED):
                    elements.append((lab, a["value"] / 100))
    total = max(0, min(40, int(level))) * (2 if reactor else 1) + aura_bonus
    res = {"slots": out, "total": total, "used": used, "free": total - used, "stats": {}, "elements": elements,
           "flat": {k: round(v, 2) for k, v in flat.items()},
           "bonus": {k: round(v * 100, 1) for k, v in sorted(bonus.items(), key=lambda kv: -abs(kv[1])) if abs(v) > 1e-9}}
    fr = LO.data().get("frames", {}).get(item) if kind == "warframe" else None
    if fr:
        s = res["stats"]
        base = frame_base(item, level)
        spct, sflat = shard_bonus(shards, shield=bool(fr[1]), energy=item not in ("Hildryn", "Hildryn Prime", "Lavos", "Lavos Prime"))
        for k, v in spct.items():
            sums[k] += v
        cut = lambda v, d=0: math.floor(v * 10 ** d + 1e-6) / 10 ** d   # the game cuts decimals off (655.5 -> 655)
        s["health"] = int(cut(base["health"] * (1 + sums["health"])))
        s["shield"] = int(cut(base["shield"] * (1 + sums["shield"])))
        s["armor"] = int(cut(base["armor"] * (1 + sums["armor"])))
        s["energy"] = int(cut(base["energy"] * (1 + sums["energy"])))
        for k, v in sflat.items():                   # Azure shards: added after every other bonus
            s[k] += int(v)
        s["sprint"] = cut(fr[4] * (1 + sums["sprint"]), 2)
        s["duration"] = cut(max(12.5, 100 * (1 + sums["duration"])))
        s["efficiency"] = cut(min(175.0, max(25.0, 100 * (1 + sums["efficiency"]))))
        s["range"] = cut(max(10.0, 100 * (1 + sums["range"])))
        s["strength"] = cut(max(0.0, 100 * (1 + sums["strength"])))
    return res


# ---------- weapon stats (the planner's recap, like the in-game screen) ----------
ELEMENTS = ("Heat", "Cold", "Electricity", "Toxin")
COMBO = {frozenset(("Heat", "Cold")): "Blast", frozenset(("Heat", "Electricity")): "Radiation",
         frozenset(("Heat", "Toxin")): "Gas", frozenset(("Cold", "Electricity")): "Magnetic",
         frozenset(("Cold", "Toxin")): "Viral", frozenset(("Electricity", "Toxin")): "Corrosive"}
COMBINED = ("Blast", "Radiation", "Gas", "Magnetic", "Viral", "Corrosive")
DAMAGE_ORDER = ("Impact", "Puncture", "Slash", "Heat", "Cold", "Electricity", "Toxin", "Blast", "Radiation", "Gas",
                "Magnetic", "Viral", "Corrosive", "Void", "Tau", "True")
VALENCE = ("Heat", "Cold", "Electricity", "Toxin", "Impact", "Magnetic", "Radiation")


def valence_capable(item: str) -> bool:
    """Kuva, Tenet and Coda weapons have a bonus element (25-60 %) that a Valence Fusion can change."""
    return item.startswith(("Kuva ", "Tenet ", "Coda ", "Dual Coda "))


def combine(order: list, innate: dict) -> dict:
    """Elements as the game combines them: the mods' elements in slot order (the same element twice counts once, at its
    first place), then the weapon's own single elements (the Kuva / Tenet / Coda bonus among them); every two in a row
    make their combined element. order: [(element, amount)]; innate: {element: amount} (single and combined).
    Returns {element: amount}."""
    seq, amount, direct = [], {}, {}
    for el, v in order:
        if el not in ELEMENTS:                      # a mod of a combined element (Magnetic Capacity…): as it is
            direct[el] = direct.get(el, 0) + v
            continue
        if el not in amount:
            seq.append(el)
        amount[el] = amount.get(el, 0) + v
    for el, v in innate.items():
        if el in ELEMENTS:
            if el not in amount:
                seq.append(el)
            amount[el] = amount.get(el, 0) + v
    out = {el: v for el, v in innate.items() if el not in ELEMENTS and v}
    for el, v in direct.items():
        out[el] = out.get(el, 0) + v
    i = 0
    while i < len(seq):
        if i + 1 < len(seq):
            a, b = seq[i], seq[i + 1]
            c = COMBO[frozenset((a, b))]
            out[c] = out.get(c, 0) + amount[a] + amount[b]
            i += 2
        else:
            out[seq[i]] = out.get(seq[i], 0) + amount[seq[i]]
            i += 1
    return out


def weapon_stats(kind: str, item: str, bonus: dict, elements: list, valence: dict | None = None,
                 flat: dict | None = None, perks: dict | None = None) -> dict | None:
    """The weapon's stats with the build: {"rows": [(key, base, modded)], "damage": [(element, base, modded)], "total":
    (base, modded), "dps": (base, modded)} or None without base stats. bonus: {label: %} (evaluate()["bonus"]);
    elements: evaluate()["elements"]; valence: {"element", "pct"} for Kuva / Tenet / Coda weapons.
    perks: the chosen Incarnon perks' stats (incarnon.bonuses): base damage, critical / status chance, multishot… added
    to the weapon's own (the "base" column then includes them), percentages added like a mod's.
    Not counted: conditional effects (Galvanized stacks, Condition Overload…), Arcanes, the Incarnon form, ammo, falloff."""
    ws = LO.data().get("wstats", {}).get(item)
    if not ws:
        return None
    if perks:
        ws = dict(ws)
        dmg0 = dict(ws.get("dmg") or {})
        t0 = sum(dmg0.values())
        if perks.get("damage") and t0:                 # "+10 Damage": the base damage, spread over its types
            k = (t0 + perks["damage"]) / t0
            ws["dmg"] = {e: v * k for e, v in dmg0.items()}
        for key, src in (("cc", "cc"), ("sc", "sc"), ("cd", "cd"), ("ms", "ms"), ("mag", "mag"), ("rng", "range")):
            if perks.get(src) and ws.get(key) is not None:
                ws[key] = ws[key] + perks[src]
        if ws.get("fr") is not None and (perks.get("fr") or perks.get("as")):
            ws["fr"] = ws["fr"] + (perks.get("fr") or 0) + (perks.get("as") or 0)
        if perks.get("pct"):
            bonus = dict(bonus)
            for lab, v in perks["pct"].items():
                bonus[lab] = bonus.get(lab, 0) + v
    b = lambda *labels: sum(bonus.get(lab, 0) for lab in labels) / 100
    melee = kind in ("melee", "archmelee") or "rng" in ws
    base = {k.title() if k != "true" else "True": float(v) for k, v in (ws.get("dmg") or {}).items()}
    total0 = sum(base.values())
    mult = 1 + (b("Melee Damage") if melee else b("Damage"))
    phys = {p: base.get(p, 0) * mult * (1 + b(p)) for p in ("Impact", "Puncture", "Slash") if base.get(p)}
    innate = {el: v * mult for el, v in base.items() if el not in ("Impact", "Puncture", "Slash")}
    if valence and valence.get("element"):
        el, v = valence["element"], total0 * float(valence.get("pct") or 0) / 100 * mult
        if el in ("Impact", "Puncture", "Slash"):
            phys[el] = phys.get(el, 0) + v * (1 + b(el))
        else:
            innate[el] = innate.get(el, 0) + v
    mods = [(el, total0 * mult * frac) for el, frac in elements]
    dmg = dict(phys)
    for el, v in combine(mods, innate).items():
        dmg[el] = dmg.get(el, 0) + v
    base_dmg = dict(base)
    if valence and valence.get("element"):
        base_dmg[valence["element"]] = base_dmg.get(valence["element"], 0) + total0 * float(valence.get("pct") or 0) / 100
    total = sum(dmg.values())
    cc0, cd0, sc0 = ws.get("cc", 0), ws.get("cd", 1), ws.get("sc", 0)
    cc, cd, sc = cc0 * (1 + b("Critical Chance")), cd0 * (1 + b("Critical Damage")), sc0 * (1 + b("Status Chance"))
    rows = []
    if melee:
        rate0 = ws.get("fr", 1)
        rate = rate0 * (1 + b("Attack Speed"))
        rows.append(("attack_speed", rate0, rate))
        if ws.get("rng"):
            rows.append(("range", ws["rng"], ws["rng"] + float((flat or {}).get("Range", 0))))
        if ws.get("slam"):
            rows.append(("slam", ws["slam"], ws["slam"] * mult))
        if ws.get("slide"):
            rows.append(("slide", ws["slide"], ws["slide"] * mult))
        if ws.get("cdur"):
            rows.append(("combo", ws["cdur"], ws["cdur"]))
        if ws.get("ft"):
            rows.append(("follow", ws["ft"], ws["ft"]))
        ms0 = ms = 1.0
    else:
        rate0 = ws.get("fr", 1)
        rate = rate0 * (1 + b("Fire Rate"))
        ms0 = ws.get("ms", 1) or 1
        ms = ms0 * (1 + b("Multishot"))
        rows.append(("fire_rate", rate0, rate))
        rows.append(("multishot", ms0, ms))
        if ws.get("mag"):
            rows.append(("magazine", ws["mag"], max(1, round(ws["mag"] * (1 + b("Magazine Capacity"))))))
        if ws.get("rl"):
            rows.append(("reload", ws["rl"], ws["rl"] / max(0.05, 1 + b("Reload Speed"))))
        if ws.get("trig"):
            rows.append(("trigger", ws["trig"], ws["trig"]))
    crit = [("crit_chance", cc0, cc), ("crit_damage", cd0, cd), ("status", sc0, sc)]
    dps = lambda t, r, m, c, d: t * r * m * (1 + min(c, 10) * (d - 1))
    order = {el: n for n, el in enumerate(DAMAGE_ORDER)}
    names = sorted(set(dmg) | set(base_dmg), key=lambda el: order.get(el, 99))
    return {"rows": rows, "crit": crit,
            "damage": [(el, base_dmg.get(el, 0), dmg.get(el, 0)) for el in names if base_dmg.get(el) or dmg.get(el)],
            "total": (total0, total), "dps": (dps(total0, rate0, ms0, cc0, cd0), dps(total, rate, ms, cc, cd)),
            "melee": melee, "perks": list((perks or {}).get("used") or [])}


def forma_count(kind: str, item: str, roles: list, forma: dict) -> int:
    """Forma a planned build needs. The item's own polarities are not tied to a slot in the public data, so among the
    general slots they count as a set: a polarity the item already has (once per copy) needs no Forma, wherever it is.
    Aura / Exilus / Stance slots are compared one by one (their own kind of Forma, counted the same here)."""
    from collections import Counter
    base = innate(kind, item, roles)
    pols = slot_polarities(kind, item, roles, forma or {})
    general = [i for i, r in enumerate(roles) if r == "general"]
    have = Counter(base[i] for i in general if base[i])
    want = Counter(pols[i] for i in general if pols[i])
    n = sum(max(0, c - have.get(p, 0)) for p, c in want.items())
    n += sum(1 for i, r in enumerate(roles) if r != "general" and r != "arcane" and pols[i] != base[i] and pols[i])
    return n


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


def item_type(item: str) -> str:
    """The weapon type of the data ("Rifle", "Shotgun", "Claws", "Robotic"…), "" for the others."""
    w = LO.data().get("weapons", {}).get(item)
    return w[1] if w else ""


# mod slots the planner gives each kind (the game file's own layouts are in loadouts.LAYOUT)
PLAN_LAYOUT = {"companion": ["general"] * 10, "archwing": ["general"] * 8, "archmelee": ["general"] * 8,
               "compweapon": ["general"] * 8}


def plan_roles(kind: str, item: str = "") -> list:
    if kind == "compweapon" and item_type(item) == "Claws":       # beasts' claws: a Posture slot like a stance
        return ["general"] * 8 + ["stance"]
    return LO.LAYOUT.get(kind) or PLAN_LAYOUT.get(kind) or ["general"] * 8


def exilus_ok(name: str) -> bool:
    """A mod that can go in an Exilus slot (utility mods). Data made before 0.4.0 does not say: then every mod can."""
    row = LO.data().get("mst", {}).get(name)
    return bool(row and (len(row) < 7 or row[6]))


def candidates(kind: str, item: str, role: str) -> list:
    """Names of the mods that fit a slot (the public data's compatibility field is rough: weapon-specific mods are matched by
    the weapon's name). An Exilus slot takes only the utility mods."""
    out = _candidates(kind, item, role)
    return [n for n in out if exilus_ok(n)] if role == "exilus" else out


def _candidates(kind: str, item: str, role: str) -> list:
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
    elif kind == "compweapon":
        claws = item_type(item) == "Claws"
        for n, m in mst.items():
            if role == "stance":
                if m[4] == "Y":
                    out.append(n)
                continue
            compat = str(m[3]).strip().lower()
            if claws:
                ok = m[4] == "C" and compat.endswith("claws")
            else:                                  # robotic weapons: rifle / shotgun mods and their own
                ok = (m[4] == "P" and m[3] in ("Rifle", "Assault Rifle", "PRIMARY")) or (m[4] == "G" and m[3] == "Shotgun") \
                    or (m[4] == "C" and compat in ("robotic", item.lower()))
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
