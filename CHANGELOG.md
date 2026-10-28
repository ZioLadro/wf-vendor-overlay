# Changelog

From 0.2.1 on, every release lists its changes here (the release page on GitHub shows the section of its version).
Italian version: [CHANGELOG.it.md](CHANGELOG.it.md).

## 0.3.1
- **Overlay stars**: *★ Best here ★* is now the best purchase among **all** the items of the vendor you are looking at
  (not only the rows on screen; the status line names it if it is scrolled away), and *★ Recommended ★* marks the
  items among the best purchases **across all vendors** (the Recommendations ranking).
- **Recommendations reviewed**: the score is now *~plat per day*: price × the copies one day of standing buys (daily cap
  16,000 + 500 × Mastery Rank), but no more than the market absorbs (≈ ¼ of the 24 h volume); a price above its 30-day
  average is pulled towards it, as in the inventory advice; items needing a higher syndicate rank than yours count half
  (⚠). The standing plan uses the same ranking.
- **Inventory advice**: *Sell* and *Rank up* no longer discount rarely traded items twice (the copies you can sell
  already follow the volume).
- **Hide Operational Supply** (setting, on by default): the event syndicate (Plague Star and other events) is left out of
  the price list, recommendations, overlay stars, standing plan and player strip while no event runs.
- **Standing plan restyled like a quest tracker**: no heavy panel (a faint band fading to the right), gold syndicate
  titles with **?** (something to buy now) or **!** (standing still to earn), objectives in white, ready ones in green,
  how to earn the standing in grey, every text outlined to read over the game.
- **Weekly tab: limited vendor offers** (Teshin's Steel Path offers, Ironwake, Nightcap, Archimedean, Acrithis, event
  vendors…; from the game data, `weekly.json` made by `build_weekly.py`): cost, limit, how many you bought this period and
  when it resets, with a filter by vendor, weekly only, tracked only. Purchases come from lastData.dat; since the file does
  not say which offer was bought, the program compares your inventory with the previous sync (what the last mission or
  visit gave you) and assigns it when only one offer fits; otherwise it asks you, with the offers whose item went up
  first (★) and the last place you were in as a hint. Answers last until the limit resets.
- **Standing plan: weekly section** with the offers you track (bought/limit, reset countdown) and the purchases to
  identify (click to choose). **Track / untrack** from the overlay: right-click an activity, a syndicate title or a
  weekly offer; settings *Standing plan: track/untrack with right-click*, *weekly offers*, and *tracked activities*
  (a list to tick, syndicate by syndicate).
- **Standing plan clickable only with the cursor**: in a mission Warframe hides the mouse cursor, and the plan then lets
  every click through to the game (its buttons disappear); it can be used again as soon as the cursor shows (menus,
  consoles, vendors). Setting *Standing plan: clickable only with the cursor* (on by default), also in ⚙.

## 0.3.0
- **Standing plan overlay** (in game, F6 shows/hides it; setting *Standing plan key*): a small always-on-top window
  listing the purchases the Recommendations suggest, grouped by syndicate, with your standing, rank and what is left of
  today's cap; for each item how many you can buy now or how much standing is missing (and the rank needed); for the
  syndicates you lack standing for, what earns it (bounties, sigil missions, Medallions, tokens…).
  - **Interactive and movable**: drag the title bar, resize from the corner, fold it (double-click the title), close it;
    ⚙ sets opacity, text size, how many purchases, one per vendor, show the activities, only the syndicates you lack
    standing for. Position, size and options are remembered. Right-click an item to hide it or open it on warframe.market.
  - **Updated with the game file**: it is read again every time AlecaFrame rewrites lastData.dat (standing and inventory).
  - **Purchases are verified before an item leaves the list**: the program remembers how many copies you owned when the
    item entered the list and removes it only when the game file shows a new copy (*Bought lately* keeps the last ones).
    Ticking an item only marks it "bought? waiting for the game file". *Show again hidden and bought items* resets it.
  - Its area is never read by the OCR, and showing it does not take the focus from the game.
  - **It switches off on vendor screens**: as soon as the OCR recognises a vendor the plan turns itself off, and stays
    off until you turn it on again with the hotkey (F6).
  - **Standing you can still earn** is counted: each syndicate shows what is earnable today out of the daily cap
    (16,000 + 500 × Mastery Rank; the whole cap again after the 00:00 UTC reset), and each item says whether the missing
    standing is reachable today or how many days it takes at the daily cap. Items and syndicates are ordered by what you
    can buy soonest.

## 0.2.9
- **Spliced Rivens** (a stat fused from two others with a Riven Splicer) are recognised and shown "frozen" in Builds:
  icy card, ❄ *Spliced* label, the spliced stat highlighted. The game data has no figures for spliced stats yet, so their
  value shows as "?"; the other stats are computed as usual. (0.2.8 wrongly called them old stats.)
- **Riven values use the single disposition** of Hotfix 44.1.3 (every Riven now uses the old 1.2 disposition), in Builds,
  Quantframe and the Riven flip score.
