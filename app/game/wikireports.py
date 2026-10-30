"""Tenet / Coda weapon bonuses reported by players on the Warframe wiki (pages "Tenet Weapons" and "Coda Weapons"):
the bonus element and percentage of each weapon Ergo Glast / Eleanor offers, with the date of the offer.

The pages are read through the standard MediaWiki API (their HTML), at most every 3 hours, kept in wiki_reports.json.
Their tables are read without relying on one layout: in every cell, a weapon (or the weapon of the cell's column), an
element (by name or its icon's alt text) and a percentage; the date from the row, else from the table's caption or the
heading above it. Only reports dated within the vendor's current 4-day cycle are shown, with the wiki as their source."""
import html as H
import json
import re
import threading
import time
from datetime import datetime, timezone

from app.core.config import APP_DIR

API = "https://wiki.warframe.com/api.php"
PAGES = {"tenet": "Tenet Weapons", "coda": "Coda Weapons"}
CACHE = APP_DIR / "wiki_reports.json"
MAX_AGE = 3 * 3600
ELEMENTS = {"impact": "Impact", "heat": "Heat", "fire": "Heat", "cold": "Cold", "freeze": "Cold",
            "electricity": "Electricity", "electric": "Electricity", "toxin": "Toxin", "magnetic": "Magnetic",
            "radiation": "Radiation"}
MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                          "dec"))}
_state = {"busy": set(), "d": None}
_lock = threading.Lock()


def _text(fragment: str) -> str:
    """A cell's text, with the alt / title of its pictures and links (an element's icon has its name there)."""
    alts = " ".join(re.findall(r'(?:alt|title)="([^"]*)"', fragment))
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", fragment) + " " + alts)).strip()


