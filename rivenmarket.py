"""Riven flipping: finds rivens listed on warframe.market for less than comparable ones are worth.

Three criteria, as asked:
  Price      the listed (direct buy) price, against a "fair price" = median price of the comparable listings of the
             same weapon (similar stats score) x a sell factor (asking prices are higher than what gets paid).
  Volume     warframe.market does not publish riven sales. It is ESTIMATED by this program: every scan remembers the
             listings seen; listings that were there and are gone at the next scan (sold, withdrawn or expired) are
             counted over the last 7 days. The estimate improves the longer you keep scanning.
  Stats      0-100 score: how useful the stats are (weights below, editable in riven_weights.json) and how well
             they rolled (0 = worst roll, 1 = best roll, computed with the formula in rivens.py).

Requests: ONE dedicated limiter for the riven endpoints (default 1 per second, the site allows about 3); a 429 answer
makes it wait (Retry-After or growing pauses) and the scan stops after repeated 429s.
Only listings are read; nothing is sent to the site.
"""
import json
import statistics
import threading
import time
from pathlib import Path

import requests

import rivens as R
from config import APP_DIR, CFG

V1 = "https://api.warframe.market/v1"        # auctions: there is no v2 auction API
V2 = "https://api.warframe.market/v2"        # weapon and stat lists
HEADERS = {"Language": "en", "Platform": "pc", "Crossplay": "true", "Accept": "application/json",
           "User-Agent": "WFVendorOverlay/1.2 (riven listings; rate limited)"}
WEAPONS_FILE = APP_DIR / "riven_weapons.json"
ATTRS_FILE = APP_DIR / "riven_attributes_v1.json"
STORE_FILE = APP_DIR / "riven_market.json"
WEIGHTS_FILE = APP_DIR / "riven_weights.json"
LIST_TTL = 7 * 24 * 3600
WINDOW = 7 * 24 * 3600                    # sales estimate: listings gone in the last 7 days
MAX_GAP = 3 * 24 * 3600                   # two scans further apart than this say nothing about what disappeared
SEARCH_MAX = 100                          # a search returns at most this many listings
KEEP_LISTINGS = 80                        # listings stored per weapon (the cheapest ones)
TYPE_OF = {"rifle": "LotusRifle", "pistol": "LotusPistol", "shotgun": "LotusShotgun", "melee": "PlayerMeleeWeapon",
           "archgun": "LotusArchgun", "kitgun": "LotusModularPistol", "zaw": "LotusModularMelee"}

# how much each positive stat is worth for flipping (1 = always wanted, 0 = nobody wants it); editable
DEFAULT_WEIGHTS = {
    "WeaponCritChanceMod": 1.0, "WeaponCritDamageMod": 1.0, "WeaponDamageAmountMod": 1.0,
    "WeaponMeleeDamageMod": 1.0, "WeaponFireIterationsMod": 1.0, "WeaponFireRateMod": 0.6,
    "WeaponStunChanceMod": 0.7, "WeaponSlashDamageMod": 0.6, "WeaponToxinDamageMod": 0.6,
    "WeaponFireDamageMod": 0.55, "WeaponFreezeDamageMod": 0.55, "WeaponElectricityDamageMod": 0.55,
    "WeaponImpactDamageMod": 0.2, "WeaponArmorPiercingDamageMod": 0.2, "WeaponProcTimeMod": 0.15,
    "WeaponFactionDamageGrineer": 0.45, "WeaponFactionDamageCorpus": 0.45, "WeaponFactionDamageInfested": 0.35,
    "WeaponMeleeFactionDamageGrineer": 0.45, "WeaponMeleeFactionDamageCorpus": 0.45,
    "WeaponMeleeFactionDamageInfested": 0.35, "WeaponClipMaxMod": 0.2, "WeaponAmmoMaxMod": 0.1,
    "WeaponReloadSpeedMod": 0.2, "WeaponProjectileSpeedMod": 0.2, "WeaponPunctureDepthMod": 0.05,
    "WeaponRecoilReductionMod": 0.0, "WeaponZoomFovMod": 0.0, "WeaponMeleeRangeIncMod": 0.3,
    "WeaponMeleeComboBonusOnHitMod": 0.35, "WeaponMeleeComboPointsOnHitMod": 0.35,
    "WeaponMeleeComboInitialBonusMod": 0.3, "ComboDurationMod": 0.1, "WeaponMeleeFinisherDamageMod": 0.2,
    "SlideAttackCritChanceMod": 0.1, "WeaponMeleeComboEfficiencyMod": 0.2,
}
UNKNOWN_WEIGHT = 0.3
HARMLESS = 0.15                           # a NEGATIVE on a stat worth this little or less costs nothing (bonus)


