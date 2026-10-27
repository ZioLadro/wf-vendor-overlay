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

import inventory as I

DATA_FILE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "loadout_data.json"
CATEGORIES = (("Suits", "warframe"), ("LongGuns", "primary"), ("Pistols", "secondary"), ("Melee", "melee"),
              ("SpaceSuits", "archwing"), ("SpaceGuns", "archgun"), ("MechSuits", "necramech"),
              ("Sentinels", "companion"), ("KubrowPets", "companion"), ("MoaPets", "companion"),
              ("SentinelWeapons", "companion"))
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
    key = re.sub(r"^(Warframe|Melee|Primary|Secondary)", "", key)
    return {"color": base, "color_name": SHARD_COLORS.get(base, base.title()), "tauforged": color.endswith("_MYTHIC"),
            "effect": SHARD_EFFECT.get(key) or _words(key) or upgrade}


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


def read(inv: dict, market=None) -> list:
    """[{"item","kind","config","forma","slots","shards","helminth"}] for every loadout with at least MIN_MODS mods.
    slots: [{"role": general|aura|exilus|stance|arcane, "name": str|"", "rank": int|None, "max": int|None}]"""
    owned = {}
    for u in inv.get("Upgrades") or []:
        oid = (u.get("ItemId") or {}).get("$oid")
        if oid:
            try:
                lvl = json.loads(u.get("UpgradeFingerprint") or "{}").get("lvl")
            except ValueError:
                lvl = None
            owned[oid] = (u.get("ItemType", ""), lvl)
    out = []
    for key, kind in CATEGORIES:
        for item in inv.get(key) or []:
            path = item.get("ItemType", "")
            names = I.names_for_path(path)
            item_name = re.sub(r"<[^>]*>\s*", "", names[0] if names else path.rsplit("/", 1)[-1]).strip() or path
            roles = LAYOUT.get(kind)
            shards = [shard(a) for a in item.get("ArchonCrystalUpgrades") or [] if isinstance(a, dict)]
            for n, cfg in enumerate(item.get("Configs") if isinstance(item.get("Configs"), list) else []):
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
                    mod_path, lvl = (ref, None) if str(ref).startswith("/") else owned.get(ref, ("", None))
                    if not mod_path:
                        slots.append({"role": role, "name": "", "rank": None, "max": None})
                        continue
                    name, mx = mod_name(mod_path)
                    slots.append({"role": role, "name": name, "rank": lvl, "max": mx})
                    if role != "arcane":
                        filled += 1
                if filled < MIN_MODS:
                    continue
                out.append({"item": item_name, "kind": kind, "path": path, "config": LETTERS[n] if n < 8 else str(n + 1),
                            "forma": int(item.get("Polarized") or 0), "slots": slots,
                            "shards": shards if kind == "warframe" else [],
                            "helminth": helminth(cfg, path) if kind == "warframe" else None})
    out.sort(key=lambda b: (b["item"].lower(), b["config"]))
    return out


def read_file(path, market=None) -> list:
    raw = Path(path).read_bytes()
    text = I.decrypt_last_data(raw) if str(path).lower().endswith(".dat") else I.unwrap_inventory(raw.decode("utf-8-sig"))
    return read(json.loads(text))
