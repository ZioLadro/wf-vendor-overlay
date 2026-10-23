"""The player's inventory: storage, import from files, and valuation helpers.

Warframe keeps the inventory on DE's servers, not in local files, so it cannot be read from disk.
Instead the inventory is built from:
  - an imported file: JSON (a raw Warframe-style inventory, or any list/dict that pairs item names with
    quantities) or CSV/TXT ("name, quantity[, rank]" lines, "3x Name", "Name x3", …), and
  - manual edits in the Inventory tab.
Each item is stored as {"n": copies, "m": copies at max rank}: "m" only matters for mods and arcanes.
"""
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from config import APP_DIR
from i18n import t

INV_FILE = APP_DIR / "inventory.json"
BUNDLED_NAMES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "gamenames.json"
USER_NAMES = APP_DIR / "gamenames.json"

NAME_KEYS = ("name", "itemname", "item_name", "item", "title", "displayname")
COUNT_KEYS = ("count", "quantity", "qty", "amount", "owned", "itemcount", "number", "have")
RANK_KEYS = ("rank", "lvl", "level", "fusionlevel", "upgradelevel")
RAW_LISTS = ("MiscItems", "RawUpgrades", "Upgrades", "Recipes", "FusionTreasures", "Consumables",
             "LevelKeys", "Ships", "WeaponSkins", "Suits")        # sections of a raw inventory that can hold sellable items
SKIP_KEYS = {"Suits", "Ships", "WeaponSkins"}                      # owned equipment, not sellable stock
MAX_UNMATCHED = 500


@dataclass
class ImportResult:
    items: dict = field(default_factory=dict)       # slug -> {"n": int, "m": int}
    unmatched: list = field(default_factory=list)   # [(raw name, quantity)]
    lines: int = 0                                  # entries read from the file
    path: str = ""                                  # file it was read from
    source: str = ""

    @property
    def matched(self) -> int:
        return len(self.items)


class Inventory:
    def __init__(self):
        self.items = {}        # slug -> {"n": int, "m": int}
        self.orders = {}       # slug -> last order placed from the app: {"id","price","qty","rank","t"}
        self.imported = None   # timestamp of the last import
        self.path = ""         # file of the last import (for "Reload file")
        self.source = ""
        self.load()

    # ---------- persistence ----------
    def load(self):
        try:
            d = json.loads(INV_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(d, dict):
            return
        self.items = {k: {"n": int(v.get("n", 0)), "m": int(v.get("m", 0))}
                      for k, v in (d.get("items") or {}).items() if isinstance(v, dict)}
        self.orders = {k: v for k, v in (d.get("orders") or {}).items() if isinstance(v, dict)}
        self.imported, self.source, self.path = d.get("imported"), d.get("source", ""), d.get("path", "")

    def save(self):
        payload = {"version": 1, "imported": self.imported, "source": self.source, "path": self.path,
                   "items": self.items, "orders": self.orders}
        tmp = INV_FILE.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, INV_FILE)
            return True
        except OSError:
            return False

    # ---------- editing ----------
    def set(self, slug: str, n: int, m: int = 0):
        n, m = max(0, int(n)), max(0, int(m))
        if n + m == 0:
            self.items.pop(slug, None)
        else:
            self.items[slug] = {"n": n, "m": m}
        self.save()

    def remove(self, slugs):
        for s in slugs:
            self.items.pop(s, None)
        self.save()

    def clear(self):
        self.items.clear()
        self.imported, self.source, self.path = None, "", ""
        self.save()

    def replace_with(self, result: ImportResult, path: str = ""):
        self.items = {k: dict(v) for k, v in result.items.items()}
        self.imported, self.source, self.path = int(time.time()), result.source, path
        self.save()

    def record_order(self, slug: str, order_id, price: int, qty: int, rank: int):
        self.orders[slug] = {"id": order_id, "price": int(price), "qty": int(qty), "rank": int(rank),
                             "t": int(time.time())}
        self.save()


# ---------- game names (ItemType path -> English name) ----------
_names_cache = None


def game_names() -> dict:
    """{"names": {path: name}, "recipes": {path: result name}, "relics": {path: name}} (bundled file)."""
    global _names_cache
    if _names_cache is None:
        _names_cache = {"names": {}, "recipes": {}, "relics": {}}
        for f in (BUNDLED_NAMES, USER_NAMES):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                for k in _names_cache:
                    _names_cache[k].update(d.get(k) or {})
            except Exception:
                pass
    return _names_cache


def names_for_path(path: str) -> list:
    """Candidate market names for a game ItemType path (most likely first)."""
    g = game_names()
    if path in g["relics"]:
        return [g["relics"][path]]
    out = []
    if path in g["names"]:
        out.append(g["names"][path])
    if path in g["recipes"]:                  # blueprint of an item
        base = g["recipes"][path]
        out += [base + " Blueprint", base]
    return out


