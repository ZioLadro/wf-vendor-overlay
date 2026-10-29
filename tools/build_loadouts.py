#!/usr/bin/env python3
"""Generates loadout_data.json: names the loadout view needs (from the public game data export).

Source: https://github.com/calamity-inc/warframe-public-export-plus (converted official game data).
Usage:  python tools/build_loadouts.py [--out data/loadout_data.json] [--cache download_folder]
  mods:      mod path -> [English name, max rank]
  rarity:    English mod name -> C/U/R/L (for the Endo cost of ranking a mod up)
  arcanes:   arcane path -> [English name, max rank]
  arcrar:    English Arcane name -> C/U/R/L (which generic picture it gets)
  abilities: ability path -> English name (every Warframe's abilities)
  suits:     Warframe path -> [its 4 ability paths, in order]
  helminth:  generic Helminth ability path -> English name
With --wfcd <folder of WFCD/warframe-items data/json> it also writes (used for polarity, drain, capacity and stats):
  mst:       mod name -> [polarity, base drain, max rank, compatibility, type, {stat: value at max rank}, Exilus (1/0)]
             (Warframe mods: stat keys; weapon mods: labels)
  frames:    Warframe name -> [health, shield, armor, energy, sprint speed (rank 30), aura polarity, [innate polarities],
             Exilus polarity]
  weapons:   weapon name -> [kind, type, [innate polarities], exilus polarity, stance polarity]
             (kind "compweapon": Sentinel / MOA / Hound weapons, and "Claws" for the beasts)
  wstats:    weapon name -> {"cc","cd","sc","fr","dmg": {type: value}, guns: "ms","mag","rl","acc","trig",
             melee: "rng","cdur","ft","slam","slide","heavy"} (base stats at rank 30, the build planner's stat recap)
  incarnon:  {"genesis": [weapon families with an Incarnon Genesis], "builtin": [weapons with Incarnon built in]}
  arc:       Arcane name -> type
  mtext:     mod / Arcane name -> [effect at rank 0, effect at max rank] (tooltips; the wiki's text is preferred)
"""
import argparse
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from build_vendors import fetch


STAT_KEYS = {"Health": "health", "Shield Capacity": "shield", "Armor": "armor", "Energy Max": "energy",
             "Sprint Speed": "sprint", "Ability Duration": "duration", "Ability Efficiency": "efficiency",
             "Ability Range": "range", "Ability Strength": "strength"}
MOD_TYPES = {"Warframe Mod": "W", "Primary Mod": "P", "Shotgun Mod": "G", "Secondary Mod": "S", "Melee Mod": "M",
             "Stance Mod": "T", "Companion Mod": "C", "Archwing Mod": "A", "Arch-Gun Mod": "R", "Arch-Melee Mod": "X",
             "Posture Mod": "Y", "Necramech Mod": "N"}


DT_NAMES = {"FIRE": "Heat", "FREEZE": "Cold", "ELECTRICITY": "Electricity", "POISON": "Toxin", "EXPLOSION": "Blast",
            "IMPACT": "Impact", "PUNCTURE": "Puncture", "SLASH": "Slash", "RADIATION": "Radiation", "VIRAL": "Viral",
            "CORROSIVE": "Corrosive", "GAS": "Gas", "MAGNETIC": "Magnetic", "TAU": "Tau", "VOID": "Void"}


def _plain(line: str) -> str:
    """A stat line without markup; the damage-type tags become their names ("<DT_SLASH_COLOR>" -> "Slash")."""
    s = str(line)

    def name(m):                                         # the tag alone ("apply <DT_SLASH_COLOR> on") -> its name;
        word = DT_NAMES.get(m.group(1), m.group(1).title())          # a tag before the name itself -> nothing
        return "" if s[m.end():].lstrip().lower().startswith(word.lower()) else word + " "
    s = re.sub(r"<DT_([A-Z]+?)(?:_COLOR)?>", name, s)
    return re.sub(r"\s{2,}", " ", re.sub(r"<[^>]+>", "", s))


def _stat_text(level: dict) -> str:
    """One rank's effect as text: its lines without markup, the "+1 Arcane Revive" note and repeated lines left out."""
    out = []
    for line in level.get("stats") or []:
        for part in _plain(line).replace("\\n", "\n").split("\n"):
            part = part.strip()
            if part and part not in out and not re.fullmatch(r"\+\d+ Arcane Revives?", part):
                out.append(part)
    return "\n".join(out)


