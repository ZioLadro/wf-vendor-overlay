"""Client warframe.market: catalogo, fuzzy match, prezzi (v2) e volumi (v1).

Rispetta il limite di 3 richieste/secondo e mette tutto in cache.
NB: i volumi usano l'endpoint v1 /items/{slug}/statistics (deprecato ma attivo);
se smette di funzionare l'overlay mostra solo il prezzo.
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
from vendors import VendorIndex

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
STORE_FILE = APP_DIR / "prices.json"   # prezzi/volumi raccolti (persistenti)
HIST_MIN_GAP = 900                         # una voce di storico ogni 15 minuti al massimo
HIST_MAX = 48                              # voci di storico per oggetto
PRUNE_AGE = 30 * 24 * 3600                 # dimentica oggetti non aggiornati da 30 giorni
CATALOG_TTL = 24 * 3600
MIN_INTERVAL = 0.35  # ~2.9 richieste/s

class Market:
    def __init__(self):
        self._lock = threading.Lock()
        self._last = 0.0
        self._store_lock = threading.Lock()
        self._data = {}      # slug -> {"price","pmax","pt","vol","vt","hist"}
        self._info = {}      # slug -> {"name","max_rank","kind"}
        self._dirty = False
        self._matcher = Matcher([])
        self.vendors = None          # VendorIndex: quali vendor vendono ogni oggetto
        self._load_store()
        self._load_catalog()

    # ---------- HTTP ----------
    def _request(self, url: str):
        for attempt in range(2):
            with self._lock:
                wait = MIN_INTERVAL - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.monotonic()
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 429 and attempt == 0:
                time.sleep(1.5)
                continue
            r.raise_for_status()
            return r.json()

    def _get(self, path: str):
        return self._request(BASE + path)["data"]

    # ---------- catalogo ----------
    @staticmethod
    def _kind(tags) -> str:
        if "mod" in tags:
            return "mod"
        if "arcane_enhancement" in tags or "arcane" in tags:
            return "arcane"
        return "altro"

    def _load_catalog(self):
        rows = None
        if CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < CATALOG_TTL:
            try:
                rows = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                if not all(isinstance(r, list) and len(r) >= 4 for r in rows):
                    rows = None          # cache di una versione precedente (senza rank/tipo)
            except Exception:
                rows = None
        if rows is None:
            rows = []
            for it in self._get("/items"):
                name = (it.get("i18n", {}).get("en", {}) or {}).get("name") or it.get("name")
                if name and it.get("slug"):
                    rows.append([name, it["slug"], int(it.get("maxRank") or 0),
                                 self._kind(it.get("tags") or [])])
            CACHE_FILE.write_text(json.dumps(rows), encoding="utf-8")
        self._info = {r[1]: {"name": r[0], "max_rank": r[2], "kind": r[3]} for r in rows}
        self._matcher = Matcher(rows)
        self.vendors = VendorIndex({norm(r[0]): r[1] for r in rows})
        self._migrate()

    def _migrate(self):
        """Dati salvati da versioni senza prezzo a rank massimo: per mod/arcane il vecchio prezzo
        mescolava tutti i rank, quindi lo scarta (verra' rilevato di nuovo)."""
        with self._store_lock:
            for slug, e in self._data.items():
                if self._info.get(slug, {}).get("max_rank", 0) > 0 and "pmax" not in e:
                    e["price"] = None
                    e.pop("pt", None)
                    self._dirty = True

    def info(self, slug: str) -> dict:
        return self._info.get(slug, {})

    # ---------- matching ----------
    def pairs(self):
        return self._matcher.pairs

    def match(self, text: str, threshold: int = 90):
        return self._matcher.match(text, threshold)

    # ---------- archivio persistente ----------
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
        """Salva su disco (scrittura atomica) se ci sono novita'."""
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
        """Ultimi dati noti (anche vecchi): {"price","pmax","pt","vol","vt"} oppure None."""
        with self._store_lock:
            e = self._data.get(slug)
            return {k: e.get(k) for k in ("price", "pmax", "pt", "vol", "vt")} if e else None

    def snapshot(self) -> list:
        """Tutti gli oggetti del listino: quelli dei vendor (anche senza dati) e quelli visti a schermo."""
        rows = []
        by_slug = self.vendors.by_slug if self.vendors else {}
        with self._store_lock:
            for slug in set(self._data) | set(by_slug):
                e = self._data.get(slug, {})
                info = self._info.get(slug, {})
                times = [t for t in (e.get("pt"), e.get("vt")) if t]
                if not times and slug not in by_slug:
                    continue
                rows.append({
                    "slug": slug,
                    "name": info.get("name") or slug.replace("_", " ").title(),
                    "kind": info.get("kind", "altro"),
                    "ranked": info.get("max_rank", 0) > 0,
                    "max_rank": info.get("max_rank", 0),
                    "price": e.get("price"), "pmax": e.get("pmax"), "vol": e.get("vol"),
                    "updated": max(times) if times else None,
                    "vendors": by_slug.get(slug, []),
                })
        rows.sort(key=lambda r: r["name"].lower())
        return rows

    def vendor_names(self) -> list:
        return self.vendors.vendor_names if self.vendors else []

    def refresh_many(self, slugs, cancel, progress=None, max_age=0):
        """Aggiorna prezzo e volume degli oggetti indicati, uno dopo l'altro (limite 3 richieste/s).

        cancel: threading.Event per interrompere. progress(fatti, totale, errori) dopo ogni oggetto.
        max_age: salta i dati piu' recenti di questi secondi (0 = forza l'aggiornamento).
        Ritorna (fatti, errori, interrotto)."""
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
            if streak >= 8:               # rete assente o API non raggiungibile: inutile insistere
                break
        self.flush()
        return done, errors, cancel.is_set() or done < len(slugs)

    def _fresh(self, slug: str, key: str, max_age):
        max_age = CFG["refresh_interval"] if max_age is None else max_age
        with self._store_lock:
            e = self._data.get(slug)
            return bool(e and e.get(key) and time.time() - e[key] < max_age)

    # ---------- prezzi ----------
    @staticmethod
    def _low3(values):
        values = sorted(values)
        return int(statistics.median(values[:3])) if values else None

    def prices(self, slug: str, max_age=None):
        """(prezzo, prezzo_rank_massimo): mediana dei 3 ordini di vendita piu' bassi di utenti
        online/in gioco. Per mod e arcane `prezzo` e' quello a rank 0 e il secondo valore e' a rank
        massimo; per gli altri oggetti il secondo valore e' None.
        Usa i dati salvati se hanno meno di max_age secondi."""
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

    # ---------- volumi ----------
    def volume_24h(self, slug: str, max_age=None):
        """Numero di scambi chiusi nelle ultime 24 ore."""
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
