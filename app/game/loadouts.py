"""Your own in-game loadouts, read from the AlecaFrame inventory file and laid out like the in-game screen.

For every Warframe, weapon, Archwing and companion: its loadouts (A, B, C…), each with the slots filled in the game's
order, the Arcanes, the forma count and, for a Warframe, the Archon Shards and the Helminth ability.
Slot order in the game data (index in a loadout's "Upgrades" list):
  Warframe        0-7 mods, 8 Aura, 9 Exilus, 10-11 Arcanes
  Primary/Secondary/Arch-gun   0-7 mods, 8 Exilus, 9 Arcane
  Melee           0-7 mods, 8 Stance, 9 Exilus, 10 Arcane
  Others (Archwing, companions)   all general
"""
import json
import re
import sys
from pathlib import Path

from app.game import inventory as I
from app.core.paths import DATA

DATA_FILE = DATA / "loadout_data.json"
CATEGORIES = (("Suits", "warframe"), ("LongGuns", "primary"), ("Pistols", "secondary"), ("Melee", "melee"),
              ("SpaceSuits", "archwing"), ("SpaceGuns", "archgun"), ("MechSuits", "necramech"),
              ("Sentinels", "companion"), ("KubrowPets", "companion"), ("MoaPets", "companion"), ("HoundPets", "companion"),
              ("SentinelWeapons", "compweapon"), ("SpecialItems", "exalted"))
# SpecialItems also holds the beast companions' claws (read as companion weapons) and summoned "suits" (Sevagoth's Shadow,
# Venari, Merulina): of the rest only the Warframes' exalted weapons (under /Lotus/Powersuits/) are kept
CLAWS = re.compile(r"PetWeapon|Claws?$")
EXALTED_SKIP = re.compile(r"(PowerSuit|Suit|/SevagothShadow\w*|/Reaper)$")
# kind -> slot roles in index order (the 8 general slots come first)
LAYOUT = {
    "warframe": ["general"] * 8 + ["aura", "exilus", "arcane", "arcane"],
    "primary": ["general"] * 8 + ["exilus", "arcane"],
    "secondary": ["general"] * 8 + ["exilus", "arcane"],
    "archgun": ["general"] * 8 + ["exilus", "arcane"],
    "melee": ["general"] * 8 + ["stance", "exilus", "arcane"],
}
LETTERS = "ABCDEFGH"
MIN_MODS = 2                          # a loadout with fewer mods than this is an unused one
SHARD_COLORS = {"RED": "Crimson", "BLUE": "Azure", "GREEN": "Emerald", "YELLOW": "Amber", "ORANGE": "Topaz",
                "PURPLE": "Violet"}
SHARD_EFFECT = {"CritDamageBoost": "Critical damage", "AbilityDuration": "Ability duration",
                "AbilityStrength": "Ability strength", "AbilityRange": "Ability range", "ParkourVelocity": "Parkour velocity",
                "ToxinDamage": "Toxin damage", "ElectricDamage": "Electric damage", "FireDamage": "Heat damage",
                "ColdDamage": "Cold damage", "CorrosiveStack": "Corrosive stacking", "CastingSpeed": "Casting speed",
                "HealthMax": "Health", "ArmourMax": "Armor", "ShieldMax": "Shields", "EnergyMax": "Energy",
                "SlashProc": "Slash status", "MagneticProc": "Magnetic status", "BlastProc": "Blast status",
                "GasProc": "Gas status", "ViralProc": "Viral status", "RadiationProc": "Radiation status",
                "HeatProc": "Heat status", "ColdProc": "Cold status", "ToxinProc": "Toxin status",
                "ElectricProc": "Electric status", "ImpactProc": "Impact status", "PunctureProc": "Puncture status",
                "SlideCritChance": "Slide crit chance", "BoltsPerKill": "Energy on kill"}

_data = None