- **Exalted weapons in Builds** (Exalted Blade, Iron Staff, Artemis Bow, Balefire Charger, Regulators, Noctua…): their
  own group in *By item*, the Warframe they belong to, their mods, Arcanes and Rivens; the *Exalted* row of *Game
  loadouts* now opens them. Capacity is not shown for them (their slot polarities are not in the public data).
- **Arbitration with its tier** in the world strip: the current Arbitration (mission, node, time left) with the tier
  from **arbi.guide** (Arbitration Goons: S 12+ Vitus Essence/min … D, Special, F; * = Saryn off-meta viable), through the
  guide's documented API (`tierlist.json`), cached 15 minutes, last good copy kept, link back to the guide on the tier.
  Which node is the Arbitration comes from browse.wf's hourly schedule (`arbys.txt`, read once a day and kept), since the
  world state often has none; node names from the game data (`nodes.json`, made by `build_nodes.py`).
- Fix: after updating, Builds kept showing the loadouts saved by the previous version (no spliced Rivens, no exalted
  weapons) until the game file changed; the saved copy is now read again after every update.

## 0.2.8
- **World strip** under the player strip: the Steel Path Omnia fissures open now, the Earth / Cetus / Orb Vallis cycles,
  when Baro Ki'Teer comes back (or leaves) and when the Prime Resurgence offer changes, with live countdowns (from
  api.warframestat.us, read every 5 minutes). Setting *World strip under the player strip*.
- **Console tab**: what the program does in the background (pictures and logos from the wiki, price updates, Riven
  scans, files read, world state, overlay messages) and every error, with the jobs in progress on top; filter by source
  or errors only, save to a file.
- **No more flashing while pictures download**: they are put where they are missing instead of rebuilding the lists and
  cards every few seconds.
- **Builds: Orokin Reactor / Catalyst** shown under the title: installed, not installed, not stated by the file, or
  deduced (older items do not say it, but one of their loadouts only fits with it).
- **Rivens with an old stat** (Gas, Ammo Efficiency: rolls the game data no longer has) now show their other stats, with
  "?" for the old one, instead of no stats at all; a stat their weapon type no longer rolls (e.g. Zoom on a shotgun)
  uses another type's figures.
- **Backgrounds**: seven original patterns (Orokin lattice, Tenno curls, Grineer plates, Corpus circuits, Infested cells,
  waves, Entrati rings), each theme with its own; or pick any of them, **your own picture** (cropped to the window and
  blended into the theme so text stays readable), or none. Settings *Background* and *Your background picture*.
- Riven polarity Unairu was reported to Quantframe as Zenurik.

## 0.2.7
- **Builds pictures from the Warframe wiki only** (mod cards and items), through the wiki's MediaWiki API (the
  article's main picture, else `File:<name>.png`). At start the program asks in the background for the pictures still
  missing for the mods of your loadouts and for the items, one at a time; they are kept in the data folder.
- **Item pictures** (Warframes, weapons, companions) next to the loadout's title, on the rows of *Game loadouts* and in
  the *By item* list.
- **By item list grouped by kind**: Warframes, primaries, secondaries, melee, Archwing, arch-guns, Necramechs, companions,
  each under its own header.
- **Themed background**: an original pattern in the theme's colours (thin gilded lattice, diamonds and arcs) behind the
  tabs; tables, lists, inputs and buttons keep solid colours so the text stays easy to read. Settings *Themed background*
  and *Background visibility*.
- **Builds and planner review**, fixes:
  - mod capacity is the item's rank (30, or 40 for Kuva, Tenet and Coda weapons and Necramechs), doubled by a Reactor /
    Catalyst; it was 30 too high;
  - a mod used as an unranked copy counted as max rank;
  - the "universal" slot polarity of the game file (Aura Forma) matches every mod: checked on a real build, the total
    capacity now equals the game's (60 + Aura 7 × 2 = 74);
  - innate polarities are placed on the slots where they save the most drain (the game file does not say where they are);
  - older items whose file entry does not say whether they have a Reactor / Catalyst are counted with one when the build
    only fits that way;
  - a Riven copied into the planner was lost when its slot was opened and confirmed;
  - typing an item name in the planner (any case, part of the name) works; half-typed names are ignored;
  - the game file is read again when it changed since the saved copy (and when it changes while the tab is open);
  - the configuration buttons no longer pile up an invisible object at every redraw; the loadout count no longer counts
    the group headers.

## 0.2.6
- **Prices and recommendations in one tab**: the price list on top, the recommendations below, with a divider you can
  drag (its position is remembered).
- **Window no longer always on top**: it comes in front when you open it (hotkey or tray) and then behaves like a normal
  window, so the game or other programs can go over it. Setting *Window always on top* brings back the old behaviour
  (restart to apply). The labels on the game stay on top as before.
- **Inventory: minimum volume** (*Min vol.*): hides the items traded fewer times than that in the last 24 hours (items
  without volume data yet stay). Remembered.
- **Syndicate logos from the Warframe wiki** in the top strip: each syndicate's picture is asked for once through the
  wiki's MediaWiki API (the article's main picture, else a file called Sigil / Icon / Logo), saved in the data folder
  (`icons`) and reused; until then the drawn badge stays. A logo that is not found is asked again after a day. Turned off
  together with *Item pictures in tooltips*.

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
