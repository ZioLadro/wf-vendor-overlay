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


def _oid(v) -> str:
    """An id as DE writes it: {"$oid": "…"}, {"$id": "…"} (older files) or a plain string."""
    if isinstance(v, dict):
        v = v.get("$oid") or v.get("$id") or ""
    return str(v or "")


def _oid_time(oid: str):
    """When a MongoDB-style id (24 hex characters) was made: its first 8 characters are the Unix time."""
    try:
        return int(oid[:8], 16) if len(oid) == 24 else None
    except ValueError:
        return None


_nw_logged = {"sig": None}


def progress_map(inv) -> dict:
    """{challenge name: progress} from the game file's ChallengeProgress (Nightwave and Calendar challenges count up there;
    a challenge's count starts again from 0 when a new instance of it is given)."""
    out = {}
    for c in (inv or {}).get("ChallengeProgress") or []:
        if isinstance(c, dict) and c.get("Name"):
            try:
                out[str(c["Name"])] = int(c.get("Progress") or 0)
            except (TypeError, ValueError):
                pass
    return out


def nightwave(ws, inv) -> dict:
    """{"expiry", "weekly": [...], "daily": [...], "daily_open": n} or None; each challenge
    {"name","desc","standing","kind","done","expiry","progress","required","maybe"}.

    Done = its count in the game file's ChallengeProgress has reached the amount required (ExportNightwave "required").
    SeasonChallengeHistory is NOT a list of completed challenges: the game adds every challenge you are GIVEN to it (this
    week's elite ones are there before you do them), so it cannot tell completion."""
    si = (ws or {}).get("SeasonInfo")
    if not isinstance(si, dict):
        return None
    prog = progress_map(inv)
    now = time.time()
    weekly, daily, how = [], [], []
    for c in si.get("ActiveChallenges") or []:
        if not isinstance(c, dict):
            continue
        exp = _date(c.get("Expiry"))
        if exp and exp < now:
            continue
        path = str(c.get("Challenge") or "")
        short = path.rsplit("/", 1)[-1]
        n = names()["nightwave"].get(path) or [_humanize(path), "", 0, "weekly"]
        required = int(n[6]) if len(n) >= 7 and n[6] else 1
        if _lang_it() and len(n) >= 6 and n[4]:
            n = [n[4], n[5] or n[1], n[2], n[3]]
        got = prog.get(short)
        done = got is not None and got >= required
        kind = "daily" if (c.get("Daily") or n[3] == "daily") else n[3]
        how.append(f"{short}={got if got is not None else '–'}/{required}")
        row = {"name": n[0], "desc": n[1], "standing": n[2], "kind": kind, "done": done, "expiry": exp,
               "progress": got or 0, "required": required, "maybe": False}
        (daily if kind == "daily" else weekly).append(row)
    sig = tuple(how)
    if sig != _nw_logged["sig"]:                        # what was read, in the Console (once per change)
        _nw_logged["sig"] = sig
        try:
            from app.core import logbus
            logbus.add("quests", "Nightwave progress from the game file: " + ", ".join(how))
        except Exception:
            pass
    key = lambda x: (x["done"], x["kind"] != "elite", x["name"])
    weekly.sort(key=key)
    daily.sort(key=key)
    return {"expiry": _date(si.get("Expiry")), "weekly": weekly, "daily": daily,
            "daily_open": sum(1 for d in daily if not d["done"])}