def data() -> dict:
    global _data
    if _data is None:
        try:
            _data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            _data = {}
        for k in ("mods", "arcanes", "abilities", "suits", "helminth"):
            _data.setdefault(k, {})
    return _data


def _words(s: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s).strip()


def mod_name(path: str):
    """(name, max rank or None) of a mod or arcane path."""
    d = data()
    if path in d["mods"]:
        return d["mods"][path][0], d["mods"][path][1] or None
    if path in d["arcanes"]:
        return d["arcanes"][path][0], d["arcanes"][path][1] or None
    names = I.names_for_path(path)
    return (re.sub(r"<[^>]*>\s*", "", names[0]).strip() if names else _words(path.rsplit("/", 1)[-1])), None


def shard(entry: dict) -> dict:
    """An Archon Shard of a Warframe: colour name, tauforged or not, and what it gives."""
    color = str(entry.get("Color", ""))
    base = color.replace("ACC_", "").replace("_MYTHIC", "")
    upgrade = str(entry.get("UpgradeType", "")).rsplit("/", 1)[-1]
    key = upgrade.replace("ArchonCrystalUpgrade", "").replace("Mythic", "")
    target = (re.match(r"^(Warframe|Melee|Primary|Secondary)", key) or [""])[0]
    key = re.sub(r"^(Warframe|Melee|Primary|Secondary)", "", key)
    return {"color": base, "color_name": SHARD_COLORS.get(base, base.title()), "tauforged": color.endswith("_MYTHIC"),
            "effect": SHARD_EFFECT.get(key) or _words(key) or upgrade, "key": key, "target": target}


def ability_name(path: str) -> str:
    d = data()
    if path in d["abilities"]:
        return d["abilities"][path]
    base = path.rsplit("/", 1)[-1]
    for cand in (base, re.sub(r"Ability$", "", base)):
        if cand in d["helminth"]:
            return d["helminth"][cand]
    return _words(re.sub(r"Ability$", "", base).replace("Helminth", "")) or base


def helminth(cfg: dict, suit_path: str):
    """The Helminth ability set on this loadout of a Warframe: {slot 1-4, replaced, ability} or None."""
    ov = cfg.get("AbilityOverride")
    if not isinstance(ov, dict) or not ov.get("Ability"):
        return None
    idx = int(ov.get("Index") or 0)
    own = (data()["suits"].get(suit_path) or [])
    replaced = ability_name(own[idx]) if 0 <= idx < len(own) else ""
    return {"slot": idx + 1, "replaced": replaced, "ability": ability_name(ov["Ability"])}


ELEMENTS = {"Heat": "Heat", "Freeze": "Cold", "Electricity": "Electricity", "Toxin": "Toxin", "Impact": "Impact",
            "Mag": "Magnetic", "Radiation": "Radiation", "Rad": "Radiation", "Puncture": "Puncture", "Slash": "Slash"}


def extras(item: dict) -> dict:
    """What else the game file says about an item: the name you gave it, the Focus lens, the Kuva / Tenet / Coda bonus
    element (25-60 %), the Exilus / Arcane slots unlocked, gilded, Valence Fusion."""
    out = {}
    nm = item.get("ItemName")
    if isinstance(nm, str) and nm.strip():
        out["custom"] = nm.split("|", 1)[1].strip() if "|" in nm else ("" if nm.startswith("/") else nm.strip())
    if item.get("FocusLens"):
        names = I.names_for_path(item["FocusLens"])
        out["lens"] = names[0] if names else _words(item["FocusLens"].rsplit("/", 1)[-1])
    try:
        fp = json.loads(item.get("UpgradeFingerprint") or "{}") if "InnateDamage" in str(item.get("UpgradeType") or "") else {}
    except ValueError:
        fp = {}
    for b in fp.get("buffs") or []:
        m = re.fullmatch(r"Innate(\w+?)Damage", str(b.get("Tag") or ""))
        if m:
            pct = 25 + 35 * min(1.0, max(0.0, int(b.get("Value") or 0) / 0x3FFFFFFF))
            out["valence"] = {"element": ELEMENTS.get(m.group(1), m.group(1)), "pct": round(pct, 1)}
    f = int(item.get("Features") or 0)
    out["exilus"], out["arcane_slot"], out["gilded"], out["valence_swap"] = bool(f & 2), bool(f & 32), bool(f & 8), bool(f & 1024)
    return out


