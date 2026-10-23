"""Quali oggetti vende ogni vendor.

- vendors.json (incluso): vendor e sindacati, generato da build_vendors.py dai dati del gioco.
  Se esiste %LOCALAPPDATA%\\WFVendorOverlay\\vendors.json ha la precedenza (per aggiornarlo/modificarlo).
- Baro Ki'Teer: non e' nei dati del gioco (l'inventario cambia a ogni visita). Il suo elenco storico viene
  letto dalla wiki (Module:Baro/data) e, quando e' presente, dal suo inventario attuale (warframestat).
  Il risultato e' salvato in baro.json e si aggiorna da solo ogni `baro_refresh_days` giorni.
I nomi vengono associati agli oggetti di warframe.market: nel listino compaiono solo quelli scambiabili.
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

from config import APP_DIR, CFG
from matcher import norm

BUNDLED = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "vendors.json"
USER_FILE = APP_DIR / "vendors.json"
BARO_FILE = APP_DIR / "baro.json"
BARO = "Baro Ki'Teer"
WIKI_URLS = (
    "https://wiki.warframe.com/w/Module:Baro/data?action=raw",
    "https://wiki.warframe.com/index.php?title=Module:Baro/data&action=raw",
)
API_URL = "https://api.warframestat.us/pc/voidTrader"
UA = "WFVendorOverlay/1.3 (overlay personale; richieste rare)"
_STR = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'')


def _read(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def lua_strings(text: str) -> list:
    """Tutte le stringhe tra apici di un sorgente Lua (ignora le righe di commento)."""
    text = re.sub(r"--\[(=*)\[.*?\]\1\]", "", text, flags=re.S)          # commenti a blocco
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("--"):
            continue
        for m in _STR.finditer(line):
            s = m.group(1) if m.group(1) is not None else m.group(2)
            out.append(s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\"))
    return out


def fetch_baro(name_slug: dict, timeout: float = 25.0):
    """Scarica gli oggetti di Baro. Ritorna ({norm: nome}, info, errori); solo nomi presenti sul market."""
    names, info, errors = {}, {}, []
    for url in WIKI_URLS:                                   # storico completo (wiki)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
            r.raise_for_status()
            found = {norm(s): s for s in lua_strings(r.text) if norm(s) in name_slug}
            if found:
                names.update(found)
                info["wiki"] = len(found)
                break
            errors.append("wiki: risposta senza oggetti riconoscibili")
        except Exception as e:
            errors.append(f"wiki: {type(e).__name__}")
    try:                                                    # inventario attuale (quando Baro e' presente)
        r = requests.get(API_URL, headers={"User-Agent": UA}, timeout=timeout)
        r.raise_for_status()
        cur = 0
        for it in (r.json().get("inventory") or []):
            n = it.get("item") or it.get("name") or ""
            if norm(n) in name_slug:
                names.setdefault(norm(n), n)
                cur += 1
        info["ora"] = cur
    except Exception as e:
        errors.append(f"worldstate: {type(e).__name__}")
    return names, info, errors


class VendorIndex:
    def __init__(self, name_slug: dict):
        self.name_slug = name_slug              # {nome normalizzato: slug} dal catalogo del market
        self.by_slug = {}                       # slug -> [vendor, ...]
        self.vendor_names = []
        self.rebuild()

    def rebuild(self):
        static = _read(USER_FILE) or _read(BUNDLED) or {}
        vendors = dict(static.get("vendors") or {})
        baro = (_read(BARO_FILE) or {}).get("names") or []
        if baro:
            vendors[BARO] = baro
        by_slug = {}
        for vname, entries in vendors.items():
            for e in entries:
                for cand in ([e] if isinstance(e, str) else e):     # [nome blueprint, nome base]: il primo che esiste
                    slug = self.name_slug.get(norm(cand))
                    if slug:
                        by_slug.setdefault(slug, set()).add(vname)
                        break
        self.by_slug = {s: sorted(v) for s, v in by_slug.items()}
        self.vendor_names = sorted({v for vs in self.by_slug.values() for v in vs})

    # ---------- Baro ----------
    def baro_age(self):
        """Secondi dall'ultimo aggiornamento di Baro (None se mai fatto)."""
        u = (_read(BARO_FILE) or {}).get("updated")
        return time.time() - u if u else None

    def baro_is_stale(self) -> bool:
        age = self.baro_age()
        return age is None or age > float(CFG["baro_refresh_days"]) * 86400

    def refresh_baro(self):
        """Aggiorna l'elenco di Baro da internet. Ritorna (ok, messaggio)."""
        names, info, errors = fetch_baro(self.name_slug)
        if not names:
            return False, "Baro: nessun dato ricevuto (" + ("; ".join(errors) or "elenco vuoto") + ")"
        old = (_read(BARO_FILE) or {}).get("names") or []
        merged = {norm(n): n for n in old}                     # lo storico non si perde mai
        merged.update(names)
        try:
            BARO_FILE.write_text(json.dumps({"updated": int(time.time()), "info": info,
                                             "names": sorted(merged.values())}, ensure_ascii=False),
                                 encoding="utf-8")
        except OSError as e:
            return False, f"Baro: impossibile salvare ({e})"
        self.rebuild()
        n = len(self.by_slug_for(BARO))
        msg = f"Baro aggiornato: {n} oggetti scambiabili"
        if errors:
            msg += " (parziale: " + "; ".join(errors) + ")"
        return True, msg

    def by_slug_for(self, vendor: str) -> list:
        return [s for s, vs in self.by_slug.items() if vendor in vs]
