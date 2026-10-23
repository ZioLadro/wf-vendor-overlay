"""Percorsi e impostazioni. Le impostazioni si possono cambiare modificando
%LOCALAPPDATA%\\WFVendorOverlay\\config.json (creato al primo avvio), anche con l'.exe.
Chiavi mancanti = valori di default; chiavi sconosciute vengono ignorate."""
import json
import os
from pathlib import Path


def _app_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    d = Path(base) / "WFVendorOverlay"
    d.mkdir(parents=True, exist_ok=True)
    return d


APP_DIR = _app_dir()

DEFAULTS = {
    # tasti
    "key_menu": "<f7>",          # apre/chiude il listino prezzi
    "key_scan": "<f8>",          # scansiona subito (e riprende se in pausa)
    "key_clear": "<f9>",         # pausa: nasconde i prezzi e ferma il rilevamento automatico
    "key_quit": "<f10>",         # esci
    # avvio e rilevamento automatico dei vendor
    "start_active": True,        # True = parte gia' attivo (senza premere F8)
    "auto_detect": True,         # rileva da solo l'apertura di un vendor e quando la lista cambia
    "watch_interval": 0.6,       # secondi tra un controllo dello schermo e l'altro
    "watch_interval_moving": 1.5,  # intervallo (piu' lento) mentre lo schermo e' in continuo movimento
    # prestazioni
    "ocr_threads": 0,            # thread dell'OCR (0 = automatico: circa 1/4 dei core, da 1 a 3)
    "ocr_priority": "below_normal",  # priorita' del processo OCR: normal | below_normal | idle
    "menu_refresh_ms": 2000,     # ogni quanto il listino aperto si aggiorna
    "refresh_skip_age": 300,     # "Aggiorna visibili" salta i dati piu' recenti di N secondi
    "refresh_confirm_over": 150, # chiede conferma se si aggiornano piu' di N oggetti insieme
    "baro_refresh_days": 7,      # ogni quanti giorni riscaricare l'elenco di Baro (wiki)
    "publish_throttle": 0.15,    # secondi minimi tra due ridisegni dell'overlay durante gli aggiornamenti
    "auto_settle_polls": 2,      # controlli consecutivi "schermo fermo" prima di scansionare
    "auto_motion_frac": 0.03,    # frazione di schermo che deve cambiare per contare come movimento
    "auto_min_gap": 3.0,         # secondi minimi tra due scansioni automatiche
    "scroll_debounce": 0.45,     # secondi senza rotellina prima di riscansionare
    # dati
    "refresh_interval": 180,     # ogni quanti secondi aggiornare prezzi e volumi
    "open_max_age": 30,          # all'apertura di un vendor aggiorna i dati piu' vecchi di N secondi
    "show_cached_max_age": 3600, # mostra subito i dati salvati se piu' recenti di N secondi
    "show_volume": True,
    "match_threshold": 90,       # soglia somiglianza nomi (0-100)
    # aspetto del volume: rosso fino a volume_low, verde da volume_high in su
    "volume_low": 10,
    "volume_high": 50,
    "volume_offset_y": 2,        # pixel tra il nome dell'oggetto e l'etichetta del volume
}


def _load() -> dict:
    cfg = dict(DEFAULTS)
    f = APP_DIR / "config.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
        except Exception:
            pass
    else:
        try:
            f.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
        except OSError:
            pass
    return cfg


CFG = _load()
