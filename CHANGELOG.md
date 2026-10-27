# Changelog

From 0.2.1 on, every release lists its changes here (the release page on GitHub shows the section of its version).
Italian version: [CHANGELOG.it.md](CHANGELOG.it.md).

## 0.2.5
Resource use, same results:
- **`prices.json` about 18 times smaller**: it kept a per-item price history that nothing read (48 entries per item).
  It is dropped the first time the program saves; loading and saving are faster and use less memory.
- **Lighter screen check while the labels are shown**: only the rectangle around the item names is captured (instead
  of the whole game window) to tell whether the vendor is still open; the comparison is the same.
- **Less polling with the game in the background**: when Warframe is not the active window the program looks for it
  every 1.2 s instead of every 0.6 s (back to normal as soon as it is active).
- **Tables**: the price list and the inventory no longer rebuild every 30 seconds just to move the "x min ago" column
  on: only that column is updated. The Builds tab's picture check stops while the tab is hidden.
- **OCR**: with *Skip the vendor's left panel* on, the screenshot is shrunk before masking, so the full-size image is no longer
  copied (same text read, checked on a test screenshot).

## 0.2.4
- **Builds scale with the window**: the cards grow and shrink with the window (width and height), keeping the same
  proportions for mod and Arcane cards, the polarity and drain symbols and the text. The build planner does the same.
- **Hover a mod card** to see its picture (bigger) with its name and rank.
- **Lighter on resources**: the Recommendations tab no longer rebuilds its table every 2 seconds when nothing changed;
  the AlecaFrame file is no longer read and hashed every 10 seconds (only when its date or size changed); the screen
  check slows down to every 1.2 s after about 12 s with nothing happening (back to normal at the first change, and never
  while labels are shown); card pictures are cached when resizing.
- **Riven scan order**: weapons whose listings keep selling are rescanned sooner, weapons watched for 3+ days with no
  sale and few listings later, so the request budget goes where prices move.

## 0.2.3
- **Builds, in-game card style**: Aura and Exilus on top, the eight mods in two rows of four, the Arcanes on the right,
  each card with its slot polarity, the mod's polarity and drain (green = matching polarity, red = mismatch) and the rank
  as diamonds. Polarities set by Forma are read from the game file, the innate ones from the public game data.
- **Capacity and stat recap** next to the build: free / total capacity (rank and Reactor/Catalyst from the file, Aura
  capacity included) and Health, Shield, Armor, Energy, Sprint speed, Ability Duration, Efficiency, Range and Strength.
  Approximate: only mods are counted (no Arcanes, Archon Shards, Helminth, set bonuses or conditional effects).
- **Build names**: the names you gave your configurations in the game (e.g. "Zombie") are imported and shown as buttons
  to switch between the configurations of an item.
- **Build planner** (Builds > Build planner): pick a Warframe or weapon, click a card to choose the mod, its rank and the
  slot polarity (Forma), see capacity, drain and stats; save, load and delete plans, or start from a copy of one of your
  loadouts.
- **Icons folder found by itself**: the program looks for AlecaFrame's icons in Overwolf's folders and follows the new
  version folder Overwolf creates at every update (setting *Find the icons folder by itself*; a folder typed in Settings
  is used first when it exists). Polarity pictures come from that folder, with a drawn fallback.
- **Rivens in builds**: an installed Riven shows its name (e.g. "Toxi-argidra"), its stats and its polarity and drain
  (10 + rank) on the card; its bonuses count in the recap. Weapons get a *Mod bonuses* recap (sum of the percentage
  bonuses of mods and Riven; base weapon stats are not shown).
- **Aya**: the game file does not carry the Aya you hold (it reports 0), so the new setting *Aya (typed by hand)* supplies
  it; Aya is hidden while it is 0.

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