# ---------- name -> market slug ----------
def resolve(market, raw: str):
    """Market slug for a name written by a human or a tool, or None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for cand in (raw, re.sub(r"\s*\(.*?\)\s*", " ", raw).strip(), re.sub(r"\s+x\d+$", "", raw, flags=re.I)):
        slug = market.slug_for_name(cand)
        if slug:
            return slug
    m = market.match(raw, 95)                 # tolerate small typos / OCR-like errors
    return m.slug if m else None


def _add(res: ImportResult, market, slug, qty, rank=None):
    mr = market.info(slug).get("max_rank", 0)
    e = res.items.setdefault(slug, {"n": 0, "m": 0})
    if mr > 0 and rank is not None and rank >= mr:
        e["m"] += qty
    else:
        e["n"] += qty


def _entry(res: ImportResult, market, name, qty, rank=None, slug=None):
    res.lines += 1
    slug = slug or resolve(market, name)
    if slug:
        _add(res, market, slug, qty, rank)
    elif len(res.unmatched) < MAX_UNMATCHED:
        res.unmatched.append((name, qty))


def _int(v, default=None):
    try:
        if isinstance(v, bool):
            return default
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _fingerprint_rank(fp):
    """Rank of a ranked mod/arcane from a raw inventory's UpgradeFingerprint (a JSON string with "lvl")."""
    try:
        return int(json.loads(fp).get("lvl")) if isinstance(fp, str) else int(fp.get("lvl"))
    except Exception:
        return None


# ---------- parsers ----------
def parse_json(data, market, res=None) -> ImportResult:
    res = res or ImportResult()
    if isinstance(data, dict) and any(k in data for k in RAW_LISTS):
        _parse_raw(data, market, res)          # a raw Warframe-style inventory
    else:
        _walk(data, market, res)
    return res


def _parse_raw(inv: dict, market, res: ImportResult):
    for section in RAW_LISTS:
        if section in SKIP_KEYS:
            continue
        for it in inv.get(section) or []:
            if not isinstance(it, dict) or "ItemType" not in it:
                continue
            path = it["ItemType"]
            qty = _int(it.get("ItemCount"), 1)
            rank = _fingerprint_rank(it["UpgradeFingerprint"]) if "UpgradeFingerprint" in it else None
            slug = None
            for cand in names_for_path(path):
                slug = resolve(market, cand)
                if slug:
                    break
            if section == "Upgrades" and rank is None:
                rank = 0
            _entry(res, market, (names_for_path(path) or [path.rsplit("/", 1)[-1]])[0], qty, rank, slug)


def _walk(node, market, res: ImportResult):
    if isinstance(node, list):
        for x in node:
            _walk(x, market, res)
        return
    if not isinstance(node, dict):
        return
    low = {str(k).lower(): v for k, v in node.items()}
    if "itemtype" in low and isinstance(low["itemtype"], str) and low["itemtype"].startswith("/"):
        slug = next((s for s in (resolve(market, c) for c in names_for_path(low["itemtype"])) if s), None)
        _entry(res, market, (names_for_path(low["itemtype"]) or [low["itemtype"]])[0],
               _int(low.get("itemcount"), 1) or 1, _fingerprint_rank(low.get("upgradefingerprint")), slug)
        return
    name = next((low[k] for k in NAME_KEYS if isinstance(low.get(k), str)), None)
    if name:
        qty = next((_int(low[k]) for k in COUNT_KEYS if k in low and _int(low[k]) is not None), 1)
        rank = next((_int(low[k]) for k in RANK_KEYS if k in low and _int(low[k]) is not None), None)
        _entry(res, market, name, qty, rank)
        return
    # {"Serration": 2, "Point Blank": 1}: a dict of name -> quantity
    if node and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in node.values()) \
            and all(isinstance(k, str) and not k.startswith("/") for k in node):
        for k, v in node.items():
            _entry(res, market, k, _int(v, 1))
        return
    for v in node.values():
        _walk(v, market, res)


_HEADER = re.compile(r"\b(name|item)\b", re.I)


def parse_text(text: str, market, res=None) -> ImportResult:
    """CSV / TXT: "name, qty[, rank]", "qty, name", "3x Name", "Name x3" or just a name (1 copy)."""
    res = res or ImportResult()
    for i, line in enumerate(text.lstrip("﻿").splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip().strip('"') for p in re.split(r"[;\t,]", line)]
        if i == 0 and _HEADER.search(line) and not re.search(r"\d", line):
            continue                                                  # header row
        name, qty, rank = None, 1, None
        if len(parts) >= 2 and re.fullmatch(r"\d+", parts[1]):
            name, qty = parts[0], int(parts[1])
            if len(parts) > 2 and re.fullmatch(r"\d+", parts[2]):
                rank = int(parts[2])
        elif len(parts) >= 2 and re.fullmatch(r"\d+", parts[0]):
            qty, name = int(parts[0]), parts[1]
        elif (m := re.fullmatch(r"(\d+)\s*[x×]\s*(.+)", line, re.I)):
            qty, name = int(m.group(1)), m.group(2)
        elif (m := re.fullmatch(r"(.+?)\s*[x×]\s*(\d+)", line, re.I)):
            name, qty = m.group(1), int(m.group(2))
        else:
            name = line
        _entry(res, market, name.strip(), qty, rank)
    return res


