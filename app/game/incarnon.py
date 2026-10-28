"""Incarnon weapons in the Builds tab: Genesis adapter installed or built in, the evolution tier reached and the perk chosen
in each tier.

From AlecaFrame's lastData.dat:
  Features & 512        the Incarnon Genesis adapter is installed on that weapon (Braton Prime, Lex Prime…)
  EvolutionProgress     [{"ItemType", "Rank", "Progress"}]: the evolution tiers unlocked, per weapon FAMILY (the base
                        weapon's path: Braton's progress is also Braton Prime's and Braton Vandal's) — Rank = tiers unlocked
  SkillTree             on the weapon: one digit per unlocked tier, the perk chosen in it ("0120": tier I has a single
                        perk, then the 2nd, 3rd, 1st)
  built in              a weapon with its own evolution progress and no Genesis in its family (Zariman / Duviri weapons,
                        Onos…)

The perk NAMES are not in the game data the program has: they are read from the weapon's page on the Warframe wiki
(wiki.warframe.com, standard MediaWiki API, the page's wikitext: "<weapon> Incarnon Genesis" for Genesis weapons, the
weapon's own page for built-in ones), parsed by tier (Evolution I…V) and kept in incarnon_perks.json in the data folder
(asked again after 14 days; a page that could not be read, after a day). When a page cannot be understood, the tab says
"option 2" instead of a name."""
import json
import re
import threading
import time

import requests

from app.core.config import APP_DIR, CFG

GENESIS_FLAG = 512
BOLD = "'" * 3
WIKI_API = "https://wiki.warframe.com/api.php"
CACHE_FILE = APP_DIR / "incarnon_perks.json"
TTL, RETRY = 14 * 86400, 86400
ROMAN = ["I", "II", "III", "IV", "V"]
_VARIANT = re.compile(r"\s+(Prime|Vandal|Wraith)$|^(Prisma|MK1-|Sancti|Telos|Synoid|Rakta|Secura)\s*", re.I)
# weapons whose family has an Incarnon Genesis adapter, and weapons with Incarnon built in (Zariman, Entrati, Duviri).
# The bundled data (tools/build_loadouts.py, key "incarnon") is used when it is there; these lists are the fallback.
GENESIS = ("Ack & Brunt", "Angstrum", "Anku", "Atomos", "Ballistica", "Bo", "Boar", "Boltor", "Braton", "Bronco", "Burston",
           "Ceramic Dagger", "Cestra", "Dera", "Despair", "Destreza", "Dread", "Dual Ichor", "Dual Toxocyst", "Furax", "Furis",
           "Gammacor", "Gorgon", "Hate", "Kunai", "Lato", "Latron", "Lex", "Magistar", "Miter", "Nami Solo", "Obex", "Okina",
           "Paris", "Sibear", "Sicarus", "Skana", "Soma", "Strun", "Stug", "Sybaris", "Torid", "Vasto", "Vectis", "Zylok")
BUILTIN = ("Felarx", "Innodem", "Laetum", "Onos", "Phenmor", "Praedos", "Ruvox", "Thalys")

_lock = threading.Lock()
_cache = None
_pending = set()
done_count = 0


def family(name: str) -> str:
    """The base weapon of a variant: Braton Prime / Braton Vandal / MK1-Braton -> Braton."""
    n = name.strip()
    for _ in range(2):
        n = _VARIANT.sub("", n).strip()
    return n


def lists() -> tuple:
    """(Genesis families, built-in Incarnon weapons) from the bundled data, else the lists above."""
    try:
        from app.game import loadouts as LO
        d = LO.data().get("incarnon") or {}
        if d.get("genesis"):
            return tuple(d["genesis"]), tuple(d.get("builtin") or BUILTIN)
    except Exception:
        pass
    return GENESIS, BUILTIN


def tier_count(kind: str, page: str) -> int:
    """How many evolution tiers the weapon has: the wiki's table when it was read, else 5 for weapons with Incarnon
    built in (Zariman, Entrati, Duviri: Evolution I-V) and 4 for Genesis adapters (EVO1-EVO4)."""
    tiers = perks(page) if page else None
    if tiers:
        return max(1, min(5, len(tiers)))
    return 5 if kind == "builtin" else 4