DE_POL = {"AP_ATTACK": "madurai", "AP_DEFENSE": "vazarin", "AP_TACTIC": "naramon", "AP_POWER": "zenurik",
          "AP_WARD": "unairu", "AP_UMBRA": "umbra", "AP_PRECEPT": "penjaga", "AP_ANY": "universal"}   # AP_UNIVERSAL: kept as WFCD has it
DE_SKIP_TYPES = ("PARAZON", "---", "HELMINTH CHARGER", None)          # Parazon, K-Drive and Helminth "mods": no slots here


def _de_kind(u: dict) -> str:
    """The mst type letter of a mod from DE's export (its type and what it fits)."""
    t, c = u.get("type"), (u.get("compatName") or "")
    if t in ("WARFRAME", "AURA"):
        return "N" if c.lower() == "necramech" else "W"
    if t == "PRIMARY":
        return "G" if c.lower() == "shotgun" else "P"
    if t == "STANCE":
        return "Y" if c == "Claws" else "T"
    if t == "MELEE" and c == "Claws":
        return "C"
    return {"SECONDARY": "S", "MELEE": "M", "SENTINEL": "C", "KAVAT": "C", "KUBROW": "C", "ARCHWING": "A",
            "ARCH-GUN": "R", "ARCH-MELEE": "X"}.get(t, "")


def de_mods(upgrades: dict, nm) -> dict:
    """name -> the game's own [polarity, base drain, max rank, compatibility, type, exilus] from DE's export: the real mod
    of each name (not the Beginner / starter copy, not the left-over "frivolous" one). Polarity, drain and rank come from
    here, so they are the game's (WFCD sometimes keeps a starter copy's numbers: Quick Thinking 4 / 3 instead of 10 / 5)."""
    out, pri_of = {}, {}
    for path, u in upgrades.items():
        if not isinstance(u, dict) or u.get("type") in DE_SKIP_TYPES or "baseDrain" not in u:
            continue
        name = nm(u.get("name", ""))
        kind = _de_kind(u)
        if not name or not kind or "/CosmeticEnhancers/" in path and u.get("type") not in ("WARFRAME",):
            continue
        pri = (0 if u.get("isStarter") else 1, 0 if u.get("isFrivolous") else 1,
               0 if re.search(r"/(Beginner|Expert|Intermediate)/", path) else 1, 0 if u.get("excludeFromCodex") else 1,
               int(u.get("fusionLimit") or 0))
        if name in out and pri_of[name] >= pri:
            continue
        pri_of[name] = pri
        out[name] = [DE_POL.get(u.get("polarity"), ""), int(u["baseDrain"]), int(u.get("fusionLimit") or 0),
                     u.get("compatName") or "", kind, 1 if u.get("isUtility") else 0]
    return out


