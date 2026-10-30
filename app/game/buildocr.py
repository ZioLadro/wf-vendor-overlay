"""A build read from a picture: a screenshot of the game's upgrade screen (or a picture shared by this program).

The picture's text is read by the OCR (the same engine as the price labels, in its own process); here the lines are
turned into a build:
  * the item: the title "UPGRADES / <item> [rank]" (any language: what follows the slash), else the best item name
    found anywhere;
  * the mods and Arcanes: every line (or two lines one under the other: long names wrap) that is a mod / Arcane name,
    above the mod library of the game screen (everything under SEARCH… / ALL is the player's own mods);
  * their slots, by position, as the game lays them out: the top row (Aura / Stance / Exilus, by the mod's type), the
    general slots in rows of four (five for companions; the game numbers them from the bottom right, see
    loadouts.py), the Arcanes and a gun's Exilus in the column on the right.
Ranks cannot be read reliably from the pips: mods are set to their maximum rank. Forma polarities are not read."""
import difflib
import re

from app.game import buildcalc as BC
from app.game import loadouts as LO

KINDS = ("warframe", "primary", "secondary", "melee", "archgun", "archmelee", "archwing", "necramech", "companion",
         "compweapon")
STOP = re.compile(r"^(search|cerca|suche|buscar|rechercher|all|tutti|tutte|rank)\b", re.I)


