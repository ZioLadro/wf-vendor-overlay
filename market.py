"""warframe.market client: catalog, fuzzy match, prices (v2) and volumes (v1).

Respects the 3 requests/second limit and caches everything.
NB: volumes use the v1 endpoint /items/{slug}/statistics (deprecated but alive);
if it stops working the overlay only shows the price.
"""
import json
import os
import re
import statistics
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from config import APP_DIR, CFG
from matcher import Match, Matcher, norm  # noqa: F401  (norm/Match riesportati)
from vendors import BARO, VendorIndex

BASE = "https://api.warframe.market/v2"
V1 = "https://api.warframe.market/v1"
HEADERS = {
    "Language": "en",
    "Platform": "pc",
    "Crossplay": "true",
    "Accept": "application/json",
    "User-Agent": "WFVendorOverlay/1.2",
}
CACHE_FILE = APP_DIR / "items_cache.json"
STORE_FILE = APP_DIR / "prices.json"   # collected prices/volumes (persistent)
HIST_MIN_GAP = 900                         # at most one history entry every 15 minutes
HIST_MAX = 48                              # history entries per item
PRUNE_AGE = 30 * 24 * 3600                 # forget items not updated for 30 days
CATALOG_TTL = 24 * 3600
MIN_INTERVAL = 0.35  # ~2.9 requests/s