def wfcd(folder: Path, skip=frozenset()) -> dict:
    """Polarity, drain and stats from the community-maintained WFCD/warframe-items data. skip: paths of mods the game keeps
    only as starter / left-over copies (their stats are not the real mod's)."""
    def load(name):
        return json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    mst, mtext, pri_of = {}, {}, {}
    # a starter / left-over copy is only skipped when the same name has another entry (else it is all there is)
    others = {m.get("name") for m in load("Mods") if m.get("uniqueName") not in skip}
    skip = {p for p in skip}
    for m in load("Mods"):
        kind = MOD_TYPES.get(m.get("type"))
        name = m.get("name")
        if not kind or not name or "baseDrain" not in m or (m.get("uniqueName") in skip and name in others):
            continue
        lim = int(m.get("fusionLimit") or 0)
        # several mods share a name (Vital Sense: the normal one, a Beginner and an Expert variant): the normal one wins,
        # then the highest rank
        pri = (0 if re.search(r"/(Beginner|Expert|Intermediate)/", str(m.get("uniqueName") or "")) else 1, lim)
        if name in mst and pri_of.get(name, (0, 0)) >= pri:
            continue
        pri_of[name] = pri
        stats = {}
        levels = m.get("levelStats") or []
        if kind == "W" and levels:
            for line in levels[-1].get("stats", []):
                hit = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)%\s*([A-Za-z ]+)", line.strip())
                if hit and hit.group(3).strip() in STAT_KEYS:
                    key = STAT_KEYS[hit.group(3).strip()]
                    stats[key] = round(stats.get(key, 0) + (1 if hit.group(1) == "+" else -1) * float(hit.group(2)) / 100, 4)
        if kind in "PGSM" and levels:                    # weapon mods: percentage stats by (plain) label, for the bonus recap
            for line in levels[-1].get("stats", []):
                hit = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)%\s*(.+)", _plain(line).strip())
                if hit:
                    label = re.sub(r"\s*\(.*?\)", "", hit.group(3)).strip()
                    stats[label] = round(stats.get(label, 0) + (1 if hit.group(1) == "+" else -1) * float(hit.group(2)) / 100, 4)
                    continue
                hit = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)\s+(Range)", _plain(line).strip())
                if hit:                                  # a flat value: Primed Reach "+3 Range" (metres)
                    key = hit.group(3) + " (flat)"
                    stats[key] = round(stats.get(key, 0) + (1 if hit.group(1) == "+" else -1) * float(hit.group(2)), 4)
        mst[name] = [m.get("polarity") or "", int(m["baseDrain"]), lim, m.get("compatName") or "", kind, stats,
                     1 if m.get("isUtility") else 0]
        if levels:
            mtext[name] = [_stat_text(levels[0]), _stat_text(levels[-1])]
    frames = {}
    for w in load("Warframes"):
        if w.get("type") == "Warframe" and w.get("name"):
            frames[w["name"]] = [w.get("health", 0), w.get("shield", 0), w.get("armor", 0), w.get("power", 0),
                                 w.get("sprintSpeed", 1), w.get("aura") or "", w.get("polarities") or [],
                                 w.get("exilusPolarity") or ""]
    companions = {}                     # name -> [family: sentinel / beast / robotic, polarities]
    for c in load("Sentinels"):
        if c.get("name") and c.get("type") == "Sentinel":
            companions[c["name"]] = ["sentinel", c.get("polarities") or []]
    for c in load("Pets"):
        if c.get("name") and c.get("type") == "Pets":
            fam = "robotic" if re.search(r"Moa|Hound", c["name"]) else "beast"
            companions[c["name"]] = [fam, c.get("polarities") or []]
    archwings = {a["name"]: a.get("polarities") or [] for a in load("Archwing") if a.get("name") and a.get("type") == "Archwing"}
    weapons = {}
    for fn, kind in (("Primary", "primary"), ("Secondary", "secondary"), ("Melee", "melee"), ("Arch-Gun", "archgun"),
                     ("Arch-Melee", "archmelee")):
        for w in load(fn):
            if w.get("name") and w.get("type") not in ("Zaw Component",):
                weapons[w["name"]] = [kind, w.get("type") or "", w.get("polarities") or [], w.get("exilusPolarity") or "",
                                      w.get("stancePolarity") or ""]
    for w in load("SentinelWeapons"):                 # companions' weapons: robotic ones by name, beasts' claws as one
        if w.get("name"):
            weapons[w["name"]] = ["compweapon", "Robotic", w.get("polarities") or [], "", ""]
    # beasts' claws: no public data has their slots; the game shows an innate Penjaga on the Posture slot and one
    # Madurai slot (checked on Panzer Vulpaphyla and Predasite claws: 2/70 with 2 Forma, 5/70 with 3)
    weapons["Claws"] = ["compweapon", "Claws", ["madurai"], "", "penjaga"]
    r4 = lambda v: round(float(v), 4) if isinstance(v, (int, float)) else None
    wstats = {}
    for fn in ("Primary", "Secondary", "Melee", "Arch-Gun", "Arch-Melee", "SentinelWeapons"):
        for w in load(fn):
            if not w.get("name") or w["name"] not in weapons:
                continue
            dmg = {k: r4(v) for k, v in (w.get("damage") or {}).items() if k != "total" and isinstance(v, (int, float)) and v}
            st = {"cc": r4(w.get("criticalChance")), "cd": r4(w.get("criticalMultiplier")), "sc": r4(w.get("procChance")),
                  "fr": r4(w.get("fireRate")), "dmg": dmg}
            if fn in ("Melee", "Arch-Melee"):
                st.update(rng=r4(w.get("range")), cdur=r4(w.get("comboDuration")), ft=r4(w.get("followThrough")),
                          slam=r4(w.get("slamAttack")), slide=r4(w.get("slideAttack")), heavy=r4(w.get("heavyAttackDamage")))
            else:
                st.update(ms=r4(w.get("multishot")), mag=w.get("magazineSize"), rl=r4(w.get("reloadTime")),
                          acc=r4(w.get("accuracy")), trig=w.get("trigger") or "")
            wstats[w["name"]] = {k: v for k, v in st.items() if v not in (None, "", {})}
    builtin = sorted(w["name"] for fn in ("Primary", "Secondary", "Melee") for w in load(fn)
                     if w.get("name") and "Incarnon" in (w.get("tags") or []))
    arc = {a["name"]: a.get("type", "") for a in load("Arcanes") if a.get("name")}
    for a in load("Arcanes"):
        if a.get("name") and a.get("levelStats"):
            mtext[a["name"]] = [_stat_text(a["levelStats"][0]), _stat_text(a["levelStats"][-1])]
    return {"mtext": mtext, "mst": mst, "frames": frames, "weapons": weapons, "arc": arc, "companions": companions, "archwings": archwings,
            "wstats": wstats, "incarnon_builtin": builtin}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "loadout_data.json"))
    ap.add_argument("--wfcd", default="", help="folder with the WFCD/warframe-items data/json files")
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    lang = fetch("dict.en", cache)
    nm = lambda key: re.sub(r"<[^>]+>\s*", "", lang.get(key, "")).strip()
    mods, arcanes, abilities, suits, rarity, best, arcrar = {}, {}, {}, {}, {}, {}, {}
    for path, u in fetch("ExportUpgrades", cache).items():
        if isinstance(u, dict) and nm(u.get("name", "")):
            mods[path] = [nm(u["name"]), int(u.get("fusionLimit") or 0)]
            r = {"COMMON": "C", "UNCOMMON": "U", "RARE": "R", "LEGENDARY": "L"}.get(u.get("rarity"))
            lim = int(u.get("fusionLimit") or 0)
            if r and lim > 0 and lim >= best.get(nm(u["name"]), 0):          # same name, several versions: the full-rank one
                best[nm(u["name"])] = lim
                rarity[nm(u["name"])] = r
    for path, u in fetch("ExportArcanes", cache).items():
        if isinstance(u, dict) and nm(u.get("name", "")):
            arcanes[path] = [nm(u["name"]), int(u.get("fusionLimit") or 0)]
            r = {"COMMON": "C", "UNCOMMON": "U", "RARE": "R", "LEGENDARY": "L"}.get(u.get("rarity"))
            if r:
                arcrar[nm(u["name"])] = r
    for path, w in fetch("ExportWarframes", cache).items():
        ab = [x for x in (w.get("abilities") or []) if isinstance(x, dict) and x.get("uniqueName")]
        if len(ab) >= 4 and w.get("productCategory") == "Suits":
            suits[path] = [x["uniqueName"] for x in ab[:4]]
        for x in ab:
            if nm(x.get("name", "")):
                abilities[x["uniqueName"]] = nm(x["name"])
    helminth = {}
    for key, val in lang.items():
        m = re.fullmatch(r"/Lotus/Language/Suits/(Helminth\w+)Name", key)
        if m and val:
            helminth[m.group(1)] = nm(key)
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "source": "calamity-inc/warframe-public-export-plus", "mods": mods, "rarity": rarity, "arcrar": arcrar, "arcanes": arcanes,
           "abilities": abilities, "suits": suits, "helminth": helminth}
    genesis = sorted({re.sub(r"\s+Incarnon Genesis$", "", nm(k)) for k in lang
                      if re.fullmatch(r"[\w&' -]+ Incarnon Genesis", nm(k))})
    if a.wfcd:
        upg = fetch("ExportUpgrades", cache)
        out.update(wfcd(Path(a.wfcd), skip=frozenset(p for p, u in upg.items() if isinstance(u, dict)
                                                       and (u.get("isStarter") or u.get("isFrivolous")))))
        out["source"] += " + WFCD/warframe-items"
        # polarity, drain and max rank as the game has them; mods WFCD does not list are added (no stats for the recap)
        fixed, added = 0, 0
        for name, (pol, base, lim, compat, kind, util) in de_mods(upg, nm).items():
            row = out["mst"].get(name)
            if row is None:
                out["mst"][name] = [pol, base, lim, compat, kind, {}, util]
                added += 1
            elif row[:3] != [pol or row[0], base, lim]:
                row[0], row[1], row[2] = pol or row[0], base, lim
                row[6] = row[6] or util
                fixed += 1
        print(f"mods: {fixed} corrected from the game's export, {added} added")
        out["incarnon"] = {"genesis": genesis, "builtin": out.pop("incarnon_builtin")}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(mods)} mods, {len(arcanes)} arcanes, {len(abilities)} abilities, {len(suits)} warframes -> {a.out}")


if __name__ == "__main__":
    main()
