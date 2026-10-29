"""World activities you follow in the Activities overlay, with live countdowns (World tab > Follow).

Every activity of the world state can be followed: the open-world cycles, Baro Ki'Teer, the Sortie and the Archon Hunt,
the Arbitration now and the next one of a tier (browse.wf's schedule, arbi.guide's tiers), a kind of Void Fissure (tier,
mission type, Steel Path / Void Storm: every open one is listed with its time left) and the invasions giving a reward.
The keys followed are kept in the setting world_tracked; the world state is the one the World tab and the strip read
(api.warframestat.us), read again here every 5 minutes while something is followed."""
import threading
import time
from datetime import datetime

from app.core.config import CFG

CYCLES = (("earthCycle", "earth"), ("cetusCycle", "cetus"), ("vallisCycle", "vallis"), ("cambionCycle", "cambion"),
          ("zarimanCycle", "zariman"), ("duviriCycle", "duviri"))
REFRESH = 300
_busy = {"on": False, "t": 0.0}


def ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def tracked() -> list:
    return list(CFG.get("world_tracked") or [])


def set_tracked(key: str, on: bool):
    from app.core.config import save_config
    cur = tracked()
    if on and key not in cur:
        cur.append(key)
    elif not on and key in cur:
        cur.remove(key)
    save_config({"world_tracked": cur})


def ensure_fresh():
    """Reads the world state again in the background when it is older than 5 minutes (only while something is followed)."""
    from app.game import world
    t, _ws = world.last()
    if not tracked() or time.time() - t < REFRESH or _busy["on"] or time.time() - _busy["t"] < 60:
        return
    _busy.update(on=True, t=time.time())

    def run():
        try:
            from app.game import arbi
            arbi.tierlist()
            arbi.schedule()
            world.fetch_world(CFG.get("language", "en"))
        except Exception as e:
            from app.core import logbus
            logbus.error("world", f"tracked activities: {type(e).__name__}: {e}")
        finally:
            _busy["on"] = False
    threading.Thread(target=run, daemon=True, name="world-track").start()


def fissure_key(f) -> str:
    kind = "sp" if f.get("isHard") else "storm" if f.get("isStorm") else "normal"
    return f"fissure:{f.get('tier') or '?'}:{f.get('missionType') or '?'}:{kind}"


def items(ws, now=None) -> list:
    """Every activity that can be followed now: [{"key","group","label","detail","expiry","starts"}] (expiry / starts:
    epoch seconds or None). One entry per kind of fissure and per invasion reward (with every open one in "list")."""
    from app.game import arbi
    now = now or time.time()
    out = []
    ws = ws or {}
    for key, name in CYCLES:
        c = ws.get(key)
        if isinstance(c, dict) and ts(c.get("expiry")):
            out.append({"key": "cycle:" + name, "group": "cycles", "name": name, "state": str(c.get("state") or ""),
                        "expiry": ts(c.get("expiry"))})
    b = ws.get("voidTrader")
    if isinstance(b, dict):
        out.append({"key": "baro", "group": "events", "name": "baro", "state": str(b.get("location") or ""),
                    "starts": ts(b.get("activation")), "expiry": ts(b.get("expiry"))})
    for key, name in (("sortie", "sortie"), ("archonHunt", "archon")):
        s = ws.get(key)
        if isinstance(s, dict) and ts(s.get("expiry")):
            out.append({"key": name, "group": "events", "name": name,
                        "state": " · ".join(x for x in (str(s.get("boss") or ""), str(s.get("faction") or "")) if x),
                        "expiry": ts(s.get("expiry"))})
    # Arbitration: now, and the next one of a tier
    try:                                               # what is in memory or on disk: never a download here (UI thread)
        rows = arbi._sched.get("rows")
        if rows is None:
            rows = arbi._parse_schedule(arbi.SCHEDULE_FILE.read_text(encoding="utf-8")) if arbi.SCHEDULE_FILE.exists() else []
        tiers = arbi._load_cache()
    except Exception:
        rows, tiers = [], None
    cur = arbi.current(rows, now) if rows else None
    if cur:
        info = arbi.node_info(cur[0]) or [cur[0], "", "", ""]
        tier = arbi.tier_of(tiers, cur[0], "")[0] if tiers else ""
        out.append({"key": "arbi", "group": "events", "name": "arbi",
                    "state": f"{info[2]} · {info[0]} ({info[1]})" + (f" · {tier}" if tier else ""), "expiry": cur[2]})
    order = {"S": 0, "A": 1, "B": 2, "C": 3}
    for want in ("S", "A", "B"):
        nxt = None
        for i, (start, node) in enumerate(rows or []):
            if start <= now:
                continue
            tier = arbi.tier_of(tiers, node, "")[0] if tiers else ""
            if tier in order and order[tier] <= order[want]:
                info = arbi.node_info(node) or [node, "", "", ""]
                nxt = {"key": "arbi_next:" + want, "group": "events", "name": "arbi_next", "tier": want,
                       "state": f"{info[2]} · {info[0]} ({info[1]}) · {tier}", "starts": start,
                       "expiry": rows[i + 1][0] if i + 1 < len(rows) else start + 3600}
                break
        if nxt:
            out.append(nxt)
    # fissures: one entry per kind, with every open one
    kinds = {}
    for f in ws.get("fissures") or []:
        if not isinstance(f, dict) or f.get("expired") or not ts(f.get("expiry")):
            continue
        k = fissure_key(f)
        e = kinds.setdefault(k, {"key": k, "group": "fissures", "name": "fissure", "tier": f.get("tier") or "?",
                                 "mission": f.get("missionType") or "?",
                                 "kind": "sp" if f.get("isHard") else "storm" if f.get("isStorm") else "normal", "list": []})
        e["list"].append({"node": str(f.get("node") or ""), "enemy": str(f.get("enemy") or ""), "expiry": ts(f.get("expiry"))})
    for e in kinds.values():
        e["list"].sort(key=lambda x: x["expiry"])
        e["expiry"] = e["list"][-1]["expiry"]
        out.append(e)
    # invasions: one entry per reward
    rewards = {}
    for i in ws.get("invasions") or []:
        if not isinstance(i, dict) or i.get("completed"):
            continue
        for side in ("attacker", "defender"):
            r = i.get(side + "Reward") if isinstance(i.get(side + "Reward"), dict) else (i.get(side) or {}).get("reward") \
                if isinstance(i.get(side), dict) else None
            name = ""
            if isinstance(r, dict):
                items_ = r.get("countedItems") or []
                name = ", ".join(f"{x.get('count', 1)} {x.get('type')}" if x.get("count", 1) > 1 else str(x.get("type"))
                                 for x in items_ if isinstance(x, dict) and x.get("type"))
                name = name or str(r.get("asString") or "")
            if not name:
                continue
            base = name.split(" ", 1)[1] if name.split(" ", 1)[0].isdigit() and " " in name else name
            e = rewards.setdefault("invasion:" + base, {"key": "invasion:" + base, "group": "invasions", "name": "invasion",
                                                       "reward": base, "list": []})
            e["list"].append({"node": str(i.get("node") or ""), "progress": float(i.get("completion") or 0), "reward": name})
    out.extend(rewards.values())
    return out


