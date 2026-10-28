"""What a mod or an Arcane does at a given rank, for the tooltips of the Builds tab and the planner.

The text comes from the Warframe wiki: its data modules Module:Mods/data and Module:Arcane/data hold every mod's and
Arcane's effect at max rank (Description) and its max rank. They are read once in the background (two requests,
standard MediaWiki "action=raw") and kept in wiki_mods.json in the data folder, read again after 14 days.

The wiki gives the max rank only. The effect at another rank is worked out with the bundled data
(loadout_data.json "mtext", from WFCD/warframe-items: the effect at rank 0 and at max rank): every number that changes
between the two goes up in a straight line with the rank, as it does in the game (Serration: 15 % at rank 0, 165 % at
rank 10, 105 % at rank 6). When the wiki's text does not have the same numbers as the bundled one, the bundled text is
used for the lower ranks; while the wiki has not been read yet, the bundled text is used for every rank."""
import json
import re
import threading
import time

import requests

from app.core.config import APP_DIR, CFG

CACHE_FILE = APP_DIR / "wiki_mods.json"
TTL, RETRY = 14 * 86400, 6 * 3600
PAGES = {"mods": "Module:Mods/data", "arcanes": "Module:Arcane/data"}
URLS = ("https://wiki.warframe.com/w/{page}?action=raw", "https://wiki.warframe.com/index.php?title={page}&action=raw")
_NUM = re.compile(r"\d+(?:\.\d+)?")

_lock = threading.Lock()
_cache = None
_busy = False
done_count = 0                      # grows when the wiki's texts arrive (the cards then get the new tooltips)


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def clean(desc: str) -> str:
    """The wiki's Description as plain text: game colour tags (<DT_HEAT_COLOR>), wiki links and templates left out."""
    t = str(desc or "").replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n").replace('\\"', '"')
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]*>", "", t)                                   # <DT_PUNCTURE_COLOR>, <LINE_SEPARATOR>…
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)          # [[Link|Text]] -> Text
    t = re.sub(r"\{\{[^{}|]*\|([^{}|]*)(?:\|[^{}]*)?\}\}", r"\1", t)  # {{D|Heat}} -> Heat
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    return "\n".join(x.strip() for x in t.split("\n") if x.strip())


def parse_lua(text: str) -> dict:
    """{name: {"desc", "max"}} from a wiki data module: entries written ["Name"] = { … } or Name = { … }, with their
    Description and MaxRank fields (nested tables inside an entry are skipped over)."""
    out = {}
    i, n = 0, len(text or "")
    entry = re.compile(r'(?:\[\s*"((?:[^"\\]|\\.)+)"\s*\]|\b([A-Za-z_][A-Za-z0-9_]*))\s*=\s*\{')
    while True:
        m = entry.search(text, i)
        if not m:
            break
        name = (m.group(1) or m.group(2) or "").replace('\\"', '"').replace("\\'", "'")
        depth, j = 1, m.end()
        while j < n and depth:                         # the end of this entry's table (strings may hold braces)
            c = text[j]
            if c == '"':
                j += 1
                while j < n and text[j] != '"':
                    j += 2 if text[j] == "\\" else 1
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1
        body = _top(text[m.end():j - 1])                # this table's own fields, not its inner tables
        d = re.search(r'\bDescription\s*=\s*"((?:[^"\\]|\\.)*)"', body)
        r = re.search(r"\bMaxRank\s*=\s*(\d+)", body)
        if d:
            out[name] = {"desc": clean(d.group(1)), "max": int(r.group(1)) if r else None}
            i = j                                       # an entry: its inner tables are not entries
        else:
            i = m.end()                                 # an outer table (Mods = {…}): look inside it
    return out


def _top(body: str) -> str:
    """A table's text with its inner tables taken out (strings kept whole)."""
    out, depth, j, n = [], 0, 0, len(body)
    while j < n:
        c = body[j]
        if c == '"':
            k = j + 1
            while k < n and body[k] != '"':
                k += 2 if body[k] == "\\" else 1
            if depth == 0:
                out.append(body[j:k + 1])
            j = k + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(c)
        j += 1
    return "".join(out)


def _fetch():
    global _busy, done_count
    from app.core import logbus
    from app.trade.market import HEADERS
    got = {}
    for kind, page in PAGES.items():
        for url in URLS:
            try:
                r = requests.get(url.format(page=page), headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)
                r.raise_for_status()
                rows = parse_lua(r.text)
                if rows:
                    got[kind] = rows
                    break
            except Exception as e:
                logbus.error("modtext", f"{page}: {type(e).__name__}: {e}")
            time.sleep(0.5)
    with _lock:
        c = _load()
        for kind, rows in got.items():
            c[kind] = rows
        c["t"] = time.time() if got else c.get("t", 0)
        c["tried"] = time.time()
        try:
            CACHE_FILE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        _busy = False
    if got:
        logbus.add("modtext", ", ".join(f"{len(v)} {k}" for k, v in got.items()) + " read from the wiki", "ok")
    done_count += 1


def want():
    """Reads the wiki's texts in the background when they are missing or old (item pictures setting off: never)."""
    global _busy
    if not CFG.get("item_previews", True):
        return
    c = _load()
    now = time.time()
    if (c.get("mods") and now - c.get("t", 0) < TTL) or now - c.get("tried", 0) < RETRY:
        return
    with _lock:
        if _busy:
            return
        _busy = True
    threading.Thread(target=_fetch, daemon=True, name="wiki-mods").start()


def _bundled(name):
    from app.game import loadouts as LO
    row = LO.data().get("mtext", {}).get(name)
    return (row[0], row[1]) if row and len(row) >= 2 else (None, None)


def _at_rank(text0: str, textmax: str, rank: int, mx: int) -> str | None:
    """textmax with every number moved to the rank, in a straight line from text0 (same numbers in the same places)."""
    a, b = _NUM.findall(text0 or ""), _NUM.findall(textmax or "")
    if not mx or len(a) != len(b):
        return None
    vals = iter([float(x) + (float(y) - float(x)) * rank / mx for x, y in zip(a, b)])

    def put(_m):
        v = next(vals)
        return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.2f}".rstrip("0").rstrip(".")
    return _NUM.sub(put, textmax)


def effect(name: str, rank, mx, arcane: bool = False) -> dict:
    """{"text": the effect at that rank, "max_text": at max rank, "max", "source": "wiki" | "data"} or {} when unknown."""
    if not name:
        return {}
    want()
    wiki = (_load().get("arcanes" if arcane else "mods") or {}).get(name) or {}
    b0, bmax = _bundled(name)
    mx = int(wiki.get("max") or mx or 0)
    top = wiki.get("desc") or bmax
    if not top:
        return {}
    r = mx if rank is None else max(0, min(int(rank), mx))
    if r == mx:
        text = top
    else:
        text = _at_rank(b0, top, r, mx) if b0 else None
        if text is None and b0 and bmax:                   # the wiki writes it otherwise: the bundled text at that rank
            text = _at_rank(b0, bmax, r, mx)
        if text is None:
            text = top
    return {"text": text, "max_text": top, "max": mx, "rank": r, "source": "wiki" if wiki.get("desc") else "data"}
