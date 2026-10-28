"""Weekly quests for the Activities overlay: Nightwave's weekly (and elite) challenges and the 1999 Calendar's challenges,
with their completion read from your game file where it can be.

What is active comes from Digital Extremes' own public world state (api.warframe.com/cdn/worldState.php, the old
content.warframe.com address as a fallback: the same file the game reads; SeasonInfo for Nightwave, KnownCalendarSeasons for the Calendar), read every 10 minutes and
kept on disk. Names and descriptions come from challenges.json (build_challenges.py).

Completion (AlecaFrame's lastData.dat):
  Nightwave: SeasonChallengeHistory lists the challenges you completed, with the same id the world state gives the active
             one: an exact match.
  Calendar:  CalendarProgress tells the last completed day of the current season and the challenge you activated (in
             progress); days up to that index are done. If the file's season is not the current one, nothing is marked."""
import json
import sys
import threading
import time
from pathlib import Path

import requests

from app.core.config import APP_DIR
from app.core.paths import DATA

WS_URLS = ("https://api.warframe.com/cdn/worldState.php",          # current address (2025 on)
           "https://content.warframe.com/dynamic/worldState.php")  # the old one, in case it comes back
WS_FILE = APP_DIR / "worldstate_de.json"
REFRESH = 600
DATA_FILE = DATA / "challenges.json"

_lock = threading.Lock()
_state = {"ws": None, "fetched": 0.0, "retry_at": 0.0}
_names = None


def names() -> dict:
    global _names
    if _names is None:
        try:
            _names = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            _names = {"nightwave": {}, "calendar": {}}
    return _names


def _humanize(path: str) -> str:
    """A readable name from a challenge path the data does not know yet (SeasonWeeklyCompleteSortie -> Complete Sortie)."""
    import re
    n = path.rsplit("/", 1)[-1]
    n = re.sub(r"^(SeasonWeeklyHard|SeasonWeekly|SeasonDaily|Calendar)", "", n)
    n = re.sub(r"(Easy|Medium|Hard|Base)$", "", n)
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", n).strip() or path


def _lang_it() -> bool:
    from app.core.config import CFG
    return CFG.get("language") == "it"


def _date(v):
    try:
        return int(v["$date"]["$numberLong"]) / 1000
    except (KeyError, TypeError, ValueError):
        try:
            return float(v) / (1000 if float(v) > 1e11 else 1)
        except (TypeError, ValueError):
            return None


def world_state(force=False):
    """DE's world state (downloaded at most every 10 minutes; the saved copy when offline). Any thread."""
    from app.core import logbus
    from app.trade.market import HEADERS
    with _lock:
        now = time.time()
        if _state["ws"] is None:
            try:
                _state["ws"] = json.loads(WS_FILE.read_text(encoding="utf-8"))
                _state["fetched"] = WS_FILE.stat().st_mtime
            except Exception:
                pass
        if not force and _state["ws"] is not None and now - _state["fetched"] < REFRESH:
            return _state["ws"]
        if now < _state["retry_at"]:
            return _state["ws"]
        errors = []
        for url in WS_URLS:
            try:
                r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20)
                r.raise_for_status()
                ws = r.json()
                if not isinstance(ws, dict):
                    raise ValueError("not a world state")
            except Exception as e:
                errors.append(f"{url.split('/')[2]}: {type(e).__name__}: {e}")
                continue
            _state["ws"], _state["fetched"] = ws, now
            try:
                WS_FILE.write_text(json.dumps(ws), encoding="utf-8")
            except OSError:
                pass
            logbus.add("quests", f"world state read from {url.split('/')[2]}", "ok")
            return ws
        _state["retry_at"] = now + 300
        logbus.error("quests", "world state: " + " | ".join(errors) + " (the saved copy is used)")
        return _state["ws"]