def available(name: str) -> dict | None:
    """What a weapon can have, whoever owns it: {"kind": "genesis"|"builtin", "page"} or None (the build planner)."""
    gen, built = lists()
    fam = family(name)
    if name in built or fam in built:
        return {"kind": "builtin", "page": name if name in built else fam}
    if fam in gen:
        return {"kind": "genesis", "page": f"{fam} Incarnon Genesis"}
    return None


def info(item: dict, name: str, evo_by_family: dict, genesis_families: set) -> dict:
    """{"kind": "genesis"|"builtin"|"available", "evo", "progress", "skill", "page"} or None (not an Incarnon weapon)."""
    fam = family(name)
    evo = evo_by_family.get(fam)
    feats = int(item.get("Features") or 0)
    skill = str(item.get("SkillTree") or "")
    if feats & GENESIS_FLAG:
        kind, page = "genesis", f"{fam} Incarnon Genesis"
    elif evo is not None and fam not in genesis_families and evo.get("exact") == item.get("ItemType"):
        kind, page = "builtin", name
    elif fam in genesis_families:
        kind, page = "available", f"{fam} Incarnon Genesis"     # the family has a Genesis, installed on another variant
    else:
        return None
    return {"kind": kind, "evo": int((evo or {}).get("rank") or 0), "progress": int((evo or {}).get("progress") or 0),
            "skill": skill, "page": page}


def index(inv: dict, names_for_path) -> tuple:
    """({family name: {"rank","progress","exact"}}, {families with a Genesis installed on some weapon})."""
    evo = {}
    for e in inv.get("EvolutionProgress") or []:
        if not isinstance(e, dict) or not e.get("ItemType"):
            continue
        names = names_for_path(e["ItemType"])
        if names:
            evo[family(re.sub(r"<[^>]*>\s*", "", names[0]).strip())] = {"rank": e.get("Rank"), "progress": e.get("Progress"),
                                                                       "exact": e["ItemType"]}
    gen = set()
    for key in ("LongGuns", "Pistols", "Melee"):
        for it in inv.get(key) or []:
            if isinstance(it, dict) and int(it.get("Features") or 0) & GENESIS_FLAG:
                names = names_for_path(it.get("ItemType", ""))
                if names:
                    gen.add(family(re.sub(r"<[^>]*>\s*", "", names[0]).strip()))
    return evo, gen


# ---------- perk names from the wiki ----------
def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


# ---------- the evolution table, whatever page it is on ----------
# Genesis pages write the tiers as "EVO1".."EVO5" (Torid Incarnon Genesis), built-in weapons as "Evolution I".."V"
# (Laetum), sometimes in a cell of its own spanning the tier's rows (rowspan), sometimes once per row. Tier I of a
# built-in weapon has no perk name (only a description of the Incarnon form). Every row of a tier names one perk: the
# first short text after the tier's label, preferably the bold one. "Evolution Challenge" rows are skipped.
_TIER = re.compile(r"^\s*(?:EVO\s*([1-5])|Evolution\s+(V|IV|III|II|I)|Tier\s+([1-5]|V|IV|III|II|I))\s*:?\s*$", re.I)
_NOT_PERK = re.compile(r"^(notes?|perks?|names?|descriptions?|effects?|evolutions?|tiers?|challenges?|unlock\w*|"
                       r"requirements?|icons?|image|-+|–|—|n/?a|none|overview)$", re.I)


def _tier_no(text: str):
    m = _TIER.match(text or "")
    if not m:
        return None
    v = next(g for g in m.groups() if g)
    return int(v) if v.isdigit() else ROMAN.index(v.upper()) + 1


def _perk_name(text: str) -> str:
    """A perk's name from a cell's text, or "" when the text is not one (a sentence, a dash, a column title)."""
    n = re.sub(r"\s+", " ", (text or "")).strip(" :.;-–—\u00a0")
    if not (2 <= len(n) <= 45) or len(n.split()) > 6 or _NOT_PERK.match(n) or re.fullmatch(r"[\d\s%+.,x×-]+", n):
        return ""
    if re.search(r"[.!?]\s|\d+\s*%|\bchallenge\b|\bevolution\b|\bincarnon genesis\b", n, re.I):
        return ""
    return n


