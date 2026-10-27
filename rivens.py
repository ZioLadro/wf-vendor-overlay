"""Revealed rivens from your inventory (AlecaFrame's lastData.dat), turned into what Quantframe's stock needs.

A revealed riven is an upgrade of type .../Lotus*RandomModRare whose fingerprint names a weapon ("compat"), a rank
("lvl"), re-rolls, a polarity and the rolled stats ("buffs" / "curses": a stat tag and a raw roll number).
(Unrevealed rivens have no weapon yet: they are ignored.)

Stat value as shown in game, at rank r:
    base(tag) x 90 x weapon disposition x M x (0.9 + roll / 53687091 / 100, kept in 0.9..1.1)  x (r + 1) / 9
  x 100 for percentages; the faction-damage stats add 1 (they are multipliers, "x1.4").
  M depends on how many positive / negative stats the riven has (the published riven table):
  2+0: 0.99 | 2+1: 1.2375 (+) and 0.495 (-) | 3+0: 0.75 | 3+1: 0.9375 (+) and 0.75 (-).
The base values, dispositions, prefixes and suffixes come from the game data (rivens.json, build_rivens.py).
"""
import json
import math
import sys
import time
from pathlib import Path

from config import APP_DIR

BUNDLED = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "rivens.json"
USER_FILE = APP_DIR / "rivens.json"
ATTR_CACHE = APP_DIR / "riven_attributes.json"
SENT_FILE = APP_DIR / "riven_sent.json"
DENOM = 53687091.0
MULT = {(2, 0): (0.99, 0.0), (2, 1): (1.2375, -0.495), (3, 0): (0.75, 0.0), (3, 1): (0.9375, -0.75)}
TWO_DIGIT = ("FactionDamageGrineer", "FactionDamageCorpus", "FactionDamageInfested")
POLARITY = {"AP_ATTACK": "madurai", "AP_DEFENSE": "vazarin", "AP_TACTIC": "naramon", "AP_UNIVERSAL": "universal",
            "AP_UMBRA": "umbra", "AP_WARD": "unairu", "AP_POWER": "zenurik", "AP_PRECEPT": "penjaga",
            "AP_ANY": "any"}
WEAPON_FIX = {"/Lotus/Weapons/Tenno/Melee/Dagger/DarkDaggerBase": "/Lotus/Weapons/Tenno/Melee/Dagger/DarkDagger",
              "/Lotus/Weapons/Tenno/Shotgun/QuadShotgunBase": "/Lotus/Weapons/Tenno/Shotgun/QuadShotgun"}

_data = None


def data() -> dict:
    global _data
    if _data is None:
        _data = {"weapons": {}, "types": {}}
        for f in (BUNDLED, USER_FILE):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                for k in _data:
                    _data[k].update(d.get(k) or {})
            except Exception:
                pass
    return _data


def _round_half_away(x: float) -> float:
    return math.copysign(math.floor(abs(x) + 0.5), x)


def fmt(v: float) -> float:
    r = _round_half_away(v * 10) / 10
    return float(round(r)) if abs(r - round(r)) < 0.05 else r


def is_revealed(item: dict) -> bool:
    t = item.get("ItemType", "")
    return t.endswith("RandomModRare") and "/Randomized/" in t and "Raw" not in t.rsplit("/", 1)[-1]


def fingerprint(item: dict) -> dict:
    try:
        f = json.loads(item.get("UpgradeFingerprint") or "{}")
        return f if isinstance(f, dict) else {}
    except ValueError:
        return {}


def stat_value(raw: float, base: float, pct: bool, tag: str, dispo: float, mult: float, rank: int) -> float:
    norm = min(1.1, max(0.9, 0.9 + raw / DENOM / 100.0))
    v = 90.0 * base * dispo * mult
    if pct:
        v *= 100.0
    v *= norm
    v *= (rank + 1) / 9.0
    if any(tag.endswith(s) for s in TWO_DIGIT):
        v += 1.0
    return fmt(v)


OLD_STATS = {"WeaponGasDamageMod": "Gas", "WeaponAmmoEfficiency": "Ammo Efficiency"}   # rolled years ago, gone from the data


