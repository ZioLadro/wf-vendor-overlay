"""World state (fissures, invasions, Baro, sortie, cycles) from the community mirror api.warframestat.us.
Parsing is tolerant: a missing or renamed field only drops that line."""
import requests

URL = "https://api.warframestat.us/pc"
UA = "WFVendorOverlay/1.6"


_last = {"t": 0.0, "ws": None}


def fetch_world(lang="en", timeout=20.0) -> dict:
    import time
    r = requests.get(URL, params={"language": lang}, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    ws = r.json()
    _last.update(t=time.time(), ws=ws)              # the last world state read (World tab, strip, tracked activities)
    return ws


def last():
    """(time read, world state) of the last download by anyone, or (0, None)."""
    return _last["t"], _last["ws"]


def _g(d, *keys, default=""):
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else None
        if v not in (None, ""):
            return v
    return default


def parse_world(ws: dict) -> list:
    """[(section_key, [row, ...])]; every row is a list of strings."""
    out = []
    cyc = []
    for key in ("earthCycle", "cetusCycle", "vallisCycle", "cambionCycle", "zarimanCycle", "duviriCycle"):
        c = ws.get(key)
        if isinstance(c, dict):
            cyc.append([key.replace("Cycle", ""), str(_g(c, "state", "choices", default="?")), str(_g(c, "timeLeft", "eta"))])
    out.append(("cycles", cyc))
    s = ws.get("sortie")
    rows = []
    if isinstance(s, dict):
        for m in s.get("variants") or s.get("missions") or []:
            rows.append([str(_g(m, "missionType")), str(_g(m, "node")), str(_g(m, "modifier", "modifierDescription"))])
        if rows:
            rows.insert(0, [str(_g(s, "boss")), "", str(_g(s, "eta"))])
    out.append(("sortie", rows))
    fis = []
    for f in ws.get("fissures") or []:
        if isinstance(f, dict) and not f.get("expired"):
            tag = " (SP)" if f.get("isHard") else (" (Storm)" if f.get("isStorm") else "")
            fis.append([str(_g(f, "tier")) + tag, str(_g(f, "missionType")), str(_g(f, "node")), str(_g(f, "eta"))])
    out.append(("fissures", fis))
    inv = []
    for i in ws.get("invasions") or []:
        if isinstance(i, dict) and not i.get("completed"):
            rew = [str(_g(i.get("attacker", {}) if isinstance(i.get("attacker"), dict) else {}, "reward", default="")),
                   str(_g(i.get("attackerReward", {}), "asString", default="")) if isinstance(i.get("attackerReward"), dict) else "",
                   str(_g(i.get("defenderReward", {}), "asString", default="")) if isinstance(i.get("defenderReward"), dict) else ""]
            rew = [x for x in rew if x]
            inv.append([str(_g(i, "node")), str(_g(i, "desc")), " / ".join(rew), f"{float(i.get('completion') or 0):.0f}%"])
    out.append(("invasions", inv))
    return out


def parse_baro(ws: dict):
    """(header, [(item, ducats, credits)]) — header is '' when he's not there / unknown."""
    b = ws.get("voidTrader")
    if not isinstance(b, dict):
        return "", []
    head = f"{_g(b, 'location')} – " + str(_g(b, 'endString' if b.get("active") else 'startString'))
    items = [(str(_g(i, "item", "name")), i.get("ducats"), i.get("credits")) for i in (b.get("inventory") or [])
             if isinstance(i, dict)]
    return head.strip(" –"), items
