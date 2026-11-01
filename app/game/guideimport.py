"""Builds from community guides on the web: a Google Doc (the Aya farming guide), arbi.guide (Arbitrations), wfpedia
(Endo farming) or any page that writes its builds as text.

How: the page is downloaded (a Google Doc as its HTML export, the tab in the link included), cut into blocks (headings,
paragraphs, list items, pictures) and read for the names the game data knows: Warframes, weapons and companions start a
build; the mods, Arcanes, Archon Shards and Helminth abilities written after it (until the next item) are its build,
when they fit that item. "rank 7" after a mod's name sets its rank. Pictures are kept with the build they follow: many
guides show the layout only as a screenshot, and the planner reads those with its picture import (OCR).

Nothing is guessed beyond the names written in the guide: read the result like any other import."""
import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse

from app.game import arcanes as A
from app.game import buildcalc as BC
from app.game import loadouts as LO

ITEM_KINDS = ("warframe", "primary", "secondary", "melee", "archgun", "archmelee", "archwing", "companion", "compweapon")
UA = "Mozilla/5.0 (TauTools build import)"
MAX_PAGE = 8 << 20
MAX_IMAGE = 8 << 20
SHARD_COLOR = {"crimson": "RED", "azure": "BLUE", "emerald": "GREEN", "amber": "YELLOW", "topaz": "ORANGE",
               "violet": "PURPLE"}
ORDINAL = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}
_PREFIX = re.compile(r"^(Primed|Amalgam|Umbral|Archon|Flawed|Galvanized)\s+", re.I)

# guides offered in the import window (the link can be any other page)
KNOWN = [("Aya farming (Google Doc)",
          "https://docs.google.com/document/d/1DWYUPPW_VPuSEk2VJKV7m-vk2FGmKfxs-xmAv9UGm9k/edit?tab=t.xmhqee68riyo"),
         ("Arbitrations (arbi.guide)", "https://arbi.guide/"),
         ("Endo farming (wfpedia)", "https://wfpedia.com/posts/endo/basics")]


class GuideError(Exception):
    pass