def _rows_to_tiers(rows: list) -> list:
    """rows: [[(text, [bold texts]), ...cells]]. [[perks of tier 1], [tier 2], ...] or []."""
    tiers, cur = {}, None
    for cells in rows:
        cells = [(c[0].strip(), c[1]) for c in cells if c and (c[0] or "").strip()]
        if not cells:
            continue
        label_at = next((i for i, c in enumerate(cells) if _tier_no(c[0])), None)
        if label_at is not None:
            cur = _tier_no(cells[label_at][0])
            rest = cells[label_at + 1:]
            tiers.setdefault(cur, [])
        elif cur is None:
            continue
        else:
            rest = cells
        if any(re.search(r"\bchallenge\b", c[0], re.I) for c in cells):
            continue
        name = ""
        for text, bolds in rest[:2]:                 # the perk is the first column after the label (or the second)
            name = next((_perk_name(b) for b in bolds if _perk_name(b)), "") or _perk_name(text)
            if name:
                break
        if name and name not in tiers[cur]:
            tiers[cur].append(name)
    if not tiers or sum(len(v) for v in tiers.values()) < 2:
        return []
    return [tiers.get(k, []) for k in range(1, max(tiers) + 1)]


def _best(tables: list) -> list:
    best = []
    for rows in tables:
        tiers = _rows_to_tiers(rows)
        if sum(len(x) for x in tiers) > sum(len(x) for x in best):
            best = tiers
    return best


def parse_html_tables(html: str) -> list:
    """The evolution table of the rendered page (MediaWiki's HTML): [[tier 1 perks], ...] or []."""
    from html.parser import HTMLParser

    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.tables, self.stack, self.cell, self.bold, self.skip = [], [], None, 0, 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self.skip += 1
            elif tag == "table":
                self.stack.append([])
            elif tag == "tr" and self.stack:
                self.stack[-1].append([])
            elif tag in ("td", "th") and self.stack:
                if not self.stack[-1]:
                    self.stack[-1].append([])
                self.cell = [[], []]                       # text pieces, bold texts
                self.stack[-1][-1].append(self.cell)
                if tag == "th":
                    self.bold += 1
                    self.cell[1].append("")
            elif tag in ("b", "strong") and self.cell is not None:
                self.bold += 1
                self.cell[1].append("")
            elif tag == "br" and self.cell is not None:
                self.cell[0].append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style"):
                self.skip = max(0, self.skip - 1)
            elif tag == "table" and self.stack:
                self.tables.append(self.stack.pop())
                self.cell = None
            elif tag in ("td", "th"):
                if tag == "th":
                    self.bold = max(0, self.bold - 1)
                self.cell = None
            elif tag in ("b", "strong"):
                self.bold = max(0, self.bold - 1)

        def handle_data(self, data):
            if self.skip or self.cell is None:
                return
            self.cell[0].append(data)
            if self.bold and self.cell[1]:
                self.cell[1][-1] += data

    r = Reader()
    try:
        r.feed(html or "")
    except Exception:
        return []
    tables = []
    for t_ in r.tables:
        rows = []
        for row in t_:
            cells = []
            for text, bolds in row:
                txt = re.sub(r"[ \t\u00a0]+", " ", "".join(text)).strip()
                first = txt.split("\n", 1)[0].strip()      # a name with a line of description under it
                cells.append((first if _perk_name(first) and not _perk_name(txt) else txt, [b.strip() for b in bolds if b.strip()]))
            rows.append(cells)
        tables.append(rows)
    return _best(tables)


def _wiki_plain(text: str) -> tuple:
    """(plain text, [bold texts]) of a piece of wikitext."""
    t_ = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", text or "", flags=re.I)
    t_ = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t_)
    t_ = re.sub(r"\{\{[^{}|]*\|([^{}|]*)\}\}", r"\1", t_)          # {{Template|Text}} -> Text
    t_ = re.sub(r"\{\{[^{}]*\}\}", "", t_)
    t_ = re.sub(r"<[^>]+>", " ", t_)
    bolds = [b.strip() for b in re.findall(BOLD + r"(.+?)" + BOLD, t_)]
    return re.sub(r"'{2,}", "", t_).strip(), bolds


