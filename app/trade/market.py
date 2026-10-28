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

from app.core.config import APP_DIR, CFG
from app.scan.matcher import Match, Matcher, norm  # noqa: F401  (norm/Match riesportati)
from app.game.vendors import BARO, VendorIndex

from app.core.version import __version__

BASE = "https://api.warframe.market/v2"
V1 = "https://api.warframe.market/v1"
HEADERS = {
    "Language": "en",
    "Platform": "pc",
    "Crossplay": "true",
    "Accept": "application/json",
    "User-Agent": f"WFVendorOverlay/{__version__} (+https://github.com/ZioLadro/wf-vendor-overlay)",
}
CACHE_FILE = APP_DIR / "items_cache.json"
STORE_FILE = APP_DIR / "prices.json"   # collected prices/volumes (persistent)
PRUNE_AGE = 30 * 24 * 3600                 # forget items not updated for 30 days
CATALOG_TTL = 24 * 3600
MIN_INTERVAL = 0.35  # ~2.9 requests/s

def average_prices(rows, max_rank=0):
    """Volume-weighted average closed price over the last 7 / 30 / 90 days from warframe.market's daily statistics:
    ([a7, a30, a90] for rank 0 or unranked items, [a7, a30, a90] for max rank or None). A value is None if no trade fell
    in that window."""
    now = datetime.now(timezone.utc)
    spans = (7, 30, 90)
    acc = {"low": [[0.0, 0] for _ in spans], "top": [[0.0, 0] for _ in spans]}
    for r in rows:
        try:
            when = datetime.fromisoformat(str(r["datetime"]).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            vol = int(r.get("volume") or 0)
            price = r.get("avg_price")
            if price is None:
                price = r.get("median")
            if vol <= 0 or price is None:
                continue
            rank = r.get("mod_rank")
            which = "low" if (not max_rank or rank in (None, 0)) else ("top" if rank == max_rank else None)
            if which is None:
                continue
            age = (now - when).days
            for i, s in enumerate(spans):
                if age < s:
                    acc[which][i][0] += float(price) * vol
                    acc[which][i][1] += vol
        except (KeyError, ValueError, TypeError):
            continue
    out = lambda a: [round(s / n, 1) if n else None for s, n in a]
    top = out(acc["top"]) if max_rank else None
    return out(acc["low"]), (top if top and any(v is not None for v in top) else None)


def max_rank_volumes(rows, max_rank, now=None):
    """(trades at max rank in the last 24 h, average trades per day at max rank over the last 7 days) from the statistics
    rows (48hours / 90days lists); None where nothing could be counted."""
    if not max_rank:
        return None, None
    now = now or datetime.now(timezone.utc)
    d1 = d7 = 0
    seen = False
    for r in rows:
        try:
            if r.get("mod_rank") != max_rank:
                continue
            when = datetime.fromisoformat(str(r["datetime"]).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            vol = int(r.get("volume") or 0)
        except (KeyError, ValueError, TypeError):
            continue
        seen = True
        age = (now - when).total_seconds()
        if age <= 86400:
            d1 += vol
        if age <= 7 * 86400:
            d7 += vol
    return (d1, round(d7 / 7.0, 2)) if seen else (0, 0.0)


SMALL_GAIN = 3          # platinum: a 3-rank mod whose max rank sells for at most this much more is priced at rank 0 only


def effective_pmax(price, pmax, max_rank, volm7=None, min_volume=None):
    """The max-rank price worth showing and counting, or None:
      - mods with only 3 ranks whose max rank sells for at most SMALL_GAIN platinum more than rank 0 (ranking it up is not
        worth it: the rank 0 price is what counts);
      - max rank traded less than `min_volume` times a day over the last week (setting pmax_min_volume; the price of a
        rank nobody buys is not a price). Unknown volume: kept."""
    if pmax is None:
        return None
    if max_rank == 3 and price is not None and pmax - price <= SMALL_GAIN:
        return None
    if min_volume is None:
        try:
            from app.core.config import CFG
            min_volume = float(CFG.get("pmax_min_volume", 0.5))
        except Exception:
            min_volume = 0.5
    if volm7 is not None and min_volume and volm7 < min_volume:
        return None
    return pmax


class Market:
    def __init__(self):
        self._lock = threading.Lock()
        self._last = 0.0
        self._store_lock = threading.Lock()
        self._data = {}      # slug -> {"price","pmax","pt","vol","vt","avg","avgm"}
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
            if r.status_code >= 400:
                from app.core import logbus
                logbus.error("warframe.market", f"HTTP {r.status_code} for {url.split('?')[0].replace(BASE, '')}")
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
                if not all(isinstance(r, list) and len(r) >= 8 for r in rows):
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
                                 it.get("id") or "", self._category(name, tags), it.get("vaulted"),
                                 ((it.get("i18n", {}).get("en", {}) or {}).get("thumb")
                                  or (it.get("i18n", {}).get("en", {}) or {}).get("icon") or "")])
            CACHE_FILE.write_text(json.dumps(rows), encoding="utf-8")
        self._info = {r[1]: {"name": r[0], "max_rank": r[2],
                            "kind": "other" if r[3] == "altro" else r[3],
                            "id": r[4], "category": r[5], "vaulted": r[6],
                            "thumb": r[7] if len(r) > 7 else ""} for r in rows}
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

    def catalog_names(self, kinds=None) -> list:
        """[(name, slug)] of the catalog, optionally only the given kinds ("mod", "arcane", "other")."""
        return [(i["name"], s) for s, i in self._info.items() if kinds is None or i.get("kind") in kinds]

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
        # older versions kept a per-item history nobody read (most of the file): dropped, saved without it next time
        for e in self._data.values():
            if e.pop("hist", None) is not None:
                self._dirty = True

    def _store(self, slug: str, **kw):
        now = time.time()
        with self._store_lock:
            e = self._data.setdefault(slug, {})
            if "price" in kw:
                e["price"], e["pmax"], e["pt"] = kw["price"], kw.get("pmax"), now
                if "bid" in kw:
                    e["bid"] = kw["bid"]
            if "vol" in kw:
                e["vol"], e["vt"] = kw["vol"], now
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
            if not e:
                return None
            out = {k: e.get(k) for k in ("price", "pmax", "pt", "vol", "vt", "avg", "avgm", "volm", "volm7", "bid", "ind")}
        out["pmax_raw"] = out["pmax"]
        out["pmax"] = effective_pmax(out["price"], out["pmax"], self._info.get(slug, {}).get("max_rank", 0), out["volm7"])
        return out

    def snapshot(self, only=None) -> list:
        """The price-list items: those with a standing cost, plus Baro Ki'Teer's (even without market data).
        `only`: a collection of slugs to restrict the result to (much cheaper than the whole list)."""
        from app.game.standing import is_hidden
        rows = []
        by_slug = self.vendors.by_slug if self.vendors else {}
        standing = self.vendors.standing if self.vendors else {}
        hidden_vendors = {e["v"] for es in standing.values() for e in es if is_hidden(e.get("t"))}
        with self._store_lock:
            for slug in (set(by_slug) if only is None else set(only) & set(by_slug)):
                entries = [e for e in standing.get(slug, []) if not is_hidden(e.get("t"))]   # e.g. Operational Supply
                if not entries and BARO not in by_slug[slug]:
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
                    "price": e.get("price"), "vol": e.get("vol"), "pmax_raw": e.get("pmax"),
                    "pmax": effective_pmax(e.get("price"), e.get("pmax"), info.get("max_rank", 0), e.get("volm7")),
                    "updated": max(times) if times else None,
                    "vendors": [v for v in by_slug.get(slug, []) if v not in hidden_vendors],
                    "standing": entries, "avg": e.get("avg"), "bid": e.get("bid"), "ind": e.get("ind"),
                })
        rows.sort(key=lambda r: r["name"].lower())
        return rows

    def vendor_names(self) -> list:
        """Vendors that still have items in the list (those paying in other currencies drop out)."""
        if not self.vendors:
            return []
        from app.game.standing import is_hidden
        return sorted({v for slug, vs in self.vendors.by_slug.items()
                       if slug in self.vendors.standing or BARO in vs for v in vs
                       if v == BARO or any(e["v"] == v and not is_hidden(e.get("t"))
                                           for e in self.vendors.standing.get(slug, []))})

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
                    return e.get("price"), effective_pmax(e.get("price"), e.get("pmax"), mr, e.get("volm7"))
        orders = self._get(f"/orders/item/{slug}")
        sells = [o for o in orders
                 if o.get("type") == "sell"
                 and (o.get("user") or {}).get("status") in ("online", "ingame")]
        if mr > 0:
            base = self._low3(o["platinum"] for o in sells if (o.get("rank") or 0) == 0)
            top = self._low3(o["platinum"] for o in sells if o.get("rank") == mr)
        else:
            base, top = self._low3(o["platinum"] for o in sells), None
        # the best price a buyer online pays right now (rank 0): what an instant sale gets (see signals.py)
        bids = [o["platinum"] for o in orders if o.get("type") == "buy"
                and (o.get("user") or {}).get("status") in ("online", "ingame") and (mr == 0 or (o.get("rank") or 0) == 0)]
        self._store(slug, price=base, pmax=top, bid=max(bids) if bids else None)
        with self._store_lock:
            volm7 = self._data.get(slug, {}).get("volm7")
        return base, effective_pmax(base, top, mr, volm7)

    def price(self, slug: str, max_age=None):
        return self.prices(slug, max_age)[0]

    # ---------- volumes ----------
    def volume_24h(self, slug: str, max_age=None):
        """Number of trades closed in the last 24 hours."""
        if self._fresh(slug, "vt", max_age) and "avg" in self._data[slug] and "ind" in self._data[slug] and (
                not self._info.get(slug, {}).get("max_rank") or "volm7" in self._data[slug]):
            return self._data[slug]["vol"]
        data = self._request(f"{V1}/items/{slug}/statistics")
        closed = data["payload"]["statistics_closed"]
        try:
            avg, avgm = average_prices(closed.get("90days") or [], self._info.get(slug, {}).get("max_rank", 0))
        except Exception:
            avg = avgm = None
        rows = closed["48hours"]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        total = 0
        for r in rows:
            t = datetime.fromisoformat(str(r["datetime"]).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if t >= cutoff:
                total += int(r.get("volume") or 0)
        self._store(slug, vol=total)
        mr = self._info.get(slug, {}).get("max_rank", 0)
        try:                                                         # trend, spike, backtest (signals.py)
            from app.trade import signals
            w = max(0, min(100, float(CFG["advice_trend_weight"]))) / 100
            ind = signals.indicators(signals.daily_series(closed.get("90days") or [], mr), w)
        except Exception:
            ind = None
        try:                                                         # trades at max rank (is that price real?)
            volm, _ = max_rank_volumes(rows, mr)
            _, volm7 = max_rank_volumes(closed.get("90days") or [], mr)
        except Exception:
            volm = volm7 = None
        with self._store_lock:                                       # price averages from the same answer (no extra request)
            if avg:
                self._data[slug]["avg"] = avg
            if avgm:
                self._data[slug]["avgm"] = avgm
            if mr and volm is not None:
                self._data[slug]["volm"], self._data[slug]["volm7"] = volm, volm7
            self._data[slug]["ind"] = ind
            self._dirty = True
        return total
