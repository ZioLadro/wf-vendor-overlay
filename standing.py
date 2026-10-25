"""Your standing per syndicate, and how much of an item it lets you buy.

Source: the public profile of your in-game name (a public Warframe endpoint, only the name is needed),
or numbers you type by hand in the Profile tab. The profile is a snapshot: refetch it to update.
The raw response is saved as profile_raw.json so a format change can be inspected.
"""
import json
import os
import time

import requests

from config import APP_DIR
from inventory import game_names

STANDING_FILE = APP_DIR / "standing.json"
RAW_FILE = APP_DIR / "profile_raw.json"
PROFILE_URL = "https://content.warframe.com/dynamic/getProfileViewingData.php"
UA = "WFVendorOverlay/1.6"


class ProfileError(Exception):
    pass


def syndicate_name(tag: str) -> str:
    return game_names().get("syndicates", {}).get(tag) or tag


def parse_profile(data) -> dict:
    """{"mr": int|None, "factions": {tag: {"standing": int, "rank": int|None}}} from the profile JSON.
    Tolerant: looks for the first result and any list of {Tag, Standing, Title} affiliations."""
    res = data
    if isinstance(data, dict) and isinstance(data.get("Results"), list) and data["Results"]:
        res = data["Results"][0]
    if not isinstance(res, dict):
        raise ProfileError("unexpected profile format")
    mr = res.get("PlayerLevel")
    aff = res.get("Affiliations")
    if aff is None and isinstance(data, dict):
        aff = data.get("Affiliations")
    factions = {}
    for a in aff or []:
        if isinstance(a, dict) and a.get("Tag"):
            st, rk = a.get("Standing"), a.get("Title")
            factions[str(a["Tag"])] = {"standing": int(st) if isinstance(st, (int, float)) else 0,
                                       "rank": int(rk) if isinstance(rk, (int, float)) else None}
    return {"mr": int(mr) if isinstance(mr, (int, float)) else None, "factions": factions}


def fetch_profile(name: str, timeout: float = 20.0) -> dict:
    """Downloads and parses the public profile. Raises ProfileError."""
    try:
        r = requests.get(PROFILE_URL, params={"n": name}, headers={"User-Agent": UA}, timeout=timeout)
    except requests.RequestException as e:
        raise ProfileError(f"network error: {type(e).__name__}")
    if r.status_code != 200:
        raise ProfileError(f"HTTP {r.status_code}" + (" (player not found?)" if r.status_code in (400, 404, 409) else ""))
    try:
        data = r.json()
        RAW_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except ValueError:
        raise ProfileError("the server did not return JSON")
    except OSError:
        pass
    return parse_profile(data)


class StandingStore:
    def __init__(self):
        self.name = ""
        self.mr = None
        self.fetched = None
        self.factions = {}     # tag -> {"standing": int, "rank": int|None, "manual": bool}
        self.version = 0       # grows at every change (lets tables know when to rebuild)
        self.load()

    def load(self):
        try:
            d = json.loads(STANDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        self.name, self.mr, self.fetched = d.get("name", ""), d.get("mr"), d.get("fetched")
        self.factions = {k: v for k, v in (d.get("factions") or {}).items() if isinstance(v, dict)}

    def save(self):
        tmp = STANDING_FILE.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"name": self.name, "mr": self.mr, "fetched": self.fetched,
                                       "factions": self.factions}, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, STANDING_FILE)
        except OSError:
            pass

    def apply_profile(self, name: str, profile: dict):
        self.name, self.mr, self.fetched = name, profile["mr"], int(time.time())
        for tag, f in profile["factions"].items():
            self.factions[tag] = {"standing": f["standing"], "rank": f["rank"], "manual": False}
        self.version += 1
        self.save()

    def set_manual(self, tag: str, standing: int, rank=None):
        cur = self.factions.get(tag, {})
        self.factions[tag] = {"standing": max(0, int(standing)),
                              "rank": cur.get("rank") if rank is None else rank, "manual": True}
        self.version += 1
        self.save()

    def get(self, tag):
        return self.factions.get(tag) if tag else None


def affordability(entries, store: StandingStore) -> list:
    """For each standing entry of an item: how many you can buy with the standing you have.

    Returns [{"vendor","tag","cost","req_rank","have","rank","count","rank_ok"}]; `have`/`count` are None
    when nothing is known about that syndicate."""
    out = []
    for e in entries:
        f = store.get(e.get("t"))
        have = f["standing"] if f else None
        rank = f.get("rank") if f else None
        req = e.get("r") or 0
        out.append({"vendor": e["v"], "tag": e.get("t"), "cost": e["s"], "req_rank": req, "have": have,
                    "rank": rank, "count": (have // e["s"]) if (have is not None and e["s"] > 0) else None,
                    "rank_ok": (rank >= req) if rank is not None else None})
    return out


_STORE = None


def get_store() -> StandingStore:
    global _STORE
    if _STORE is None:
        _STORE = StandingStore()
    return _STORE


def afford_text(entries, store=None) -> str:
    """Tooltip: how many of the item you can buy with your standing, per faction."""
    from i18n import t
    store = store or get_store()
    lines = []
    for a in affordability(entries, store):
        syn = syndicate_name(a["tag"]) if a["tag"] else a["vendor"]
        if a["count"] is None:
            lines.append(t("aff.unknown", vendor=a["vendor"], syn=syn))
            continue
        line = t("aff.line", vendor=a["vendor"], syn=syn, count=a["count"], have=f"{a['have']:,}".replace(",", " "),
                 cost=f"{a['cost']:,}".replace(",", " "))
        if a["rank_ok"] is False:
            line += t("aff.rank_low", req=a["req_rank"], rank=a["rank"])
        lines.append(line)
    return "\n".join(lines)
