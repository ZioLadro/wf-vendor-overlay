"""Optional icons from a folder of your own (Settings > assets folder): Archon Shard pictures in the Builds tab.

The folder is whatever you point to (for example the `assets` folder of an AlecaFrame installation, unpacked);
the program only reads from it and never copies or ships those files. Without the folder everything still works."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from config import CFG

_cache = {}


def _root():
    d = str(CFG.get("assets_dir") or "").strip()
    return Path(d) if d else None


def pixmap(rel: str, size: int = 0):
    """QPixmap of img/<rel> from the assets folder (None if not set or not found)."""
    root = _root()
    if not root:
        return None
    key = (str(root), rel, size)
    if key in _cache:
        return _cache[key]
    pm = None
    for base in (root / "img", root / "assets" / "img", root):
        f = base / rel
        if f.is_file():
            p = QPixmap(str(f))
            if not p.isNull():
                pm = p.scaledToHeight(size, Qt.TransformationMode.SmoothTransformation) if size else p
            break
    _cache[key] = pm
    return pm


def shard(color: str, tauforged: bool, size: int = 36):
    return pixmap(f"archonShards/{color.lower()}{'_mythic' if tauforged else ''}.webp", size)


ARCANE_PICTURE = {"C": "bronze", "U": "silver", "R": "gold", "L": "primed"}
WALLET_FILES = {"endo": "endo.png", "plat": "platinum.png", "ducats": "ducats.png", "aya": "aya.webp",
                "regal": "regalAya.webp", "credits": "credits.png"}


def arcane(name: str, height: int = 52):
    """The generic picture for an Arcane's rarity (bronze, silver, gold, primed) from the icons folder; None without it."""
    import loadouts
    rar = loadouts.data().get("arcrar", {}).get(name)
    return pixmap(f"arcanes/{ARCANE_PICTURE[rar]}.webp", height) if rar else None


def wallet(kind: str, height: int = 20):
    f = WALLET_FILES.get(kind)
    return pixmap(f, height) if f else None
