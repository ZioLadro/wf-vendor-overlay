#!/usr/bin/env python3
"""Generates nodes.json: star-chart node id -> [node, planet, mission type, faction] in English, used to name the
Arbitration from its node id (the schedule only has ids).

Source: https://github.com/calamity-inc/warframe-public-export-plus (ExportRegions, ExportMissionTypes, ExportFactions,
dict.en). Usage: python tools/build_nodes.py [--out data/nodes.json] [--cache download_folder]"""
import argparse
import json
import re
import tempfile
from pathlib import Path

from build_vendors import fetch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "nodes.json"))
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "wf_export_cache"))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    lang = fetch("dict.en", cache)
    nm = lambda key: re.sub(r"<[^>]+>\s*", "", lang.get(key, "") or "").strip()
    mtypes = {k: nm(v.get("name", "")).title() for k, v in fetch("ExportMissionTypes", cache).items()}
    factions = {k: nm(v.get("name", "")).title() for k, v in fetch("ExportFactions", cache).items()}
    out = {}
    for node, r in fetch("ExportRegions", cache).items():
        name = nm(r.get("name", ""))
        if name:
            out[node] = [name, nm(r.get("systemName", "")), mtypes.get(r.get("missionType"), "") or nm(r.get("missionName", "")),
                         factions.get(r.get("faction"), "")]
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} nodes -> {a.out}")


if __name__ == "__main__":
    main()
