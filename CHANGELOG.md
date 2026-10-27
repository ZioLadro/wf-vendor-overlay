# Changelog

From 0.2.1 on, every release lists its changes here (the release page on GitHub shows the section of its version).
Italian version: [CHANGELOG.it.md](CHANGELOG.it.md).

## 0.2.2
- **Builds**: new *Game loadouts* view that follows the in-game loadout screen: your named loadouts with the Warframe,
  primary, secondary, melee and Exalted weapon, the companion, the Archwing and the Necramech (with their ranks, the names
  you gave them and the mod configuration each loadout uses). Click a row to see its mods, Arcanes, Archon Shards and
  Helminth. The previous list is still there as *By item*. Read from the AlecaFrame file; focus school and K-Drive are not shown.
- **Top strip**: Endo, platinum, ducats and Aya you hold (compact: 3k, 30k, 1.2M; exact value in the tooltip), with the icons
  of the icons folder when it is set.
- Arcanes on the Builds cards use the generic rarity picture (bronze, silver, gold, primed) of the icons folder: no download
  from the market or the wiki. With the icons folder set, Archon Shards show only the picture and the effect (not the colour name).
- New program icon: the silhouette of a man with dreadlocks, half cybernetic, holding a sniper rifle, with a small W and O.

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
