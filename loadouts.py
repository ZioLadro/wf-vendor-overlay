"""Your own in-game loadouts (the mods you have equipped), read from the AlecaFrame inventory file.

Every Warframe, weapon, Archwing and companion keeps up to 8 loadouts ("configs"). Each lists the equipped mods, as
a game path or as the id of one of your mods; both are turned into mod names here. This is the most reliable way
to get a build into the Builds tab: it comes from the game data, not from a web page.
"""
import json
import re
from pathlib import Path

import inventory as I

CATEGORIES = (("Suits", "warframe"), ("LongGuns", "primary"), ("Pistols", "secondary"), ("Melee", "melee"),
              ("SpaceSuits", "archwing"), ("SpaceGuns", "archgun"), ("SpecialItems", "other"),
              ("KubrowPets", "companion"), ("MoaPets", "companion"), ("Sentinels", "companion"),
              ("SentinelWeapons", "companion"), ("Hoverboards", "other"), ("OperatorAmps", "other"),
              ("MechSuits", "necramech"), ("CrewShipHarnesses", "other"))
LETTERS = "ABCDEFGH"
MIN_MODS = 3                          # a loadout with fewer mods than this is not a build


def _configs(item):
    c = item.get("Configs")
    return c if isinstance(c, list) else []


def read(inv: dict, market) -> list:
    """[{"item", "kind", "config", "mods": [(slug | None, name)]}] for every loadout with at least MIN_MODS mods."""
    by_id = {}
    for u in inv.get("Upgrades") or []:
        oid = (u.get("ItemId") or {}).get("$oid")
        if oid:
            by_id[oid] = u.get("ItemType", "")
    out = []
    for key, kind in CATEGORIES:
        for item in inv.get(key) or []:
            path = item.get("ItemType", "")
            names = I.names_for_path(path)
            item_name = re.sub(r"<[^>]*>\s*", "", names[0] if names else path.rsplit("/", 1)[-1]).strip() or path
            for n, cfg in enumerate(_configs(item)):
                if not isinstance(cfg, dict):
                    continue
                mods, seen = [], set()
                for ref in cfg.get("Upgrades") or []:
                    if not ref:
                        continue
                    mod_path = ref if str(ref).startswith("/") else by_id.get(ref, "")
                    if not mod_path or mod_path in seen:
                        continue
                    seen.add(mod_path)
                    nm = I.names_for_path(mod_path)
                    name = nm[0] if nm else ""
                    if not name:
                        continue
                    slug = I.resolve(market, name)
                    mods.append((slug, market.info(slug).get("name", name) if slug else name))
                if len(mods) >= MIN_MODS:
                    out.append({"item": item_name, "kind": kind, "config": LETTERS[n] if n < len(LETTERS) else str(n + 1),
                                "mods": mods})
    out.sort(key=lambda b: (b["item"].lower(), b["config"]))
    return out


def read_file(path, market) -> list:
    raw = Path(path).read_bytes()
    text = I.decrypt_last_data(raw) if str(path).lower().endswith(".dat") else I.unwrap_inventory(raw.decode("utf-8-sig"))
    return read(json.loads(text), market)