class Market:
    def __init__(self):
        self._lock = threading.Lock()
        self._last = 0.0
        self._store_lock = threading.Lock()
        self._data = {}      # slug -> {"price","pmax","pt","vol","vt","hist"}
        self._info = {}      # slug -> {"name","max_rank","kind"}
        self._dirty = False
        self._matcher = Matcher([])
        self.vendors = None          # VendorIndex: which vendors sell each item
        self._name_slug = {}         # normalised name -> slug
        self._load_store()
        self._load_catalog()

    # ---------- HTTP ----------
    def throttle(self):
        """Blocks until the next request is allowed (shared by every call to warframe.market)."""
        with self._lock:
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def _request(self, url: str):
        for attempt in range(2):
            self.throttle()
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 429 and attempt == 0:
                time.sleep(1.5)
                continue
            r.raise_for_status()
            return r.json()

    def _get(self, path: str):
        return self._request(BASE + path)["data"]

    # ---------- catalog ----------
    @staticmethod
    def _kind(tags) -> str:
        if "mod" in tags:
            return "mod"
        if "arcane_enhancement" in tags or "arcane" in tags:
            return "arcane"
        return "other"

    @staticmethod
    def _category(name: str, tags) -> str:
        """Inventory category (set / relic / mod / arcane / warframe_part / weapon_part / other),
        from the market tags with the item name as a fallback."""
        tags = {str(x).lower() for x in tags}
        if "set" in tags or name.endswith(" Set"):
            return "set"
        if "relic" in tags or name.endswith(" Relic"):
            return "relic"
        if "mod" in tags:
            return "mod"
        if "arcane_enhancement" in tags or "arcane" in tags:
            return "arcane"
        if tags & {"component", "blueprint"} or re.search(r"\bBlueprint$", name):
            if "warframe" in tags:
                return "warframe_part"
            if tags & {"primary", "secondary", "melee", "archwing", "sentinel", "companion", "weapon",
                       "kitgun", "zaw", "necramech", "robotic"}:
                return "weapon_part"
        return "other"

    def _load_catalog(self):
        rows = None
        if CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < CATALOG_TTL:
            try:
                rows = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                if not all(isinstance(r, list) and len(r) >= 7 for r in rows):
                    rows = None          # cache from an older version (no id/category)
            except Exception:
                rows = None
        if rows is None:
            rows = []
            for it in self._get("/items"):
                name = (it.get("i18n", {}).get("en", {}) or {}).get("name") or it.get("name")
                if name and it.get("slug"):
                    tags = it.get("tags") or []
                    rows.append([name, it["slug"], int(it.get("maxRank") or 0), self._kind(tags),
                                 it.get("id") or "", self._category(name, tags), it.get("vaulted")])
            CACHE_FILE.write_text(json.dumps(rows), encoding="utf-8")
        self._info = {r[1]: {"name": r[0], "max_rank": r[2],
                            "kind": "other" if r[3] == "altro" else r[3],
                            "id": r[4], "category": r[5], "vaulted": r[6]} for r in rows}
        self._matcher = Matcher(rows)
        self._name_slug = {norm(r[0]): r[1] for r in rows}
        self.vendors = VendorIndex(self._name_slug)
        self._migrate()

    def _migrate(self):
        """Data saved by versions without the max-rank price: for mods/arcanes the old price
        mixed all ranks, so it is dropped (it will be collected again)."""
        with self._store_lock:
            for slug, e in self._data.items():
                if self._info.get(slug, {}).get("max_rank", 0) > 0 and "pmax" not in e:
                    e["price"] = None
                    e.pop("pt", None)
                    self._dirty = True

    def info(self, slug: str) -> dict:
        return self._info.get(slug, {})

    def slug_for_name(self, name: str):
        """Market slug for an item name (exact match after normalisation), or None."""
        return self._name_slug.get(norm(name))

    # ---------- matching ----------
    def pairs(self):
        return self._matcher.pairs

    def match(self, text: str, threshold: int = 90):
        return self._matcher.match(text, threshold)

    # ---------- persistent store ----------
    def _load_store(self):
        try:
            data = json.loads(STORE_FILE.read_text(encoding="utf-8")).get("prices", {})
        except Exception:
            data = {}
        now = time.time()
        self._data = {
            slug: e for slug, e in data.items()
            if isinstance(e, dict) and now - max(e.get("pt") or 0, e.get("vt") or 0) < PRUNE_AGE
        }

    def _store(self, slug: str, **kw):
        now = time.time()
        with self._store_lock:
            e = self._data.setdefault(slug, {})
            if "price" in kw:
                e["price"], e["pmax"], e["pt"] = kw["price"], kw.get("pmax"), now
            if "vol" in kw:
                e["vol"], e["vt"] = kw["vol"], now
            hist = e.setdefault("hist", [])
            if not hist or now - hist[-1][0] >= HIST_MIN_GAP:
                hist.append([int(now), e.get("price"), e.get("vol"), e.get("pmax")])
                del hist[:-HIST_MAX]
            self._dirty = True

    def flush(self):
        """Saves to disk (atomic write) if anything changed."""
        with self._store_lock:
            if not self._dirty:
                return
            payload = {"version": 1, "saved": int(time.time()), "prices": self._data}
            tmp = STORE_FILE.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
                os.replace(tmp, STORE_FILE)
                self._dirty = False
            except OSError:
                pass

    def cached(self, slug: str):
        """Last known data (even if old): {"price","pmax","pt","vol","vt"} or None."""
        with self._store_lock:
            e = self._data.get(slug)
            return {k: e.get(k) for k in ("price", "pmax", "pt", "vol", "vt")} if e else None

    def snapshot(self, only=None) -> list:
        """The price-list items: those with a standing cost, plus Baro Ki'Teer's (even without market data).
        `only`: a collection of slugs to restrict the result to (much cheaper than the whole list)."""
        rows = []
        by_slug = self.vendors.by_slug if self.vendors else {}
        standing = self.vendors.standing if self.vendors else {}
        with self._store_lock:
            for slug in (set(by_slug) if only is None else set(only) & set(by_slug)):
                if slug not in standing and BARO not in by_slug[slug]:
                    continue                    # no standing cost and not Baro's: not listed
                e = self._data.get(slug, {})
                info = self._info.get(slug, {})
                times = [t for t in (e.get("pt"), e.get("vt")) if t]
                rows.append({
                    "slug": slug,
                    "name": info.get("name") or slug.replace("_", " ").title(),
                    "kind": info.get("kind", "other"),
                    "ranked": info.get("max_rank", 0) > 0,
                    "max_rank": info.get("max_rank", 0),
                    "price": e.get("price"), "pmax": e.get("pmax"), "vol": e.get("vol"),
                    "updated": max(times) if times else None,
                    "vendors": by_slug.get(slug, []),
                    "standing": standing.get(slug, []),
                })
        rows.sort(key=lambda r: r["name"].lower())
        return rows

    def vendor_names(self) -> list:
        """Vendors that still have items in the list (those paying in other currencies drop out)."""
        if not self.vendors:
            return []
        return sorted({v for slug, vs in self.vendors.by_slug.items()
                       if slug in self.vendors.standing or BARO in vs for v in vs
                       if v == BARO or any(e["v"] == v for e in self.vendors.standing.get(slug, []))})

    def refresh_many(self, slugs, cancel, progress=None, max_age=0):
        """Updates price and volume of the given items one after the other (3 requests/s limit).

        cancel: threading.Event to stop. progress(done, total, errors) after every item.
        max_age: skip data newer than this many seconds (0 = force the update).
        Returns (done, errors, interrupted)."""
        slugs = list(slugs)
        done = errors = streak = 0
        for i, slug in enumerate(slugs):
            if cancel.is_set():
                break
            failed = False
            for fn in (self.prices, self.volume_24h):
                if cancel.is_set():
                    break
                try:
                    fn(slug, max_age)
                except Exception:
                    failed = True
            errors += failed
            streak = streak + 1 if failed else 0
            done = i + 1
            if progress:
                progress(done, len(slugs), errors)
            if done % 15 == 0:
                self.flush()
            if streak >= 8:               # no network or API unreachable: pointless to insist
                break
        self.flush()
        return done, errors, cancel.is_set() or done < len(slugs)

    def _fresh(self, slug: str, key: str, max_age):
        max_age = CFG["refresh_interval"] if max_age is None else max_age
        with self._store_lock:
            e = self._data.get(slug)
            return bool(e and e.get(key) and time.time() - e[key] < max_age)

    # ---------- prices ----------
    @staticmethod
    def _low3(values):
        values = sorted(values)
        return int(statistics.median(values[:3])) if values else None

    def prices(self, slug: str, max_age=None):
        """(price, max_rank_price): median of the 3 lowest sell orders from online/in-game users.
        For mods and arcanes `price` is the rank 0 one and the second value is at max rank;
        for every other item the second value is None.
        Uses the saved data if it is less than max_age seconds old."""
        mr = self._info.get(slug, {}).get("max_rank", 0)
        if self._fresh(slug, "pt", max_age):
            with self._store_lock:
                e = self._data[slug]
                if mr == 0 or "pmax" in e:
                    return e.get("price"), e.get("pmax")
        orders = self._get(f"/orders/item/{slug}")
        sells = [o for o in orders
                 if o.get("type") == "sell"
                 and (o.get("user") or {}).get("status") in ("online", "ingame")]
        if mr > 0:
            base = self._low3(o["platinum"] for o in sells if (o.get("rank") or 0) == 0)
            top = self._low3(o["platinum"] for o in sells if o.get("rank") == mr)
        else:
            base, top = self._low3(o["platinum"] for o in sells), None
        self._store(slug, price=base, pmax=top)
        return base, top

    def price(self, slug: str, max_age=None):
        return self.prices(slug, max_age)[0]

    # ---------- volumes ----------
    def volume_24h(self, slug: str, max_age=None):
        """Number of trades closed in the last 24 hours."""
        if self._fresh(slug, "vt", max_age):
            return self._data[slug]["vol"]
        data = self._request(f"{V1}/items/{slug}/statistics")
        rows = data["payload"]["statistics_closed"]["48hours"]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        total = 0
        for r in rows:
            t = datetime.fromisoformat(str(r["datetime"]).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if t >= cutoff:
                total += int(r.get("volume") or 0)
        self._store(slug, vol=total)
        return total
