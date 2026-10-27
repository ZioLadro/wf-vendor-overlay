"""Finds AlecaFrame's data files by itself, so nothing has to be imported by hand.

AlecaFrame keeps its files in one folder: lastData.dat (your inventory and standing, rewritten when you enter or
leave a mission), lastUsername.txt (your in-game name), version.txt, deltas.dat, ... This module only LOCATES and
reads those files (plain file reads, nothing else): how AlecaFrame itself obtains the data from the game is its own
business and is not reproduced here.
"""
import os
from pathlib import Path

DATA_NAME = "lastData.dat"
USER_NAME = "lastUsername.txt"


def _roots():
    seen = []
    for var in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(var)
        if base:
            for sub in ("AlecaFrame", "alecaframe", "Alecaframe"):
                p = Path(base) / sub
                if p not in seen:
                    seen.append(p)
    return seen


def find_data_file(extra_dirs=()) -> str:
    """Path of the most recently written lastData.dat found in the usual AlecaFrame folders ('' if none)."""
    best, best_t = "", -1.0
    for root in [Path(d) for d in extra_dirs] + _roots():
        try:
            if not root.is_dir():
                continue
            cands = [root / DATA_NAME] + [d / DATA_NAME for d in root.iterdir() if d.is_dir()]
            for c in cands:
                if c.is_file() and c.stat().st_mtime > best_t:
                    best, best_t = str(c), c.stat().st_mtime
        except OSError:
            continue
    return best


def last_username(data_path: str) -> str:
    """The in-game name AlecaFrame saved next to lastData.dat ('' if not there)."""
    try:
        text = (Path(data_path).parent / USER_NAME).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""
    name = text.strip().splitlines()[0].strip() if text.strip() else ""
    return name[:40]


def sync_player_name(data_path: str) -> bool:
    """Puts AlecaFrame's last user name in the player strip, unless you typed a different name yourself.
    Returns True when the name changed."""
    from config import CFG, save_config
    name = last_username(data_path)
    if not name:
        return False
    cur, auto = CFG["player_name"], CFG.get("player_name_auto", "")
    if name == cur or (cur and cur != auto):
        if auto != name and name == cur:
            save_config({"player_name_auto": name})
        return False
    save_config({"player_name": name, "player_name_auto": name})
    return True