def read(inv: dict, market=None) -> list:
    """[{"item","kind","config","forma","slots","shards","helminth"}] for every loadout with at least MIN_MODS mods.
    slots: [{"role": general|aura|exilus|stance|arcane, "name": str|"", "rank": int|None, "max": int|None}]"""
    from app.game import rivens as RV
    owned, rivens = {}, {}
    for u in inv.get("Upgrades") or []:
        oid = (u.get("ItemId") or {}).get("$oid")
        if oid and "/Randomized/" in str(u.get("ItemType", "")):
            try:
                rivens[oid] = RV.compute(u, partial=True)
            except ValueError:
                rivens[oid] = {"unrevealed": True}
        if oid:
            try:
                lvl = json.loads(u.get("UpgradeFingerprint") or "{}").get("lvl")
            except ValueError:
                lvl = None
            owned[oid] = (u.get("ItemType", ""), lvl)
    from app.game import buildcalc as BC
    from app.game import incarnon as INC
    evo, genesis = INC.index(inv, I.names_for_path)
    out = []
    for key, cat_kind in CATEGORIES:
        for item in inv.get(key) or []:
            kind = cat_kind                                    # (the claws in SpecialItems change it for themselves)
            path = item.get("ItemType", "")
            names = I.names_for_path(path)
            item_name = re.sub(r"<[^>]*>\s*", "", names[0] if names else path.rsplit("/", 1)[-1]).strip() or path
            roles = LAYOUT.get(kind)
            cfgs = item.get("Configs") if isinstance(item.get("Configs"), list) else []
            owner = ""
            if kind == "exalted" and not path.startswith("/Lotus/Powersuits/") and CLAWS.search(path):
                kind = "compweapon"                            # a Kubrow's / Kavat's claws: a companion weapon
                if not names:
                    item_name = "Claws"
                longest = max((len(c.get("Upgrades") or []) for c in cfgs if isinstance(c, dict)), default=8)
                roles = ["general"] * 8 + (["stance"] if longest >= 9 else [])     # the Posture mod, like a stance
            elif kind == "exalted":
                if not path.startswith("/Lotus/Powersuits/") or EXALTED_SKIP.search(path):
                    continue
                if not names:                                  # no name in the game data: from the path
                    item_name = _words(path.rsplit("/", 1)[-1])
                owner = exalted_owner(path)
                # melee ones have a stance slot (11 entries), ranged ones an Exilus and an Arcane (10), older ones 8 slots
                longest = max((len(c.get("Upgrades") or []) for c in cfgs if isinstance(c, dict)), default=8)
                roles = LAYOUT["melee"] if longest >= 11 else (LAYOUT["primary"] if longest == 10 else ["general"] * 8)
            reactor = bool((item.get("Features") or 0) & 1)
            # file: the game file says it is there; none: the file says it is not; unknown: not stated; guess: deduced from a build
            reactor_src = "file" if reactor else ("none" if "Features" in item else "unknown")
            level = _rank(item.get("XP"), 1000 if key in _FRAME_KINDS + ("SpecialItems",) and kind != "compweapon" else 500,
                          max_rank(item_name, kind))
            shards = [shard(a) for a in item.get("ArchonCrystalUpgrades") or [] if isinstance(a, dict)]
            first = len(out)
            for n, cfg in enumerate(cfgs):
                if not isinstance(cfg, dict):
                    continue
                refs = list(cfg.get("Upgrades") or [])
                size = len(roles) if roles else max(8, len(refs))
                refs += [""] * (size - len(refs))
                slots, filled = [], 0
                for i, ref in enumerate(refs[:size]):
                    role = roles[i] if roles else "general"
                    if not ref:
                        slots.append({"role": role, "name": "", "rank": None, "max": None})
                        continue
                    mod_path, lvl = (ref, 0) if str(ref).startswith("/") else owned.get(ref, ("", None))   # a path = an unranked copy
                    if not mod_path:
                        slots.append({"role": role, "name": "", "rank": None, "max": None})
                        continue
                    rv = rivens.get(ref)
                    if rv and rv.get("unrevealed"):
                        slots.append({"role": role, "name": "Riven", "rank": lvl, "max": 8, "riven": {"unrevealed": True}})
                        filled += role != "arcane"
                        continue
                    if rv:
                        slots.append({"role": role, "name": rv["mod_name"] if rv.get("spliced") else rv["mod_name"] + " (Riven)", "rank": rv["rank"], "max": 8, "riven": rv})
                        filled += role != "arcane"
                        continue
                    name, mx = mod_name(mod_path)
                    slots.append({"role": role, "name": name, "rank": lvl, "max": mx})
                    if role != "arcane":
                        filled += 1
                if filled < MIN_MODS:
                    continue
                roles = [s["role"] for s in slots]
                mods = [((s["name"], s["rank"], s["riven"]) if s.get("riven") and not s["riven"].get("unrevealed") else (s["name"], s["rank"]))
                        if s["name"] else None for s in slots]
                pols = BC.fitted_polarities(kind, item_name, roles, item.get("Polarity"), mods)
                calc = BC.evaluate(kind, item_name, roles, mods, pols, reactor, level,
                                       shards=shards if kind == "warframe" else None)
                if not reactor and "Features" not in item and calc["free"] < 0:
                    # older items do not say whether a Reactor / Catalyst is installed; a build that only fits with one has it
                    reactor, reactor_src = True, "guess"
                    calc = BC.evaluate(kind, item_name, roles, mods, pols, reactor, level,
                                       shards=shards if kind == "warframe" else None)
                formaed = set()
                for f in item.get("Polarity") or []:
                    try:
                        formaed.add(int(f.get("Slot")))
                    except (TypeError, ValueError, AttributeError):
                        pass
                for i, (s, c) in enumerate(zip(slots, calc["slots"])):
                    # where the slot's polarity comes from (the capacity details): the file's Forma, or the item's own
                    s.update(pol=c["pol"], mpol=c["mpol"], drain=c["drain"], state=c["state"],
                             pol_src=("forma" if i in formaed else "innate") if c["pol"] else "")
                cname = str(cfg.get("Name") or "").strip()
                out.append({"item": item_name, "kind": kind, "path": path, "config": LETTERS[n] if n < 8 else str(n + 1),
                            "cfg_name": cname, "owner": owner, "reactor": reactor, "level": level,
                            "capacity": ({k: calc[k] for k in ("total", "used", "free")} if kind != "exalted" else None), "stats": calc["stats"], "bonus": calc["bonus"],
                            "elements": calc.get("elements") or [], "flat": calc.get("flat") or {},
                            # what the game file says, as read (Builds: "Copy data for a capacity check")
                            "raw": {"ItemType": path, "XP": item.get("XP"), "Features": item.get("Features"),
                                    "Polarized": item.get("Polarized"), "Polarity": item.get("Polarity"),
                                    "Upgrades": [[(owned.get(r) or (r, None))[0] if r and not str(r).startswith("/") else r,
                                                  (owned.get(r) or (None, None))[1]] for r in refs[:len(roles)]]},
                            "oid": (item.get("ItemId") or {}).get("$oid", ""), "idx": n,
                            "forma": int(item.get("Polarized") or 0), "slots": slots,
                            "shards": shards if kind == "warframe" else [],
                            "helminth": helminth(cfg, path) if kind == "warframe" else None,
                            "incarnon": INC.info(item, item_name, evo, genesis) if kind in ("primary", "secondary", "melee") else None,
                            "extras": extras(item)})
            sib = [{"idx": b["idx"], "config": b["config"], "name": b["cfg_name"]} for b in out[first:]]
            for b in out[first:]:
                b["configs"] = sib
                if reactor and not b["reactor"]:          # deduced from a later configuration: it is the same item
                    b["capacity"]["total"] += b["level"]
                    b["capacity"]["free"] += b["level"]
                b["reactor"], b["reactor_src"] = reactor, reactor_src
    out.sort(key=lambda b: (b["item"].lower(), b["config"]))
    return out


