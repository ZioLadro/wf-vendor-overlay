"""Arbitration tier list from arbi.guide (the Arbitration Goons community guide, github.com/remesis/ARBI_GUIDE).

Its public API (documented in the repo's tierlist.txt): GET https://arbi.guide/tierlist.json, no token. "nodes" lists every
rated node (id, name, planet, mission_type, tier, saryn_viable); tiers are S, A, B, C, D, F or Special (Survival /
Disruption, rated separately); a node not listed is F (or "default_tier"). saryn_viable is the guide's "*".
As the guide asks: cached for at least 5 minutes, the last good copy is kept when the site is unavailable, a 429 waits
for Retry-After, and the program links back to https://arbi.guide where the tier is shown."""
import json
import sys
import threading
import time
from pathlib import Path

import requests

from app.core.config import APP_DIR
from app.core.paths import DATA

URL = "https://arbi.guide/tierlist.json"
SITE = "https://arbi.guide"
CACHE_FILE = APP_DIR / "arbi_tierlist.json"
MIN_AGE = 15 * 60                  # seconds between two downloads (the guide asks for at least 5 minutes)
TIER_INFO = {"S": "12+", "A": "11+", "B": "10+", "C": "9+", "D": "< 9"}       # Vitus Essence per minute

_lock = threading.Lock()
_state = {"data": None, "fetched": 0.0, "retry_at": 0.0}


def _load_cache():
    if _state["data"] is None:
        try:
            d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(d.get("nodes"), list):
                _state["data"], _state["fetched"] = d, float(d.get("_saved") or 0)
        except Exception:
            pass
    return _state["data"]


def tierlist(force=False):
    """The tier list (downloaded at most every MIN_AGE seconds; the last good copy otherwise). Any thread."""
    from app.core import logbus
    from app.trade.market import HEADERS
    with _lock:
        data = _load_cache()
        now = time.time()
        if not force and data is not None and now - _state["fetched"] < MIN_AGE:
            return data
        if now < _state["retry_at"]:
            return data
        try:
            r = requests.get(URL, headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/json"}, timeout=15)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After") or 300)
                _state["retry_at"] = now + wait
                logbus.add("arbi.guide", f"too many requests: waiting {int(wait)} s as the site asks", "warn")
                return data
            r.raise_for_status()
            d = r.json()
            if not isinstance(d.get("nodes"), list):
                raise ValueError("unexpected answer (no node list)")
            d["_saved"] = now
            _state["data"], _state["fetched"] = d, now
            try:
                CACHE_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
            logbus.add("arbi.guide", f"tier list read: {len(d['nodes'])} nodes (version {d.get('version', '?')})", "ok")
        except Exception as e:
            _state["retry_at"] = now + 300
            logbus.error("arbi.guide", f"{type(e).__name__}: {e} (the last saved copy is used)")
        return _state["data"]


# The Arbitration of each hour: browse.wf publishes the schedule (arbys.txt: "<unix time>,<node id>" per hour), since the
# game's own world state does not list it. Read once a day, kept on disk; credited in the strip's tooltip.
SCHEDULE_URL = "https://browse.wf/arbys.txt"
SCHEDULE_FILE = APP_DIR / "arbys.txt"
SCHEDULE_AGE = 24 * 3600
NODES_FILE = DATA / "nodes.json"
_sched = {"rows": None, "fetched": 0.0, "retry_at": 0.0}
_nodes = {}


def node_info(node_id: str):
    """[node, planet, mission type, faction] of a star-chart node id (from the bundled nodes.json), or None."""
    if not _nodes:
        try:
            _nodes.update(json.loads(NODES_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return _nodes.get(node_id)


def _parse_schedule(text: str) -> list:
    rows = []
    for line in text.splitlines():
        a, _, b = line.strip().partition(",")
        if a.isdigit() and b:
            rows.append((int(a), b.strip()))
    rows.sort()
    return rows


def schedule():
    """[(start time, node id)] of the Arbitrations, hour by hour (downloaded once a day; the saved copy otherwise)."""
    from app.core import logbus
    from app.trade.market import HEADERS
    with _lock:
        now = time.time()
        if _sched["rows"] is None:
            try:
                _sched["rows"] = _parse_schedule(SCHEDULE_FILE.read_text(encoding="utf-8"))
                _sched["fetched"] = SCHEDULE_FILE.stat().st_mtime
            except OSError:
                _sched["rows"] = []
        last = _sched["rows"][-1][0] if _sched["rows"] else 0
        if (now - _sched["fetched"] < SCHEDULE_AGE and last > now + 3600) or now < _sched["retry_at"]:
            return _sched["rows"]
        try:
            r = requests.get(SCHEDULE_URL, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)
            r.raise_for_status()
            rows = _parse_schedule(r.text)
            if not rows:
                raise ValueError("empty schedule")
            _sched["rows"], _sched["fetched"] = rows, now
            try:
                SCHEDULE_FILE.write_text(r.text, encoding="utf-8")
            except OSError:
                pass
            logbus.add("arbitration", f"schedule read from browse.wf: {len(rows)} hours, until "
                       f"{time.strftime('%d/%m/%Y', time.localtime(rows[-1][0]))}", "ok")
        except Exception as e:
            _sched["retry_at"] = now + 600
            logbus.error("arbitration", f"browse.wf schedule: {type(e).__name__}: {e} (the saved copy is used)")
        return _sched["rows"]


def current(rows, now=None):
    """(node id, start, end) of the Arbitration running now, or None."""
    import bisect
    now = time.time() if now is None else now
    i = bisect.bisect_right(rows, (int(now), "\uffff")) - 1
    if i < 0 or not rows:
        return None
    start, node = rows[i]
    end = rows[i + 1][0] if i + 1 < len(rows) else start + 3600
    return (node, start, end) if start <= now < end else None


def tier_of(data, node_id="", node_name="") -> tuple:
    """(tier, saryn_viable, node) for an Arbitration node, matched by id (SolNode…) or by 'Name (Planet)'."""
    if not data:
        return "", False, None
    norm = lambda s: str(s or "").strip().lower()
    for n in data.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        if node_id and n.get("id") == node_id:
            return str(n.get("tier") or "F"), bool(n.get("saryn_viable")), n
        if node_name and norm(f"{n.get('name')} ({n.get('planet')})") == norm(node_name):
            return str(n.get("tier") or "F"), bool(n.get("saryn_viable")), n
    return str(data.get("default_tier") or "F"), False, None
