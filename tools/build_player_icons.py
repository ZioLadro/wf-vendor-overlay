#!/usr/bin/env python3
"""Generates data/player_icons.json: the picture of every profile glyph (avatar) and the Mastery Rank emblems, as game
icon paths. The program downloads the pictures it needs from browse.wf (which hosts the game's icons by path) and keeps
them in its data folder (app/ui/playericons.py).

Source: https://github.com/calamity-inc/warframe-public-export-plus (ExportFlavour: glyphs; ExportTextIcons: ranks).
Usage:  python tools/build_player_icons.py [--out data/player_icons.json] [--cache download_folder]"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_vendors import fetch      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "player_icons.json"))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    avatars = {p: e["icon"] for p, e in fetch("ExportFlavour", cache).items()
               if isinstance(e, dict) and "/AvatarImages/" in p and e.get("icon")}
    ranks = {}
    for k, v in fetch("ExportTextIcons", cache).items():
        m = re.fullmatch(r"RANK_(\d+)", k)
        if m and isinstance(v, dict) and v.get("DIT_AUTO"):
            ranks[int(m.group(1))] = v["DIT_AUTO"]
    Path(a.out).write_text(json.dumps({"avatars": avatars, "mastery": {str(k): ranks[k] for k in sorted(ranks)}},
                                      separators=(",", ":")), encoding="utf-8")
    print(f"{len(avatars)} glyphs, {len(ranks)} mastery ranks -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
