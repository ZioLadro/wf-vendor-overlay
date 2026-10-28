"""Where the program's own files are: ROOT is the project folder (from source) or PyInstaller's bundle folder (exe);
DATA holds the bundled game data (data/*.json, made by tools/build_*.py), ASSETS the icon.
Your settings and collected data are elsewhere: config.APP_DIR (%LOCALAPPDATA%\\WFVendorOverlay)."""
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
