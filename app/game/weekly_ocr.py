"""What the vendor screen itself says about the limited offers (Weekly tab), as a second check of what you bought,
besides the game file. Read from the text of every scan (automatic or F8), the same OCR that reads the prices.

What the game shows (checked on Palladino, Archimedean Yonta, Acrithis, Kaya Velasco, Flare Varleon, Teshin):
  - a limited offer whose limit you reached stays in the list with "PURCHASE LIMIT REACHED" over its card (the name
    still under it): that offer is bought out;
  - some vendors drop it from the list instead: an offer seen earlier this period and now missing, while the rest of
    that view is still there and nothing took its place (a scroll swaps as many offers as it hides), is bought out;
  - an offer listed without the overlay is still on sale.
Names are written "35.000 X Kuva", "150,000 Credits", "6.000 Endo" (the amount first), often on two lines
("Arcane Universal" / "Fallout") and sometimes with the OCR gluing words ("Requiem IRelic"): the amount is taken off,
two lines of the same card are joined, and names are compared without spaces. A few offers have another name on
screen than in the game data (the Requiem relics). The vendor is the one with the most offers on screen, or the one
named in the header ("THE STEEL PATH HONORS", "PALLADINO", "ARCHIMEDEAN YONTA"…, read loosely: the OCR often keeps
only part of it), among the vendors that can be open where you are (the game's log: Archimedean Yonta only in the
Chrysalith, Palladino only in Iron Wake…; vendors open anywhere, like Teshin, always count). Two offers with the same name (Teshin's Kuva ×10,000 and ×50,000) are told apart by the amount;
when it cannot be read they are not used as evidence.

What it is used for: an offer on sale cannot be the purchase being identified (when its limit would be reached), and
an assignment saying it was is asked again; a bought-out offer identifies the purchase, or shows as bought "(OCR)" until
the game file says so too. Kept in weekly_state.json (key "ocr") until each offer's own reset."""
import re
import time

from app.scan.matcher import norm

MIN_OFFERS = 2                       # offers of one vendor read on screen before it counts as that vendor's screen
_index = None


