"""What the vendor screen itself says about the limited offers (Weekly tab): an offer whose limit you reached is no longer
listed by the vendor, so the text read on the screen (the same OCR that reads the prices) is a second check of what you
bought, besides the game file.

From every scan (automatic or F8) the program looks for the names of the limited offers (data/weekly.json) in the text
read. A vendor counts as recognised when at least two of its offers are on screen (or one and the vendor's name). Then:
  - an offer on screen is NOT sold out this period: a purchase the game file has not identified cannot be that offer
    (when its limit would be reached), and an assignment saying it was is wrong and is asked again;
  - an offer seen on screen earlier this period and now missing, while the rest of that view is still there and nothing
    took its place (scrolling shows new offers in place of the old ones; a purchase leaves a gap), has been bought out:
    an unidentified purchase at that vendor is assigned to it, and the Weekly tab shows it bought ("OCR") until the
    game file says so too.
Two offers with the same name (Teshin's Kuva ×10,000 and ×50,000) are told apart by the amount read next to the name;
when it cannot be read they are not used as evidence.
Kept in weekly_state.json with the rest (key "ocr"), until each offer's own reset."""
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


def _vendor_words(name: str) -> set:
    """Words of the vendor's display name that the game shows in its header: "Teshin (Steel Path)" -> {"teshin"}."""
    base = re.split(r"[(·]", name)[0]
    return {w for w in norm(base).split() if len(w) >= 4}


def index():
    """{vendor: {"names": {norm name: [offers]}, "words": {header words}}} for every vendor with limited offers."""
    global _index
    if _index is None:
        from app.game.weekly import data
        out = {}
        for vend, v in data().items():
            names = {}
            for i in v.get("items") or []:
                n = norm(i.get("name") or "")
                if len(n) >= 4:
                    names.setdefault(n, [])
                    if all(o["id"] != i["id"] for o in names[n]):
                        names[n].append(i)
            if names:
                out[vend] = {"names": names, "words": _vendor_words(v.get("name") or "")}
        _index = out
    return _index


def _match(text: str, name: str) -> bool:
    if text == name:
        return True
    if len(name) >= 5:
        try:
            from rapidfuzz import fuzz
            if fuzz.ratio(text, name) >= 88:
                return True
        except ImportError:
            pass
    # the name with something around it on the same line (an amount, a "x2"…), but not a longer item's name
    return len(name) >= 8 and name in text and len(text) <= len(name) + 12


_QTY = re.compile(r"(?<![\d.,])x?\s?(\d{1,3}(?:[.,\s]\d{3})+|\d+)\s?x?(?![\d.,])", re.I)


def _amounts(line, texts) -> set:
    """Numbers written on the name's own line or right under / above it (the offer's amount: "x10,000", "10.000")."""
    txt, x, y, w, h = line
    found = set()
    for t2, x2, y2, w2, h2 in texts:
        same = t2 is txt or (abs(y2 - y) <= 2.5 * max(h, h2) and abs((x2 + w2 / 2) - (x + w / 2)) <= max(w, w2))
        if not same:
            continue
        for m in _QTY.finditer(str(t2)):
            try:
                found.add(int(re.sub(r"[.,\s]", "", m.group(1))))
            except ValueError:
                pass
    return found


def read(texts) -> dict | None:
    """The limited-offer vendor shown in the scanned text: {"vendor", "sure": {offer ids surely listed}, "any": {offer
    ids that may be listed}} or None. texts: [(text, x, y, w, h)] as the OCR returns them."""
    lines = [(str(tx), x, y, w, h) for tx, x, y, w, h in (texts or []) if tx]
    normed = [(norm(l[0]), l) for l in lines]
    best = None
    for vend, ix in index().items():
        hits = {}
        for nt, line in normed:
            if len(nt) < 4:
                continue
            for n, offers in ix["names"].items():
                if _match(nt, n):
                    hits.setdefault(n, []).append(line)
        header = any(w in nt.split() for nt, _l in normed for w in ix["words"])
        score = len(hits)
        if score >= MIN_OFFERS or (score >= 1 and header):
            key = (score, header)
            if best is None or key > best[0]:
                best = (key, vend, hits, None)
            elif key == best[0]:
                best = (key, None, None, True)          # two vendors fit as well: do not guess
    if not best or best[1] is None:
        return None
    _key, vend, hits, _tie = best
    sure, anyp, pos = set(), set(), {}
    for n, found in hits.items():
        offers = index()[vend]["names"][n]
        for o in offers:                                   # where the name is written (to tell a scroll from a gap)
            pos[o["id"]] = [round(found[0][1]), round(found[0][2]), round(found[0][4])]
        if len(offers) == 1:
            sure.add(offers[0]["id"])
            anyp.add(offers[0]["id"])
            continue
        amounts = set()
        for line in found:
            amounts |= _amounts(line, lines)
        matched = [o for o in offers if int(o.get("qty") or 1) in amounts]
        for o in matched:
            sure.add(o["id"])
        anyp |= {o["id"] for o in offers}
    return {"vendor": vend, "sure": sure, "any": anyp, "pos": pos}


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