_owners = {}


def exalted_owner(path: str) -> str:
    """The Warframe an exalted weapon belongs to (from the folder its game path shares with the Warframe's own)."""
    folder = path.rsplit("/", 1)[0] + "/"
    if not _owners:
        for suit in data().get("suits", {}):
            names = I.names_for_path(suit)
            if names:
                n = re.sub(r"<[^>]*>\s*", "", names[0]).strip()
                f = suit.rsplit("/", 1)[0] + "/"
                if f not in _owners or len(n) < len(_owners[f]):    # the base Warframe (shorter than "… Prime")
                    _owners[f] = n
    return _owners.get(folder, "")


def _load(path):
    raw = Path(path).read_bytes()
    text = I.decrypt_last_data(raw) if str(path).lower().endswith(".dat") else I.unwrap_inventory(raw.decode("utf-8-sig"))
    return json.loads(text)


def read_file(path, market=None) -> list:
    return read(_load(path))


# ---------- the in-game loadout screen: named loadouts with Warframe, weapons, companion, Archwing, Necramech ----------
# rank 30 needs this much XP per rank squared: 1000 for Warframes, companions, Archwings, Necramechs; 500 for weapons
_FRAME_KINDS = ("Suits", "SpaceSuits", "MechSuits", "Sentinels", "KubrowPets", "MoaPets", "HoundPets", "Pets", "CrewShipHarness")


