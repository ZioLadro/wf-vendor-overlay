"""A Riven's stats read from a picture: the game's Riven card or tooltip (name, "+172.1% Critical Chance",
"x0.62 Damage to Corpus", "MR 16", rerolls), a screenshot or a video frame.

The OCR gives the lines (same engine as the price labels); here they are turned into the planner's Riven: weapon and
name, every stat line with its value (a faction multiplier "x0.62" becomes -38 %), labels corrected to the game's own
names (data/rivens.json), mastery rank and rerolls when they can be read."""
import difflib
import re

from app.game.buildocr import Names, _k

STAT = re.compile(r"^\s*([+\-−]|x|×)?\s*(\d{1,4}(?:[.,]\d{1,3})?)\s*(%|x)?\s+([A-Za-z][A-Za-z ()/'\-]+?)\s*$")
_labels = None


def labels() -> dict:
    """{normalised label: game label} of every Riven stat (parentheses dropped: "Fire Rate (x2 for Bows)")."""
    global _labels
    if _labels is None:
        import json
        from app.core.paths import DATA
        out = {}
        try:
            d = json.loads((DATA / "rivens.json").read_text(encoding="utf-8"))
            for stats in (d.get("types") or {}).values():
                for row in stats.values():
                    lab = re.sub(r"\s*\(.*?\)", "", str(row[4])).strip()
                    out[_k(lab)] = lab
        except Exception:
            pass
        for lab in ("Damage to Corpus", "Damage to Grineer", "Damage to Infested", "Damage to Orokin",
                    "Damage to The Murmur", "Ammo Efficiency"):
            out.setdefault(_k(lab), lab)
        _labels = out
    return _labels


def _label(text: str) -> str:
    k = _k(text)
    table = labels()
    if k in table:
        return table[k]
    c = difflib.get_close_matches(k, list(table), n=1, cutoff=0.75)
    return table[c[0]] if c else text.strip()


def parse(lines, current_name: str = "") -> dict:
    """lines: [(text, x, y, w, h, …)]. {"mod_name", "weapon", "attributes": [{label, value, pct, positive}], "mr",
    "rerolls"}; raises ValueError when no stat line is found."""
    rows = sorted((tuple(ln) for ln in lines if ln and str(ln[0]).strip()), key=lambda l: (l[2], l[1]))
    names = Names.get()
    name = weapon = ""
    name_y = None
    for i, ln in enumerate(rows):                        # the name: a weapon and the Riven's word, maybe on two lines
        hit = names.riven(ln[0])
        if hit:
            weapon, name = hit
            name_y = ln[2]
            cx = ln[1] + ln[3] / 2
            for nxt in rows[i + 1:]:                     # the rest of the name on the line below
                if nxt[2] - ln[2] > 2.5 * ln[4]:
                    break
                if nxt[2] > ln[2] and abs(nxt[1] + nxt[3] / 2 - cx) < ln[3] * 0.6 \
                        and re.fullmatch(r"[a-z][a-z\-]{2,}", nxt[0].strip()):
                    name = name.rstrip("-") + "-" + nxt[0].strip()
                    break
            break
    if current_name:                                     # the slot's Riven: its name wins over a cursor-blurred one
        cur = current_name.replace(" (Riven)", "")
        if not name or difflib.SequenceMatcher(None, _k(cur), _k(name)).ratio() > 0.75:
            name = cur
            weapon = weapon or (names.riven(cur) or ("", ""))[0]
    attrs, mr, rerolls = [], None, None
    for ln in rows:
        text = str(ln[0]).replace("−", "-").strip()
        if name_y is not None and ln[2] < name_y:
            continue
        m = re.fullmatch(r"MR\s*(\d{1,2})", text, re.I)
        if m:
            mr = int(m.group(1))
            same = [r for r in rows if r is not ln and abs(r[2] - ln[2]) < ln[4] and r[1] > ln[1]
                    and re.fullmatch(r"\D?\d{1,4}", str(r[0]).strip())]
            if same:                                     # the rerolls: "⟳ 20" read as "020" / "969"
                d = re.sub(r"\D", "", same[0][0])
                rerolls = int(d[1:]) if len(d) >= 2 and d[0] in "0969" else int(d)
            continue
        m = STAT.match(text)
        if not m:
            continue
        sign, num, unit, lab = m.group(1) or "", float(m.group(2).replace(",", ".")), m.group(3) or "", m.group(4)
        label = _label(lab)
        if sign in ("x", "×") or (unit == "x" and not sign):  # a faction multiplier: x0.62 = -38 %
            value = round((num - 1) * 100, 1)
            pct = True
        else:
            value = -num if sign in ("-",) else num
            pct = unit == "%"
        attrs.append({"label": label, "value": value, "pct": pct, "positive": value >= 0})
    if not attrs:
        raise ValueError("no Riven stats in the picture")
    return {"mod_name": name, "weapon": weapon, "attributes": attrs[:4], "mr": mr, "rerolls": rerolls}
