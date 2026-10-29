"""Riven flipping: finds rivens listed on warframe.market for less than comparable ones are worth.

Three criteria, as asked:
  Price      the listed (direct buy) price, against a "fair price" = median price of the comparable listings of the
             same weapon (similar stats score) x a sell factor (asking prices are higher than what gets paid).
  Volume     warframe.market does not publish riven sales. It is ESTIMATED by this program: every scan remembers the
             listings seen; listings that were there and are gone at the next scan (sold, withdrawn or expired) are
             counted over the last 7 days. The estimate improves the longer you keep scanning.
  Stats      0-100 score: how useful the stats are (weights below, editable in riven_weights.json) and how well
             they rolled (0 = worst roll, 1 = best roll, computed with the formula in rivens.py).

The database (riven_market.json) grows with every scan and refines the search:
  history    per weapon and per day: median asking price, cheapest price and number of listings (kept 180 days), so the
             tab shows the 7 / 30-day trend; a weapon whose prices are falling gets its fair price lowered by the fall
             (a riven that looks cheap only because its weapon is crashing is no deal).
  gone       the listings that disappeared between two scans, with their price, stats and how long they were listed
             (kept 30 days). Those gone within FAST_DAYS are most likely sold: their prices, for rivens with similar
             stats, are a better guide than asking prices, so the fair price leans on them when there are enough.
  schedule   the tab can scan by itself every N hours (setting riven_auto_hours) while the program runs.

Requests: ONE dedicated limiter for the riven endpoints. warframe.market asks that contract (auction) searches stay
around 10-20 per minute, so the default is 12 per minute and the limit can never be set above 20; a 429 answer
makes it wait (Retry-After or growing pauses) and the scan stops after repeated 429s.
Only listings are read; nothing is sent to the site.
"""
import json
import statistics
import threading
import time
from pathlib import Path

import requests

from app.game import rivens as R
from app.core.config import APP_DIR, CFG

V1 = "https://api.warframe.market/v1"        # auctions: there is no v2 auction API
V2 = "https://api.warframe.market/v2"        # weapon and stat lists
from app.core.version import __version__

# warframe.market's rules: an own, descriptive User-Agent (never a browser's); contract (auction) searches are
# expected to stay around 10-20 requests per minute, the general limit is 3 per second.
HEADERS = {"Language": "en", "Platform": "pc", "Crossplay": "true", "Accept": "application/json",
           "User-Agent": f"WFVendorOverlay/{__version__} (+https://github.com/ZioLadro/wf-vendor-overlay)"}
MAX_RPM = 20
WEAPONS_FILE = APP_DIR / "riven_weapons.json"
ATTRS_FILE = APP_DIR / "riven_attributes_v1.json"
STORE_FILE = APP_DIR / "riven_market.json"
WEIGHTS_FILE = APP_DIR / "riven_weights.json"
LIST_TTL = 7 * 24 * 3600
WINDOW = 7 * 24 * 3600                    # sales estimate: listings gone in the last 7 days
MAX_GAP = 3 * 24 * 3600                   # two scans further apart than this say nothing about what disappeared
SEARCH_MAX = 100                          # a search returns at most this many listings
KEEP_LISTINGS = 80                        # listings stored per weapon (the cheapest ones)
HIST_DAYS = 180                           # daily price points kept per weapon
GONE_DAYS = 30                            # disappeared listings kept per weapon (for the "likely sold" prices)
GONE_KEEP = 40                            # at most this many per weapon (the most recent)
FAST_DAYS = 5                             # gone within this many days of being listed = most likely sold
SOLD_FACTOR = 0.95                        # a few of those were withdrawn, not sold
SOLD_WEIGHT = 0.6                         # weight of the "likely sold" median against the asking one when both exist
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
    """One line in riven.log (kept under ~200 KB), also shown in the Console."""
    try:
        from app.core import logbus
        logbus.add("rivens", msg, "error" if "error" in str(msg).lower() or "stopped" in str(msg).lower() else "info")
    except Exception:
        pass
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
    """Spaces the riven requests (requests per MINUTE, from the settings, never above MAX_RPM) and backs off on 429."""

    def __init__(self, rpm=None, market=None, sleep=time.sleep, clock=time.monotonic):
        self.rpm = float(rpm if rpm is not None else CFG["riven_rpm"])
        self.market, self._sleep, self._clock = market, sleep, clock
        self._lock = threading.Lock()
        self._next = 0.0
        self.hits = 0                      # consecutive 429s

    @property
    def interval(self):
        return 60.0 / max(1.0, min(float(MAX_RPM), self.rpm))

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
        pause = min(120.0, float(retry_after)) if retry_after else 20.0 * 2 ** (self.hits - 1)
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
                "status": str(owner.get("status") or "").lower(), "updated": str(a.get("updated") or ""),
                "created": str(a.get("created") or "")}
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


PHYS = {"WeaponImpactDamageMod": "impact", "WeaponArmorPiercingDamageMod": "puncture", "WeaponSlashDamageMod": "slash"}
ELEM = ("WeaponFireDamageMod", "WeaponFreezeDamageMod", "WeaponElectricityDamageMod", "WeaponToxinDamageMod")
_profiles = {}


def weapon_stats(name):
    """Base stats of the weapon a riven is for (the build planner's data): its best variant (Prime, Kuva…), or None."""
    from app.game import loadouts as LO
    ws = LO.data().get("wstats") or {}
    pre = ("Kuva ", "Tenet ", "Coda ", "Prisma ", "MK1-", "Rakta ", "Secura ", "Sancti ", "Synoid ", "Telos ", "Vaykor ",
           "Dex ", "Mara ", "Vandal ", "Wraith ")
    low = name.lower()
    cands = [v for k, v in ws.items() if k.lower() == low or k.lower() in (low + " prime", low + " vandal", low + " wraith")
             or any(k.lower() == p.lower() + low for p in pre)]
    if not cands:
        return None
    return max(cands, key=lambda v: float(v.get("cc") or 0) * float(v.get("cd") or 0) + float(v.get("sc") or 0))


def profile_weights(name, w=None):
    """The stat weights for this weapon (riven_weights.json adjusted to what the weapon is good at):
    a crit weapon (crit chance 20 %+) wants crit chance and damage, a weapon with little crit (under 10 %) much less;
    a status weapon (status 25 %+) wants status chance, elements and status duration; a slash weapon slash.
    Also returns the physical damage types that make up less than 20 % of its damage: a NEGATIVE on them costs nothing
    (on a slash weapon, -impact even helps)."""
    key = (name, id(w))
    if key in _profiles:
        return _profiles[key]
    w = dict(w or weights())
    st = weapon_stats(name) or {}
    cc, cd, sc = float(st.get("cc") or 0), float(st.get("cd") or 0), float(st.get("sc") or 0)
    dmg = {k.lower(): float(v or 0) for k, v in (st.get("dmg") or {}).items()}
    total = sum(dmg.values()) or 0.0
    harmless = set()
    if st:
        crit = cc >= 0.2 or (cc >= 0.15 and cd >= 2.4)
        if crit:
            w["WeaponCritChanceMod"] = w["WeaponCritDamageMod"] = 1.0
        elif cc < 0.1:
            w["WeaponCritChanceMod"] = w.get("WeaponCritChanceMod", 1.0) * 0.45
            w["WeaponCritDamageMod"] = w.get("WeaponCritDamageMod", 1.0) * 0.35
        if sc >= 0.25:
            w["WeaponStunChanceMod"] = 1.0
            for e in ELEM:
                w[e] = min(1.0, w.get(e, 0.55) + 0.2)
            w["WeaponProcTimeMod"] = max(w.get("WeaponProcTimeMod", 0.15), 0.35)
        elif sc < 0.1:
            w["WeaponStunChanceMod"] = w.get("WeaponStunChanceMod", 0.7) * 0.5
        if total:
            for tag, typ in PHYS.items():
                share = dmg.get(typ, 0.0) / total
                if share >= 0.5:
                    w[tag] = max(w.get(tag, 0.2), 0.85 if typ == "slash" else 0.5)
                if share < 0.2:
                    harmless.add(tag)
    out = (w, harmless, {"cc": cc, "cd": cd, "sc": sc})
    _profiles[key] = out
    return out


def stats_score(listing, wtype, dispo, index, w=None, weapon=""):
    """(score 0-100, [tags]) of a parsed listing. Useful stats weigh most; a good roll adds up to 2x. With the weapon's
    name the weights follow what the weapon is good at (profile_weights)."""
    w = w or weights()
    harmless = set()
    if weapon:
        w, harmless, _st = profile_weights(weapon, w)
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
        if wt <= HARMLESS or tag in harmless:
            score += 6.0                    # a negative that costs nothing makes the riven better
        else:
            score -= 30.0 * wt
    return max(0.0, min(100.0, score)), tags


def _iso(s):
    try:
        from datetime import datetime, timezone
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    except (TypeError, ValueError):
        return None


def listing_age(listing, seen, now):
    """Days a listing has been on the market: from its creation date on warframe.market (or, if missing, from when this
    program first saw it). None if neither is known."""
    t = [x for x in (_iso(listing.get("created")), seen.get(listing["id"]) if seen else None) if x]
    return (now - min(t)) / 86400 if t else None


def fair_price(score, others, factor, window=15.0, min_comps=3, tags=None):
    """Median price of the comparable rivens x factor; None if too few.
    others: [(score, price)] or [(score, price, positive tags, seller)].
    With the riven's positive stats (tags), rivens with the same stat combination come first (2 of the same positive
    stats, or all of them when it has fewer): what a stat combination sells for says more than a score (the
    "god roll" pricing of riven snipers); their score may differ more (+-25). Without 3 of them, the score window.
    The same seller listing the same combination several times counts once (a flood of copies would set the price)."""
    def dedup(rows):
        seen, out = set(), []
        for r in rows:
            k = (r[3], tuple(sorted(r[2]))) if len(r) > 3 and r[3] else None
            if k and k in seen:
                continue
            if k:
                seen.add(k)
            out.append(r)
        return out
    rows = dedup(list(others))
    if tags:
        mine = set(tags)
        need = min(2, len(mine))
        same = [r[1] for r in rows if len(r) > 2 and len(mine & set(r[2])) >= need and abs(r[0] - score) <= 25.0]
        if len(same) >= min_comps:
            return int(statistics.median(same) * factor)
    comps = [r[1] for r in rows if abs(r[0] - score) <= window]
    if len(comps) < min_comps:
        return None
    return int(statistics.median(comps) * factor)


def positives(listing, index):
    """The game's stat tags of a listing's positive stats."""
    return [index.get(a["url"]) or a["url"] for a in listing["attrs"] if a["positive"]]


GRADES = ((0.9, "S"), (0.75, "A"), (0.5, "B"), (0.25, "C"), (0.0, "D"))


def grade(q):
    """A letter for how well a stat rolled (0 = the lowest roll, 1 = the highest; the game rolls 90-110 %)."""
    if q is None:
        return "?"
    return next(g for lim, g in GRADES if q >= lim)


def roll_grades(listing, wtype, index, dispo=None):
    """[(label tag, value, grade)] of every stat of a listing."""
    pos = [a for a in listing["attrs"] if a["positive"]]
    neg = [a for a in listing["attrs"] if not a["positive"]]
    out = []
    for a in listing["attrs"]:
        tag = index.get(a["url"])
        q = roll_quality(a, tag, wtype, dispo or R.DISPOSITION, listing.get("rank", 8), len(pos), len(neg)) if tag else None
        out.append((tag or a["url"], a["value"], grade(q)))
    return out


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
            seen = w.get("seen") if isinstance(w.get("seen"), dict) else {}
            prev_listings = {l["id"]: l for l in w.get("listings") or []}
            if prev and gap <= MAX_GAP:
                full = len(all_ids) >= SEARCH_MAX
                top = max(all_ids.values(), default=0)
                gone_ids = [i for i, p in prev.items() if i not in all_ids and (not full or p < top)]
                self._journal_gone(url_name, gone_ids, now)
                if gone_ids:
                    w["gone"] = (w.get("gone") or []) + [[now, len(gone_ids)]]
                    log_ = w.setdefault("sold", [])
                    for i in gone_ids:                 # what disappeared, for the "likely sold" prices
                        l = prev_listings.get(i)
                        if l:
                            log_.append({"t": now, "price": l["price"], "rank": l["rank"], "rerolls": l["rerolls"],
                                         "attrs": [[a["url"], a["positive"], a["value"]] for a in l["attrs"]],
                                         "age": max(0, now - int(seen.get(i) or w.get("t") or now))})
            elif prev:
                w["first"] = now                           # too long since the last scan: restart the observation
            w["gone"] = [g for g in w.get("gone", []) if now - g[0] <= WINDOW]
            w["sold"] = [g for g in w.get("sold", []) if now - g["t"] <= GONE_DAYS * 86400][-GONE_KEEP:]
            w["seen"] = {i: int(seen.get(i) or now) for i in all_ids}
            prices = sorted(p for p in all_ids.values() if p > 0)
            if prices:                                     # one history point per day (the day's last scan)
                day = now // 86400
                pt = [day, int(statistics.median(prices)), prices[0], len(prices)]
                h = [x for x in w.get("hist", []) if x[0] != day and day - x[0] <= HIST_DAYS]
                w["hist"] = h + [pt]
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

    def trend(self, url_name, days):
        """Change of the median asking price over about `days` days (0.12 = +12 %), or None without enough history."""
        h = (self.d["weapons"].get(url_name) or {}).get("hist") or []
        if len(h) < 2:
            return None
        last = h[-1]
        old = [x for x in h[:-1] if last[0] - x[0] >= days * 0.7]
        if not old:
            return None
        ref = min(old, key=lambda x: abs(last[0] - x[0] - days))
        return (last[1] - ref[1]) / ref[1] if ref[1] else None

    def likely_sold(self, url_name, now=None):
        """Listings gone within FAST_DAYS of being listed, in the last GONE_DAYS days (most likely sold), parsed like
        search results."""
        now = int(now or time.time())
        out = []
        for g in (self.d["weapons"].get(url_name) or {}).get("sold") or []:
            if now - g["t"] <= GONE_DAYS * 86400 and g.get("age", 0) <= FAST_DAYS * 86400:
                out.append({"id": f"sold-{g['t']}-{g['price']}", "price": g["price"], "rank": g.get("rank", 0),
                            "rerolls": g.get("rerolls", 0), "age": g.get("age", 0),
                            "attrs": [{"url": a[0], "positive": a[1], "value": a[2]} for a in g.get("attrs") or []]})
        return out

    def stale_order(self, urls, now=None, names=None):
        """Weapon URLs in the order to scan them: never scanned first; then the "watched" weapons (some sales, a deal
        found in the last week, or rivens that trade in game) whose last scan is 2.5+ days old, so that two scans never
        lie more than MAX_GAP apart and the sales estimate stays valid; then by how overdue they are, sooner for weapons
        that sell, give deals or trade a lot in game, later for dead ones (watched 3+ days, no sale, few listings).
        names: {url: weapon name} for DE's popularity."""
        from app.trade import rivenweekly as WK
        now = int(now or time.time())
        names = names or {}
        deals = self.d.get("deals") or {}

        def overdue(u):
            w = self.d["weapons"].get(u) or {}
            if not w.get("t"):
                return float("inf")
            sold, days = self.sales(u, now)
            pop = WK.popularity(names.get(u) or w.get("name") or u)
            dealt = sum(1 for t in deals.get(u) or [] if now - t <= 7 * 86400)
            age = now - int(w["t"])
            watched = sold > 0 or dealt > 0 or pop >= 5
            if watched and age >= MAX_GAP - 12 * 3600:
                return 1e12 + age                         # before the gap makes the sales estimate restart
            weight = 1.0 + min(3.0, sold / 5.0) + min(2.0, dealt / 2.0) + min(1.5, pop / 20.0)
            if days >= 3.0 and sold == 0 and not dealt and int(w.get("n") or 0) <= 3:
                weight = 0.25
            return age * weight
        return sorted(urls, key=lambda u: -overdue(u))

    def note_deals(self, rows, now=None):
        """Remembers which weapons gave deals (for the scan order): one time per weapon per scan of it."""
        now = int(now or time.time())
        with self.lock:
            d = self.d.setdefault("deals", {})
            for r in rows:
                t = int((self.d["weapons"].get(r["url"]) or {}).get("t") or 0)
                lst = d.setdefault(r["url"], [])
                if t and t not in lst:
                    lst.append(t)
            for u in list(d):
                d[u] = [x for x in d[u] if now - x <= 14 * 86400][-20:]
                if not d[u]:
                    del d[u]

    # ---------- marks ----------
    def set_contacted(self, listing_id, on=True):
        with self.lock:
            c = self.d.setdefault("contacted", {})
            now = int(time.time())
            for k in [k for k, v in c.items() if now - v > 14 * 86400]:
                del c[k]
            if on:
                c[str(listing_id)] = now
            else:
                c.pop(str(listing_id), None)
            self.version += 1
        self.save()

    # ---------- flip journal ----------
    def journal(self):
        return self.d.setdefault("journal", [])

    def journal_buy(self, row, price=None):
        """A riven you bought (from a row of the table): its price, the fair price then, the stats."""
        l = row["listing"]
        with self.lock:
            self.journal().append({"id": str(l["id"]), "url": row["url"], "weapon": row["weapon"], "riven": l["name"],
                                   "rerolls": l.get("rerolls", 0), "rank": l.get("rank", 0),
                                   "attrs": [[a["url"], a["positive"], a["value"]] for a in l["attrs"]],
                                   "buy": int(price if price is not None else l["price"]), "fair": int(row["fair"]),
                                   "t_buy": int(time.time()), "state": "held", "list": None, "t_list": None,
                                   "sold": None, "t_sold": None, "auction": None})
            self.version += 1
        self.save()

    def journal_set(self, idx, **kw):
        with self.lock:
            j = self.journal()
            if 0 <= idx < len(j):
                j[idx].update(kw)
                if kw.get("state") == "sold" and not j[idx].get("t_sold"):
                    j[idx]["t_sold"] = int(time.time())
                self.version += 1
        self.save()

    def journal_remove(self, idx):
        with self.lock:
            j = self.journal()
            if 0 <= idx < len(j):
                j.pop(idx)
                self.version += 1
        self.save()

    def journal_own_listings(self, url, auctions, me):
        """Your own auctions seen in a scan: a riven of the journal listed at a price (matched by weapon and name)."""
        if not me:
            return
        for a in auctions:
            owner = a.get("owner") or {}
            if str(owner.get("ingame_name") or "").lower() != me.lower():
                continue
            name = str((a.get("item") or {}).get("name") or "").lower()
            for e in self.journal():
                if e["url"] == url and e["riven"].lower() == name and e["state"] in ("held", "listed"):
                    e.update(state="listed", list=int(a.get("buyout_price") or a.get("starting_price") or 0),
                             auction=a.get("id"), t_list=e.get("t_list") or int(time.time()))
                    break

    def _journal_gone(self, url, gone_ids, now):
        """(lock held) Your listed riven left the site: most likely sold, at the price it was listed at."""
        gone = set(gone_ids)
        for e in self.journal():
            if e["url"] == url and e["state"] == "listed" and e.get("auction") in gone:
                e.update(state="sold", sold=e.get("list"), t_sold=now, auto=True)

    def calibration(self):
        """{weapon url: factor, "*": factor}: what your resales got against the fair price shown when you bought
        (median of sold / fair; 3+ sales for the overall factor, 2+ for a weapon's own), kept within 0.6-1.3."""
        out = {}
        sold = [e for e in self.d.get("journal") or [] if e.get("state") == "sold" and e.get("sold") and e.get("fair")]
        clip = lambda x: max(0.6, min(1.3, x))
        if len(sold) >= 3:
            out["*"] = clip(statistics.median(e["sold"] / e["fair"] for e in sold[-20:]))
        by = {}
        for e in sold:
            by.setdefault(e["url"], []).append(e["sold"] / e["fair"])
        for u, v in by.items():
            if len(v) >= 2:
                out[u] = clip(statistics.median(v))
        return out

    def journal_summary(self):
        j = self.d.get("journal") or []
        sold = [e for e in j if e.get("state") == "sold" and e.get("sold") is not None]
        held = [e for e in j if e.get("state") in ("held", "listed")]
        days = [(e["t_sold"] - e["t_buy"]) / 86400 for e in sold if e.get("t_sold") and e.get("t_buy")]
        return {"n_sold": len(sold), "profit": sum(e["sold"] - e["buy"] for e in sold),
                "invested": sum(e["buy"] for e in held), "n_held": len(held),
                "days": statistics.median(days) if days else None}


# ---------- the scan ----------
def scan_weapon(weapon, limiter, store, cancel=None):
    d = get_json(V1 + "/auctions/search", limiter, cancel=cancel,
                 params={"type": "riven", "weapon_url_name": weapon["url_name"], "sort_by": "price_asc",
                         "buyout_policy": "direct"})
    auctions = (d.get("payload") or {}).get("auctions") or []
    ids = {a["id"]: int(a.get("buyout_price") or 0) for a in auctions
           if a.get("id") and not a.get("closed") and a.get("visible", True)}
    listings = [p for p in (parse_auction(a) for a in auctions) if p]
    with store.lock:
        store.journal_own_listings(weapon["url_name"], auctions, str(CFG.get("player_name") or ""))
    store.update(weapon["url_name"], weapon["name"], ids, listings)
    if CFG.get("riven_bids") and watched(store, weapon):
        try:                                       # auctions you can bid on: one more request, watched weapons only
            d = get_json(V1 + "/auctions/search", limiter, cancel=cancel,
                         params={"type": "riven", "weapon_url_name": weapon["url_name"], "sort_by": "price_asc"})
            bids = [p for p in (parse_bid(a) for a in (d.get("payload") or {}).get("auctions") or []) if p]
            with store.lock:
                store.d["weapons"][weapon["url_name"]]["bids"] = sorted(bids, key=lambda x: x["price"])[:20]
        except RivenError as e:
            log(f"bids of {weapon['name']}: {e}")
    return len(listings)


def watched(store, weapon, now=None):
    """A weapon worth a closer look: its rivens sell, it gave a deal this week, or they trade a lot in game."""
    from app.trade import rivenweekly as WK
    now = int(now or time.time())
    u = weapon["url_name"]
    sold, _days = store.sales(u, now)
    dealt = any(now - t <= 7 * 86400 for t in (store.d.get("deals") or {}).get(u) or [])
    return sold > 0 or dealt or WK.popularity(weapon["name"]) >= 5


def parse_bid(a):
    """An auction you can bid on (not a direct sale) -> a listing whose price is the next bid it would take, or None."""
    if a.get("is_direct_sell", True) or a.get("closed") or not a.get("visible", True):
        return None
    nxt = int(a.get("top_bid") or 0) + int(a.get("minimal_increment") or 1) if a.get("top_bid") else int(a.get("starting_price") or 0)
    if nxt <= 0:
        return None
    p = parse_auction(dict(a, buyout_price=nxt))
    if p:
        p.update(bid=True, buyout=a.get("buyout_price"), top_bid=a.get("top_bid"))
    return p


def pick_weapons(all_weapons, store, wanted_names, limit):
    """Which weapons to scan now: the named ones if any (comma separated), else the stalest `limit`."""
    want = {R._norm(n) for n in str(wanted_names or "").split(",") if n.strip()}
    pool = [w for w in all_weapons if not want or R._norm(w["name"]) in want or R._norm(w["url_name"]) in want]
    order = store.stale_order([w["url_name"] for w in pool], names={w["url_name"]: w["name"] for w in pool})
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
    try:
        from app.trade import rivenweekly as WK
        WK.refresh(wait=True)                      # DE's weekly in-game riven trades (once a day at most)
    except Exception as e:
        log(f"weekly riven data: {e}")
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
    store.d["last_scan"] = int(time.time())
    store.save()
    if progress:
        progress(done, len(todo), "")
    return done, err


DE_WEIGHT = 0.25                          # weight of DE's in-game median (scaled by the stats score) in the fair price


def de_fair(de, score):
    """A fair price from DE's weekly in-game median for the weapon: the median riven of that weapon traded at the median;
    a better-than-usual riven (score) is worth more: x0.6 at score 0, x1.0 at 50, x1.4 at 100."""
    if not de or not de.get("median"):
        return None
    return int(de["median"] * (0.6 + 0.8 * score / 100.0))


def expected_days(sell_days, sales, days, n):
    """How many days a riven of this weapon takes to sell: the median time of the likely-sold ones; else the listings
    queue divided by the sales rate; else a week (not known yet)."""
    if sell_days:
        return max(0.5, min(60.0, sell_days))
    if days >= 1.0 and sales:
        return max(0.5, min(60.0, (n or 1) / (sales / days) / 2))
    return 7.0


def opportunities(store, weapons_by_url, index, factor=None, online_only=None, min_margin=None, min_score=None,
                  max_price=None, min_sales=None, now=None, include_hidden=False):
    """Rows for the table: the cheap listings, best expected profit a day first (or best margin: setting riven_sort)."""
    from app.trade import rivenweekly as WK
    factor = float(CFG["riven_sell_factor"]) / 100.0 if factor is None else factor
    online_only = bool(CFG["riven_online_only"]) if online_only is None else online_only
    min_margin = int(CFG["riven_min_margin"]) if min_margin is None else min_margin
    min_score = int(CFG["riven_min_score"]) if min_score is None else min_score
    max_price = int(CFG["riven_max_price"]) if max_price is None else max_price
    min_sales = int(CFG["riven_min_sales"]) if min_sales is None else min_sales
    max_age = float(CFG.get("riven_max_age_days", 14) or 0)
    hidden_w = {R._norm(x) for x in CFG.get("riven_hidden_weapons") or []}
    hidden_s = {str(x).lower() for x in CFG.get("riven_hidden_sellers") or []}
    me = str(CFG.get("player_name") or "").lower()
    now_ = int(now or time.time())
    w = weights()
    calib = store.calibration()
    contacted = store.d.get("contacted") or {}
    rows = []
    for url, wd in store.d["weapons"].items():
        info = weapons_by_url.get(url) or {"name": wd.get("name", url), "type": ""}
        if not include_hidden and (R._norm(info["name"]) in hidden_w or R._norm(url) in hidden_w):
            continue
        dispo = R.DISPOSITION                    # Hotfix 44.1.3: one disposition (1.2) for every weapon
        scored, comps_all = [], []
        seen = wd.get("seen") if isinstance(wd.get("seen"), dict) else {}
        listings = list(wd.get("listings") or []) + [dict(b, bid=True) for b in wd.get("bids") or []]
        for l in listings:
            s, tags = stats_score(l, info["type"], dispo, index, w, info["name"])
            age = listing_age(l, seen, now_)
            # comparables: every seller (online or not), but listings stuck for more than twice the max age say what
            # does NOT sell, so they are left out of the fair price; bids are not prices
            if not l.get("bid") and not (max_age and age is not None and age > 2 * max_age):
                comps_all.append((s, l, age, positives(l, index)))
            if online_only and l["status"] not in ("ingame", "online"):
                continue
            if l["seller"].lower() in hidden_s and not include_hidden:
                continue
            if me and l["seller"].lower() == me:
                continue                           # your own listing
            scored.append((s, l, tags, age))
        sales, days = store.sales(url, now)
        sold = store.likely_sold(url, now)
        sold_scored = [(stats_score(x, info["type"], dispo, index, w, info["name"])[0], x["price"], positives(x, index), "")
                       for x in sold]
        t7, t30 = store.trend(url, 7), store.trend(url, 30)
        sell_days = statistics.median([x["age"] for x in sold]) / 86400 if sold else None
        k = calib.get(url, calib.get("*", 1.0))
        for s, l, tags, age in scored:
            if s < min_score or (max_price and l["price"] > max_price):
                continue
            if max_age and age is not None and age > max_age:
                continue                           # on sale for too long at that price: probably not a real offer
            mine = positives(l, index)
            ask = fair_price(s, [(o[0], o[1]["price"], o[3], o[1]["seller"]) for o in comps_all if o[1]["id"] != l["id"]],
                             factor, tags=mine)
            got = fair_price(s, sold_scored, SOLD_FACTOR, tags=mine)
            de = WK.lookup(info["name"], info["type"], l["rerolls"] > 0)
            dfair = de_fair(de, s)
            if ask is None and got is None and dfair is None:
                continue
            parts = [(SOLD_WEIGHT, got), (1 - SOLD_WEIGHT, ask), (DE_WEIGHT, dfair)]
            parts = [(wt, v) for wt, v in parts if v is not None]
            fair = int(sum(wt * v for wt, v in parts) / sum(wt for wt, _v in parts))
            basis = "+".join(n for n, v in (("sold", got), ("ask", ask), ("de", dfair)) if v is not None)
            if t7 is not None and t7 < -0.05:      # falling prices: the fair price follows the fall (up to 30 %)
                fair = int(fair * (1 + max(-0.3, t7)))
            fair = int(fair * k)                   # what your own resales say (the flip journal)
            margin = fair - l["price"]
            if margin < min_margin:
                continue
            if days >= 1.0 and sales < min_sales:
                continue
            hist = wd.get("hist") or []
            exp_days = expected_days(sell_days, sales, days, wd.get("n"))
            rows.append({"weapon": info["name"], "url": url, "type": info["type"], "listing": l, "score": s, "tags": tags,
                         "fair": fair, "margin": margin, "sales": sales, "days": days, "n": wd.get("n", len(scored)),
                         "ask": ask, "got": got, "de": de, "de_fair": dfair, "basis": basis, "calib": k,
                         "t7": t7, "t30": t30, "n_sold": len(sold), "sell_days": sell_days,
                         "median": hist[-1][1] if hist else None, "hist_days": len(hist), "age": age,
                         "exp_days": exp_days, "per_day": margin / (exp_days + 1.0),
                         "bid": bool(l.get("bid")), "contacted": contacted.get(str(l["id"])),
                         "pop": WK.popularity(info["name"])})
    if str(CFG.get("riven_sort") or "day") == "margin":
        rows.sort(key=lambda r: -r["margin"])
    else:
        rows.sort(key=lambda r: -r["per_day"])
    return rows


def comparables(store, row, index, n=8):
    """The listings and likely-sold rivens of the same weapon closest to this riven's stats score (the detail panel):
    [(score, price, listing, "listed" | "sold")], closest first."""
    wd = store.d["weapons"].get(row["url"]) or {}
    out = []
    for l in wd.get("listings") or []:
        if l["id"] != row["listing"]["id"]:
            out.append((stats_score(l, row["type"], R.DISPOSITION, index, None, row["weapon"])[0], l["price"], l, "listed"))
    for x in store.likely_sold(row["url"]):
        out.append((stats_score(x, row["type"], R.DISPOSITION, index, None, row["weapon"])[0], x["price"], x, "sold"))
    mine = set(positives(row["listing"], index))
    out.sort(key=lambda o: (-len(mine & set(positives(o[2], index))), abs(o[0] - row["score"])))
    return out[:n]


def backtest(store, weapons_by_url, index, factor=None):
    """How close the fair price comes to what rivens likely sold for: every likely-sold riven is priced from the other
    listings of its weapon and compared with its price. {"n", "mae" (median error, fraction), "bias" (median of
    (fair - sold) / sold: + = fair price too high)} or None with fewer than 5 cases."""
    factor = float(CFG["riven_sell_factor"]) / 100.0 if factor is None else factor
    errs = []
    w = weights()
    for url, wd in store.d["weapons"].items():
        info = weapons_by_url.get(url) or {"name": wd.get("name", url), "type": ""}
        comps = [(stats_score(l, info["type"], R.DISPOSITION, index, w, info["name"])[0], l["price"], positives(l, index),
                  l["seller"]) for l in wd.get("listings") or []]
        for x in store.likely_sold(url):
            if x["price"] <= 0:
                continue
            s = stats_score(x, info["type"], R.DISPOSITION, index, w, info["name"])[0]
            f = fair_price(s, comps, factor, tags=positives(x, index))
            if f:
                errs.append((f - x["price"] * SOLD_FACTOR) / (x["price"] * SOLD_FACTOR))
    if len(errs) < 5:
        return None
    return {"n": len(errs), "mae": statistics.median(abs(e) for e in errs), "bias": statistics.median(errs)}


_dispo_cache = {}


def _dispo(name):
    key = R._norm(name)
    if not _dispo_cache:
        for _p, (n, d) in R.data()["weapons"].items():
            _dispo_cache.setdefault(R._norm(n), d)
    return _dispo_cache.get(key, 0)


def auction_url(listing):
    return "https://warframe.market/auction/" + str(listing["id"])


WHISPER = "/w {seller} Hi, I would like to buy {weapon} {riven} for {price} platinum"


def whisper(row):
    """The in-game message to the seller, from the template in Settings (riven_whisper: {seller}, {weapon}, {riven},
    {price} are filled in)."""
    l = row["listing"]
    tpl = str(CFG.get("riven_whisper") or WHISPER)
    try:
        return tpl.format(seller=l["seller"], weapon=row["weapon"], riven=l["name"], price=l["price"])
    except (KeyError, IndexError, ValueError):
        return WHISPER.format(seller=l["seller"], weapon=row["weapon"], riven=l["name"], price=l["price"])


# ---------- live check of the best deals: is the seller online now, is the riven still listed? ----------
# One request per deal: GET /v1/auctions/entry/{id} gives the auction as it is now (closed / still visible, price) with
# its owner's status (ingame / online / offline). Its own limiter, slow on purpose (LIVE_RPM a minute, never above 10),
# and paused while a riven scan runs, so the riven requests together stay inside the 10-20 a minute warframe.market asks.
LIVE_RPM = 6
LIVE = {}                                   # auction id -> {"status", "gone", "price", "t", "last_seen"}
_live_lock = threading.Lock()


def live(listing):
    """What the last live check said about this listing ({} when not checked, or checked too long ago)."""
    with _live_lock:
        x = LIVE.get(str(listing.get("id")))
    if not x or time.time() - x["t"] > 15 * 60:
        return {}
    return x


def check_listing(listing, limiter, cancel=None):
    """The auction as it is now: {"status", "gone", "price", "t", "last_seen"}. Raises RivenError / RivenRateLimited."""
    now = time.time()
    try:
        j = get_json(f"{V1}/auctions/entry/{listing['id']}", limiter, cancel=cancel)
    except RivenError as e:
        if "HTTP 404" in str(e):                      # removed (sold, withdrawn)
            out = {"status": "", "gone": True, "price": None, "t": now, "last_seen": ""}
            with _live_lock:
                LIVE[str(listing["id"])] = out
            return out
        raise
    a = ((j or {}).get("payload") or {}).get("auction") or {}
    owner = a.get("owner")
    status = str((owner or {}).get("status") or "").lower() if isinstance(owner, dict) else ""
    seen = str((owner or {}).get("last_seen") or "") if isinstance(owner, dict) else ""
    if not status and listing.get("seller"):             # the owner given as an id only: ask its profile
        p = get_json(f"{V1}/profile/{listing['seller']}", limiter, cancel=cancel)
        prof = ((p or {}).get("payload") or {}).get("profile") or {}
        status, seen = str(prof.get("status") or "").lower(), str(prof.get("last_seen") or "")
    out = {"status": status, "gone": bool(a.get("closed")) or a.get("visible") is False or bool(a.get("private")),
           "price": a.get("buyout_price"), "t": now, "last_seen": seen}
    with _live_lock:
        LIVE[str(listing["id"])] = out
    return out


class LiveChecker:
    """Checks the best deals one after another, again and again (each about every riven_live_minutes): the table
    shows whether the seller is in game now. rows(): the deals to check (best first); busy(): True while a scan runs."""

    def __init__(self, rows, busy, market=None, on_change=None):
        self.rows, self.busy, self.on_change = rows, busy, on_change
        self.limiter = Limiter(rpm=min(10, max(1, int(CFG.get("riven_live_rpm") or LIVE_RPM))), market=market)
        self.stop = threading.Event()
        self.thread = None
        self.paused_until = 0.0

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.stop.clear()
            self.thread = threading.Thread(target=self._run, daemon=True, name="riven-live")
            self.thread.start()

    def _next(self):
        top = int(CFG.get("riven_live_top") or 0)
        if top <= 0:
            return None
        every = max(1.0, float(CFG.get("riven_live_minutes") or 3)) * 60
        now = time.time()
        due = []
        for r in (self.rows() or [])[:top]:
            l = r["listing"]
            x = LIVE.get(str(l["id"]))
            if x and x.get("gone"):
                continue
            if not x or now - x["t"] >= every:
                due.append((x["t"] if x else 0, l))
        return min(due, key=lambda d: d[0])[1] if due else None

    def _run(self):
        while not self.stop.is_set():
            if self.busy() or time.time() < self.paused_until:
                self.stop.wait(5)
                continue
            l = self._next()
            if l is None:
                self.stop.wait(10)
                continue
            before = dict(LIVE.get(str(l["id"])) or {})
            try:
                now = check_listing(l, self.limiter, cancel=self.stop)
            except RivenRateLimited:
                self.paused_until = time.time() + 15 * 60    # the site said "too many": leave it alone for a while
                log("live check: rate limited, paused for 15 minutes")
                continue
            except RivenError as e:
                log(f"live check of {l.get('id')}: {e}")
                self.stop.wait(30)
                continue
            if self.on_change and (before.get("status") != now["status"] or before.get("gone") != now["gone"]):
                self.on_change(l, now, before)
