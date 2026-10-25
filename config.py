"""Paths and settings. Settings can be changed from the Settings tab of the price list, or by editing
%LOCALAPPDATA%\\WFVendorOverlay\\config.json (created on first run), also with the .exe.
Missing keys = default values; unknown keys are ignored."""
import json
import os
from pathlib import Path


def _app_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    d = Path(base) / "WFVendorOverlay"
    d.mkdir(parents=True, exist_ok=True)
    return d


APP_DIR = _app_dir()
CONFIG_FILE = APP_DIR / "config.json"

DEFAULTS = {
    # interface
    "language": "en",            # "en" | "it" (restart required)
    # keys (pynput format, e.g. "<f7>" or "<ctrl>+<f7>")
    "key_menu": "<f7>",          # opens/closes the price list
    "key_scan": "<f8>",          # scan now (and resume if paused)
    "key_clear": "<f9>",         # pause: hides prices and stops automatic detection
    "key_quit": "<f10>",         # quit
    # startup and automatic vendor detection
    "start_active": True,        # True = starts already active (no need to press F8)
    "auto_detect": True,         # detect a vendor being opened / the list changing by itself
    "watch_interval": 0.6,       # seconds between two screen checks
    "watch_interval_moving": 1.5,  # (slower) interval while the screen is constantly moving
    # performance
    "ocr_threads": 0,            # OCR threads (0 = automatic: about 1/4 of the cores, from 1 to 3)
    "ocr_priority": "below_normal",  # OCR process priority: normal | below_normal | idle
    "menu_refresh_ms": 2000,     # how often the open price list redraws
    "refresh_skip_age": 300,     # "Update shown" skips data newer than N seconds
    "refresh_confirm_over": 150, # ask for confirmation when updating more than N items at once
    "baro_refresh_days": 7,      # how often to re-download Baro's list (wiki), in days
    "publish_throttle": 0.15,    # minimum seconds between two overlay redraws while updating
    "auto_settle_polls": 2,      # consecutive "screen is still" checks before scanning
    "auto_motion_frac": 0.03,    # fraction of the screen that must change to count as movement
    "auto_min_gap": 3.0,         # minimum seconds between two automatic scans
    "scroll_debounce": 0.45,     # seconds without mouse wheel before rescanning
    # data
    "refresh_interval": 180,     # seconds between price/volume refreshes
    "open_max_age": 30,          # when a vendor opens, refresh data older than N seconds
    "show_cached_max_age": 3600, # show saved data right away if newer than N seconds
    "show_volume": True,
    "match_threshold": 90,       # name similarity threshold (0-100)
    # volume look: red up to volume_low, green from volume_high up
    "volume_low": 10,
    "volume_high": 50,
    "volume_offset_y": 2,        # pixels between the item name and the volume label
    "hide_zero_volume": False,   # hide items with zero trades in the last 24 h (price list)
    # profile and world state
    "open_list_on_start": True,  # open the price-list window when the program starts
    "player_name": "",           # in-game name, to fetch your public profile (standing per syndicate)
    "world_refresh_s": 60,       # world state refresh period while its tab is open (seconds)
    # inventory
    "inv_exclude_maxed": False,  # inventory: leave out mods/arcanes that are at max rank
    "sell_price_offset": 0,      # added to the market price when suggesting a sell price (e.g. -1)
    # recommendations
    "rec_min_volume": 10,        # ignore items traded less than this in 24 h
    "rec_min_price": 5,          # ignore items cheaper than this (platinum)
    "rec_top": 200,              # maximum rows in the recommendations table
}


def _load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k, v in data.items():
                d = DEFAULTS.get(k)
                if d is None:
                    continue                                   # unknown key
                if type(v) is type(d) or (type(d) is float and type(v) is int):
                    cfg[k] = v                                 # wrong types (e.g. "yes" for a number) are ignored
        except Exception:
            pass
    else:
        try:
            CONFIG_FILE.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
        except OSError:
            pass
    return cfg


CFG = _load()


def save_config(updates: dict) -> bool:
    """Applies `updates` to CFG (in place, so every module sees them) and writes config.json."""
    for k, v in updates.items():
        if k in DEFAULTS:
            CFG[k] = v
    try:
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(CFG, indent=2), encoding="utf-8")
        os.replace(tmp, CONFIG_FILE)
        return True
    except OSError:
        return False
