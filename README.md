# WF Vendor Overlay

🇬🇧 English · [🇮🇹 Italiano](README.it.md)

A Windows companion for Warframe. Its core: when you open a vendor, it shows next to each item the **platinum price**
(right of the name) and the **24-hour trade volume** (below the name; red = rarely traded, green = heavily traded),
from warframe.market, by reading the screen with OCR. Around it:

- **Activities** (in game, F6): what to buy with your standing and how to earn it, the weekly vendor offers you follow,
  this week's Nightwave challenges and the 1999 Calendar, ticked off as you complete them.
- **Price list window** (F7): every tradable item that costs standing, recommendations, your inventory with sell advice
  and sell orders, Riven flipping, your in-game builds, weekly vendor limits, standing, world state.

The program never reads the game's memory, network traffic or files. What it knows about your account (standing,
inventory, loadouts, purchases, challenges) comes from **AlecaFrame's** `lastData.dat`, read when AlecaFrame updates it;
without AlecaFrame the price overlay and the market features still work.

**Contents:** [Getting started](#getting-started) · [Price overlay](#price-overlay-in-game) ·
[Activities](#activities-in-game-f6) · [Price list window](#price-list-window-f7) · [Data sources](#data-sources) ·
[Updates](#updates-current-version-037) · [Files and settings](#files-and-settings) · [Performance](#performance) ·
[For developers](#for-developers) · [Notes and limits](#notes-and-limits)

## Getting started
1. Download `WFVendorOverlay-windows.zip` from the [latest release](https://github.com/ZioLadro/wf-vendor-overlay/releases/latest),
   unzip it anywhere and run `WFVendorOverlay.exe` (the exe is not code-signed, so Windows SmartScreen may warn).
2. Run Warframe in **Borderless** windowed mode. If Warframe runs as administrator, run the overlay as administrator too.
3. Optional: keep **AlecaFrame** running; its file is found by itself (`%LOCALAPPDATA%\AlecaFrame`).
4. Language: English by default; Settings → General → Language (English / Italiano), then restart.

| Key | Action |
|---|---|
| **F6** | show/hide **Activities** |
| **F7** | open/close the **price list** window |
| **F8** | scan now (and resume if paused) |
| **F9** | pause |
| **F10** | quit |

The same actions are in the tray icon menu (click on the icon = price list). Keys can be changed in Settings.

## Price overlay (in game)
Price label: `12p` = platinum · `–` = nobody selling online · `n/a` = error / data unavailable.
For **mods and arcanes** it shows two prices: `12p · max 45p` = rank 0 price (what the vendor sells) and **max-rank**
price. The volume is the total of the trades of all ranks.

- **Starts active**: open a vendor and, when the screen settles, the overlay scans by itself.
- **Saved data** in `prices.json`: the last known values show up at once, then they are refreshed in the background.
  When a vendor opens, data older than 30 s is refreshed; prices of the vendors shown refresh every 180 s.
- **Scrolling** with the mouse wheel: the labels vanish at once and come back ~0.5 s after scrolling stops. Other list
  changes (dragged scrollbar, keyboard) are detected by comparing the pixels under the names.
- **Leaving the vendor**: the labels disappear as soon as you close the vendor or change page.
- The OCR reads **only the Warframe window**, and only while it is the active window (setting *Read only the Warframe
  window*; turn it off if the game is not detected, e.g. cloud gaming). Labels are hidden in other windows.
- **Stars**: *★ Best here ★* marks the best purchase among **all the items of the vendor you are looking at** (even the
  ones scrolled out of view: the status line names it, *Best buy at …*); *★ Recommended ★* marks the items among the
  best purchases **across all vendors** (the Recommendations ranking). Settings *Stars on recommended items* /
  *Recommended items marked*.

**Recognising the vendor screen.** After reading the names, the program checks which vendor's stock they belong to
(from `vendors.json` and Baro's list). Labels appear only if at least 3 matched items (setting *Items needed*) and 60 %
of everything matched belong to the **same vendor**; names outside that vendor's stock are dropped. This keeps labels off
inventory, chat or codex pages that merely show some item names. The program also **reads the vendor's name** in the top
20 % of the game window (setting *Vendor name zone*; e.g. *Cephalon Simaris*, *Red Veil*): when it is there and at least
one item is that vendor's, labels are shown even with few items. *Require the vendor name* makes it mandatory (stricter,
but vendors whose heading is not their name would never match). F8 writes everything it read to `last_scan.txt` in the
data folder, to see why a vendor was or was not recognised. Turn it off with *Recognise the vendor screen*.

## Activities (in game, F6)
A small always-on-top window over the game, styled like a quest tracker, movable (drag the title) and resizable
(corner). ⚙ sets opacity, text size and what it lists. It shows, per syndicate:

- the **purchases the Recommendations suggest**, the standing each still needs, the days it takes at your daily cap
  (16,000 + 500 × Mastery Rank), **where to buy it** (⌖ the NPC and place: *Hok, Cetus* for Zaw parts, *Rude Zuud,
  Fortuna* for kitgun parts, *any Relay* for the faction syndicates…) and the **activities that earn that standing**. An item is removed only when the game
  file shows you bought it;
- the **weekly vendor offers you follow** (bought / limit, reset countdown; see the Weekly tab);
- **Nightwave**: today's daily (☼) and this week's challenges (elite ones ★), with their standing, goal and progress
  (e.g. 14/15); completed ones are ticked ✔ (from the challenge counters in your game file, *ChallengeProgress*);
- **1999 Calendar**: the current season's challenges, the one in progress and how many are done (done = days up to the
  last completed day in your game file);
- **Daily and weekly**: the trades you have left today, the Sortie and the Archon Hunt (missions done of 3, from the game file's completed missions),
  Elite Deep / Temporal Archimedea (started, score), Netracells (of 5 a week) and Descendia (floors reached of 21, normal and Steel Path). What
  the file cannot tell (whether an Archimedea is finished) is marked (?): right-click to tick it by hand until the reset.

**Right-click** an item to hide it or open it on warframe.market, a syndicate's title or an activity to stop following
it (*Track again every activity* in ⚙). With *Activities: clickable only
with the cursor* (on by default) the window lets clicks through while Warframe hides the cursor (in missions), so it never gets in
the way. When a vendor screen is recognised, Activities switches off (the price labels take over) until you press F6.
Settings: *Activities key*, *Activities: Nightwave and 1999 Calendar*, *Activities: where to buy*, *Hide Operational Supply* (the event syndicate
is left out while no event runs).

## Price list window (F7)
**Opens by itself at start** (setting *Open the price list at start*). It is a normal window: it comes in front when you
open it and does not stay above the game (setting *Window always on top* to keep it there). While it is on top of the
game its area is blanked before the OCR, so it never reads its own names.

On top of every tab:
- **Player strip**: your profile glyph and Mastery Rank emblem (pictures from browse.wf, downloaded once), name (from
  AlecaFrame's `lastUsername.txt`, or click to type it), mastery rank, trades left
  (⚠ when the last sync is before the daily reset), wallet (Endo, platinum, ducats, Aya; compact, exact value in the
  tooltip) and a badge per syndicate with rank and standing (hover for the standing left today). Syndicate logos are
  downloaded from the wiki once; without them the badges are drawn in the syndicate colours.
- **World strip**: Steel Path Omnia fissures, Earth / Cetus / Orb Vallis cycles, Baro Ki'Teer, Prime Resurgence and the
  current **Arbitration** with its tier from [arbi.guide](https://arbi.guide), all with live countdowns.

### Prices and recommendations
The first tab: price list on top, recommendations below (drag the divider; remembered).

**Price list.** All the **tradable items that cost standing** (from `vendors.json`: vendors and syndicates) plus
everything sold by **Baro Ki'Teer**, listed from the start even without data (price `–`, updated `never`). Columns: name,
vendors, **standing cost**, type (Mod / Arcane / Other), price, max-rank price, 24 h volume (coloured like the overlay),
last update. Click headers to sort; search box and vendor/type filters.

- Standing cost is the base cost from the game data (no rank discounts); `min – max` when several vendors sell it, the
  tooltip shows vendor, cost and required rank.
- **Hover** a name: how many you can buy with your standing, per syndicate, and whether your rank is enough.
- **Hide zero volume** hides items with no trades in 24 h (items without data stay).
- **Right-click** a name (here and in Recommendations): open it on warframe.market or on the wiki, or copy the name.
- **Update shown** refreshes every visible row (skipping data newer than `refresh_skip_age`); **Update selected**
  refreshes the selected rows; **Stop** interrupts. The limit is 3 requests/s (2 per item): about 2 minutes per 100
  items, ~20 for the whole catalog; above `refresh_confirm_over` items it asks first.
- **Update Baro list**: Baro is not in the game data; his list is read from the wiki (and his current inventory) and
  reloads by itself every `baro_refresh_days` days.

**Recommendations.** What is worth buying with standing, for every (item, vendor) pair with a standing cost:

```
plat per 1000 standing = price / standing cost × 1000
copies per day         = min(daily standing cap / standing cost, max(1, volume × 0.25))
~plat per day (score)  = expected price × copies per day   (daily cap = 16,000 + 500 × Mastery Rank)
```
**Expected price** (`app/trade/signals.py`: classic, open trading techniques scaled to warframe.market's daily data):
the current price, pulled towards the 30-day average when above it; × a **trend** factor from two exponential moving
averages (EMA 7 / EMA 30 days: falling prices lower it, up to −15 %); × the item's **backtest calibration** (the same
estimate replayed on the item's last weeks with only the data known each day, against the price it really traded at in
the 7 days after: an item whose estimates were 10 % too optimistic gets 10 % less); never above the lowest seller and never
below the best **buy order** online (bid). The *Trend* column shows ↑/↓ with *sell now* (falling, or a **spike**: today
far above its 20-day Bollinger band, z ≥ 2) or *wait* (rising); its tooltip lists EMAs, z, backtest and bid/ask.
As many copies as one day of standing buys, but no more than the market absorbs (about a quarter of the 24 h volume).
A price above its 30-day average is pulled towards it, and an item that needs a higher syndicate rank than yours counts
half (⚠). Items below the **minimum volume** or **minimum price** (editable in the tab) are left out; prices are rank 0.
*Best per vendor* shows one row per vendor. Items with no market data yet cannot be rated: **Fetch missing data**
downloads them (pick one vendor first to keep it quick).

### Inventory
Your items with their market prices, sell advice and one-click sell orders (inspired by AlecaFrame's Inventory tab).

- **Source**: AlecaFrame's `lastData.dat`, found and re-read by itself (decrypted locally). You can also **Import file…**
  (replaces the inventory), **Paste list…**, or **Add item…** / **Edit** by hand. Accepted besides `lastData.dat`: a raw
  Warframe-style inventory JSON (`MiscItems`, `RawUpgrades`… with `ItemType` paths), any JSON pairing names with
  quantities (`{"Serration": 2}`), and CSV/TXT lines such as `Serration, 2, 10`, `3x Mirage Prime Set` or
  `Ash Prime Blueprint x2`. Names are matched to the market catalog (small typos tolerated); unmatched ones are listed.
- **Categories** (Sets, Warframe parts, Weapon parts, Mods, Arcanes, Relics, Other) and **filters** like AlecaFrame's:
  minimum platinum, more than one owned, prime / normal, vaulted, listed from here, *Exclude max-rank mods/arcanes*,
  *Exclude installed* (mods and Arcanes in one of your loadouts: never suggested for sale), *Min vol.*
- **Value** = copies × rank 0 price + max-rank copies × max-rank price. **Update prices** refreshes the shown items.
  The program keeps the 7/30/90-day average price too (*vs 30 d* column); a spike above the 30-day average is pulled
  towards it by *Advice: trend weight* (default 50 %).
- **Advice: ducats** lists prime parts by ducats per platinum given up (`ducats / max(price × liquidity, 0.5)`, with
  `liquidity = min(1, volume / liquid volume)`): *Ducats* at or above the minimum ratio (default 10), else *Sell*.
  **Advice: sell** ranks the rest by `expected price × copies you can expect to sell (≈ ¼ of the daily volume)`, with a
  *Signal* column (*sell now* / *wait*, as in the recommendations). Both can select
  the rows, ready for *Sell*.
- **Rank up…**: which mods are worth ranking to max to sell them: platinum gained per copy (max-rank price − current
  price) per 1000 Endo, with the Endo and Credits needed (`base × (2^max − 2^rank)`, per the
  [wiki](https://wiki.warframe.com/w/Fusion)). Type the Endo you have and the best rows that fit are selected.
- **Sell…** places a **sell order** on warframe.market for each selected item. Sign in first (email and password, sent
  only to warframe.market; **only the session token is stored**, *Sign out* deletes it). A window shows quantity, rank,
  price (market price + `sell_price_offset`) and **the exact request**; nothing is sent until you press *Place order*.
  Caveat: this uses the v1 REST API as documented by community libraries; check your first order on the site. Accounts
  that sign in with Discord/Google may not work.
- **Item pictures** appear when hovering a name (warframe.market images, downloaded once; switch off in Settings).

**Quantframe.** Items can be handed to [Quantframe](https://github.com/Kenya-DK/quantframe-react) through its local HTTP
server (Quantframe: Settings > Advanced > HTTP Server; here: *Quantframe address*, default `127.0.0.1:4808`, only
addresses on this computer):
- **Inventory > Send to Quantframe…**: selected rows (all shown if none) to its **stock**, ranked mods per rank;
- **Builds > Missing → Quantframe**: the mods you lack for a build to its **wish list**;
- **Inventory > Rivens → Quantframe…**: your **revealed** rivens (weapon, name, rank, re-rolls, polarity, stats
  recomputed from `rivens.json`; values may differ by a decimal from the game) to its riven stock.

A check window comes first; already-sent items start unchecked because quantities add up. No purchase price is sent.
Mind that Quantframe's Live Scraper may list stock items for sale or place buy orders, depending on its own settings.

### Riven flip
**Scan the market** reads the riven listings of the next weapons on warframe.market (least recently scanned first;
*Weapons per scan* and *Only these weapons* in Settings) and lists rivens priced **below what comparable ones are
worth**, best profit first:

- **Price**: the direct-buy price against a *fair price* = median of comparable listings of the same weapon (stats score
  within ±15, at least 3) × *Expected resale* (default 85 %). warframe.market returns at most the 100 cheapest listings
  per weapon, which keeps the fair price on the cautious side for popular weapons.
- **Sales**: an **estimate** (warframe.market does not publish riven sales): listings that disappear between scans
  over the last 7 days. It needs repeated scans; "–" until a weapon has been watched for a day.
- **Stats**: a 0–100 score from how useful each stat is and how well it rolled. Custom weights in `riven_weights.json`
  in the data folder, e.g. `{"WeaponFireRateMod": 0.9}` (0 to 1; keys of `rivens.json`).

**The program's own database** (`riven_market.json`) grows with every scan and refines the search:
- **price history**: per weapon and per day, the median asking price, the cheapest one and the number of listings
  (180 days). The *Trend* column shows the 7-day change (30-day when there is no week yet); when a weapon's prices
  are falling (⚠) its fair price is lowered by the fall (up to 30 %), so a riven that looks cheap only because its
  weapon is crashing is not shown as a deal;
- **likely sold**: the listings that disappeared within 5 days of being listed (last 30 days), with price and stats.
  When there are at least 3 comparable ones, the fair price leans on what those were listed at (60 %) rather than only
  on today's asking prices (✔ next to the fair price; the tooltip shows both).

**Scheduled scans**: *Scan by itself every (hours)* (Settings > Riven flip; 0 = off) scans the next weapons every N
hours while the program runs, with the same request limit; the tab shows when the next one is due. More scans make the
history and the sales estimate better.

**Listing age**: the scan reads every direct-buy listing, of online and offline sellers (all of them count for the fair
price and the sales estimate); the table shows deals from sellers in game or online only (setting). The *On sale for*
column shows how long a listing has been up (its creation date on warframe.market); listings older than *Hide listings
older than (days)* (default 14) are not shown as deals, and those older than twice that are left out of the fair price
(a price that has not sold for weeks says what does NOT sell).

Riven requests have their own limiter (*Riven requests per minute*, default 12, never above 20, as warframe.market
asks); on "too many requests" it waits and stops after three in a row. The tab only reads: nothing is posted.
*Open the auction* and *Copy whisper* help you contact the seller. Profit and fair price are estimates.

### Builds
Your in-game loadouts, shown like the game's loadout screen, from `lastData.dat` (*Reload from file* after AlecaFrame
refreshed it).

- **Game loadouts** (default view): your named loadouts with Warframe, weapons, Exalted weapon, companion, Archwing and
  Necramech; click a row for that item's build. **By item**: every item's configurations, grouped by kind, with
  thumbnails and a name/kind filter. Focus school and K-Drive are not shown.
- **Cards** like the in-game build screen: Aura, Exilus and Stance slots, eight mod slots (slot polarity, mod polarity
  and drain, rank), Arcanes, **Archon Shards** (colour, tauforged, effect), **Helminth** ability, forma count, Orokin
  **Reactor / Catalyst** (from the file, *deduced* for older items whose loadouts only fit with one). Cards **scale with
  the window** and show the mod's picture on hover.
- **Capacity** = rank (40 for Kuva/Tenet/Coda weapons and Necramechs) × 2 with Reactor/Catalyst + aura; innate
  polarities are placed where they save the most drain (the file does not say where they are). An approximate **stat
  recap** counts mods only (not Arcanes, shards, Helminth, set bonuses or conditional effects).
- **Incarnon**: whether the Genesis adapter is installed (or the Incarnon is built in, or the Genesis is on another
  variant of the weapon), the evolution tier reached (shared by all variants) and the perk chosen in each tier, from the
  game file; perk names and the adapter's picture from the weapon's wiki page (read once, kept in `incarnon_perks.json`;
  "option 2" when the page cannot be understood).
- **Rivens** show name, stats, polarity and drain and count in the recap; **spliced Rivens** are shown frozen (❄) with
  their spliced stat as "?".
- **Build planner** (third view): choose a Warframe or weapon, click a card to pick mod, rank and slot polarity (Forma);
  capacity, drain and stats update. *Save* keeps plans in `build_plans.json`; *Copy from my loadout…* starts from yours.

Pictures in this tab come **only from the Warframe wiki** (MediaWiki API, one request at a time); the missing ones are
fetched in the background at start and kept in the data folder. Names and stats come from the bundled
`loadout_data.json` (public game data and WFCD/warframe-items, rebuilt with `tools/build_loadouts.py`). An optional **icons
folder** (Settings > Inventory; AlecaFrame's unpacked `assets` is found by itself) adds Archon Shard and wallet pictures;
those files are only read where they are, never copied.

### Weekly
The vendor offers with a purchase limit (Teshin, Ironwake, Nightcap, Archimedean, Acrithis…), what you bought this
period and when it resets. The game file records each limited purchase but not which offer it was, so the program works
it out from what AlecaFrame's `deltas.dat` recorded as gained and from your inventory against the previous sync; when it
is ambiguous you are asked to pick it (★ = likely candidates). Tick *Track* to follow an offer in Activities.
**Bought → Quantframe…** sends what you bought this period to Quantframe's stock (tradable items only, check window first).

### Profile
Your standing and rank per syndicate and your mastery rank, **read from `lastData.dat`** (re-read when it changes,
setting *AlecaFrame file check*, every 10 s). AlecaFrame rewrites the file when you enter or leave a mission, so numbers
update at those moments. The file stores *total* standing; the program subtracts the start of your current rank, so the
numbers match the game. *Left today* is the standing you can still earn today. You can type or correct any value by hand
(kept until the next read). Negative standing means you are in the opposite faction.

### World, Console
**World**: fissures, invasions, sortie, cycles and Baro's current stock with platinum prices (refreshes while the tab
is open, setting *World state refresh*). **Console**: what runs in the background and every error.

### Settings
One sub-tab per category. **Save** applies and stores them in `config.json`; **Save and restart** also relaunches the
program; settings marked ⟳ (language, hotkeys, OCR…) need a restart. **Restore defaults** loads the defaults (press Save
to apply). **Theme and font**: colour themes inspired by Warframe's factions, allies and enemies (plus *Classic*), each
with its background pattern, another pattern, your own picture or none; font family and size. Previewed at once, kept
only when you press Save. The in-game overlays keep their own colours.

## Data sources
| What | From |
|---|---|
| Prices, volumes, item catalog, sell orders, riven listings | [warframe.market](https://warframe.market) (v1 and v2 API, max 3 requests/s) |
| Your standing, inventory, loadouts, purchases, challenges | AlecaFrame's `lastData.dat` / `deltas.dat` on your PC |
| Vendors, standing costs, names, weekly offers, challenge names | public game data, bundled (`tools/build_*.py`) |
| Pictures (builds, syndicate logos), Baro's list | [wiki.warframe.com](https://wiki.warframe.com) |
| World state (fissures, cycles, Baro…) | [api.warframestat.us](https://api.warframestat.us) |
| Nightwave and 1999 Calendar | DE's public world state (`api.warframe.com`), every 10 min |
| Profile glyph, Mastery Rank emblem | [browse.wf](https://browse.wf) (game icons by path), once |
| Arbitration tier / schedule | [arbi.guide](https://arbi.guide) / browse.wf |
| Updates | GitHub releases of this repository |

Every request identifies the program with its own `User-Agent` (name, version, repository) and results are cached.

## Updates (current version 0.3.7)
At start the program looks (in the background, setting *Check for updates at start*) for a newer **GitHub release**.
The update window lists **what changed since your version** (every version in between, from the changelog in your
language) and offers *Install now* / *Later* / *Skip this version*. You can also check in **Settings → Updates**.

Installing downloads `WFVendorOverlay-windows.zip`, verifies its SHA-256 against the release's `.sha256` file, replaces
the program files after it exits and restarts it. Your data (`%LOCALAPPDATA%\WFVendorOverlay`) is never touched. Each
step goes to `update.log` in the data folder; as a manual fallback close the program and unzip the release over its
folder. Only the packaged Windows build updates itself; from source use `git pull`. The checksum only proves the download
was not corrupted: it trusts this repository's releases.

What changed in each version: [CHANGELOG.md](CHANGELOG.md) (from 0.2.1 on).

## Files and settings
Everything lives in `%LOCALAPPDATA%\WFVendorOverlay`:

| File | Content |
|---|---|
| `config.json` | settings |
| `prices.json`, `items_cache.json`, `baro.json` | collected prices and volumes, market catalog, Baro's list |
| `inventory.json`, `standing.json`, `loadouts.json` | inventory and orders placed from the app, standing, builds cache |
| `goals.json`, `weekly_state.json`, `worldstate_de.json` | Activities plan, weekly purchases and tracked offers, DE world state copy |
| `build_plans.json`, `riven_weights.json` | build planner plans, custom riven weights (optional) |
| `market_session.json` | warframe.market session token |
| `vendors.json`, `gamenames.json` | optional: override the bundled ones |
| `img\`, `icons\`, `backdrop\` | downloaded pictures, syndicate logos, generated backgrounds |
| `overlay.log`, `riven.log`, `update.log`, `last_scan.txt` | errors, Riven flip requests, updater steps, last OCR read (F8) |

Main keys of `config.json` (all of them are in Settings, with explanations):

| key | meaning (default) |
|---|---|
| `language` | `en` or `it` |
| `key_goals` / `key_menu` / `key_scan` / `key_clear` / `key_quit` | hotkeys (`<f6>` `<f7>` `<f8>` `<f9>` `<f10>`) |
| `start_active` / `auto_detect` | start scanning at once / detect vendors by itself (true) |
| `refresh_interval` | seconds between automatic refreshes (180) |
| `open_max_age` | when a vendor opens, refresh data older than N s (30) |
| `show_cached_max_age` | show saved data newer than N s right away (3600) |
| `refresh_skip_age` / `refresh_confirm_over` / `baro_refresh_days` | update-shown skip age (300 s) / confirm above N items (150) / Baro refresh (7 days) |
| `volume_low` / `volume_high` | volume red up to `low`, green from `high` (10 / 50) |
| `match_threshold` | name similarity threshold (90) |
| `watch_interval`, `watch_interval_moving`, `ocr_threads`, `ocr_priority`, `publish_throttle` | detection and performance |
| `rec_min_volume`, `rec_min_price`, `rec_top` | recommendations filters |
| `sell_price_offset` | added to the market price when selling (0) |

## Performance
The scan (OCR) is the heavy part. To avoid disturbing the game:
- OCR and name matching run in a **separate process** (`app/scan/ocr_worker.py`) at "below normal" priority with few threads
  (about 1/4 of the cores, 1 to 3); the overlay, keys and mouse wheel always stay responsive.
- If the screen has not changed since the last scan, the result is reused without redoing the OCR.
- While playing, the screen is checked less often (`watch_interval_moving`).
- Still lagging? `ocr_priority` = `idle`, `ocr_threads` = 1, a higher `watch_interval` (1.0), or `auto_detect` off and
  scan only with F8.

## For developers
**From source** (Windows, 64-bit Python 3.12):
```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

**Building the executable** (the OCR models are bundled):
```
powershell -ExecutionPolicy Bypass -File build.ps1            # dist\WFVendorOverlay folder (recommended)
powershell -ExecutionPolicy Bypass -File build.ps1 -Console   # with a console (to see errors)
powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile   # single .exe (slower startup)
```

**Publishing a version**: change `app/core/version.py`, add the version's section to `CHANGELOG.md` and `CHANGELOG.it.md`,
commit, then `git tag vX.Y.Z && git push origin vX.Y.Z`. The workflow in `.github/workflows/release.yml` builds the
Windows package and creates the release (zip, checksum, notes from the changelog).

**Project layout**

```
main.py              entry point (also starts the OCR process)
app/
  core/              settings (config), translations (i18n), paths, log (logbus), theme, shared UI pieces (uiutil),
                     version, self-update (updater)
  scan/              screen reading: scanner, ocr, ocr_worker (separate process), matcher, overlay (price labels),
                     winrect, wheel
  trade/             warframe.market: market (catalog, prices, volumes), refresher, market_auth (sell orders),
                     recommend, advice, signals (trend, spikes, backtest), rivenmarket (riven listings), quantframe
  game/              game data and your account: vendors, standing, inventory, aleca (AlecaFrame file), loadouts,
                     buildcalc, rivens, weekly, quests (Nightwave / Calendar), goals (Activities plan), world, arbi
  ui/                windows and tabs: menu (main window), *_tab, *_dialog, goals_overlay (Activities), buildcards,
                     player_bar, world_strip, update_box, logos, icons, previews
data/                bundled game data (vendors, gamenames, rivens, loadout_data, nodes, weekly, challenges, places, player_icons .json)
assets/              icon.png, icon.ico
tools/               builders of data/ (build_*.py: python tools/build_vendors.py …; build_places.py: where to buy), build_icon.py,
                     prepare_models.py (OCR models)
docs/                screenshots
build.ps1            Windows build (PyInstaller)
```

## Notes and limits
- Volumes use the warframe.market v1 statistics endpoint (deprecated but alive); if it stops working only the price is
  shown.
- Max-rank price = median of the 3 lowest sell orders from online users at that rank; `–` if nobody sells at that rank.
  It is not shown nor counted (overlay, price list, inventory value, advice) for mods with only 3 ranks whose max rank
  sells for at most 3p more than rank 0, nor when that rank trades less than *Max-rank price: smallest trades a day*
  (7-day average, default 0.5).
- Prices older than *Refresh data older than (hours)* (default 2) in the price list rows shown and in the
  recommendations are refreshed by themselves, 150 at a time, recommended and oldest first.
- AlecaFrame's `lastData.dat` is read once per change, in the background, for every tab (decrypted and parsed once, then
  each tab's work done off the window's thread): the window no longer freezes when AlecaFrame rewrites it.
- The vendor list comes from the public game data: vendors missing from it (e.g. Varzia) are not included. Regenerate
  with `python tools/build_vendors.py` (a copy in the data folder takes precedence).
- AlecaFrame updates `lastData.dat` only when it syncs (entering or leaving a mission, logging in): what you did since
  shows up at the next sync. AlecaFrame reports 0 Aya, so type it in Settings > Inventory (*Aya (typed by hand)*).
- Nightwave and Calendar completion depend on what the game file records; the Calendar is marked by day.