LOG_FILE = APP_DIR / "riven.log"


def log(msg):
    """One line in riven.log (kept under ~200 KB)."""
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 200_000:
            LOG_FILE.write_text("", encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


class RivenRateLimited(Exception):
    pass


class RivenError(Exception):
    pass


class Limiter:
    """Spaces the riven requests (requests per second, from the settings) and backs off on 429."""

    def __init__(self, rps=None, market=None, sleep=time.sleep, clock=time.monotonic):
        self.rps = float(rps if rps is not None else CFG["riven_rps"])
        self.market, self._sleep, self._clock = market, sleep, clock
        self._lock = threading.Lock()
        self._next = 0.0
        self.hits = 0                      # consecutive 429s

    @property
    def interval(self):
        return 1.0 / max(0.1, min(2.5, self.rps))     # never faster than 2.5 / s, whatever the setting

    def wait(self):
        with self._lock:
            now = self._clock()
            if self._next > now:
                self._sleep(self._next - now)
            self._next = max(now, self._next) + self.interval
        if self.market is not None:
            self.market.throttle()          # also respect the spacing shared with the other warframe.market calls

    def penalty(self, retry_after=None):
        """Called on a 429: waits, longer every time; raises RivenRateLimited after the 3rd in a row."""
        self.hits += 1
        if self.hits >= 3:
            raise RivenRateLimited("warframe.market keeps answering 'too many requests'")
        pause = min(60.0, float(retry_after)) if retry_after else 5.0 * 2 ** (self.hits - 1)
        with self._lock:
            self._next = max(self._next, self._clock()) + pause
        self._sleep(pause)

    def ok(self):
        self.hits = 0


def get_json(url, limiter, params=None, cancel=None, timeout=12):
    """GET with the limiter. Retries after a 429 (see Limiter.penalty). Raises RivenError / RivenRateLimited."""
    while True:
        if cancel is not None and cancel.is_set():
            raise RivenError("cancelled")
        limiter.wait()
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        except requests.RequestException as e:
            log(f"GET {url} failed: {type(e).__name__}: {e}")
            raise RivenError(f"{type(e).__name__}: {e}")
        log(f"GET {url} {params or ''} -> {r.status_code}")
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            limiter.penalty(float(ra) if ra and ra.replace(".", "", 1).isdigit() else None)
            continue
        if r.status_code >= 400:
            log(f"  answer: {r.text[:300]!r}")
            raise RivenError(f"HTTP {r.status_code}")
        limiter.ok()
        try:
            return r.json()
        except ValueError:
            log(f"  not JSON: {r.text[:300]!r}")
            raise RivenError("invalid answer")


# ---------- lists (weapons, attributes): downloaded rarely and cached ----------
def _cached(path, fetch):
    try:
        c = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - c.get("time", 0) < LIST_TTL and c.get("data"):
            return c["data"]
    except Exception:
        pass
    data = fetch()
    try:
        path.write_text(json.dumps({"time": int(time.time()), "data": data}), encoding="utf-8")
    except OSError:
        pass
    return data


def weapon_list(limiter, cancel=None):
    """[{url_name, name, type, dispo}] of the weapons that can have a riven (v2 list)."""
    def fetch():
        d = get_json(V2 + "/riven/weapons", limiter, cancel=cancel)
        out = []
        for i in d.get("data") or []:
            if not i.get("slug"):
                continue
            name = ((i.get("i18n") or {}).get("en") or {}).get("name") or i["slug"]
            typ = "archgun" if i.get("group") == "archgun" else str(i.get("rivenType") or "").lower()
            out.append({"url_name": i["slug"], "name": name, "type": typ, "dispo": i.get("disposition") or 0})
        return out
    return _cached(WEAPONS_FILE, fetch)


def attribute_list(limiter, cancel=None):
    """[{url_name, prefix, suffix, effect}] of the riven stats (v2 list)."""
    def fetch():
        d = get_json(V2 + "/riven/attributes", limiter, cancel=cancel)
        return [{"url_name": a["slug"], "prefix": a.get("prefix") or "", "suffix": a.get("suffix") or "",
                 "effect": ((a.get("i18n") or {}).get("en") or {}).get("name") or ""}
                for a in d.get("data") or [] if a.get("slug")]
    return _cached(ATTRS_FILE, fetch)


def stat_index(attrs):
    """{wfm attribute url_name: stat tag of the game data}, matched by prefix + suffix, else by the effect text."""
    by_ps, by_label = {}, {}
    for typ in R.data()["types"].values():
        for tag, v in typ.items():
            by_ps.setdefault(f"{R._norm(v[1])}|{R._norm(v[2])}", tag)
            by_label.setdefault(R._norm(v[4]), tag)
    out = {}
    for a in attrs:
        tag = by_ps.get(f"{R._norm(a.get('prefix'))}|{R._norm(a.get('suffix'))}") \
            or by_label.get(R._norm(a.get("effect")))
        if tag:
            out[a["url_name"]] = tag
    return out


def weights():
    w = dict(DEFAULT_WEIGHTS)
    try:
        user = json.loads(WEIGHTS_FILE.read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, (int, float)):
                w[k] = max(0.0, min(1.0, float(v)))
    except Exception:
        pass
    return w


# ---------- reading and scoring a listing ----------
def parse_auction(a):
    """A search result -> compact dict, or None when it is not a usable direct-buy riven listing."""
    try:
        it = a.get("item") or {}
        price = a.get("buyout_price")
        if it.get("type") != "riven" or not price or a.get("closed") or not a.get("visible", True):
            return None
        attrs = [{"url": x["url_name"], "positive": bool(x.get("positive")), "value": float(x.get("value", 0))}
                 for x in it.get("attributes") or [] if x.get("url_name")]
        if not attrs:
            return None
        owner = a.get("owner") or {}
        return {"id": a["id"], "price": int(price), "name": it.get("name") or "", "rank": int(it.get("mod_rank") or 0),
                "rerolls": int(it.get("re_rolls") or 0), "mr": int(it.get("mastery_level") or 0),
                "pol": str(it.get("polarity") or ""), "attrs": attrs, "seller": owner.get("ingame_name") or "",
                "status": str(owner.get("status") or "").lower(), "updated": str(a.get("updated") or "")}
    except (KeyError, TypeError, ValueError):
        return None


def roll_quality(attr, tag, wtype, dispo, rank, n_pos, n_neg):
    """0 = worst possible roll, 1 = best, for one listed stat; None when it cannot be worked out."""
    stats = R.data()["types"].get("/Lotus/Upgrades/Mods/Randomized/" + TYPE_OF.get(wtype, "") + "RandomModRare")
    base = (stats or {}).get(tag)
    mult = R.MULT.get((n_pos, n_neg))
    if not base or not mult or not dispo:
        return None
    m = mult[0] if attr["positive"] else mult[1]
    if not m:
        return None
    unit = 90.0 * base[0] * dispo * m * (100.0 if base[3] else 1.0) * (rank + 1) / 9.0
    v = abs(attr["value"])
    if tag.endswith(R.TWO_DIGIT):
        return None                          # shown as multipliers: the unit used by the site is not certain
    if unit <= 0:
        return None
    norm = v / abs(unit)
    return max(0.0, min(1.0, (norm - 0.9) / 0.2))


def stats_score(listing, wtype, dispo, index, w=None):
    """(score 0-100, [tags]) of a parsed listing. Useful stats weigh most; a good roll adds up to 2x."""
    w = w or weights()
    pos = [a for a in listing["attrs"] if a["positive"]]
    neg = [a for a in listing["attrs"] if not a["positive"]]
    top = sorted(w.values(), reverse=True)[:3]
    denom = sum(top) or 1.0
    got, tags = 0.0, []
    for a in pos:
        tag = index.get(a["url"])
        tags.append(tag or a["url"])
        wt = w.get(tag, UNKNOWN_WEIGHT) if tag else UNKNOWN_WEIGHT
        q = roll_quality(a, tag, wtype, dispo, listing["rank"], len(pos), len(neg)) if tag else None
        got += wt * (0.5 + 0.5 * (0.5 if q is None else q))
    score = 100.0 * got / denom
    for a in neg:
        tag = index.get(a["url"])
        wt = w.get(tag, UNKNOWN_WEIGHT) if tag else UNKNOWN_WEIGHT
        if wt <= HARMLESS:
            score += 6.0                    # a negative that costs nothing makes the riven better
        else:
            score -= 30.0 * wt
    return max(0.0, min(100.0, score)), tags


def fair_price(score, others, factor, window=15.0, min_comps=3):
    """Median price of the comparable listings (stats score within +-window) x factor; None if too few."""
    comps = [p for s, p in others if abs(s - score) <= window]
    if len(comps) < min_comps:
        return None
    return int(statistics.median(comps) * factor)


# ---------- storage and the sales estimate ----------
class Store:
    def __init__(self, path=None):
        self.path = path or STORE_FILE
        self.lock = threading.Lock()
        self.version = 0
        self.d = {"weapons": {}}
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("weapons"), dict):
                self.d = d
        except Exception:
            pass

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self.d), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    def update(self, url_name, name, all_ids, listings, now=None):
        """Records a scan. all_ids = every listing seen (any seller status); listings = the usable ones (parsed).
        all_ids: {listing id: price}. A search returns at most 100 listings (the cheapest), so a known listing that is
        missing is counted as gone only if it was cheaper than the dearest listing now shown (otherwise it may just
        have been pushed out by cheaper ones). The gap since the last scan must also be short enough to mean something."""
        now = int(now or time.time())
        with self.lock:
            w = self.d["weapons"].setdefault(url_name, {"name": name, "t": 0, "ids": {}, "gone": [], "first": now})
            prev, gap = w.get("ids") if isinstance(w.get("ids"), dict) else {}, now - int(w.get("t") or 0)
            if prev and gap <= MAX_GAP:
                full = len(all_ids) >= SEARCH_MAX
                top = max(all_ids.values(), default=0)
                gone = sum(1 for i, p in prev.items() if i not in all_ids and (not full or p < top))
                if gone:
                    w["gone"] = (w.get("gone") or []) + [[now, gone]]
            elif prev:
                w["first"] = now                           # too long since the last scan: restart the observation
            w["gone"] = [g for g in w.get("gone", []) if now - g[0] <= WINDOW]
            w.update(name=name, t=now, ids=dict(all_ids), n=len(all_ids))
            w["listings"] = sorted(listings, key=lambda x: x["price"])[:KEEP_LISTINGS]
            self.version += 1
            return w

    def sales(self, url_name, now=None):
        """(listings gone in the last 7 days, days observed (max 7)) for a weapon."""
        now = int(now or time.time())
        w = self.d["weapons"].get(url_name)
        if not w:
            return 0, 0.0
        n = sum(g[1] for g in w.get("gone", []) if now - g[0] <= WINDOW)
        return n, min(WINDOW, max(0, now - int(w.get("first") or now))) / 86400.0

    def stale_order(self, urls):
        """Weapon URLs, the ones never scanned first, then the least recently scanned."""
        return sorted(urls, key=lambda u: int((self.d["weapons"].get(u) or {}).get("t") or 0))


