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
    "key_goals": "<f6>",         # shows/hides the in-game Activities overlay
    # startup and automatic vendor detection
    "start_active": True,        # True = starts already active (no need to press F8)
    "auto_detect": True,         # detect a vendor being opened / the list changing by itself
    "watch_interval": 0.6,       # seconds between two screen checks
    "watch_interval_moving": 1.5,  # (slower) interval while the screen is constantly moving
    # performance
    "ocr_threads": 0,            # OCR threads (0 = automatic: about 1/4 of the cores, from 1 to 3)
    "ocr_priority": "below_normal",  # OCR process priority: normal | below_normal | idle
    "ocr_width": 1400,           # the screenshot is shrunk to this width before the OCR (0 = full size): faster
    "ocr_mask_panel": False,     # do not read the left info panel of the vendor (a bit faster)
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
    "player_name_auto": "",      # last name taken from AlecaFrame's lastUsername.txt (a name typed by hand is never overwritten)
    "player_name": "",           # shown in the player strip (the game files do not contain it)
    "assets_dir": "",             # optional folder of icons of your own (e.g. AlecaFrame's unpacked assets): shard pictures in Builds
    "assets_auto": True,          # look for the icons folder by itself (Overwolf's AlecaFrame folder; follows its version changes)
    "aya_manual": 0,              # Aya you hold, typed by hand: the game file does not always carry it
    "item_previews": True,        # picture of the item (from warframe.market) in the tooltip of the item tables
    "inv_exclude_installed": False,   # Inventory: leave out the mods/Arcanes that sit in a loadout
    "rankup_min_gain": 10,        # rank-up advice: minimum platinum gained per copy (max-rank price - current price)
    "inv_hide_zero_volume": False,   # Inventory: hide items with no trades in 24 h
    "market_split": [3, 2],          # Prices tab: height of the price list and of the recommendations
    "world_strip": True,             # show fissures (Steel Path Omnia), cycles, Baro and Prime Resurgence under the player strip
    "backdrop_style": "auto",        # background: auto (the theme's own pattern), one of theme.BACKDROPS, image, none
    "backdrop_image": "",            # your own picture for backdrop_style "image"
    "backdrop": True,                # themed background pattern behind the tabs (tables and inputs keep solid colours)
    "backdrop_strength": 45,         # how visible the pattern is (0-100)
    "goals_visible": False,          # Activities overlay: shown (remembered between sessions)
    "goals_geom": [],                # its position and size [x, y, width, height]
    "goals_collapsed": False,
    "goals_opacity": 45,             # background opacity (%): a faint band, like a quest tracker
    "goals_font": 12,                # text size (px)
    "goals_items": 8,                # how many recommended purchases it tracks
    "goals_per_vendor": True,        # at most one item per vendor (the best one)
    "goals_activities": True,        # what to do to earn the standing that is missing
    "goals_only_short": False,       # only the syndicates you still lack standing for
    "goals_quests": True,            # Nightwave weekly challenges and the 1999 Calendar (DE's world state)
    "goals_cal_rows": 4,             # how many Calendar challenges still to do are listed
    "goals_routine": True,           # Activities: Sortie, Archon Hunt, Deep / Temporal Archimedea, Descendia
    "goals_manual_done": {},         # Activities: routine entries ticked by hand {key: until when (epoch)}
    "goals_where": True,             # Activities: where to buy each item (the NPC and place) under it
    "goals_weekly": True,            # show the weekly vendor offers you track (Weekly tab)
    "goals_track_interact": True,    # right-click lines of the plan to track / untrack them
    "goals_untracked": [],           # activities left out of the plan: "<syndicate tag>|<n>" or "<tag>|*"
    "goals_click_only_cursor": True, # usable only while the mouse cursor is visible (in a mission clicks go to the game)
    "hide_operational_supply": True, # leave out the event syndicate (Plague Star…) while no event runs
    "window_on_top": False,          # keep the program's window above every other window (the labels on the game always are)
    "inv_min_volume": 0,             # Inventory: hide items traded fewer times than this in 24 h (0 = off)
    "hide_negative_ranks": False,    # player strip / Profile: hide syndicates with a negative rank
    "ducat_min_ratio": 10,       # advice: trade for ducats if ducats per platinum (adjusted for liquidity) >= this
    "advice_trend_weight": 50,   # advice: how much a price above its 30-day average is pulled towards it (0 = ignore the trend, 100 = use the average)
    "advice_liquid_volume": 10,  # advice: volume (24 h) from which an item counts as fully liquid
    "sell_min_price": 5,         # advice: do not suggest selling items cheaper than this (platinum)
    "rec_overlay": True,         # mark the top recommended items with stars on the overlay
    "rec_overlay_top": 10,       # how many of the vendor's best items get the stars (the first one: "Best here")
    "quantframe_url": "http://127.0.0.1:4808",  # Quantframe's local HTTP server (Quantframe > Settings > Advanced > HTTP Server); this computer only
    "riven_rpm": 12,              # Riven flip: warframe.market requests per MINUTE (it asks for 10-20 for auction searches; max 20)
    "riven_scan_weapons": 20,     # weapons scanned per click (the least recently scanned first)
    "riven_weapon_filter": "",    # only these weapons (names separated by commas); empty = all, in rotation
    "riven_sell_factor": 85,      # % of the median comparable asking price expected when you resell
    "riven_online_only": True,    # only sellers who are in game or online
    "riven_min_margin": 20,       # platinum: smallest expected profit shown
    "riven_min_score": 50,        # smallest stats score (0-100)
    "riven_max_price": 0,         # platinum: do not show rivens above this price (0 = no limit)
    "riven_max_age_days": 14,     # Riven flip: listings on sale for longer than this are not shown as deals (0 = no limit)
    "riven_auto_hours": 0,        # Riven flip: scan by itself every N hours while the program runs (0 = only by hand)
    "riven_min_sales": 0,         # listings gone in 7 days (estimated sales) from which a weapon is shown, once observed for a day
    "theme": "classic",           # colour theme (see theme.py): classic, or a faction: tenno, grineer, corpus, infested, orokin...
    "ui_font": "Segoe UI",        # font family of the windows
    "ui_font_size": 13,           # font size (pixels)
    "rec_best_per_vendor": False,  # Recommendations tab: only the best item of each vendor
    "skip_update_version": "",   # a version the user chose not to be reminded about
    "check_updates": True,       # look for a new version at start (nothing is installed without asking)
    "vendor_check": True,        # show prices only when the matched items belong to one vendor (a vendor screen)
    "vendor_header": True,       # also read the vendor name on screen (confirms the vendor)
    "vendor_header_top": 20,     # the vendor name is looked for only in this top part of the window (% of its height)
    "vendor_header_required": False,   # ... and require it (stricter; vendors with unknown headings then never match)
    "vendor_min_items": 3,       # ... at least this many
    "vendor_min_share": 0.6,     # ... and at least this share of everything matched
    "only_warframe": True,       # read only the Warframe window, and only while it is the active window
    # profile and world state
    "open_list_on_start": True,  # open the price-list window when the program starts
    "profile_reload_s": 10,      # re-read the imported AlecaFrame file (standing, inventory) when it changed (0 = never)
    "world_refresh_s": 60,       # world state refresh period while its tab is open (seconds)
    # inventory
    "inv_exclude_maxed": False,  # inventory: leave out mods/arcanes that are at max rank
    "sell_price_offset": 0,      # added to the market price when suggesting a sell price (e.g. -1)
    # recommendations
    "stale_refresh_h": 2,          # price list / recommendations: data older than this many hours is refreshed by itself (0 = off)
    "pmax_min_volume": 0.5,       # max-rank price shown/counted only if that rank trades at least this often a day (7-day average)
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