def parse_wiki_tables(wikitext: str) -> list:
    """The evolution table written as wikitext ({| ... |}): [[tier 1 perks], ...] or []."""
    text = re.sub(r"<!--.*?-->", "", wikitext or "", flags=re.S)
    tables = []
    for block in re.findall(r"\{\|(.*?)\n\|\}", text, flags=re.S):
        rows = []
        for raw in re.split(r"\n\|-[^\n]*", block):
            cells = []
            for line in raw.split("\n"):
                if not line.strip() or line.startswith("|+"):
                    continue
                if line[:1] in "|!":
                    for part in re.split(r"\|\||!!", line[1:]):
                        # a cell's attributes come before a single "|": rowspan="2" | EVO1
                        m = re.match(r"^\s*(?:[a-z-]+\s*=\s*(?:\"[^\"]*\"|\S+)\s*)+\|(?!\|)(.*)$", part, re.I)
                        cells.append(_wiki_plain(m.group(1) if m else part))
                elif cells:                                   # the cell goes on on the next line
                    txt, b = _wiki_plain(line)
                    cells[-1] = ((cells[-1][0] + "\n" + txt).strip(), cells[-1][1] + b)
            rows.append(cells)
        tables.append(rows)
    return _best(tables)


def parse_evo_table(wikitext: str) -> list:
    """The wiki's evolution table (as on every Incarnon page, checked on Torid Incarnon Genesis): rows headed "EVO1",
    "EVO2"... and, in each, the perks written in bold followed by their icon ([[File:...]]).
    [[perks of tier 1], [tier 2], ...] or []."""
    text = re.sub(r"<!--.*?-->", "", wikitext or "", flags=re.S)
    start = text.find("Evolutions")
    if start < 0:
        return []
    body = text[start:]
    marks = [(m.start(), int(m.group(1))) for m in re.finditer(r"\bEVO\s*([1-5])\b", body)]
    tiers = {}
    for i, (pos, n) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        chunk = body[pos:end].split("|}", 1)[0]            # the table ends there
        names = []
        for m in re.finditer(BOLD + r"([^\n]{2,60}?)" + BOLD + r"\s*\[\[File:", chunk):
            name = m.group(1).strip()
            if name not in names:
                names.append(name)
        if names and n not in tiers:
            tiers[n] = names
    if not tiers:
        return []
    return [tiers.get(k, []) for k in range(1, max(tiers) + 1)]


def parse_tiers(wikitext: str) -> list:
    """[[perk names of tier I], [tier II], …] from a page's wikitext: the text is cut at every "Evolution I/II/III/IV/V"
    and, in each piece, the bold names ('''Name''') are the perks. Empty when nothing like that is found."""
    text = re.sub(r"<!--.*?-->", "", wikitext or "", flags=re.S)
    marks = [(m.start(), m.group(1)) for m in re.finditer(r"Evolution\s+(V|IV|III|II|I)\b", text)]
    tiers = {}
    for i, (pos, roman) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        chunk = text[pos:end]
        found = []
        for m in re.finditer(r"'''([^\n]{3,48}?)'''", chunk):
            name = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", m.group(1)).strip(" :.")   # [[Link|Text]] -> Text
            if (not name or "|" in name or "{" in name or "''" in name or name in found
                    or re.search(r"Evolution|Genesis|Challenge|Unlock", name, re.I)):
                continue
            found.append(name)
        if found and len(found) >= len(tiers.get(roman, [])):    # the fullest mention wins (the table, not the intro)
            tiers[roman] = found[:4]
    if not tiers:
        return []
    last = max(ROMAN.index(r) for r in tiers)
    return [tiers.get(r, []) for r in ROMAN[:last + 1]]


def perks(page: str):
    """The cached perk names of a wiki page ([[tier I], [tier II], …]) or None; asks for them in the background."""
    if not page:
        return None
    c = _load().get(page)
    now = time.time()
    if c and c.get("v") != PARSER:            # read by an older reader (names missing or wrong): read again, and show
        if CFG.get("item_previews", True):    # what it had meanwhile
            _want(page)
        return c.get("tiers") or None
    if c and now - c.get("t", 0) < (TTL if c.get("tiers") else RETRY):
        return c.get("tiers") or None
    if CFG.get("item_previews", True):
        _want(page)
    return (c or {}).get("tiers") or None


def _want(page):
    with _lock:
        if page in _pending:
            return
        _pending.add(page)
    threading.Thread(target=_get, args=(page,), daemon=True, name="incarnon-wiki").start()


PARSER = 4              # cache entries made by an older reader are read again (0.4.0: the evolution table itself)