# ---------- the scan ----------
def scan_weapon(weapon, limiter, store, cancel=None):
    d = get_json(V1 + "/auctions/search", limiter, cancel=cancel,
                 params={"type": "riven", "weapon_url_name": weapon["url_name"], "sort_by": "price_asc",
                         "buyout_policy": "direct"})
    auctions = (d.get("payload") or {}).get("auctions") or []
    ids = {a["id"]: int(a.get("buyout_price") or 0) for a in auctions
           if a.get("id") and not a.get("closed") and a.get("visible", True)}
    listings = [p for p in (parse_auction(a) for a in auctions) if p]
    store.update(weapon["url_name"], weapon["name"], ids, listings)
    return len(listings)


def pick_weapons(all_weapons, store, wanted_names, limit):
    """Which weapons to scan now: the named ones if any (comma separated), else the stalest `limit`."""
    want = {R._norm(n) for n in str(wanted_names or "").split(",") if n.strip()}
    pool = [w for w in all_weapons if not want or R._norm(w["name"]) in want or R._norm(w["url_name"]) in want]
    order = store.stale_order([w["url_name"] for w in pool])
    by = {w["url_name"]: w for w in pool}
    return [by[u] for u in order[:max(1, int(limit))]]


def scan(limiter, store, progress=None, cancel=None, wanted=None, limit=None):
    """Scans the next weapons. progress(done, total, name). Returns (weapons scanned, error text or "")."""
    cancel = cancel or threading.Event()
    try:
        weapons = weapon_list(limiter, cancel)
        attribute_list(limiter, cancel)
    except (RivenError, RivenRateLimited) as e:
        log(f"scan stopped before starting: {e}")
        return 0, str(e)
    log(f"scan: {len(weapons)} weapons known")
    todo = pick_weapons(weapons, store, CFG["riven_weapon_filter"] if wanted is None else wanted,
                        CFG["riven_scan_weapons"] if limit is None else limit)
    done, err = 0, ""
    for i, wp in enumerate(todo, start=1):
        if cancel.is_set():
            break
        if progress:
            progress(i - 1, len(todo), wp["name"])
        try:
            scan_weapon(wp, limiter, store, cancel)
            done += 1
        except RivenRateLimited as e:
            err = str(e)
            break
        except RivenError as e:
            if str(e) == "cancelled":
                break
            err = f"{wp['name']}: {e}"
    store.save()
    if progress:
        progress(done, len(todo), "")
    return done, err