def max_rank(name: str, kind: str = "") -> int:
    """Kuva, Tenet and Coda weapons and Necramechs go up to rank 40, everything else to 30."""
    return 40 if kind == "necramech" or name.startswith(("Kuva ", "Tenet ", "Coda ", "Dual Coda ")) else 30


def _rank(xp, per, cap=30) -> int:
    try:
        return min(cap, int((max(0, float(xp)) / per) ** 0.5))
    except (TypeError, ValueError):
        return 0


def _row(role, ref, owned):
    """One slot of a preset: the owned item the preset points to ({"role","item","rank","maxed","oid","idx"} or None)."""
    if not isinstance(ref, dict):
        return None
    oid = (ref.get("ItemId") or {}).get("$oid")
    hit = owned.get(oid)
    if not hit:
        return None
    sect, it = hit
    path = it.get("ItemType", "")
    names = I.names_for_path(path)
    name = re.sub(r"<[^>]*>\s*", "", names[0] if names else path.rsplit("/", 1)[-1]).strip() or path
    if not names and CLAWS.search(path):        # a beast companion's own claws: no name in the data
        name = "Claws"
    rk = _rank(it.get("XP"), 1000 if sect in _FRAME_KINDS else 500)
    custom = ""
    if isinstance(it.get("ItemName"), str) and "|" in it["ItemName"]:      # a name you gave it, or a Kuva/Tenet weapon's own
        custom = it["ItemName"].split("|", 1)[1].strip()
    if isinstance(it.get("Details"), dict) and it["Details"].get("Name"):    # a companion's name
        custom = str(it["Details"]["Name"])
    return {"role": role, "item": name, "custom": custom, "path": path, "rank": rk, "maxed": rk >= 30, "oid": oid,
            "idx": int(ref.get("mod") or 0)}