def followed(ws, now=None) -> list:
    """The followed activities as they are now (items() of the followed keys), plus the followed ones not running now
    ({"key", "missing": True}: a fissure kind with none open, an invasion reward with no invasion)."""
    keys = tracked()
    have = {e["key"]: e for e in items(ws, now)}
    return [have.get(k) or {"key": k, "missing": True} for k in keys]


def _tr(key, default):
    from app.core.i18n import t
    s = t(key)
    return default if s == key else s


def left(seconds) -> str:
    s = max(0, int(seconds))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s % 60:02d}s"


def title(e) -> str:
    """The activity's name ("Cetus", "Omnia Survival (Steel Path)", "Invasions: Orokin Catalyst")."""
    from app.core.i18n import t
    k = e["key"]
    if k.startswith("cycle:"):
        n = k.split(":", 1)[1]
        return _tr("strip." + n, _tr("wt.cycle." + n, n.title()))
    if k.startswith("fissure:"):
        _f, tier, mission, kind = (k.split(":") + ["", "", ""])[:4]
        tag = {"sp": " (" + t("wt.sp") + ")", "storm": " (" + t("wt.storm") + ")"}.get(kind, "")
        return t("wt.fissure", tier=tier, mission=mission) + tag
    if k.startswith("invasion:"):
        return t("wt.invasion", reward=k.split(":", 1)[1])
    if k.startswith("arbi_next:"):
        return t("wt.arbi_next", tier=k.split(":", 1)[1])
    return t("wt." + k)


def text(e, now=None) -> str:
    """One line for the overlay and the World tab: what it is, its state now and the live countdown."""
    from app.core.i18n import t
    now = now or time.time()
    name = title(e)
    if e.get("missing"):
        return f"{name}: " + t("wt.none")
    k = e["key"]
    if k.startswith("cycle:"):
        st = e.get("state") or ""
        return f"{name}: {_tr('cycle.' + st, st)} · {left(e['expiry'] - now)}"
    if k == "baro":
        if e.get("starts") and e["starts"] > now:
            return f"{name}: " + t("wt.baro.in", left=left(e["starts"] - now), loc=e.get("state") or "?")
        return f"{name}: " + t("wt.baro.here", loc=e.get("state") or "?", left=left((e.get("expiry") or now) - now))
    if k.startswith("arbi_next:"):
        return f"{name}: {e['state']} · " + t("wt.in", left=left(e["starts"] - now))
    if k.startswith("fissure:"):
        lst = [x for x in e.get("list") or [] if x["expiry"] > now]
        if not lst:
            return f"{name}: " + t("wt.none")
        return f"{name}: " + ", ".join(f"{x['node']} {left(x['expiry'] - now)}" for x in lst[:3]) \
            + (f" (+{len(lst) - 3})" if len(lst) > 3 else "")
    if k.startswith("invasion:"):
        return f"{name}: " + ", ".join(f"{x['node']} {x['progress']:.0f}%" for x in (e.get("list") or [])[:3])
    exp = e.get("expiry")
    return f"{name}: {e.get('state') or ''}" + (f" · {left(exp - now)}" if exp else "")


def soon(e, now=None) -> bool:
    """True when it ends (or starts) within 10 minutes: shown in the "soon" colour."""
    now = now or time.time()
    when = e.get("starts") if e.get("starts") and e["starts"] > now else e.get("expiry")
    return bool(when) and 0 < when - now <= 600