def _k(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


class Names:
    """The names to look for, normalised: mods (mst), Arcanes, items by kind."""
    _cache = None

    def __init__(self):
        d = LO.data()
        self.mods = {_k(n): n for n in (d.get("mst") or {})}
        self.arcanes = {_k(n): n for n in (d.get("arc") or {})}
        self.items = {}
        for kind in KINDS:
            try:
                for n in BC.items(kind):
                    self.items.setdefault(_k(n), (n, kind))
            except Exception:
                pass
        self._mod_keys, self._arc_keys = list(self.mods), list(self.arcanes)

    @classmethod
    def get(cls):
        if cls._cache is None:
            cls._cache = cls()
        return cls._cache

    def match(self, text: str):
        """("mod" | "arcane", name, score) of the best name for a piece of text, or None."""
        k = _k(text)
        if len(k) < 4:
            return None
        if k in self.mods:
            return "mod", self.mods[k], 1.0
        if k in self.arcanes:
            return "arcane", self.arcanes[k], 1.0
        best = None
        for kind, keys, table in (("mod", self._mod_keys, self.mods), ("arcane", self._arc_keys, self.arcanes)):
            for c in difflib.get_close_matches(k, keys, n=1, cutoff=0.86):
                s = difflib.SequenceMatcher(None, k, c).ratio()
                if best is None or s > best[2]:
                    best = (kind, table[c], s)
        return best

    def riven(self, text: str):
        """(weapon, riven name) when a text is a Riven's name: a weapon's name and the Riven's made-up word
        ("Kuva Bramma Acri-critacan"), else None."""
        k = _k(text)
        if not hasattr(self, "_riven_w"):
            self._riven_w = {}
            for kind in ("primary", "secondary", "melee", "archgun", "archmelee"):
                try:
                    for n in BC.items(kind):
                        self._riven_w.setdefault(_k(n), n)
                except Exception:
                    pass
        best = max((w for w in self._riven_w if k.startswith(w) and len(k) - len(w) >= 3), key=len, default=None)
        if not best:
            return None
        weapon = self._riven_w[best]
        words = text.split()
        rest = " ".join(words[len(weapon.split()):]).strip(" -")
        # a Riven's word: capitalised syllables joined by a hyphen ("Acri-critacan", "Sati-", "Critatis"), not a word
        # in capitals ("VALENZA") or several words
        if not re.fullmatch(r"[A-Z][a-z]{2,}(-[a-z]*)?", rest or ""):
            return None
        return weapon, f"{weapon} {rest}"

    def item(self, text: str, loose=True):
        """(name, kind) of an item in a piece of text: the whole text, else the longest item name inside it (a weapon
        renamed "RIKK LUZK KUVA ZARR" holds "Kuva Zarr", "PHARAOH CLAWS" holds "Claws"), else a close spelling."""
        k = _k(re.sub(r"\[.*?\]|\(.*?\)", "", text))
        if len(k) < 4:
            return None
        if k in self.items:
            return self.items[k]
        inside = [c for c in self.items if len(c) >= 5 and c in k]
        if inside:
            return self.items[max(inside, key=len)]
        if not loose:
            return None
        c = difflib.get_close_matches(k, list(self.items), n=1, cutoff=0.84)
        return self.items[c[0]] if c else None


def _title(lines, names):
    """(item, kind) from the screen's title ("UPGRADES / Cyte-09 [30]", "POTENZIAMENTI / …")."""
    for ln in sorted(lines, key=lambda l: l[2]):
        text = ln[0]
        if "/" in text:
            hit = names.item(text.split("/", 1)[1])
            if hit:
                return hit
    for ln in sorted(lines, key=lambda l: l[2]):                # a shared picture: the item alone in its title bar
        if _k(ln[0]) in names.items:
            return names.items[_k(ln[0])]
    return None


# stat labels of the screen's left panel (not mods, even when they are spelled like one: "Range" ~ "Rage")
STAT_WORDS = {_k(w) for w in ("Range", "Health", "Shield", "Armor", "Energy", "Duration", "Efficiency", "Strength",
                              "Sprint Speed", "Follow Through", "Attack Speed", "Combo Duration", "Slide Attack",
                              "Slam Attack", "Fire Rate", "Multishot", "Magazine", "Reload", "Accuracy", "Trigger",
                              "Punch Through", "Critical Chance", "Critical Damage", "Status", "Total", "Impact",
                              "Puncture", "Slash", "Rank Bonuses", "Capacity", "Recovery Time")}


def _cards(lines, names, bottom, left=0.0):
    """[(kind, name, x centre, y centre)] of the mod / Arcane names above `bottom`, joining a name split on two lines."""
    rows = sorted((ln for ln in lines if ln[2] < bottom and ln[1] + ln[3] / 2 > left
                   and _k(ln[0]) not in STAT_WORDS), key=lambda l: (l[2], l[1]))
    used, out = set(), []
    for i, ln in enumerate(rows):
        if i in used:
            continue
        text, x, y, w, h = ln[:5]
        if len(re.sub(r"[^A-Za-z]", "", text)) < 3:             # a number (drain, rank, capacity): not a name
            continue
        hit = names.match(text)
        if hit is not None and hit[2] < 0.97 and names.riven(text):
            hit = None                                          # "Kuva Bramma Acri-…" read as some mod: a Riven
        if hit is None or hit[2] < 0.97:                        # the rest of the name on the line below?
            cx = x + w / 2
            for j in range(i + 1, len(rows)):
                t2, x2, y2, w2, h2 = rows[j][:5]
                if y2 - y > 2.2 * h:
                    break
                if len(re.sub(r"[^A-Za-z]", "", t2)) < 3:
                    continue
                if j in used or abs((x2 + w2 / 2) - cx) > max(w, w2) * 0.6 or y2 <= y:
                    continue
                both = names.match(text + " " + t2)
                if both and (hit is None or both[2] > hit[2]):
                    hit = both
                    used.add(j)
                    x, w = min(x, x2), max(x + w, x2 + w2) - min(x, x2)
                    h = y2 + h2 - y
                break
        if hit is None:                                         # a Riven ("Kuva Bramma Acri-" + "critacan")?
            rv = names.riven(text)
            if rv is not None:
                cx = x + w / 2
                for j in range(i + 1, len(rows)):
                    t2, x2, y2, w2, h2 = rows[j][:5]
                    if y2 - y > 2.2 * h:
                        break
                    if j not in used and y2 > y and abs((x2 + w2 / 2) - cx) <= max(w, w2) * 0.6 \
                            and re.fullmatch(r"[a-z][a-z\-]{2,}", t2.strip()):
                        rv = (rv[0], rv[1] + "-" + t2.strip())      # a Riven's name breaks at its hyphen
                        used.add(j)
                        h = y2 + h2 - y
                        break
                hit = ("riven", rv[1], 1.0, rv[0])
        if hit is not None:
            used.add(i)
            out.append((hit[0], hit[1], x + w / 2, y + h / 2, h) + ((hit[3],) if len(hit) > 3 else ()))
    return out


def _clusters(values, tol):
    """Groups of close values (sorted), as lists of indices into `values`."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    groups = []
    for i in order:
        if groups and values[i] - values[groups[-1][-1]] <= tol:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def parse(lines, width: int = 0, height: int = 0, kind_hint: str = "", item_hint: str = "", image=None):
    """lines: [(text, x, y, w, h, …)] in pixels. Returns {"item", "kind", "mods": [(name, rank) or None per slot],
    "found": [names], "unplaced": [names], "rows": n} or raises ValueError with a short reason."""
    names = Names.get()
    lines = [tuple(ln) for ln in lines if ln and str(ln[0]).strip()]
    if not lines:
        raise ValueError("no text in the picture")
    stops = [ln[2] for ln in lines if STOP.match(str(ln[0]).strip()) and ln[2] > (height or 1e9) * 0.25]
    bottom = min(stops) if stops else float("inf")             # the mod library starts here (the game's screen)
    hit = (item_hint, kind_hint) if item_hint and kind_hint else _title(lines, names)
    left = 0.0                    # the stats panel's labels are left out by name (STAT_WORDS), not by position
    cards = _cards(lines, names, bottom, left)
    if not cards:
        raise ValueError("no mod names found")
    if not hit:
        raise ValueError("the item was not recognised")
    item, kind = hit
    roles = BC.plan_roles(kind, item)
    out = [None] * len(roles)
    found = [c[1] for c in cards]
    arcanes = sorted((c for c in cards if c[0] == "arcane"), key=lambda c: (c[3], c[2]))
    mods = [c for c in cards if c[0] == "mod"]

    def mtype(name):
        info = BC.mod_info(name)
        return (info[3] if info else "", info[4] if info else "")

    special_role = {}
    general = [c for c in cards if c[0] == "riven"]
    for c in mods:
        compat, typ = mtype(c[1])
        if compat == "AURA" and "aura" in roles:
            special_role[c] = "aura"
        elif typ in ("T", "Y") and "stance" in roles:
            special_role[c] = "stance"
        else:
            general.append(c)
    # rows of the general slots: the most common card height sets the tolerance
    hs = sorted(c[4] for c in general) or [30]
    tol = hs[len(hs) // 4] * 1.6                                 # a single line's height (two-line names are taller)
    groups = [[general[i] for i in g] for g in _clusters([c[3] for c in general], tol)]
    ncol = 5 if roles.count("general") >= 10 else 4
    # a top row above the general rows holding only one or two cards (with an Aura / Stance, or before two full rows)
    # is the special row: its non-Aura / Stance mod is the Exilus
    special_y = [c[3] for c in special_role]
    exilus = []
    if groups and len(groups[0]) <= 2 and len(groups) >= 2 and "exilus" in roles:
        first = groups[0]
        near_special = special_y and abs(sum(c[3] for c in first) / len(first) - sum(special_y) / len(special_y)) <= tol
        if near_special or (len(groups) >= 3 and len(groups[1]) >= 3):
            exilus += first
            groups = groups[1:]
    flat = [c for g in groups for c in g]
    where, step = {}, 0.0
    if flat:
        # the columns: the x positions of all the general cards grouped; the general slots are the first ncol columns,
        # a column further right holds a gun's Exilus (and the Arcanes)
        allx = [c[2] for c in flat]
        gaps = sorted(b - a for a, b in zip(sorted(allx), sorted(allx)[1:]) if b - a > 20)
        step = gaps[len(gaps) // 2] if gaps else 200
        cl = _clusters(allx, step * 0.45)
        xs = [sum(allx[i] for i in g) / len(g) for g in cl]
        keep = []
        if len(xs) > ncol:
            right = (xs[ncol - 1] + xs[ncol]) / 2
            for c in flat:
                if c[2] > right and "exilus" in roles and len(exilus) < 1:
                    exilus.append(c)
                elif c[2] <= right:
                    keep.append(c)
            xs = xs[:ncol]
        else:
            keep = flat
        groups = [[c for c in g if c in keep] for g in groups]
        groups = [g for g in groups if g]
        # rows again without the right column (it sits between two rows and may have merged them)
        kept = [c for g in groups for c in g]
        groups = [[kept[i] for i in g] for g in _clusters([c[3] for c in kept], tol)]
        cols = xs if len(xs) >= ncol else xs + [xs[-1] + step * (k + 1) for k in range(ncol - len(xs))]
        n_general = roles.count("general")
        gen_idx = [i for i, r in enumerate(roles) if r == "general"]
        unplaced = []
        for r, g in enumerate(groups):
            for c in g:
                col = min(range(len(cols)), key=lambda k: abs(cols[k] - c[2]))
                pos = r * ncol + col
                if pos >= n_general:
                    unplaced.append(c[1])
                    continue
                idx = gen_idx[n_general - 1 - pos]                # the game: its last slot top left
                if out[idx] is None:
                    out[idx] = _entry(c, lines, step)
                    where[idx] = c
                else:
                    unplaced.append(c[1])
    else:
        unplaced = []
    for c, role in special_role.items():
        i = next((k for k, r in enumerate(roles) if r == role and out[k] is None), None)
        if i is not None:
            out[i] = _entry(c, lines, step)
            where[i] = c
    for c in exilus:
        i = next((k for k, r in enumerate(roles) if r == "exilus" and out[k] is None), None)
        if i is not None:
            out[i] = _entry(c, lines, step)
            where[i] = c
        else:
            unplaced.append(c[1])
    from app.ui.planner_tab import arcane_max
    for c in arcanes:
        i = next((k for k, r in enumerate(roles) if r == "arcane" and out[k] is None), None)
        if i is not None:
            out[i] = (c[1], arcane_max(c[1]))
    pols, unknown = {}, []
    if image is not None and where:
        if not step:                                            # no general row: a card's width from a name's height
            step = 6.0 * (sorted(c[4] for c in where.values())[0])
        for i, c in where.items():
            state, bubble = _colours(image, c[2], c[3], step)
            m = out[i]
            mp = (m[2].get("polarity") if len(m) > 2 else (BC.mod_info(m[0]) or [""])[0]) if m else ""
            if state == "match":
                pols[i] = "universal" if bubble else mp
            elif state == "":
                pols[i] = ""                                    # white: the slot has no polarity (not even innate)
            # the drain written on the card, when it can be read: the polarity and rank that give it (the colour
            # first; a number that does not fit it means the colour was misread)
            d = _drain_read(lines, c[2], c[3], step)
            if d is not None and m and len(m) == 2:
                info = BC.mod_info(m[0])
                if info:
                    other = "naramon" if mp != "naramon" else "madurai"
                    for sp in dict.fromkeys([pols.get(i, ""), "", mp, other]):
                        fits = [rk for rk in range(int(info[2]), -1, -1) if abs(BC.drain(info, rk, sp)[0]) == d]
                        if fits:
                            out[i] = (m[0], fits[0])
                            pols[i] = sp
                            if sp == other and m[0] not in unknown:
                                unknown.append(m[0])
                            elif sp != other and m[0] in unknown:
                                unknown.remove(m[0])
                            break
            elif state == "mismatch":                         # another polarity (which one is not readable): one
                unknown.append(m[0].replace(" (Riven)", ""))   # that is not the mod's, so the drain is the game's
                pols[i] = "naramon" if mp != "naramon" else "madurai"
    return {"item": item, "kind": kind, "mods": out, "found": found, "unplaced": unplaced, "pols": pols,
            "mismatch": unknown}


ATTR = re.compile(r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*(%|x)?\s+([A-Za-z][A-Za-z ()/'-]+)$")


def _entry(c, lines, step):
    """The slot's (name, rank) — a Riven: (name, 8, riven) with the stats written on its card when the picture has them
    (a picture shared by this program); the game's card shows none."""
    if c[0] != "riven":
        return (c[1], (BC.mod_info(c[1]) or [0, 0, 0])[2])
    attrs = []
    for ln in lines:
        t_, x, y, w, h = ln[:5]
        if step and abs((x + w / 2) - c[2]) <= step * 0.5 and c[3] - step * 0.55 <= y + h / 2 < c[3] - h * 0.3:
            m = ATTR.match(str(t_).replace("−", "-"))
            if m:
                v = float(m.group(1).replace(",", "."))
                attrs.append({"label": m.group(3).strip(), "value": v, "pct": m.group(2) == "%",
                              "positive": not m.group(1).startswith("-")})
    riven = {"mod_name": c[1], "weapon": c[5] if len(c) > 5 else "", "rank": 8, "polarity": "madurai",
             "attributes": attrs}
    return (c[1] + " (Riven)", 8, riven)


def _drain_read(lines, cx, cy, step):
    """The drain number the OCR read at a card's top right ("8Y", "^14—", "12"), or None."""
    for ln in lines:
        t_, x, y, w, h = ln[:5]
        mx, my = x + w / 2, y + h / 2
        if cx + 0.18 * step <= mx <= cx + 0.52 * step and cy - 0.27 * step <= my <= cy - 0.03 * step:
            m = re.match(r"^\D{0,2}?(\d{1,2})", str(t_).strip())
            if m:
                return int(m.group(1))
    return None


def _colours(image, cx, cy, step):
    """("match" | "mismatch" | "", Omni Forma bubble?) of a card from its picture: the colour of the drain at the card's
    top right (green: the slot has the mod's polarity, red: another one, white: none) and the game's green bubble on
    the card's top right corner (an Omni Forma, when the drain is green)."""
    def count(x0, y0, x1, y1, test):
        w, h = image.size
        box = (max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1)))
        if box[2] <= box[0] or box[3] <= box[1]:
            return 0, 1
        px = list(image.crop(box).getdata())
        return sum(1 for p in px if test(p)), len(px)
    lime = lambda p: p[1] > 110 and p[1] > p[0] + 25 and p[1] > p[2] + 50
    red = lambda p: p[0] > 150 and p[0] > p[1] + 60 and p[0] > p[2] + 40
    region = (cx + 0.26 * step, cy - 0.21 * step, cx + 0.46 * step, cy - 0.07 * step)
    g, n = count(*region, lime)
    r, _n = count(*region, red)
    state = "match" if g >= max(4, n * 0.02) and g > r else ("mismatch" if r >= max(4, n * 0.02) else "")
    b, nb = count(cx + 0.44 * step, cy - 0.40 * step, cx + 0.60 * step, cy - 0.22 * step, lime)
    return state, b >= max(6, nb * 0.025)