# lastData.dat (AlecaFrame-style): the inventory JSON, PKCS#7-padded and AES-128-CBC encrypted with a
# fixed key and IV (published in the open-source tools that write this file). Values transcribed from
# a third-party source: if a file cannot be decoded, the error says so instead of importing garbage.
DAT_KEY = bytes([76, 69, 79, 45, 65, 76, 69, 67, 9, 69, 79, 45, 65, 76, 69, 67])
DAT_IV = bytes([49, 50, 70, 71, 66, 51, 54, 45, 76, 69, 51, 45, 113, 61, 57, 0])


def decrypt_last_data(raw: bytes) -> str:
    """Decrypts the contents of a lastData.dat file into the inventory JSON text. Raises ValueError."""
    try:
        from cryptography.hazmat.primitives import padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        raise ValueError(t("inv.dat.nolib"))
    if not raw or len(raw) % 16:
        raise ValueError(t("inv.dat.failed"))
    try:
        dec = Cipher(algorithms.AES(DAT_KEY), modes.CBC(DAT_IV)).decryptor()
        padded = dec.update(raw) + dec.finalize()
        unpad = padding.PKCS7(128).unpadder()
        text = (unpad.update(padded) + unpad.finalize()).decode("utf-8")
        json.loads(text)                                  # must be JSON, otherwise the key does not fit
        return text
    except Exception:
        raise ValueError(t("inv.dat.failed"))


def parse_file(path, market) -> ImportResult:
    p = Path(path)
    raw = p.read_bytes()
    head = raw.lstrip(b"\xef\xbb\xbf \t\r\n")[:1]
    if head in (b"{", b"["):
        text = raw.decode("utf-8-sig", errors="replace")
    elif p.suffix.lower() == ".dat" or b"\x00" in raw[:2048]:
        text = decrypt_last_data(raw)
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    res = ImportResult(source=p.name)
    res.path = str(p)
    stripped = text.lstrip()
    if p.suffix.lower() in (".json", ".dat") or stripped[:1] in "{[":
        try:
            return parse_json(json.loads(text), market, res)
        except json.JSONDecodeError:
            if p.suffix.lower() in (".json", ".dat"):
                raise ValueError("not valid JSON")
    return parse_text(text, market, res)


# ---------- valuation / filtering helpers ----------
def is_prime(name: str) -> bool:
    return bool(re.search(r"\bPrime\b", name))


def build_rows(inv: Inventory, market, query="", category=None, min_plat=0, exclude_maxed=False,
               multiple=False, part_type=None, vaulted=None, listed=None):
    """Rows of the Inventory tab after the filters, plus the estimated total value in platinum.

    Filters mirror AlecaFrame's: minimum platinum, more than one owned, part type (prime/normal),
    vaulted, order placed — plus the category and "exclude max-rank mods/arcanes".
    The value of an item is copies × rank 0 price, plus max-rank copies × max-rank price."""
    q = query.strip().lower()
    rows, total = [], 0
    for slug, e in inv.items.items():
        info = market.info(slug)
        if not info:
            continue                                   # item no longer in the market catalog
        ranked = info.get("max_rank", 0) > 0
        n, m = e["n"], (0 if (exclude_maxed and ranked) else e["m"])
        if n + m == 0:
            continue
        name = info["name"]
        if q and q not in name.lower():
            continue
        if category is not None and info.get("category") != category:
            continue
        if multiple and n + m < 2:
            continue
        if part_type == "prime" and not is_prime(name):
            continue
        if part_type == "normal" and is_prime(name):
            continue
        if vaulted is not None and bool(info.get("vaulted")) != vaulted:
            continue
        if listed is not None and (slug in inv.orders) != listed:
            continue
        c = market.cached(slug) or {}
        price, pmax = c.get("price"), c.get("pmax")
        unit = price if n > 0 else pmax
        if min_plat and (unit is None or unit < min_plat):
            continue
        value = None
        parts = [(n, price)] + ([(m, pmax)] if ranked else [(m, price)])
        if all(cnt == 0 or p is not None for cnt, p in parts):
            value = sum(cnt * p for cnt, p in parts if cnt)
            total += value
        updated = max([t for t in (c.get("pt"), c.get("vt")) if t] or [0]) or None
        rows.append({"slug": slug, "name": name, "category": info.get("category", "other"),
                     "n": n, "m": m, "ranked": ranked, "max_rank": info.get("max_rank", 0),
                     "price": price, "pmax": pmax, "vol": c.get("vol"), "value": value,
                     "updated": updated, "order": inv.orders.get(slug)})
    rows.sort(key=lambda r: (-(r["value"] or 0), r["name"].lower()))
    return rows, total