def presets(inv: dict) -> dict:
    """The loadouts as the game shows them: {"presets": [{"name","favorite","warframe":[rows],"companion":[rows]}],
    "tenno": {"archwing": [rows], "necramech": [rows]}}. Rows come from LoadOutPresets (see _row): the items are looked up
    among the owned ones by id; "idx" is the mod configuration (A=0, B=1...) the preset uses for that item."""
    owned = {}
    for sect, lst in inv.items():
        if isinstance(lst, list):
            for it in lst:
                if isinstance(it, dict) and isinstance((it.get("ItemId") or {}).get("$oid"), str):
                    owned[it["ItemId"]["$oid"]] = (sect, it)
    lp = inv.get("LoadOutPresets") if isinstance(inv.get("LoadOutPresets"), dict) else {}

    def rows(entry, spec):
        out = []
        for key, role in spec:
            r = _row(role, (entry or {}).get(key), owned)
            if r:
                out.append(r)
        return out
    normal, sentinel = lp.get("NORMAL") or [], lp.get("SENTINEL") or []
    out = []
    for i, e in enumerate(normal):
        wf = rows(e, (("s", "warframe"), ("l", "primary"), ("p", "secondary"), ("m", "melee"), ("a", "exalted")))
        if not wf or wf[0]["role"] != "warframe":
            continue
        name = e.get("n") or ""
        if not name or name.startswith("/"):                  # unnamed, or a bundle's language key
            name = wf[0]["item"] + " Loadout"
        se = sentinel[i] if i < len(sentinel) else None
        comp = rows(se, (("s", "companion"),))
        if comp:
            # the companion's weapon: a Sentinel or a MOA uses the robotic weapon ("l"); a Kubrow, Kavat, Vulpaphyla,
            # Predasite… its own claws ("b"). The preset keeps both, so "l" alone showed the same Sentinel weapon for
            # every companion.
            sect = owned.get(comp[0]["oid"], ("", {}))[0]
            key = "l" if sect in ("Sentinels", "MoaPets") else "b"
            comp += rows(se, ((key, "companion_weapon"),))
        out.append({"name": name, "favorite": bool(e.get("Favorite")), "warframe": wf, "companion": comp})
    tenno = {"archwing": rows((lp.get("ARCHWING") or [None])[0], (("s", "archwing"), ("l", "archgun"), ("m", "archmelee"))),
             "necramech": rows((lp.get("MECH") or [None])[0], (("s", "necramech"), ("h", "archgun"), ("a", "necramech_weapon")))}
    return {"presets": out, "tenno": tenno}


def owned_mods(inv: dict) -> dict:
    """Mods and Arcanes you own: {name: {"n": copies, "rank": highest rank among them}} (Upgrades: ranked copies, one
    entry each; RawUpgrades: unranked copies, counted). Rivens are left out (they are not picked by name)."""
    out = {}
    for u in inv.get("Upgrades") or []:
        path = str(u.get("ItemType") or "") if isinstance(u, dict) else ""
        if not path or "/Randomized/" in path:
            continue
        try:
            lvl = int(json.loads(u.get("UpgradeFingerprint") or "{}").get("lvl") or 0)
        except (ValueError, TypeError, AttributeError):
            lvl = 0
        name = mod_name(path)[0]
        e = out.setdefault(name, {"n": 0, "rank": 0})
        e["n"] += 1
        e["rank"] = max(e["rank"], lvl)
    for u in inv.get("RawUpgrades") or []:
        path = str(u.get("ItemType") or "") if isinstance(u, dict) else ""
        if not path or "/Randomized/" in path:
            continue
        name = mod_name(path)[0]
        e = out.setdefault(name, {"n": 0, "rank": 0})
        e["n"] += int(u.get("ItemCount") or 1)
    return out


def read_all_file(path) -> dict:
    """Everything the Builds tab shows: {"loadouts": read(), "presets": presets(), "owned": owned_mods()}."""
    inv = _load(path)
    return {"loadouts": read(inv), "presets": presets(inv), "owned": owned_mods(inv)}