def cached():
    """The last world state read (never waits for the network: the overlay calls it every few seconds)."""
    with _lock:
        if _state["ws"] is None:
            try:
                _state["ws"] = json.loads(WS_FILE.read_text(encoding="utf-8"))
                _state["fetched"] = WS_FILE.stat().st_mtime
            except Exception:
                pass
        return _state["ws"]


def refresh_async():
    """Reads the world state again in the background when it is due."""
    if time.time() - _state["fetched"] >= REFRESH and time.time() >= _state["retry_at"]:
        threading.Thread(target=world_state, daemon=True, name="worldstate-de").start()


def nightwave(ws, inv) -> dict:
    """{"expiry", "weekly": [{"name","desc","standing","kind","done","expiry"}], "daily_open": n} or None."""
    si = (ws or {}).get("SeasonInfo")
    if not isinstance(si, dict):
        return None
    done_ids = {str(h.get("id")) for h in (inv or {}).get("SeasonChallengeHistory") or [] if isinstance(h, dict)}
    done_names = {str(h.get("challenge")) for h in (inv or {}).get("SeasonChallengeHistory") or [] if isinstance(h, dict)}
    now = time.time()
    out, daily_open = [], 0
    for c in si.get("ActiveChallenges") or []:
        if not isinstance(c, dict):
            continue
        exp = _date(c.get("Expiry"))
        if exp and exp < now:
            continue
        path = str(c.get("Challenge") or "")
        oid = str((c.get("_id") or {}).get("$oid") or "")
        n = names()["nightwave"].get(path) or [_humanize(path), "", 0, "weekly"]
        if _lang_it() and len(n) >= 6 and n[4]:
            n = [n[4], n[5] or n[1], n[2], n[3]]
        done = oid in done_ids if oid else None
        if c.get("Daily") or n[3] == "daily":
            daily_open += 0 if done else 1
            continue
        out.append({"name": n[0], "desc": n[1], "standing": n[2], "kind": n[3], "done": done, "expiry": exp,
                    "maybe": (not done) and path.rsplit("/", 1)[-1] in done_names and not oid})
    out.sort(key=lambda x: (x["done"] is True, x["kind"] != "elite", x["name"]))
    return {"expiry": _date(si.get("Expiry")), "weekly": out, "daily_open": daily_open}


def calendar(ws, inv) -> dict:
    """The 1999 Calendar's current season: {"season","expiry","challenges": [{"name","desc","day","done","active"}]} or
    None. Only the days with a challenge are listed."""
    now = time.time()
    seasons = [s for s in (ws or {}).get("KnownCalendarSeasons") or [] if isinstance(s, dict)]
    cur = next((s for s in seasons if (_date(s.get("Activation")) or 0) <= now < (_date(s.get("Expiry")) or 0)), None)
    if cur is None:
        return None
    prog = ((inv or {}).get("CalendarProgress") or {}).get("SeasonProgress") or {}
    same = prog.get("SeasonType") == cur.get("Season")
    last_day = int(prog.get("LastCompletedDayIdx", -1)) if same else -1
    active = set(prog.get("ActivatedChallenges") or []) if same else set()
    out = []
    for idx, d in enumerate(cur.get("Days") or []):
        for e in d.get("events") or []:
            if isinstance(e, dict) and e.get("type") == "CET_CHALLENGE" and e.get("challenge"):
                path = e["challenge"]
                n = names()["calendar"].get(path) or [_humanize(path), ""]
                if _lang_it() and len(n) >= 4 and n[2]:
                    n = [n[2], n[3] or n[1]]
                out.append({"name": n[0], "desc": n[1], "day": d.get("day", idx + 1), "done": idx <= last_day if same else None,
                            "active": path.rsplit("/", 1)[-1] in active})
    season = str(cur.get("Season") or "").replace("CST_", "").title()
    if _lang_it():
        season = {"Winter": "Inverno", "Spring": "Primavera", "Summer": "Estate", "Autumn": "Autunno"}.get(season, season)
    return {"season": season, "expiry": _date(cur.get("Expiry")),
            "challenges": out, "known": same}
