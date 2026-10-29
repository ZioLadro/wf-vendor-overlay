"""What rivens really sold for in the game last week: DE's own weekly riven trade data.

Every week Digital Extremes publishes, per weapon, the in-game trades of its rivens (separately for rivens never rolled
and rolled ones): median, average, standard deviation, min, max and a popularity figure ("pop"). These are the prices
players actually paid in trade chat, not asking prices. Official file: https://www-static.warframe.com/repos/
weeklyRivensPC.json; when it cannot be read, the same file from the community archive
(https://warframe-weekly-rivens-archive.pages.dev, kept by CloudeaSoft) is used.

Read at most once a day (the data changes once a week), kept in riven_weekly.json with the medians of the last weeks
(for a weekly trend). Weapons without data of their own (kitguns, zaws) use their riven type's row."""
import json
import threading
import time
from datetime import datetime, timezone

import requests

from app.core.config import APP_DIR

OFFICIAL = "https://www-static.warframe.com/repos/weeklyRivensPC.json"
ARCHIVE = "https://warframe-weekly-rivens-archive.pages.dev/PC/{week}_weeklyRivensPC.json"
CACHE_FILE = APP_DIR / "riven_weekly.json"
MAX_AGE = 24 * 3600
KEEP_WEEKS = 12
TYPE_ROW = {"rifle": "Rifle Riven Mod", "pistol": "Pistol Riven Mod", "shotgun": "Shotgun Riven Mod",
            "melee": "Melee Riven Mod", "archgun": "Archgun Riven Mod", "kitgun": "Kitgun Riven Mod",
            "zaw": "Zaw Riven Mod"}

_lock = threading.Lock()
_state = {"d": None, "busy": False}


def _norm(s):
    return "".join(c for c in str(s or "").lower() if c.isalnum())


def week_key(t=None):
    y, w, _d = datetime.fromtimestamp(t or time.time(), timezone.utc).isocalendar()
    return f"{y}_W{w:02d}"


def _load():
    if _state["d"] is None:
        try:
            _state["d"] = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _state["d"] = {}
    return _state["d"]


def parse(rows):
    """{(weapon key or "type:<Riven type>"), rerolled: {median, avg, sd, min, max, pop}} from the official list."""
    out = {}
    for r in rows or []:
        if not isinstance(r, dict) or r.get("median") is None:
            continue
        key = _norm(r.get("compatibility")) if r.get("compatibility") else "type:" + str(r.get("itemType") or "")
        out[f"{key}|{int(bool(r.get('rerolled')))}"] = {
            "median": float(r.get("median") or 0), "avg": float(r.get("avg") or 0), "sd": float(r.get("stddev") or 0),
            "min": float(r.get("min") or 0), "max": float(r.get("max") or 0), "pop": float(r.get("pop") or 0)}
    return out


def _download():
    from app.core import logbus
    from app.trade.market import HEADERS
    h = {"User-Agent": HEADERS["User-Agent"], "Accept": "application/json"}
    tries = [("DE", OFFICIAL)] + [("archive", ARCHIVE.format(week=week_key(time.time() - n * 7 * 86400))) for n in (0, 1)]
    for src, url in tries:
        try:
            r = requests.get(url, headers=h, timeout=20)
            r.raise_for_status()
            rows = r.json()
            data = parse(rows)
            if data:
                return src, data
        except Exception as e:
            logbus.add("riven", f"weekly riven data ({src}): {type(e).__name__}: {e}", "warn")
    return None, None


def refresh(force=False, wait=False):
    """Reads the weekly data again when it is a day old (in the background unless wait)."""
    d = _load()
    if not force and time.time() - float(d.get("t") or 0) < MAX_AGE:
        return
    with _lock:
        if _state["busy"]:
            return
        _state["busy"] = True

    def run():
        from app.core import logbus
        try:
            src, data = _download()
            with _lock:
                d = _load()
                d["t"] = time.time()
                if data:
                    wk = week_key()
                    hist = dict(d.get("hist") or {})
                    hist[wk] = {k: v["median"] for k, v in data.items()}
                    d.update(rows=data, week=wk, src=src, hist=dict(sorted(hist.items())[-KEEP_WEEKS:]))
                    logbus.add("riven", f"weekly riven trades read ({src}): {len(data)} rows", "ok")
                try:
                    CACHE_FILE.write_text(json.dumps(d), encoding="utf-8")
                except OSError:
                    pass
        finally:
            _state["busy"] = False
    if wait:
        run()
    else:
        threading.Thread(target=run, daemon=True, name="riven-weekly").start()


def lookup(weapon_name, wtype="", rerolled=False):
    """{median, avg, sd, min, max, pop, own (True = the weapon's own row), trend (vs ~4 weeks ago)} or None."""
    d = _load()
    rows = d.get("rows") or {}
    if not rows:
        return None
    key = f"{_norm(weapon_name)}|{int(bool(rerolled))}"
    own = rows.get(key)
    row = own or rows.get(f"type:{TYPE_ROW.get(wtype, '')}|{int(bool(rerolled))}")
    if not row:
        return None
    out = dict(row, own=bool(own))
    hist = d.get("hist") or {}
    weeks = sorted(hist)
    if own and len(weeks) >= 3:
        old = hist[weeks[max(0, len(weeks) - 5)]].get(key)
        if old:
            out["trend"] = (row["median"] - old) / old
    return out


def popularity(weapon_name):
    """The weapon's weekly trade popularity (both rows), 0 when unknown: how much its rivens trade in game."""
    rows = _load().get("rows") or {}
    k = _norm(weapon_name)
    return sum((rows.get(f"{k}|{r}") or {}).get("pop", 0) for r in (0, 1))
