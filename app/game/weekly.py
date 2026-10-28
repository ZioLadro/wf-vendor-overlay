"""Vendor offers with a purchase limit (most reset every week: Teshin's Steel Path offers, Ironwake, Nightcap, Archimedean,
Acrithis…): what each one offers (weekly.json, made by build_weekly.py from the game data) and what you bought this period.

What you bought comes from AlecaFrame's lastData.dat ("RecentVendorPurchases": per vendor, each limited purchase with the
number bought and when its limit resets). The file does not say WHICH offer it was (only an id the game servers make up when
the vendor's stock rotates), so the program works it out: when a new purchase appears, it looks at what AlecaFrame recorded
as gained in deltas.dat (the last mission / visit, item by item) and at your inventory against the previous sync, and keeps
the vendor's limited offers whose item came in (see Weekly.guess). One candidate left: assigned. Several (or none): you
are asked to pick it, with the last place you were in (LastRegionPlayed) as a hint, since many of these vendors are on one
planet or hub only. Your answers and the tracked offers are kept in weekly_state.json."""
import json
import sys
import threading
import time
from pathlib import Path

from app.core.config import APP_DIR
from app.core.paths import DATA

DATA_FILE = DATA / "weekly.json"
STATE_FILE = APP_DIR / "weekly_state.json"
UNKNOWN = "?"
SKIP = "skip"                         # "I do not know / not important": the purchase is left out

_data = None
_lock = threading.Lock()
_raw_cache = {"key": None, "inv": None}


def data() -> dict:
    """{manifest path: {"name", "items": [{"id","store","path","name","qty","limit","hours","cost"}]}}. "id" tells apart two
    offers of the same item in different amounts (Teshin sells Kuva ×10,000 and ×50,000)."""
    global _data
    if _data is None:
        try:
            _data = json.loads(DATA_FILE.read_text(encoding="utf-8")).get("vendors") or {}
        except Exception:
            _data = {}
        from app.game.weekly_ocr import ALIASES
        for v in _data.values():
            for i in v.get("items", []):
                i["id"] = f"{i['store']}#{i['qty']}"
                i["name"] = ALIASES.get(i["name"], i["name"])      # the name the game shows (Requiem I Relic…)
    return _data


def offer_key(vendor: str, offer: str) -> str:
    return f"{vendor}|{offer}"


def raw_inventory(path: str):
    """The decrypted lastData.dat (re-read only when the file changed). In the program it comes from the shared background
    reader (app/game/gamefile.py), so nothing is decrypted on the window's thread."""
    import os
    try:
        from app.game import gamefile
        gf = gamefile._gf
        if gf is not None and gf.timer.isActive():
            d = gf.data(path)
            if d is not None or os.path.normcase(gf.path() or "") == os.path.normcase(path):
                return d                        # still being read: the next look will have it
    except Exception:
        pass
    import os
    from app.game import inventory as I
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, st.st_mtime_ns, st.st_size)
    if _raw_cache["key"] != key:
        raw = Path(path).read_bytes()
        text = I.decrypt_last_data(raw) if path.lower().endswith(".dat") else I.unwrap_inventory(raw.decode("utf-8-sig"))
        _raw_cache["key"], _raw_cache["inv"] = key, json.loads(text)
    return _raw_cache["inv"]


_deltas_cache = {"key": None, "d": None}


def read_deltas(last_data_path: str) -> dict:
    """AlecaFrame's deltas.dat next to lastData.dat: {item path: amount gained since its previous state} ({} if absent)."""
    import os
    from app.game import inventory as I
    p = Path(last_data_path).with_name("deltas.dat")
    try:
        st = os.stat(p)
    except OSError:
        return {}
    key = (str(p), st.st_mtime_ns, st.st_size)
    if _deltas_cache["key"] != key:
        try:
            d = json.loads(I.decrypt_last_data(p.read_bytes()))
            cd = d.get("currentDeltas") if isinstance(d, dict) else None
            _deltas_cache["d"] = {k: int(v) for k, v in (cd or {}).items() if isinstance(v, (int, float))}
        except Exception:
            _deltas_cache["d"] = {}
        _deltas_cache["key"] = key
    return _deltas_cache["d"]


def counts(inv: dict) -> dict:
    """How many of every item type you own (stackable items by count, the others one each)."""
    out = {}
    for lst in inv.values():
        if isinstance(lst, list):
            for it in lst:
                if isinstance(it, dict) and isinstance(it.get("ItemType"), str):
                    n = it.get("ItemCount")
                    out[it["ItemType"]] = out.get(it["ItemType"], 0) + (int(n) if isinstance(n, (int, float)) else 1)
    for k in ("PremiumCredits", "RegularCredits"):
        if isinstance(inv.get(k), (int, float)):
            out[k] = int(inv[k])
    return out


