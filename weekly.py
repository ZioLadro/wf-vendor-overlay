"""Vendor offers with a purchase limit (most reset every week: Teshin's Steel Path offers, Ironwake, Nightcap, Archimedean,
Acrithis…): what each one offers (weekly.json, made by build_weekly.py from the game data) and what you bought this period.

What you bought comes from AlecaFrame's lastData.dat ("RecentVendorPurchases": per vendor, each limited purchase with the
number bought and when its limit resets). The file does not say WHICH offer it was (only an id the game servers make up when
the vendor's stock rotates), so the program works it out: when a new purchase appears, it compares your inventory with the
previous sync (AlecaFrame rewrites the file each time you extract or leave a relay, with what the last mission or visit
gave you) and keeps the vendor's limited offers whose item went up. One candidate left: assigned. Several (or none): you
are asked to pick it, with the last place you were in (LastRegionPlayed) as a hint, since many of these vendors are on one
planet or hub only. Your answers and the tracked offers are kept in weekly_state.json."""
import json
import sys
import threading
import time
from pathlib import Path

from config import APP_DIR

DATA_FILE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "weekly.json"
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
        for v in _data.values():
            for i in v.get("items", []):
                i["id"] = f"{i['store']}#{i['qty']}"
    return _data


def offer_key(vendor: str, offer: str) -> str:
    return f"{vendor}|{offer}"


def raw_inventory(path: str):
    """The decrypted lastData.dat (re-read only when the file changed)."""
    import os
    import inventory as I
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
        self.region = ""
        try:
            d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.assign = dict(d.get("assign") or {})
            self.tracked = set(d.get("tracked") or [])
            self.snapshot = dict(d.get("snapshot") or {})
            self.candidates = dict(d.get("candidates") or {})
        except Exception:
            pass
        self.current = []
        self.version = 0

    def save(self):
        try:
            STATE_FILE.write_text(json.dumps({"assign": self.assign, "tracked": sorted(self.tracked),
                                              "snapshot": self.snapshot, "candidates": self.candidates},
                                             ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def sync(self, inv: dict) -> list:
        """Reads the purchases of the game file; works out the new ones. Returns the purchases needing your answer."""
        import logbus
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
                if self.snapshot:
                    went_up = [i for i in items if cur.get(i["path"], 0) > self.snapshot.get(i["path"], 0)]
                else:
                    went_up = []
                if len(went_up) == 1:
                    self.assign[k] = went_up[0]["id"]
                    logbus.add("weekly", f"{data()[p['vendor']]['name']}: purchase recognised as {went_up[0]['name']} "
                               f"(it went up in your inventory)", "ok")
                else:
                    self.assign[k] = UNKNOWN
                    self.candidates[k] = [i["id"] for i in went_up]
                    logbus.add("weekly", f"{data()[p['vendor']]['name']}: new limited purchase to identify "
                               f"({len(went_up)} candidates from the inventory)", "warn")
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
        out = []
        for vend, v in data().items():
            for i in v["items"]:
                if weekly_only and i["hours"] < 168:
                    continue
                k = offer_key(vend, i["id"])
                out.append(dict(i, vendor=vend, vendor_name=v["name"], bought=bought.get(k, 0), expiry=expiry.get(k),
                                tracked=k in self.tracked, key=k))
        return out


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
