"""Arbitration tier list from arbi.guide (the Arbitration Goons community guide, github.com/remesis/ARBI_GUIDE).

Its public API (documented in the repo's tierlist.txt): GET https://arbi.guide/tierlist.json, no token. "nodes" lists every
rated node (id, name, planet, mission_type, tier, saryn_viable); tiers are S, A, B, C, D, F or Special (Survival /
Disruption, rated separately); a node not listed is F (or "default_tier"). saryn_viable is the guide's "*".
As the guide asks: cached for at least 5 minutes, the last good copy is kept when the site is unavailable, a 429 waits
for Retry-After, and the program links back to https://arbi.guide where the tier is shown."""
import json
import threading
import time

import requests

from config import APP_DIR

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
    import logbus
    from market import HEADERS
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
