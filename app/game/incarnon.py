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
WIKI_API = "https://wiki.warframe.com/api.php"
CACHE_FILE = APP_DIR / "incarnon_perks.json"
TTL, RETRY = 14 * 86400, 86400
ROMAN = ["I", "II", "III", "IV", "V"]
_VARIANT = re.compile(r"\s+(Prime|Vandal|Wraith)$|^(Prisma|MK1-)\s*", re.I)

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
    if c and c.get("v") != PARSER and not c.get("tiers"):
        c = None                              # failed with an older parser: try again now
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


BOLD = "'" * 3
PARSER = 2              # failed cache entries made by an older parser are read again


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


def _get(page):
    global done_count
    from app.core import logbus
    from app.trade.market import HEADERS
    tiers, how = [], ""
    try:
        h = {"User-Agent": HEADERS["User-Agent"]}
        r = requests.get(WIKI_API, params={"action": "parse", "page": page, "prop": "wikitext", "format": "json",
                                           "redirects": 1}, headers=h, timeout=15)
        r.raise_for_status()
        wt = ((r.json().get("parse") or {}).get("wikitext") or {}).get("*") or ""
        tiers, how = parse_tiers(wt), "wikitext"
        if not tiers:                         # the perks come from a template: read the rendered page instead
            time.sleep(0.5)
            r = requests.get(WIKI_API, params={"action": "parse", "page": page, "prop": "text", "format": "json",
                                               "redirects": 1, "disablelimitreport": 1}, headers=h, timeout=20)
            r.raise_for_status()
            html = ((r.json().get("parse") or {}).get("text") or {}).get("*") or ""
            marked = html_to_marked(html)
            tiers, how = parse_tiers(marked), "page"
            if not tiers:                     # kept so the page's layout can be looked at (and the reader fixed)
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
    unlocked = max(inc["evo"], len(inc["skill"]))
    total = len(tiers) if tiers else None
    head += " · " + t("inc.evo", n=ROMAN[unlocked - 1] if 0 < unlocked <= 5 else "–",
                      total=f"/{ROMAN[total - 1]}" if total and total <= 5 else "")
    lines = []
    for i, ch in enumerate(inc["skill"][:5]):
        k = int(ch) if ch.isdigit() else 0
        names = tiers[i] if tiers and i < len(tiers) else []
        name = names[k] if k < len(names) else (names[0] if len(names) == 1 else t("inc.option", n=k + 1))
        lines.append(f"{ROMAN[i]}: {name}")
    return head, lines