def opportunities(store, weapons_by_url, index, factor=None, online_only=None, min_margin=None, min_score=None,
                  max_price=None, min_sales=None, now=None):
    """Rows for the table: the cheap listings, best margin first."""
    factor = float(CFG["riven_sell_factor"]) / 100.0 if factor is None else factor
    online_only = bool(CFG["riven_online_only"]) if online_only is None else online_only
    min_margin = int(CFG["riven_min_margin"]) if min_margin is None else min_margin
    min_score = int(CFG["riven_min_score"]) if min_score is None else min_score
    max_price = int(CFG["riven_max_price"]) if max_price is None else max_price
    min_sales = int(CFG["riven_min_sales"]) if min_sales is None else min_sales
    w = weights()
    rows = []
    for url, wd in store.d["weapons"].items():
        info = weapons_by_url.get(url) or {"name": wd.get("name", url), "type": ""}
        dispo = info.get("dispo") or _dispo(info["name"])
        scored = []
        for l in wd.get("listings") or []:
            if online_only and l["status"] not in ("ingame", "online"):
                continue
            s, tags = stats_score(l, info["type"], dispo, index, w)
            scored.append((s, l, tags))
        sales, days = store.sales(url, now)
        for s, l, tags in scored:
            if s < min_score or (max_price and l["price"] > max_price):
                continue
            fair = fair_price(s, [(o[0], o[1]["price"]) for o in scored if o[1]["id"] != l["id"]], factor)
            if fair is None:
                continue
            margin = fair - l["price"]
            if margin < min_margin:
                continue
            if days >= 1.0 and sales < min_sales:
                continue
            rows.append({"weapon": info["name"], "url": url, "listing": l, "score": s, "tags": tags, "fair": fair,
                         "margin": margin, "sales": sales, "days": days, "n": wd.get("n", len(scored))})
    rows.sort(key=lambda r: -r["margin"])
    return rows


_dispo_cache = {}


def _dispo(name):
    key = R._norm(name)
    if not _dispo_cache:
        for _p, (n, d) in R.data()["weapons"].items():
            _dispo_cache.setdefault(R._norm(n), d)
    return _dispo_cache.get(key, 0)


def auction_url(listing):
    return "https://warframe.market/auction/" + str(listing["id"])


def whisper(row):
    l = row["listing"]
    return (f"/w {l['seller']} Hi! I want to buy: {row['weapon']} {l['name']} for {l['price']} platinum. "
            f"(warframe.market)")