def html_to_marked(html: str) -> str:
    """The rendered page as plain text, with bold text and table headers marked as bold wikitext, so parse_tiers reads it
    like wikitext (the evolutions are usually drawn by a template or a Lua module: the page's own wikitext then holds
    only the call, not the perks)."""
    import html as _html
    h = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", html or "")
    h = re.sub(r"(?is)<(b|strong|th)\b[^>]*>(.*?)</\1>",
               lambda m: "\n" + BOLD + re.sub(r"<[^>]+>", "", m.group(2)).strip() + BOLD + "\n", h)
    h = re.sub(r"(?i)<br\s*/?>|</(tr|p|li|div|h\d)>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return _html.unescape(h)


def read_page(wikitext: str, html: str) -> tuple:
    """(tiers, how): the evolution table from the rendered page, else from the wikitext, else the older readers."""
    for how, fn, src in (("page table", parse_html_tables, html), ("wikitext table", parse_wiki_tables, wikitext),
                         ("wikitext", parse_evo_table, wikitext), ("wikitext", parse_tiers, wikitext),
                         ("page", lambda h: parse_tiers(html_to_marked(h)), html)):
        if src:
            tiers = fn(src)
            if tiers:
                return tiers, how
    return [], ""


def _get(page):
    global done_count
    from app.core import logbus
    from app.trade.market import HEADERS
    tiers, how, wt, html = [], "", "", ""
    try:
        h = {"User-Agent": HEADERS["User-Agent"]}
        r = requests.get(WIKI_API, params={"action": "parse", "page": page, "prop": "text", "format": "json",
                                           "redirects": 1, "disablelimitreport": 1}, headers=h, timeout=20)
        r.raise_for_status()
        html = ((r.json().get("parse") or {}).get("text") or {}).get("*") or ""
        tiers, how = read_page("", html)
        if not tiers:                         # the page's own wikitext, in case the table is written there
            time.sleep(0.5)
            r = requests.get(WIKI_API, params={"action": "parse", "page": page, "prop": "wikitext", "format": "json",
                                               "redirects": 1}, headers=h, timeout=15)
            r.raise_for_status()
            wt = ((r.json().get("parse") or {}).get("wikitext") or {}).get("*") or ""
            tiers, how = read_page(wt, html)
        if not tiers:                         # kept so the page's layout can be looked at (and the reader fixed)
            try:
                d = APP_DIR / "incarnon_debug"
                d.mkdir(exist_ok=True)
                (d / (re.sub(r"[^A-Za-z0-9]+", "_", page) + ".txt")).write_text(
                    "=== wikitext ===\n" + wt + "\n\n=== page html ===\n" + html, encoding="utf-8")
            except OSError:
                pass
        logbus.add("incarnon", f"{page}: {sum(len(x) for x in tiers)} perks in {len(tiers)} tiers read from the wiki"
                   + (f" ({how})" if tiers else " — page saved in the incarnon_debug folder"), "ok" if tiers else "warn")
    except Exception as e:
        logbus.error("incarnon", f"{page}: {type(e).__name__}: {e}")
        old = (_load().get(page) or {}).get("tiers") or []
        if old:                               # keep what an older reading had (and try again tomorrow)
            tiers = old
    with _lock:
        _load()[page] = {"t": time.time(), "tiers": tiers, "v": PARSER}
        try:
            CACHE_FILE.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        _pending.discard(page)
    done_count += 1


def describe(inc: dict, t) -> tuple:
    """(one-line summary, [perk lines]) for the Builds tab. t = the translation function."""
    if not inc:
        return "", []
    head = t("inc." + inc["kind"])
    if inc["kind"] == "available":
        return head, []
    tiers = perks(inc["page"])
    total = tier_count(inc["kind"], inc["page"])
    unlocked = min(total, max(inc["evo"], len(inc["skill"])))
    head += " · " + t("inc.evo", n=ROMAN[unlocked - 1] if 0 < unlocked <= 5 else "–",
                      total=f"/{ROMAN[total - 1]}" if total and total <= 5 else "")
    lines = [f"{ROMAN[i]}: {perk_name(tiers, i, ch, t)}" for i, ch in enumerate(inc["skill"][:total])]
    return head, lines


def perk_name(tiers, i: int, choice, t) -> str:
    """The name of the perk chosen in tier i (0 = tier I) — choice: the SkillTree digit (or an int)."""
    k = int(choice) if str(choice).isdigit() else 0
    names = tiers[i] if tiers and i < len(tiers) else []
    if k < len(names):
        return names[k]
    if len(names) == 1:
        return names[0]
    if i == 0 and not names:
        return t("inc.form")                  # tier I unlocks the Incarnon form itself (no perk name on built-in pages)
    return t("inc.option", n=k + 1)