def parse_date(text: str):
    """The first date in a text (2026-10-28, 28/10/2026, October 28, 2026, 28 Oct 2026, Oct 28) as an epoch, or None."""
    t = text.lower()
    m = re.search(r"(20\d\d)-(\d\d?)-(\d\d?)", t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"(\d\d?)[/.](\d\d?)[/.](20\d\d)", t)
        if m:
            a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            d, mo = (a, b) if a > 12 else ((b, a) if b > 12 else (a, b))     # day first unless it cannot be
        else:
            m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d\d?)(?:st|nd|rd|th)?,?"
                          r"(?:\s+(20\d\d))?", t)
            if m:
                mo, d, y = MONTHS[m.group(1)], int(m.group(2)), int(m.group(3) or datetime.now(timezone.utc).year)
            else:
                m = re.search(r"\b(\d\d?)(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
                              r"(?:,?\s+(20\d\d))?", t)
                if not m:
                    return None
                d, mo, y = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3) or datetime.now(timezone.utc).year)
    try:
        return datetime(y, mo, d, tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _element(text: str):
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in ELEMENTS:
            return ELEMENTS[word]
    return None


def _pct(text: str):
    m = re.search(r"(\d{2}(?:[.,]\d{1,2})?)\s*%", text)
    if m:
        v = float(m.group(1).replace(",", "."))
        if 25 <= v <= 60:
            return v
    return None


def parse_html(html: str, weapons: list) -> list:
    """[{"weapon", "element", "pct", "date"}] of every report in a page's HTML. weapons: the vendor's weapon names."""
    def weapon_in(text):
        low = text.lower()
        best = None
        for w in weapons:
            short = re.sub(r"^(Coda|Tenet|Dual Coda)\s+", "", w)
            for k in (w.lower(), short.lower()):
                if re.search(r"\b" + re.escape(k) + r"\b", low) and (best is None or len(k) > best[1]):
                    best = (w, len(k))
        return best[0] if best else None
    out = []
    for tm in re.finditer(r"<table\b.*?</table>", html, re.S | re.I):
        table = tm.group(0)
        before = re.sub(r"<[^>]+>", " ", html[max(0, tm.start() - 1500):tm.start()])
        heads = re.findall(r"<h[2-5][^>]*>(.*?)</h[2-5]>", html[max(0, tm.start() - 4000):tm.start()], re.S)
        cap = re.search(r"<caption[^>]*>(.*?)</caption>", table, re.S)
        table_date = parse_date(_text(cap.group(1))) if cap else None
        if table_date is None and heads:
            table_date = parse_date(_text(heads[-1]))
        if table_date is None:
            table_date = parse_date(H.unescape(before[-300:]))
        rows = re.findall(r"<tr\b.*?</tr>", table, re.S | re.I)
        cols = {}
        for row in rows:
            cells = [_text(c) for c in re.findall(r"<t[hd]\b.*?</t[hd]>", row, re.S | re.I)]
            if not cells:
                continue
            row_weapons = [weapon_in(c) for c in cells]
            if not cols and sum(1 for w in row_weapons if w) >= 2 and not any(_pct(c) for c in cells):
                cols = {i: w for i, w in enumerate(row_weapons) if w}      # a header of weapons (one per column)
                continue
            row_date = next((d for d in (parse_date(c) for c in cells) if d), None) or table_date
            row_weapon = next((w for w in row_weapons if w), None)
            for i, c in enumerate(cells):
                el, pct = _element(c), _pct(c)
                if not el or pct is None:
                    continue
                w = row_weapons[i] or cols.get(i) or (row_weapon if sum(1 for x in row_weapons if x) <= 1 else None)
                if w:
                    out.append({"weapon": w, "element": el, "pct": pct, "date": row_date})
    return out


def _load() -> dict:
    if _state["d"] is None:
        try:
            _state["d"] = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            _state["d"] = {}
    return _state["d"]


def refresh(vendor: str, weapons: list, done=None):
    """Reads the vendor's wiki page in the background when the copy is 3 hours old; done() afterwards (any thread)."""
    d = _load().get(vendor) or {}
    if time.time() - float(d.get("t") or 0) < MAX_AGE:
        return
    with _lock:
        if vendor in _state["busy"]:
            return
        _state["busy"].add(vendor)

    def run():
        from app.core import logbus
        try:
            import requests
            from app.trade.market import HEADERS
            r = requests.get(API, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20, params={
                "action": "parse", "page": PAGES[vendor], "prop": "text", "format": "json", "redirects": 1})
            r.raise_for_status()
            reports = parse_html((r.json().get("parse") or {}).get("text", {}).get("*", ""), weapons)
            with _lock:
                _load()[vendor] = {"t": time.time(), "reports": reports}
                try:
                    CACHE.write_text(json.dumps(_state["d"]), encoding="utf-8")
                except OSError:
                    pass
            logbus.add("weekly", f"wiki {PAGES[vendor]}: {len(reports)} reported bonuses", "ok" if reports else "warn")
        except Exception as e:
            logbus.add("weekly", f"wiki {PAGES[vendor]}: {type(e).__name__}: {e}", "warn")
            with _lock:
                _load()[vendor] = dict(_load().get(vendor) or {}, t=time.time() - MAX_AGE + 1800)   # again in 30 min
        finally:
            _state["busy"].discard(vendor)
            if done:
                try:
                    done()
                except Exception:
                    pass
    threading.Thread(target=run, daemon=True, name=f"wiki-{vendor}").start()


def current(vendor: str, start: float, end: float) -> dict:
    """{weapon: {"element", "pct", "date"}} reported for the cycle [start, end) (a report dated the day before the
    cycle counts: time zones), the latest per weapon."""
    out = {}
    for r in (_load().get(vendor) or {}).get("reports") or []:
        d = r.get("date")
        if d is None or not (start - 86400 <= d < end):
            continue
        if r["weapon"] not in out or (out[r["weapon"]].get("date") or 0) < d:
            out[r["weapon"]] = r
    return out
