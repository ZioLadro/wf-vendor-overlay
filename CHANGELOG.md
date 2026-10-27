# Changelog

From 0.2.1 on, every release lists its changes here (the release page on GitHub shows the section of its version).
Italian version: [CHANGELOG.it.md](CHANGELOG.it.md).

## 0.2.1
- New program icon (a W and an O drawn as a scope reticle), used by the executable, the window, the taskbar and the tray.
  It is drawn by `build_icon.py`, so it can be regenerated.
- The taskbar now groups and shows the program under its own identity instead of Python's.
- This changelog; the release page now shows the notes of its version.

## 0.2.0
- **Inventory**: *Rank up…* advice (which mods are worth ranking up to sell them, by platinum per Endo, with Endo and
  Credits costs); *Exclude installed* leaves out the mods and Arcanes that sit in a loadout; buttons on two rows.
- Advice takes the price trend into account (7/30/90-day averages, *vs 30 d* column, *trend weight* setting).
- **Builds**: only your own loadouts, laid out like the game's screen with Archon Shards and Helminth; mod and Arcane
  pictures (warframe.market, then the Warframe wiki); optional icons folder for Archon Shard pictures. Overframe and
  YouTube creators removed.
- Trades left: warning when the AlecaFrame sync is older than the daily reset.
- Item pictures in the tooltips of the item tables.
- Fix: startup error `WinError 5` (the OCR process now starts as a plain program with a local authenticated connection).
- Fix: startup error `WinError 87` after a restart or update.

## 0.1.13 and earlier
See the [releases](https://github.com/ZioLadro/wf-vendor-overlay/releases) and the commit history.