# ---------- daily and weekly routine: Sortie, Archon Hunt, Deep / Temporal Archimedea, Descendia ----------
def _last_weekly_reset(now):
    day = int(now // 86400)
    return (day - (day + 3) % 7) * 86400              # Monday 00:00 UTC


def _sync_time(inv):
    """When AlecaFrame last synced the game file (from the id of LastInventorySync), or None."""
    return _oid_time(_oid((inv or {}).get("LastInventorySync")))


def _sortie(ws, inv, now, lite):
    """Sortie (lite=False) or Archon Hunt (lite=True): (missions done, missions, done, expiry) or None."""
    key = "LiteSorties" if lite else "Sorties"
    cur = next((x for x in (ws or {}).get(key) or [] if isinstance(x, dict)
                and (_date(x.get("Activation")) or 0) <= now < (_date(x.get("Expiry")) or 0)), None)
    completed = [str(x) for x in (inv or {}).get("CompletedSorties") or []]
    mine = [x for x in completed if ("_Lite_" in x) == lite]
    reward = _oid(((inv or {}).get("LastLiteSortieReward" if lite else "LastSortieReward") or [{}])[-1].get("SortieId"))
    total = 3
    if cur:
        sid, exp = _oid(cur.get("_id")), _date(cur.get("Expiry"))
        total = len(cur.get("Missions") or cur.get("Variants") or []) or 3
    else:
        # no world state: the newest id you played, if it is still running (an id is made ~15 min before the start)
        span = 7 * 86400 if lite else 86400
        ids = sorted({x.rsplit("_", 1)[-1] for x in mine}, key=lambda i: _oid_time(i) or 0)
        sid = ids[-1] if ids else ""
        start = (_oid_time(sid) or 0) + 900
        exp = start + span if sid else None
        if not sid or now >= exp:
            return None
    n = sum(1 for x in mine if x.endswith("_" + sid)) if sid else 0
    return min(n, total), total, (reward == sid and bool(sid)) or n >= total, exp


def routine(ws, inv, now=None) -> list:
    """[{"key","name","done" (True / False / None = unknown),"progress","expiry"}] for the Sortie, the Archon Hunt, Deep and
    Temporal Archimedea and Descendia, from the game file (and the world state for what is running now)."""
    now = time.time() if now is None else now
    it = _lang_it()
    rows = []
    for lite, key, name in ((False, "sortie", "Sortie"), (True, "archon", "Archon Hunt" if not it else "Caccia all'Arconte")):
        s = _sortie(ws, inv, now, lite)
        if s is None:
            reset = _last_weekly_reset(now) + 7 * 86400 if lite else None
            rows.append({"key": key, "name": name, "done": False, "progress": "0/3", "expiry": reset})
        else:
            n, total, done, exp = s
            rows.append({"key": key, "name": name, "done": done, "progress": f"{n}/{total}", "expiry": exp})
    week_end = _last_weekly_reset(now) + 7 * 86400
    fresh = (_sync_time(inv) or 0) >= _last_weekly_reset(now)     # the file was written this week
    for key, prefix, name in (("eda", "EntratiLab", "Elite Deep Archimedea"), ("eta", "EchoesHex", "Elite Temporal Archimedea")):
        if f"{prefix}ConquestUnlocked" not in (inv or {}):
            continue
        started = bool((inv or {}).get(f"{prefix}ConquestUnlocked")) and fresh
        score = int((inv or {}).get(f"{prefix}ConquestCacheScoreMission") or 0) if fresh else 0
        prog = (t_started(it) + (f" · {score}" if score else "")) if started else ""
        rows.append({"key": key, "name": name, "done": None if started else False, "progress": prog, "expiry": week_end})
    if "EntratiVaultCountLastPeriod" in (inv or {}):     # Netracells: 5 a week (reset date in the file)
        reset = _date((inv or {}).get("EntratiVaultCountResetDate")) or week_end
        n = int((inv or {}).get("EntratiVaultCountLastPeriod") or 0) if reset > now else 0
        if reset <= now:
            reset = week_end
        rows.append({"key": "netracells", "name": "Netracells", "done": n >= 5, "progress": f"{min(n, 5)}/5",
                     "expiry": reset})
    for d in (inv or {}).get("DescentRewards") or []:
        if not isinstance(d, dict):
            continue
        exp = _date(d.get("Expiry"))
        if not exp or exp <= now:
            continue                                   # last week's run
        floors = max((p.get("FloorCheckpoint") or 0 for p in d.get("PendingRewards") or []), default=21) or 21
        got = int(d.get("FloorClaimed") or 0)
        hard = "HARD" in str(d.get("Category"))
        name = "Descendia" + ((" (Percorso d'Acciaio)" if it else " (Steel Path)") if hard else "")
        rows.append({"key": "descendia_" + ("sp" if hard else "n"), "name": name, "done": got >= floors,
                     "progress": f"{got}/{floors}", "expiry": exp})
    return rows


def t_started(it: bool) -> str:
    return "iniziata" if it else "started"


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
    prog_ = progress_map(inv)
    for idx, d in enumerate(cur.get("Days") or []):
        for e in d.get("events") or []:
            if isinstance(e, dict) and e.get("type") == "CET_CHALLENGE" and e.get("challenge"):
                path = e["challenge"]
                n = names()["calendar"].get(path) or [_humanize(path), ""]
                req = int(n[4]) if len(n) >= 5 and n[4] else None
                if _lang_it() and len(n) >= 4 and n[2]:
                    n = [n[2], n[3] or n[1]]
                short = path.rsplit("/", 1)[-1]
                out.append({"name": n[0], "desc": n[1], "day": d.get("day", idx + 1), "done": idx <= last_day if same else None,
                            "active": short in active, "required": req, "progress": prog_.get(short, 0)})
    season = str(cur.get("Season") or "").replace("CST_", "").title()
    if _lang_it():
        season = {"Winter": "Inverno", "Spring": "Primavera", "Summer": "Estate", "Autumn": "Autunno"}.get(season, season)
    return {"season": season, "expiry": _date(cur.get("Expiry")),
            "challenges": out, "known": same}