def purchases(inv: dict, now=None) -> list:
    """Limited purchases still counting this period: [{"vendor","id","n","expiry"}] (only vendors with limited offers)."""
    now = time.time() if now is None else now
    out = []
    for v in inv.get("RecentVendorPurchases") or []:
        vend = v.get("VendorType") if isinstance(v, dict) else None
        if vend not in data():
            continue
        for p in v.get("PurchaseHistory") or []:
            try:
                exp = int(p["Expiry"]["$date"]["$numberLong"]) / 1000
            except (KeyError, TypeError, ValueError):
                continue
            if now < exp < now + 35 * 86400:     # a far-off expiry = an event's lifetime limit, not a periodic one
                out.append({"vendor": vend, "id": str(p.get("ItemId") or ""), "n": int(p.get("NumPurchased") or 0),
                            "expiry": exp})
    return out


class Weekly:
    def __init__(self):
        self.assign, self.tracked, self.snapshot, self.candidates = {}, set(), {}, {}
        self.ocr = {}                     # what the vendor screens showed (weekly_ocr.py): {vendor: {"seen","gone","views"}}
        self.region = ""
        try:
            d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.assign = dict(d.get("assign") or {})
            self.tracked = set(d.get("tracked") or [])
            self.snapshot = dict(d.get("snapshot") or {})
            self.candidates = dict(d.get("candidates") or {})
            self.ocr = {k: v for k, v in (d.get("ocr") or {}).items() if isinstance(v, dict)}
        except Exception:
            pass
        self.current = []
        self.version = 0

    def save(self):
        try:
            STATE_FILE.write_text(json.dumps({"assign": self.assign, "tracked": sorted(self.tracked),
                                              "snapshot": self.snapshot, "candidates": self.candidates,
                                              "ocr": self.ocr},
                                             ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def guess(items, cur, snapshot, deltas, n):
        """(offer or None, candidates, how). Evidence, most precise first:
        1. deltas.dat: what AlecaFrame recorded as gained since its previous state (the last mission / visit), item by
           item. An offer whose item was gained in an exact multiple of the offer's amount × purchases is the best match
           (Kuva ×10,000 bought once = +10,000 exactly); then any offer whose item was gained at least once.
        2. the inventory compared with the previous sync (this program's own copy): items that went up.
        The two are combined: when the deltas leave several offers, the ones that also went up in the inventory win."""
        items = list({i["id"]: i for i in items}.values())     # the same offer listed twice (Teshin's Kuva) is one
        d_any = [i for i in items if deltas.get(i["path"], 0) >= i["qty"]] if deltas else []
        d_exact = [i for i in d_any if deltas[i["path"]] % i["qty"] == 0 and deltas[i["path"]] >= i["qty"] * max(1, n)]
        d_equal = [i for i in d_exact if deltas[i["path"]] == i["qty"] * max(1, n)]     # exactly what was bought
        s_up = [i for i in items if cur.get(i["path"], 0) > snapshot.get(i["path"], 0)] if snapshot else []
        s_ids = {i["id"] for i in s_up}
        for pool, how in ((d_equal, "deltas"), (d_exact, "deltas"), ([i for i in d_exact if i["id"] in s_ids], "deltas+inventory"),
                          (d_any, "deltas"), ([i for i in d_any if i["id"] in s_ids], "deltas+inventory")):
            if len(pool) == 1:
                return pool[0], [pool[0]["id"]], how
        if not deltas and len(s_up) == 1:
            return s_up[0], [s_up[0]["id"]], "inventory"
        cands = d_exact or d_any or s_up
        return None, [i["id"] for i in cands], ""

    def sync(self, inv: dict, deltas: dict | None = None) -> list:
        """Reads the purchases of the game file (and AlecaFrame's deltas.dat, when there); works out the new ones.
        Returns the purchases needing your answer."""
        from app.core import logbus
        with _lock:
            now = time.time()
            cur = counts(inv)
            self.region = str(inv.get("LastRegionPlayed") or "")
            self.current = purchases(inv, now)
            changed = False
            for p in self.current:
                k = f"{p['vendor']}|{p['id']}"
                if k in self.assign:
                    continue
                items = data()[p["vendor"]]["items"]
                offer, cands, how = self.guess(items, cur, self.snapshot, deltas or {}, p["n"])
                if offer:
                    self.assign[k] = offer["id"]
                    logbus.add("weekly", f"{data()[p['vendor']]['name']}: purchase recognised as {offer['name']} "
                               f"(from {how})", "ok")
                else:
                    self.assign[k] = UNKNOWN
                    self.candidates[k] = cands
                    logbus.add("weekly", f"{data()[p['vendor']]['name']}: new limited purchase to identify "
                               f"({len(cands)} candidates from deltas.dat and the inventory)", "warn")
                changed = True
            live = {f"{p['vendor']}|{p['id']}" for p in self.current}
            for k in [k for k in self.assign if k not in live]:        # reset: the purchase no longer counts
                self.assign.pop(k, None)
                self.candidates.pop(k, None)
                changed = True
            if cur != self.snapshot:
                self.snapshot = cur
                changed = True
            if changed:
                self.version += 1
                self.save()
            return self.unknown()

    def ocr_scan(self, texts) -> bool:
        """The text read on the screen by a vendor scan: checks the limited offers shown (weekly_ocr.py). True when
        something changed."""
        from app.core import logbus
        from app.game import weekly_ocr as WO
        seen = WO.read(texts)
        if not seen:
            return False
        with _lock:
            before = json.dumps([self.assign, self.candidates, {v: sorted(x.get("gone", {})) for v, x in self.ocr.items()}],
                                sort_keys=True)
            log = WO.apply(self, seen)
            name = data()[seen["vendor"]]["name"]
            for line in log:
                logbus.add("weekly", f"{name}: {line}", "ok")
            after = json.dumps([self.assign, self.candidates, {v: sorted(x.get("gone", {})) for v, x in self.ocr.items()}],
                               sort_keys=True)
            self.save()
            if before != after:
                self.version += 1
                return True
            return False

    def unknown(self) -> list:
        """Purchases to identify: [{"key","vendor","vendor_name","n","expiry","candidates": [store…], "items": [...]}]."""
        out = []
        for p in self.current:
            k = f"{p['vendor']}|{p['id']}"
            if self.assign.get(k) == UNKNOWN:
                v = data()[p["vendor"]]
                cand = self.candidates.get(k) or []
                items = sorted(v["items"], key=lambda i: (i["id"] not in cand, i["name"].lower(), i["qty"]))
                out.append(dict(p, key=k, vendor_name=v["name"], candidates=cand, items=items))
        return out

    def identify(self, key: str, offer: str):
        with _lock:
            self.assign[key] = offer
            self.candidates.pop(key, None)
            self.version += 1
            self.save()

    def track(self, vendor: str, offer: str, on: bool):
        k = offer_key(vendor, offer)
        (self.tracked.add if on else self.tracked.discard)(k)
        self.version += 1
        self.save()

    def offers(self, weekly_only=True) -> list:
        """Every limited offer with what you bought this period: [{"vendor","vendor_name","store","name","qty","limit",
        "hours","cost","bought","expiry","tracked"}]."""
        bought, expiry = {}, {}
        for p in self.current:
            offer = self.assign.get(f"{p['vendor']}|{p['id']}")
            if offer and offer not in (UNKNOWN, SKIP):
                k = offer_key(p["vendor"], offer)
                bought[k] = bought.get(k, 0) + p["n"]
                expiry[k] = min(expiry.get(k, p["expiry"]), p["expiry"])
        try:
            from app.game import quests
            ws = quests.cached()
        except Exception:
            ws = None
        active = {vend: vendor_active(vend, ws, self.current) for vend in data()}
        now = time.time()
        gone = {offer_key(v, oid) for v, st in self.ocr.items() for oid, e in (st.get("gone") or {}).items()
                if e.get("until", 0) > now}
        out = []
        for vend, v in data().items():
            for i in v["items"]:
                if weekly_only and i["hours"] < 168:
                    continue
                k = offer_key(vend, i["id"])
                b = bought.get(k, 0)
                # bought out according to the vendor screen, the game file not there yet: shown bought ("OCR")
                ocr = k in gone and b < i["limit"]
                out.append(dict(i, vendor=vend, vendor_name=v["name"], bought=i["limit"] if ocr else b, ocr=ocr,
                                expiry=expiry.get(k), tracked=k in self.tracked, key=k, active=active.get(vend)))
        return out


# vendors that only exist during an event (time gated): shown as active only while the event runs
EVENT_HINT = ("/Events/", "/Prequel/Triad")


def event_keyword(vendor: str) -> str:
    """The word that names the vendor's event in the world state: .../JadeShadowsEventVendorManifest -> JadeShadows."""
    import re
    n = vendor.rstrip("/").rsplit("/", 1)[-1]
    n = re.sub(r"(VendorProducts|Vendor)?Manifest$", "", n)
    n = re.sub(r"(PostEvent|EventClan|Event|Invasion|Exchange|Clan)+$", "", n)
    return n


def vendor_active(vendor: str, ws=None, purchases=(), now=None):
    """True / False for event vendors (an active event in DE's world state mentions it, or a purchase of yours from it
    still counts), None (= always there) for the others."""
    if not any(h in vendor for h in EVENT_HINT):
        return None
    now = time.time() if now is None else now
    if any(p["vendor"] == vendor and p["expiry"] > now for p in purchases):
        return True
    if not ws:
        return False
    kw = event_keyword(vendor).lower()
    if not kw:
        return False
    from app.game.quests import _date
    for g in (ws.get("Goals") or []) + (ws.get("Events") or []):
        if not isinstance(g, dict):
            continue
        start, end = _date(g.get("Activation")), _date(g.get("Expiry"))
        if (start and start > now) or (end and end < now):
            continue
        if kw in json.dumps(g).lower():
            return True
    return False


_weekly = None


def get() -> Weekly:
    global _weekly
    if _weekly is None:
        _weekly = Weekly()
    return _weekly


def next_reset(now=None) -> float:
    """Monday 00:00 UTC after now: when the weekly limits reset."""
    now = time.time() if now is None else now
    day = int(now // 86400)
    weekday = (day + 3) % 7                     # 1970-01-01 was a Thursday: Monday = 0
    return (day - weekday + 7) * 86400