def compute(item: dict, partial: bool = False) -> dict:
    """One riven from an inventory upgrade. Raises ValueError with the reason when it cannot be worked out.
    partial: a stat the game data no longer has (an old roll such as Gas or Ammo Efficiency) is kept with value None
    instead of failing the whole riven (the Builds tab shows the other stats)."""
    f, d = fingerprint(item), data()
    compat = WEAPON_FIX.get(f.get("compat", ""), f.get("compat", ""))
    if not compat or not f.get("buffs"):
        raise ValueError("not revealed")
    if "challenge" in f:
        raise ValueError("not revealed (challenge pending)")
    weapon = d["weapons"].get(compat) or d["weapons"].get(f.get("compat", ""))
    stats = d["types"].get(item.get("ItemType", ""))
    if not weapon or not stats:
        raise ValueError(f"unknown weapon or riven type ({compat.rsplit('/', 1)[-1]})")
    nb, nc = len(f["buffs"]), len(f.get("curses") or [])
    if (nb, nc) not in MULT:
        raise ValueError(f"{nb} positive and {nc} negative stats: not a known riven layout")
    good, bad = MULT[(nb, nc)]
    rank = int(f.get("lvl") or 0)
    attrs = []
    for entries, positive in ((f["buffs"], True), (f.get("curses") or [], False)):
        for s in entries:
            base = stats.get(s.get("Tag"))
            if not base and partial:                   # a stat this riven type no longer rolls: another type's figures
                base = next((st[s.get("Tag")] for st in d["types"].values() if s.get("Tag") in st), None)
            if not base and partial:
                tag = str(s.get("Tag", ""))
                attrs.append({"tag": tag, "label": OLD_STATS.get(tag) or tag.replace("Weapon", "").replace("Mod", ""),
                              "positive": positive, "value": None, "raw": float(s.get("Value", 0)), "prefix": "",
                              "suffix": "", "pct": True})
                continue
            if not base:
                raise ValueError(f"unknown stat {s.get('Tag')}")
            raw = float(s.get("Value", 0))
            v = stat_value(raw, base[0], bool(base[3]), s["Tag"], weapon[1], good if positive else bad, rank)
            if not positive and s["Tag"] == "WeaponMeleeComboPointsOnHitMod" and v > 0:
                v = -v
            attrs.append({"tag": s["Tag"], "label": base[4], "positive": positive, "value": v, "raw": raw,
                          "prefix": base[1], "suffix": base[2], "pct": bool(base[3])})
    pos = sorted((a for a in attrs if a["positive"]), key=lambda a: -a["raw"])
    neg = [a for a in attrs if not a["positive"]]
    if any(not a["prefix"] for a in pos):             # an old stat without a name part: no riven name can be built
        name = "Riven"
    else:
        name = pos[0]["prefix"].capitalize() + pos[1]["suffix"] if nb == 2 else \
            f"{pos[0]['prefix'].capitalize()}-{pos[1]['prefix']}{pos[2]['suffix']}"
    return {"id": (item.get("ItemId") or {}).get("$oid", ""), "weapon_path": compat, "weapon": weapon[0],
            "mod_name": name, "rank": rank, "rerolls": int(f.get("rerolls") or 0),
            "mastery_rank": int(f.get("lvlReq") or 0), "polarity": POLARITY.get(f.get("pol", ""), (f.get("pol") or "").lower()),
            "attributes": pos + neg}


def describe(riven: dict) -> str:
    parts = []
    for a in riven["attributes"]:
        v = a["value"]
        txt = f"{v:+g}{'%' if a['pct'] else ''}" if a["pct"] or not a["tag"].endswith(TWO_DIGIT) else f"x{v:g}"
        parts.append(f"{txt} {a['label']}")
    return ", ".join(parts)


def from_inventory(inv: dict):
    """(rivens, skipped): every revealed riven of the inventory JSON (dict), and [(reason)] for the unusable ones."""
    out, skipped = [], []
    for key in ("Upgrades", "RawUpgrades"):
        for item in inv.get(key) or []:
            if not is_revealed(item):
                continue
            try:
                out.append(compute(item))
            except ValueError as e:
                if str(e) != "not revealed":
                    skipped.append(str(e))
    return out, skipped


def read_file(path: str):
    """Rivens of an AlecaFrame lastData.dat (or a plain inventory JSON). Raises ValueError."""
    from inventory import decrypt_last_data
    raw = Path(path).read_bytes()
    text = decrypt_last_data(raw) if path.lower().endswith(".dat") else raw.decode("utf-8-sig")
    return from_inventory(json.loads(text))


# ---------- warframe.market attribute names (needed by Quantframe) ----------
def _norm(s) -> str:
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def build_attribute_map(attrs: list) -> dict:
    """{(prefix, suffix): slug} and {label: slug} from warframe.market's riven attribute list."""
    by_ps, by_name = {}, {}
    for a in attrs:
        slug = a.get("slug") or a.get("url_name")
        if not slug:
            continue
        by_ps.setdefault(f"{_norm(a.get('prefix'))}|{_norm(a.get('suffix'))}", slug)
        name = ((a.get("i18n") or {}).get("en") or {}).get("name") or a.get("effect") or a.get("name")
        if name:
            by_name.setdefault(_norm(name), slug)
    return {"ps": by_ps, "names": by_name, "time": int(time.time())}


def load_attribute_map(market, max_age_days=30) -> dict:
    try:
        c = json.loads(ATTR_CACHE.read_text(encoding="utf-8"))
        if c.get("ps") and time.time() - c.get("time", 0) < max_age_days * 86400:
            return c
    except Exception:
        pass
    c = build_attribute_map(market._get("/riven/attributes"))
    if not c["ps"]:
        raise ValueError("warframe.market returned no riven attributes")
    try:
        ATTR_CACHE.write_text(json.dumps(c), encoding="utf-8")
    except OSError:
        pass
    return c


def slug_for(attr: dict, amap: dict):
    return amap["ps"].get(f"{_norm(attr['prefix'])}|{_norm(attr['suffix'])}") or amap["names"].get(_norm(attr["label"]))


def payload(riven: dict, amap: dict) -> dict:
    """The body for Quantframe's POST /stock_riven. Raises ValueError for a stat warframe.market does not know."""
    attrs = []
    for a in riven["attributes"]:
        slug = slug_for(a, amap)
        if not slug:
            raise ValueError(f"no warframe.market attribute for {a['label']}")
        attrs.append({"wfmUrl": slug, "positive": a["positive"], "value": a["value"], "formattedValue": ""})
    return {"raw": riven["weapon_path"], "mod_name": riven["mod_name"], "mastery_rank": riven["mastery_rank"],
            "re_rolls": riven["rerolls"], "polarity": riven["polarity"], "rank": riven["rank"], "attributes": attrs}


# ---------- what was already sent ----------
def load_sent() -> dict:
    try:
        d = json.loads(SENT_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def mark_sent(riven_id: str):
    d = load_sent()
    d[riven_id] = int(time.time())
    try:
        SENT_FILE.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass
