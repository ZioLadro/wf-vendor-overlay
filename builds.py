"""Builds: lists of mods you want for a Warframe / weapon / companion, checked against your inventory.

A build is added from an Overframe link (the page is downloaded once, on your request, and the mod names written in
it are picked out) or from a pasted list of mod names. You review the mods found before saving. For every saved build
the tab shows which mods you already own and what the missing ones cost on warframe.market.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from config import APP_DIR

BUILDS_FILE = APP_DIR / "builds.json"
LOG_FILE = APP_DIR / "builds.log"
ALLOWED_HOSTS = ("overframe.gg", "www.overframe.gg")
MAX_PAGE = 3_000_000
UA = "WFVendorOverlay (build import; user-initiated)"

# Overframe abbreviates some prefixes ("Arc. Flow", "Trans. Fortitude")
ABBREV = [(re.compile(r"\bArc\.\s*"), "Arcane "), (re.compile(r"\bTrans\.\s*"), "Transient "),
          (re.compile(r"\bPrim\.\s*"), "Primed ")]
MAX_PRECHECKED = 10


class BuildError(Exception):
    pass


def log(msg: str):
    """One line in builds.log (kept under ~200 KB): what a page import saw, to diagnose a failing import."""
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 200_000:
            LOG_FILE.write_text("", encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


# ---------- reading a page ----------
class _SameHost(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).hostname not in ALLOWED_HOSTS:
            raise BuildError("redirected to another site")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_url(url: str) -> str:
    url = (url or "").strip()
    if url and "://" not in url:
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        raise BuildError("only overframe.gg links are accepted")
    return url


def fetch_page(url: str, timeout: float = 15.0) -> str:
    """HTML of an Overframe page. Raises BuildError (with the HTTP status when there is one)."""
    url = check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
                                               "Accept-Language": "en"})
    try:
        with urllib.request.build_opener(_SameHost).open(req, timeout=timeout) as r:
            raw = r.read(MAX_PAGE + 1)
            log(f"GET {url} -> {r.status}, {len(raw)} bytes, {r.headers.get('Content-Type', '')}")
    except BuildError:
        raise
    except urllib.error.HTTPError as e:
        log(f"GET {url} -> HTTP {e.code} {e.reason}")
        if e.code in (401, 403, 429, 503):
            raise BuildError(f"HTTP {e.code}: overframe.gg refuses automatic downloads (see 'Add from text')")
        raise BuildError(f"HTTP {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        log(f"GET {url} failed: {type(e).__name__}: {e}")
        raise BuildError(f"{type(e).__name__}: {e}")
    if len(raw) > MAX_PAGE:
        raise BuildError("page too large")
    return raw.decode("utf-8", errors="replace")


def page_title(page: str) -> str:
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', page, re.I) \
        or re.search(r"<title[^>]*>([^<]+)</title>", page, re.I)
    if not m:
        return ""
    title = html.unescape(m.group(1)).strip()
    return re.sub(r"\s*[|\-–]\s*Overframe.*$", "", title, flags=re.I)[:80]


_ATTR = re.compile(r"""\b(?:alt|title|aria-label|data-name|data-tip|data-tooltip)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)


def _tag_to_text(m):
    """A tag becomes a space plus the texts of its alt/title/aria-label attributes (mod cards are often images)."""
    vals = [a or b for a, b in _ATTR.findall(m.group(0))]
    return " \n ".join([""] + [html.unescape(v) for v in vals if v.strip()] + [""]) if vals else " "


def page_text(page: str, with_scripts=False) -> str:
    if not with_scripts:
        page = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page)
    text = re.sub(r"<[^>]+>", _tag_to_text, page)
    return html.unescape(text)


_JSON_SCRIPT = re.compile(r"""(?is)<script\b[^>]*(?:id=["']__NEXT_DATA__["']|type=["']application/(?:ld\+)?json["'])[^>]*>(.*?)</script>""")
_BUILD_KEYS = ("mod", "slot", "build", "loadout", "equip", "arcane")
_REFERENCE_KEYS = ("suggest", "option", "alternat", "reference", "catalog", "allmods", "all_mods", "available")


def json_mods(page: str, market) -> list:
    """Mod names found in the page's JSON data (Next.js pages keep their data there), only inside parts whose key
    path looks like a build (mods / slots / loadout...) and not like a list of options. [(slug, name)]."""
    rx, by_name = _regex(market)
    if rx is None:
        return []
    out, seen = [], set()

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [str(k).lower()])
        elif isinstance(node, list):
            for v in node:
                walk(v, path)
        elif isinstance(node, str) and 2 < len(node) < 60:
            joined = "/".join(path)
            if any(k in joined for k in _BUILD_KEYS) and not any(k in joined for k in _REFERENCE_KEYS):
                name = expand(node.strip())
                slug = by_name.get(name)
                if slug and slug not in seen:
                    seen.add(slug)
                    out.append((slug, name))

    for m in _JSON_SCRIPT.finditer(page):
        try:
            walk(json.loads(m.group(1)), [])
        except ValueError:
            continue
    return out


def extract_from_page(page: str, market, url: str = ""):
    """Best effort on an Overframe page. Returns (mods, how): how = "json" (build data), "text" (page text, which
    may include suggestion lists), "scripts" (anything in the page source, noisy) or "" (nothing). Logs what it saw."""
    j = json_mods(page, market)
    text = extract_mods(page_text(page), market)
    scripts = extract_mods(page_text(page, with_scripts=True), market)
    log(f"page {url}: {len(page)} chars, json_script={'yes' if _JSON_SCRIPT.search(page) else 'no'}, "
        f"mods: json={len(j)} text={len(text)} scripts={len(scripts)}")
    if len(j) >= 3:
        return j, "json"
    if text:
        return text, "text"
    if scripts:
        return scripts, "scripts"
    return [], ""


def expand(text: str) -> str:
    for rx, full in ABBREV:
        text = rx.sub(full, text)
    return text


# ---------- picking mod names out of text ----------
_rx_cache = (None, None)


def _regex(market):
    global _rx_cache
    names = market.catalog_names(("mod", "arcane"))
    key = len(names)
    if _rx_cache[0] == key:
        return _rx_cache[1]
    by_name = {n: s for n, s in names}
    alt = "|".join(re.escape(n) for n in sorted(by_name, key=len, reverse=True))
    rx = re.compile(r"(?<![A-Za-z'])(?:" + alt + r")(?![A-Za-z'])") if alt else None
    _rx_cache = (key, (rx, by_name))
    return _rx_cache[1]


def extract_mods(text: str, market) -> list:
    """[(slug, name)] of the known mod/arcane names found in the text, in order of first appearance."""
    rx, by_name = _regex(market)
    if rx is None:
        return []
    seen, out = set(), []
    for m in rx.finditer(expand(text)):
        slug = by_name[m.group(0)]
        if slug not in seen:
            seen.add(slug)
            out.append((slug, m.group(0)))
    return out


def parse_list(text: str, market) -> list:
    """A pasted list, one mod per line ("Serration", "Serration - rank 10", "• Blind Rage"...).
    Returns [(slug | None, name)]; unknown names keep slug None."""
    out, seen = [], set()
    for line in expand(text).splitlines():
        name = re.sub(r"^[\s\-–•*·\d.)]+", "", line)
        name = re.split(r"\s+[-–(]\s*(?:rank|r)\b|\s*\(|\s{2,}|\t", name, maxsplit=1, flags=re.I)[0].strip(" \t,;:")
        if len(name) < 3:
            continue
        slug = market.slug_for_name(name)
        if not slug:
            m = market.match(name, 85)
            slug, name = (m.slug, market.info(m.slug).get("name", name)) if m else (None, name)
        else:
            name = market.info(slug).get("name", name)
        key = slug or name.lower()
        if key not in seen:
            seen.add(key)
            out.append((slug, name))
    return out


# ---------- storage ----------
class BuildStore:
    def __init__(self, path=None):
        self.path = path or BUILDS_FILE
        self.builds = []
        self.version = 0
        self.load()

    def load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        for b in (d.get("builds") if isinstance(d, dict) else []) or []:
            if isinstance(b, dict) and b.get("id") and isinstance(b.get("mods"), list):
                self.builds.append({"id": b["id"], "name": str(b.get("name", ""))[:80], "url": b.get("url", ""),
                                    "added": b.get("added", 0),
                                    "mods": [{"slug": m.get("slug"), "name": str(m.get("name", ""))}
                                             for m in b["mods"] if isinstance(m, dict)]})

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"version": 1, "builds": self.builds}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass
        self.version += 1

    def add(self, name: str, mods, url: str = "") -> dict:
        b = {"id": f"{int(time.time() * 1000)}", "name": name.strip()[:80], "url": url, "added": int(time.time()),
             "mods": [{"slug": s, "name": n} for s, n in mods]}
        self.builds.append(b)
        self.save()
        return b

    def get(self, bid):
        return next((b for b in self.builds if b["id"] == bid), None)

    def remove(self, bid):
        self.builds = [b for b in self.builds if b["id"] != bid]
        self.save()

    def rename(self, bid, name):
        b = self.get(bid)
        if b:
            b["name"] = name.strip()[:80]
            self.save()


# ---------- checking a build against the inventory and the prices ----------
OK, LOW, MISSING, UNKNOWN = "ok", "low", "missing", "unknown"


def evaluate(build: dict, inventory, market) -> dict:
    """Rows (one per mod) and totals. Prices come from the saved market data only (no network).
    ok = you have it at max rank; low = you have it but not at max rank (needs Endo, no platinum);
    missing = you do not have it (cost = what it sells for: max-rank price for ranked mods);
    unknown = not a warframe.market item (not tradable, or a name that was not recognised)."""
    rows, cost, n_missing, n_unknown, no_price = [], 0, 0, 0, []
    for m in build["mods"]:
        slug = m.get("slug")
        if not slug:
            rows.append({"name": m["name"], "slug": None, "status": UNKNOWN, "price": None, "vol": None, "cost": 0})
            n_unknown += 1
            continue
        info = market.info(slug)
        ranked = info.get("max_rank", 0) > 0
        e = inventory.items.get(slug, {"n": 0, "m": 0})
        if e["n"] > 0 and (e["m"] > 0 or not ranked):
            status = OK
        elif e["n"] > 0:
            status = LOW
        else:
            status = MISSING
        c = market.cached(slug) or {}
        price = (c.get("pmax") or c.get("price")) if ranked else c.get("price")
        row_cost = 0
        if status == MISSING:
            n_missing += 1
            if price is None:
                no_price.append(slug)
            else:
                row_cost = int(price)
        cost += row_cost
        rows.append({"name": info.get("name") or m["name"], "slug": slug, "status": status, "price": price,
                     "vol": c.get("vol"), "cost": row_cost, "owned": e["n"]})
    return {"rows": rows, "cost": cost, "missing": n_missing, "unknown": n_unknown, "total": len(rows),
            "no_price": no_price, "low": sum(1 for r in rows if r["status"] == LOW)}
