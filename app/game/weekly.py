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
            self._first_loaded = dict(d.get("first") or {})
        except Exception:
            pass
        self.current = []
        self.version = 0
        self.first = dict(self._first_loaded) if hasattr(self, "_first_loaded") else {}

    def save(self):
        try:
            STATE_FILE.write_text(json.dumps({"assign": self.assign, "tracked": sorted(self.tracked),
                                              "snapshot": self.snapshot, "candidates": self.candidates,
                                              "ocr": self.ocr, "first": self.first},
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
                    self.first.setdefault(k, now)
                    logbus.add("weekly", f"{data()[p['vendor']]['name']}: new limited purchase to identify "
                               f"({len(cands)} candidates from deltas.dat and the inventory)", "warn")
                changed = True
            live = {f"{p['vendor']}|{p['id']}" for p in self.current}
            for k in [k for k in self.assign if k not in live]:        # reset: the purchase no longer counts
                self.assign.pop(k, None)
                self.candidates.pop(k, None)
                self.first.pop(k, None)
                changed = True
            for p in self.current:                    # purchases to identify from before 0.4.9: seen from now on
                k = f"{p['vendor']}|{p['id']}"
                if self.assign.get(k) == UNKNOWN and k not in self.first:
                    self.first[k] = now
                    changed = True
            if self._refine():
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
        from app.game.eelog import LOCATION
        seen = WO.read(texts, allow=lambda v: LOCATION.allows(v, (data().get(v) or {}).get("name", "")))
        if not seen:
            return False
        with _lock:
            before = json.dumps([self.assign, self.candidates, {v: sorted(x.get("gone", {})) for v, x in self.ocr.items()}],
                                sort_keys=True)
            log = WO.apply(self, seen)
            self._refine()
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

    def possible(self, p, k=None) -> list:
        """The offers a purchase can still be, with everything known (lock held): an offer whose limit is below the number
        bought cannot be it; one already taken by another purchase of the same vendor this period cannot (the game keeps
        one entry per offer); one the vendor screen showed on sale after this purchase appeared, with a limit the number
        bought reaches, cannot. The candidates found from deltas.dat / the inventory are kept when some survive."""
        k = k or f"{p['vendor']}|{p['id']}"
        items = {i["id"]: i for i in data()[p["vendor"]]["items"]}
        taken = {self.assign.get(f"{q['vendor']}|{q['id']}") for q in self.current
                 if q["vendor"] == p["vendor"] and q["id"] != p["id"]} - {UNKNOWN, SKIP, None}
        since = float(self.first.get(k) or 0)
        seen = (self.ocr.get(p["vendor"]) or {}).get("seen") or {}
        ok = [i for i in items.values() if int(i.get("limit") or 1) >= p["n"] and i["id"] not in taken
              and not (i["id"] in seen and seen[i["id"]].get("t", 0) > since and p["n"] >= int(i.get("limit") or 1))]
        cands = [i for i in ok if i["id"] in (self.candidates.get(k) or [])]
        return cands or ok

    def _refine(self) -> bool:
        """Works out more purchases from what is already known (lock held); True when some were assigned.
        - only one offer possible (possible()): it is that one;
        - shop items the game's log named (EE.log, a purchase screen) narrow the possible offers when some match;
        - the vendor screen showed the offer bought out (OCR "gone") and it is among the possible ones: preferred;
        - a group of purchases of one vendor with the same number bought whose possible offers are exactly as many as
          the purchases (4 purchases of 10 at Palladino, 4 relics with a limit of 10): each offer is one of them; which is
          which does not matter, every one was bought that many times."""
        from app.core import logbus
        try:
            from app.game.eelog import LOCATION
            logged = LOCATION.store_items()
        except Exception:
            logged = set()
        changed, again = False, True
        while again:
            again = False
            unk = [p for p in self.current if self.assign.get(f"{p['vendor']}|{p['id']}") == UNKNOWN]
            for p in unk:
                k = f"{p['vendor']}|{p['id']}"
                poss = self.possible(p, k)
                hit = [i for i in poss if i.get("store") in logged]
                gone = set(((self.ocr.get(p["vendor"]) or {}).get("gone") or {}))
                ocr = [i for i in poss if i["id"] in gone]
                for pool, how in ((poss, "the only offer left"), (hit, "the game's log"), (ocr, "the vendor screen")):
                    if len(pool) == 1:
                        self.assign[k] = pool[0]["id"]
                        self.candidates.pop(k, None)
                        logbus.add("weekly", f"{data()[p['vendor']]['name']}: purchase recognised as {pool[0]['name']} "
                                   f"({how})", "ok")
                        changed = again = True
                        break
                else:
                    ids = [i["id"] for i in (hit or ocr or poss)]
                    if ids != self.candidates.get(k):
                        self.candidates[k] = ids
                        changed = True
                if again:
                    break
            if again:
                continue
            groups = {}
            for p in unk:
                groups.setdefault((p["vendor"], p["n"]), []).append(p)
            for (vend, n), ps in groups.items():
                union = {}
                for p in ps:
                    for i in self.possible(p):
                        union[i["id"]] = i
                if len(ps) > 1 and len(union) == len(ps):
                    for p, oid in zip(ps, sorted(union)):
                        self.assign[f"{p['vendor']}|{p['id']}"] = oid
                        self.candidates.pop(f"{p['vendor']}|{p['id']}", None)
                    logbus.add("weekly", f"{data()[vend]['name']}: {len(ps)} purchases of {n} recognised together as "
                               + ", ".join(union[o]["name"] for o in sorted(union)), "ok")
                    changed = again = True
                    break
        return changed

    def unknown(self) -> list:
        """Purchases to identify: [{"key","vendor","vendor_name","n","expiry","candidates": [store…], "items": [...]}]."""
        out = []
        for p in self.current:
            k = f"{p['vendor']}|{p['id']}"
            if self.assign.get(k) == UNKNOWN:
                v = data()[p["vendor"]]
                cand = self.candidates.get(k) or []
                poss = {i["id"] for i in self.possible(p, k)}
                items = sorted(v["items"], key=lambda i: (i["id"] not in cand, i["id"] not in poss, i["name"].lower(), i["qty"]))
                out.append(dict(p, key=k, vendor_name=v["name"], candidates=cand, possible=sorted(poss), items=items))
        return out

    def identify(self, key: str, offer: str):
        with _lock:
            self.assign[key] = offer
            self.candidates.pop(key, None)
            self._refine()                         # one answer can settle others (the offer is no longer free)
            self.version += 1
            self.save()

    def groups(self) -> list:
        """Purchases to identify that can be answered at once: a vendor's purchases with the same number bought whose
        possible offers are just one more than the purchases ("which one did you NOT buy?").
        [{"vendor","vendor_name","n","keys","offers": [items]}]."""
        out = {}
        for u in self.unknown():
            g = out.setdefault((u["vendor"], u["n"]), {"vendor": u["vendor"], "vendor_name": u["vendor_name"], "n": u["n"],
                                                     "keys": [], "ids": set()})
            g["keys"].append(u["key"])
            g["ids"] |= set(u["possible"])
        res = []
        for g in out.values():
            if len(g["keys"]) >= 2 and len(g["ids"]) == len(g["keys"]) + 1:
                items = {i["id"]: i for i in data()[g["vendor"]]["items"]}
                res.append(dict(g, offers=sorted((items[i] for i in g["ids"]), key=lambda i: i["name"].lower())))
        return res

    def identify_group(self, keys, not_bought):
        """Answers a group (groups()): every possible offer but not_bought, one per purchase."""
        with _lock:
            ids = set()
            for p in self.current:
                k = f"{p['vendor']}|{p['id']}"
                if k in keys:
                    ids |= {i["id"] for i in self.possible(p, k)}
            for k, oid in zip(keys, sorted(ids - {not_bought})):
                self.assign[k] = oid
                self.candidates.pop(k, None)
            self._refine()
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
                out.append(dict(i, vendor=vend, vendor_name=v["name"], bought=i["limit"] if ocr else b, ocr=ocr, cat=category(i),
                                expiry=expiry.get(k), tracked=k in self.tracked, key=k, active=active.get(vend)))
        return out


# vendors that only exist during an event (time gated): shown as active only while the event runs
EVENT_HINT = ("/Events/", "/Prequel/Triad")


# offer categories (the Weekly tab's filter): (key, test on the item path / name), first match wins
CATEGORIES = (
    ("kuva", lambda p, n: p.endswith("/MiscItems/Kuva")),
    ("riven", lambda p, n: "/Randomized/" in p or "Riven" in n or p.endswith("/SentientSecretItem")),
    ("arcane", lambda p, n: "/CosmeticEnhancers/" in p),
    ("mod", lambda p, n: "/Upgrades/Mods/" in p and "/FusionBundles/" not in p),
    ("endo_credits", lambda p, n: "/FusionBundles/" in p or "/CreditBundles/" in p or "/FusionTreasures/" in p),
    ("relic", lambda p, n: "/Projections/" in p),
    ("upgrade", lambda p, n: any(x in p for x in ("ArcaneUnlocker", "UtilityUnlocker", "/MiscItems/Forma", "Catalyst", "Reactor",
                                                  "/Focus/", "/NarmerSorties/ArchonCrystal")) or "Adapter" in n),
    ("blueprint", lambda p, n: "/Recipes/" in p or n.endswith("Blueprint")),
    ("weapon", lambda p, n: p.startswith("/Lotus/Weapons/") or "/Powersuits/" in p),
    ("cosmetic", lambda p, n: any(x in p for x in ("/Skins/", "/ShipDecos/", "/AvatarImages/", "/PhotoBooth", "Photobooth",
                                                  "/SongItems/", "/Guild/", "/DangerRoom/"))),
    ("task", lambda p, n: "/Packages/Tasks/" in p or "/CrewMember" in p),
    ("resource", lambda p, n: "/Resources/" in p or "/MiscItems/" in p or "/Gameplay/" in p or "/SyndicateDogTags/" in p
                              or "Pack" in n),
)


def category(item: dict) -> str:
    p, n = str(item.get("path") or ""), str(item.get("name") or "")
    for key, test in CATEGORIES:
        if test(p, n):
            return key
    return "other"


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