# ---------- downloading ----------
def page_url(url: str) -> str:
    """The address to download: a Google Doc's HTML export (its tab too); other pages as they are."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    u = urlparse(url)
    m = re.search(r"/document/d/([\w-]+)", u.path)
    if u.hostname and u.hostname.endswith("docs.google.com") and m:
        tab = (parse_qs(u.query).get("tab") or [""])[0]
        return f"https://docs.google.com/document/d/{m.group(1)}/export?format=html" + (f"&tab={tab}" if tab else "")
    return url


def fetch(url: str, timeout: float = 25.0, limit: int = MAX_PAGE) -> bytes:
    import requests
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise GuideError("not a web address")
    try:
        with requests.get(url, headers={"User-Agent": UA}, timeout=timeout, stream=True) as r:
            if r.status_code != 200:
                raise GuideError(f"HTTP {r.status_code}")
            out = b""
            for chunk in r.iter_content(1 << 16):
                out += chunk
                if len(out) > limit:
                    raise GuideError("the page is too large")
            return out
    except GuideError:
        raise
    except Exception as e:
        raise GuideError(f"{type(e).__name__}: {e}")


# ---------- the page as blocks ----------
class _Blocks(HTMLParser):
    """[("h", level, text) | ("p", 0, text) | ("img", 0, url)] in reading order; scripts, styles and menus left out."""
    BLOCK = {"p", "li", "td", "th", "div", "dd", "dt", "blockquote", "pre", "figcaption", "tr", "section", "article"}
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "svg", "head", "button", "select"}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.buf, self.kind, self.skip = base, [], [], "p", 0
        self.links = []

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if text:
            self.out.append((self.kind[0], int(self.kind[1:] or 0) if self.kind.startswith("h") else 0, text))
        self.buf, self.kind = [], "p"

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        a = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self._flush()
            self.kind = tag
        elif tag in self.BLOCK:
            self._flush()
        elif tag == "br":
            self._flush()
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            if src and not src.startswith("data:"):
                self._flush()
                self.out.append(("img", 0, urljoin(self.base, src)))
        elif tag == "a" and a.get("href"):
            self.links.append(urljoin(self.base, a["href"]))

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)

    def close(self):
        super().close()
        self._flush()


def blocks(html: str, base: str = "") -> tuple:
    """(blocks, links) of a page (see _Blocks)."""
    b = _Blocks(base)
    b.feed(html)
    b.close()
    return b.out, b.links


# ---------- names ----------
_names = None


def _names_index():
    """(regex of every known name, {lower name: (what, name, kind)}): what = item / mod / arcane / helminth."""
    global _names
    if _names is None:
        idx = {}
        for kind in ITEM_KINDS:
            for n in BC.items(kind):
                idx.setdefault(n.lower(), ("item", n, kind))
        for n in LO.data().get("mst", {}):
            idx.setdefault(n.lower(), ("mod", n, ""))
        for n in LO.data().get("arc", {}):
            idx[n.lower()] = ("arcane", n, "")
        try:
            from app.ui import abilitybar as AB
            for n, path in AB.helminth_choices():
                idx.setdefault(n.lower(), ("helminth", n, path))
        except Exception:
            pass
        names = sorted({v[1] for v in idx.values() if len(v[1]) >= 3}, key=len, reverse=True)
        long_ = [re.escape(n) for n in names if len(n) >= 5]
        short = [re.escape(n) for n in names if len(n) < 5]
        rx_long = re.compile(r"(?<![\w'])(" + "|".join(long_) + r")(?![\w'])", re.I) if long_ else None
        rx_short = re.compile(r"(?<![\w'])(" + "|".join(short) + r")(?![\w'])") if short else None
        _names = (rx_long, rx_short, idx)
    return _names


RANK_AFTER = re.compile(r"^\s*[\(\[,:-]?\s*(?:r(?:ank)?\.?\s*)(\d{1,2})\b", re.I)
RANK_BEFORE = re.compile(r"\b(?:r(?:ank)?\.?\s*)(\d{1,2})\s*$", re.I)


def find_names(text: str) -> list:
    """[(what, name, kind or path, rank or None, start)] of the known names in a text, in reading order; a longer name
    wins over the shorter ones inside it (Primed Continuity, not Continuity)."""
    rx_long, rx_short, idx = _names_index()
    spans = []
    for rx in (rx_long, rx_short):
        if rx is None:
            continue
        for m in rx.finditer(text):
            spans.append((m.start(), m.end(), m.group(1)))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    out, end = [], -1
    for a, b, word in spans:
        if a < end:
            continue
        what, name, extra = idx.get(word.lower(), (None, None, None))
        if not what:
            continue
        rank = None
        m = RANK_AFTER.match(text[b:b + 14]) or RANK_BEFORE.search(text[max(0, a - 10):a])
        if m:
            rank = int(m.group(1))
        out.append((what, name, extra, rank, a))
        end = b
    return out


_SHARD_STRICT = re.compile(r"(?:(\d)\s*x?\s*)?(tauforged\s+)?(crimson|azure|emerald|amber|topaz|violet)\s+archon\s+shards?"
                           r"(?:\s*\(([^)]*)\))?([^,;\n]*)", re.I)
# a line that speaks of shards may name only the colours: "Shards: 2 Azure (energy), Crimson strength"
_SHARD_LOOSE = re.compile(r"(?:(\d)\s*x?\s*)?(tauforged\s+)?\b(crimson|azure|emerald|amber|topaz|violet)\b"
                          r"(?:\s+archon)?(?:\s+shards?)?(?:\s*\(([^)]*)\))?([^,;\n]*)", re.I)


def _shards(text: str) -> list:
    """Archon Shards written in a text ("3x Tauforged Violet Archon Shard (Melee CD)", "2x Azure Archon Shard Energy
    Max", or on a line about shards "2 Azure (energy), Crimson strength"). The words in brackets or after the shard
    pick its bonus; none = the colour's first bonus."""
    out = []
    found = list(_SHARD_STRICT.finditer(text))
    if not found and "shard" in text.lower():
        found = list(_SHARD_LOOSE.finditer(text))
    for m in found:
        color = SHARD_COLOR[m.group(3).lower()]
        want = set(re.findall(r"[a-z]+", ((m.group(4) or "") + " " + (m.group(5) or "")).lower()))
        want |= {"critical"} if "cd" in want or "crit" in want else set()
        want |= {"damage"} if "cd" in want else set()
        want |= {"armor"} if "armour" in want else set()
        rows = BC.SHARD_CHOICES.get(color) or []
        best = max(rows, key=lambda r: len(want & set(re.findall(r"[a-z]+", r[1].lower()))), default=None)
        if not best:
            continue
        for _ in range(int(m.group(1) or 1)):
            out.append({"color": color, "key": best[0], "tauforged": bool(m.group(2))})
    return out[:5]


def _fits(kind, item, name, arcane=False) -> bool:
    if arcane:
        return any(name in A.slot_candidates(kind, item, n) for n in range(2))
    roles = set(BC.plan_roles(kind, item)) - {"arcane"}
    return any(name in BC.candidates(kind, item, r) for r in roles)


def parse(html: str, base: str = "") -> dict:
    """{"builds": [{"title", "item", "kind", "mods": [(name, rank)], "arcanes": [(name, rank)], "shards", "helminth",
    "images": [url], "notes": [names that did not fit]}], "links": [urls], "images": n} of a guide page."""
    bl, links = blocks(html, base)
    builds, cur = [], None
    heading = ""
    for typ, level, text in bl:
        if typ == "img":
            if cur is not None:
                cur["images"].append(text)
            continue
        found = find_names(text)
        items = [f for f in found if f[0] == "item"]
        bare = text.strip(" *•-☆🔻·")
        is_title = typ == "h" or bool(items and (
            (len(text) <= 90 and len(items[0][1]) >= 0.3 * len(bare))           # a short line that is mostly a name
            or (bare.lower().startswith(items[0][1].lower())                     # "Kuva Ogris: Heavy Caliber, …"
                and re.match(r"\s*(\(.*?\))?\s*[:\-–—]", bare[len(items[0][1]):]))))
        if typ == "h":
            heading = text
        if items and is_title:
            what, name, kind, _r, _a = items[0]
            cur = {"title": text if typ == "h" else (heading or text), "item": name, "kind": kind, "mods": [],
                   "arcanes": [], "shards": [], "helminth": None, "images": [], "notes": []}
            builds.append(cur)
            found = [f for f in found if f is not items[0]]
        if cur is None:
            continue
        cur["shards"] += _shards(text)
        for what, name, extra, rank, _a in found:
            if what == "mod":
                if not _fits(cur["kind"], cur["item"], name):
                    cur["notes"].append(name)
                elif name not in [m[0] for m in cur["mods"]]:
                    cur["mods"].append((name, rank))
            elif what == "arcane":
                if not _fits(cur["kind"], cur["item"], name, arcane=True):
                    cur["notes"].append(name)
                elif name not in [m[0] for m in cur["arcanes"]]:
                    cur["arcanes"].append((name, rank))
            elif what == "helminth" and cur["kind"] == "warframe" and cur["helminth"] is None \
                    and re.search(r"subsum|helminth|infus", text, re.I):
                slot = next((v for k, v in ORDINAL.items() if re.search(r"\b" + k + r"\b", text, re.I)), 1)
                cur["helminth"] = {"slot": slot, "path": extra}
    keep = [b for b in builds if b["mods"] or b["arcanes"] or b["images"]]
    # the same item named again later without anything new: drop the empty repeats
    for b in keep:
        b["shards"] = b["shards"][:5]
    return {"builds": keep, "links": list(dict.fromkeys(links)), "images": sum(len(b["images"]) for b in keep)}


def build_links(links: list, base: str, limit: int = 12) -> list:
    """Links of the same site that look like build pages (wfpedia's "…-build" pages, say): read with "follow links"."""
    host = urlparse(base).hostname
    out = []
    for u in links:
        p = urlparse(u)
        if p.hostname == host and re.search(r"build", p.path, re.I) and u.split("#")[0] != base.split("#")[0]:
            out.append(u.split("#")[0])
    return list(dict.fromkeys(out))[:limit]


def read(url: str, follow: bool = False, progress=lambda _t: None) -> dict:
    """Downloads a guide and finds its builds (follow: also the build pages it links to on the same site)."""
    target = page_url(url)
    progress(target)
    html = fetch(target).decode("utf-8", errors="replace")
    res = parse(html, target)
    res["source"] = target
    if follow:
        for u in build_links(res["links"], target):
            progress(u)
            try:
                sub = parse(fetch(u).decode("utf-8", errors="replace"), u)
            except GuideError:
                continue
            for b in sub["builds"]:
                b["source"] = u
            res["builds"] += sub["builds"]
            res["images"] += sub["images"]
    return res


def download_image(url: str, folder) -> str:
    """Saves a guide's picture (for the picture import) and returns its path."""
    from pathlib import Path
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data = fetch(url, limit=MAX_IMAGE)
    ext = ".png" if data[:8].startswith(b"\x89PNG") else ".jpg" if data[:3] == b"\xff\xd8\xff" else \
        ".webp" if data[8:12] == b"WEBP" else ".gif" if data[:4] == b"GIF8" else ".img"
    path = folder / (hashlib.sha1(url.encode()).hexdigest()[:16] + ext)
    path.write_bytes(data)
    return str(path)


# ---------- into the planner's slots ----------
def family(name: str) -> str:
    return _PREFIX.sub("", name or "").strip().lower()


def place(kind: str, item: str, roles: list, mods: list, arcanes: list) -> tuple:
    """([(name, rank) or None per slot], [names that found no slot]) for a build's mods and Arcanes: an Aura / Stance in
    its slot, the general slots in the guide's order, an Exilus mod that does not fit a general slot (or once they are
    full) in the Exilus slot, the Arcanes in their slots (the same one only once). Ranks: the guide's, else the top."""
    out = [None] * len(roles)
    unplaced, fams = [], set()

    def top(name, arc=False):
        if arc:
            return A.max_rank(name)
        info = BC.mod_info(name)
        return info[2] if info else 0
    for name, rank in mods:
        fam = family(name)
        if fam in fams:
            continue                                   # Vitality and Primed Vitality: the first one written
        mx = top(name)
        r = mx if rank is None else max(0, min(mx, int(rank)))
        order = []
        for want in ("aura", "stance"):
            if want in roles and name in BC.candidates(kind, item, want):
                order.append(want)
        if name in BC.candidates(kind, item, "general"):
            order.append("general")
        if "exilus" in roles and name in BC.candidates(kind, item, "exilus"):
            order.append("exilus")
        slot = None
        for want in order:
            slot = next((i for i, rl in enumerate(roles) if rl == want and out[i] is None), None)
            if slot is not None:
                break
        if slot is None:
            unplaced.append(name)
            continue
        out[slot] = (name, r)
        fams.add(fam)
    ordinal, used = 0, set()
    for i, rl in enumerate(roles):
        if rl != "arcane":
            continue
        cands = A.slot_candidates(kind, item, ordinal)
        ordinal += 1
        pick = next(((n, rk) for n, rk in arcanes if n in cands and n not in used), None)
        if pick:
            mx = top(pick[0], True)
            out[i] = (pick[0], mx if pick[1] is None else max(0, min(mx, int(pick[1]))))
            used.add(pick[0])
    unplaced += [n for n, _r in arcanes if n not in used]
    return out, unplaced