def period_end(offer: dict, now: float, vendor: str = "") -> float:
    """When an observation of this offer stops meaning anything: its limit resets. Offers without a period in the game
    data are the rotating ones (Teshin's weekly offer: the next Monday) or, at an event vendor, the event's own limit."""
    from app.game.weekly import EVENT_HINT, next_reset
    h = int(offer.get("hours") or 0)
    if h == 168:
        return next_reset(now)
    if h == 24:
        return (int(now // 86400) + 1) * 86400
    if h > 0:
        return now + h * 3600
    if not any(x in vendor for x in EVENT_HINT):
        return next_reset(now)
    return now + 30 * 86400                  # an event's lifetime limit: a month is plenty


# the header the game shows for a vendor (the vendor manifest's last part -> words, spaces left out when compared)
HEADERS = {"TeshinHardModeVendorManifest": ("thesteelpathhonors", "teshin"),
           "IronwakeDondaVendorManifest": ("palladino", "ironwake"),
           "ArchimedeanVendorManifest": ("archimedeanyonta", "archimedean"),
           "AcrithisVendorManifest": ("acrithis",),
           "Nova1999ConquestShopManifest": ("kayavelasco",),
           "Temple1999VendorManifest": ("flarevarleon", "memorabilia"),
           "NightcapVendorManifest": ("nightcap",),
           "AspirantZorbaVendorManifest": ("zorba",),
           "HunhowVendorManifest": ("hunhow",),
           "EntratiLabVendorManifest": ("cavia", "bird3"),
           "ShadowgrapherEventVendorManifest": ("shadowgrapher",)}
# offers the game names otherwise on screen than in its data
ALIASES = {"T5 Void Projection Immortal ABronze": "Requiem I Relic", "T5 Void Projection Immortal BBronze": "Requiem II Relic",
           "T5 Void Projection Immortal CBronze": "Requiem III Relic", "T5 Void Projection Immortal DBronze": "Requiem IV Relic"}
_LIMIT = re.compile(r"purchase\s*limit|limit\s*reach|^\s*reached\s*$", re.I)
_AMOUNT = re.compile(r"^\s*(\d{1,3}(?:[.,\s]\d{3})+|\d+)\s*[xX×]?\s+(?=\D)")


def key(s: str) -> str:
    """A name compared without spaces or punctuation (the OCR glues or splits words)."""
    return re.sub(r"[^a-z0-9]", "", norm(s))


def split_amount(text: str) -> tuple:
    """("35.000 X Kuva") -> (35000, "Kuva"); a text without an amount in front -> (None, text)."""
    m = _AMOUNT.match(text or "")
    if not m:
        return None, text or ""
    try:
        return int(re.sub(r"[.,\s]", "", m.group(1))), text[m.end():]
    except ValueError:
        return None, text


def _vendor_words(vend: str, name: str) -> tuple:
    """Header words of a vendor: the known ones, else the first word of its name ("Teshin (Steel Path)" -> teshin)."""
    last = vend.rstrip("/").rsplit("/", 1)[-1]
    if last in HEADERS:
        return HEADERS[last]
    base = re.split(r"[(·]", name)[0]
    return tuple(key(w) for w in norm(base).split() if len(w) >= 5)


def index():
    """{vendor: {"names": {name key: [offers]}, "words": (header words)}}; every offer gets "shown_qty", the amount
    written on its card when the data puts it in the name ("150000 Credits")."""
    global _index
    if _index is None:
        from app.game.weekly import data
        out = {}
        for vend, v in data().items():
            names = {}
            for i in v.get("items") or []:
                qty, base = split_amount(ALIASES.get(i.get("name") or "", i.get("name") or ""))
                k = key(base)
                if len(k) >= 4:
                    names.setdefault(k, [])
                    if all(o["id"] != i["id"] for o in names[k]):
                        names[k].append(dict(i, shown_qty=qty or int(i.get("qty") or 1)))
            if names:
                out[vend] = {"names": names, "words": _vendor_words(vend, v.get("name") or "")}
        _index = out
    return _index


def _lines(texts) -> list:
    """The text read as {"t","x","y","w","h","xc"}; a name on two lines of the same card is also given joined."""
    ls = [{"t": str(tx), "x": float(x), "y": float(y), "w": float(w), "h": float(h), "xc": float(x) + float(w) / 2}
          for tx, x, y, w, h in (texts or []) if tx]
    out = list(ls)
    for a in ls:
        for b in ls:
            dy = b["y"] - a["y"]
            if b is not a and 0 < dy <= 1.8 * max(a["h"], b["h"], 1) and abs(b["xc"] - a["xc"]) <= 0.5 * max(a["w"], b["w"]):
                out.append(dict(a, t=a["t"] + " " + b["t"], h=dy + b["h"], joined=True))
    return out


def _best_name(k: str, names: dict):
    """The vendor's offer name a text is: the same without spaces, else the only close one (Requiem I / II Relic are
    close to each other: a fuzzy match counts only when no other name is nearly as close)."""
    if k in names:
        return k
    if len(k) < 6:
        return None
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return None
    scored = sorted(((fuzz.ratio(k, n), n) for n in names if len(n) >= 6), reverse=True)
    if scored and scored[0][0] >= 90 and (len(scored) == 1 or scored[1][0] < scored[0][0] - 4):
        return scored[0][1]
    return None


def _header(lines, words) -> bool:
    """The vendor's name in the header (the topmost text), read loosely: "JRABILIA" is MEMORABILIA cut short."""
    if not lines or not words:
        return False
    bottom = max(l["y"] + l["h"] for l in lines)
    top = [key(l["t"]) for l in lines if l["y"] < 0.1 * bottom and not l.get("joined")]
    try:
        from rapidfuzz import fuzz
    except ImportError:
        fuzz = None
    for t_ in top:
        for w in words:
            if len(t_) >= 4 and (w in t_ or (len(t_) >= 6 and t_ in w)):
                return True
            if fuzz and len(t_) >= 6 and fuzz.partial_ratio(t_, w) >= 85 and len(w) >= 6:
                return True
    return False


def _amounts(line, lines) -> set:
    """The offer's amount: in front of the name ("35.000 X Kuva"), else a number right under / above it."""
    q, _rest = split_amount(line["t"])
    if q:
        return {q}
    found = set()
    for o in lines:
        if o.get("joined") or abs(o["y"] - line["y"]) > 2.5 * max(o["h"], line["h"]) or abs(o["xc"] - line["xc"]) > max(o["w"], line["w"]):
            continue
        for m in re.finditer(r"(?<![\d.,])x?\s?(\d{1,3}(?:[.,\s]\d{3})+|\d+)\s?x?(?![\d.,])", o["t"], re.I):
            try:
                found.add(int(re.sub(r"[.,\s]", "", m.group(1))))
            except ValueError:
                pass
    return found


def read(texts, allow=None) -> dict | None:
    """The limited-offer vendor shown in the scanned text: {"vendor", "sure": {offers surely on sale}, "any": {offers
    maybe listed}, "maxed": {offers showing PURCHASE LIMIT REACHED}, "pos": {offer: [x, y, h]}} or None.
    texts: [(text, x, y, w, h)] as the OCR returns them. allow: vendor -> False when you are somewhere it cannot be
    opened (the game's log, eelog), so its offers on screen do not count."""
    lines = _lines(texts)
    singles = [l for l in lines if not l.get("joined")]
    best = None
    pool = {v: ix for v, ix in index().items() if allow is None or allow(v)}
    named = {v for v, ix in pool.items() if _header(singles, ix["words"])}
    for vend, ix in pool.items():
        if named and vend not in named:
            continue                                     # the header names another vendor: only that one counts
        hits = {}                                       # name key -> [lines where it is written]
        for l in lines:
            if _LIMIT.search(l["t"]):
                continue
            k = _best_name(key(split_amount(l["t"])[1]), ix["names"])
            if k:
                hits.setdefault(k, []).append(l)
        header = vend in named
        score = len(hits) + (2 if header else 0)
        if hits and (len(hits) >= MIN_OFFERS or header):
            if best is None or score > best[0]:
                best = (score, vend, hits)
            elif score == best[0]:
                best = (score, None, None)              # two vendors fit as well: do not guess
    if not best or best[1] is None:
        return None
    _score, vend, hits = best
    overlays = [l for l in singles if _LIMIT.search(l["t"])]
    sure, anyp, maxed, pos = set(), set(), set(), {}
    for n, found in hits.items():
        offers = index()[vend]["names"][n]
        top = min(found, key=lambda l: l["y"])
        for o in offers:                                   # where the name is written (to tell a scroll from a gap)
            pos[o["id"]] = [round(top["x"]), round(top["y"]), round(top["h"])]
        anyp |= {o["id"] for o in offers}
        if len(offers) == 1:
            ids = {offers[0]["id"]}
        else:
            amounts = set()
            for line in found:
                amounts |= _amounts(line, singles)
            ids = {o["id"] for o in offers if o["shown_qty"] in amounts}
        # PURCHASE LIMIT REACHED written on the card, above its name
        limit = any(0 < top["y"] - o["y"] <= 6 * max(o["h"], 1) and abs(o["xc"] - top["xc"]) <= 0.6 * max(o["w"], top["w"]) + 10
                    for o in overlays)
        (maxed if limit else sure).update(ids)
    return {"vendor": vend, "sure": sure, "any": anyp, "maxed": maxed, "pos": pos}


def scrolled(old_pos: dict, pos: dict) -> bool:
    """True when every offer still on screen moved by the same amount (the list was scrolled), False when some stayed
    where they were or they moved differently (a gap closed up: the offers after it shift into its place)."""
    moves = []
    for oid, (x, y, h) in (old_pos or {}).items():
        if oid in pos:
            x2, y2, h2 = pos[oid]
            moves.append((x2 - x, y2 - y, max(4, h, h2)))
    if len(moves) < 2:
        return False
    dx0, dy0, _ = moves[0]
    uniform = all(abs(dx - dx0) <= tol and abs(dy - dy0) <= tol for dx, dy, tol in moves)
    return uniform and any(abs(dx) > tol or abs(dy) > tol for dx, dy, tol in moves)


def gone_from(views: list, present: set, pos: dict | None = None) -> set:
    """Offers that left the screen without anything taking their place: compared with each earlier view of the same
    vendor (this period), the ones missing now when most of that view is still there, it was not a scroll (the offers
    still there did not all move by the same amount) and fewer new ones appeared than went away.
    views: [{"ids": offers surely seen, "any": offers maybe seen, "pos": {id: [x, y, h]}}]."""
    out = set()
    for v in views:
        old, old_any = set(v.get("ids") or []), set(v.get("any") or v.get("ids") or [])
        stay, went, came = old & present, old - present, present - old_any
        if not went or len(stay) < max(2, int(0.6 * len(old))) or len(came) >= len(went):
            continue
        if pos is not None and scrolled(v.get("pos") or {}, pos):
            continue
        out |= went
    return out


def apply(w, seen: dict, now=None) -> list:
    """Uses one reading of the screen (read()) on the Weekly state w (weekly.Weekly, lock held by the caller).
    Returns log lines of what changed."""
    from app.game.weekly import SKIP, UNKNOWN, data
    now = time.time() if now is None else now
    vend = seen["vendor"]
    items = {i["id"]: i for i in data()[vend]["items"]}
    st = w.ocr.setdefault(vend, {"seen": {}, "gone": {}, "views": []})
    # what no longer counts: observations older than the offer's reset
    for key in ("seen", "gone"):
        st[key] = {k: v for k, v in st[key].items() if k in items and v.get("until", 0) > now}
    st["views"] = [v for v in st["views"] if v.get("until", 0) > now][-12:]
    sure, anyp = set(seen["sure"]), set(seen["any"])
    log = []
    gone = gone_from(st["views"], anyp, seen.get("pos") or {}) - anyp
    for oid in seen.get("maxed") or ():                  # PURCHASE LIMIT REACHED on its card
        if oid in items and oid not in st["gone"]:
            st["gone"][oid] = {"t": now, "until": period_end(items[oid], now, vend), "how": "limit"}
            log.append(f"{items[oid]['name']}: purchase limit reached (on screen)")
    for oid in sure:
        until = period_end(items[oid], now, vend)
        st["seen"][oid] = {"t": now, "until": until}
        if st["gone"].pop(oid, None):
            log.append(f"{items[oid]['name']}: on sale again on screen (not bought out)")
    for oid in gone:
        if oid in items and oid not in st["gone"]:
            st["gone"][oid] = {"t": now, "until": period_end(items[oid], now, vend)}
            log.append(f"{items[oid]['name']}: no longer listed by the vendor (bought out)")
    if sure:
        st["views"].append({"t": now, "ids": sorted(sure), "any": sorted(anyp), "pos": seen.get("pos") or {}, "until": min(period_end(items[i], now, vend) for i in sure)})
    # the game file's purchases at this vendor
    for p in w.current:
        if p["vendor"] != vend:
            continue
        k = f"{p['vendor']}|{p['id']}"
        cur = w.assign.get(k)
        if cur and cur not in (UNKNOWN, SKIP):
            o = items.get(cur)
            if o and cur in sure and int(o.get("limit") or 1) <= p["n"]:
                # the assigned offer is still for sale: it was not this purchase
                w.assign[k] = UNKNOWN
                w.candidates[k] = [i for i in items if i not in sure]
                log.append(f"purchase {p['id']} was taken for {o['name']}, which is still on sale: asked again")
                cur = UNKNOWN
            else:
                continue
        if cur != UNKNOWN:
            continue
        cands = [c for c in (w.candidates.get(k) or list(items)) if c in items]
        cands = [c for c in cands if not (c in sure and int(items[c].get("limit") or 1) <= p["n"])]
        gone_c = [c for c in cands if c in st["gone"]]
        pick = gone_c[0] if len(gone_c) == 1 else (cands[0] if len(cands) == 1 else None)
        if pick:
            w.assign[k] = pick
            w.candidates.pop(k, None)
            log.append(f"purchase recognised as {items[pick]['name']} (from the vendor screen)")
        elif cands != (w.candidates.get(k) or []):
            w.candidates[k] = cands
    return log
