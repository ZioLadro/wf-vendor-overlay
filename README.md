# WF Vendor Overlay

🇬🇧 English · [🇮🇹 Italiano](README.it.md)

Shows next to the items of Warframe's vendors the **platinum price** (to the right of the name) and the
**24-hour trade volume** (below the name, centred; red = rarely traded, green = heavily traded), using
warframe.market data and reading the screen with OCR. It only uses screenshots: it never touches the
game's memory or files.

Price label: `12p` = platinum · `–` = nobody selling online · `n/a` = error / data unavailable.
For **mods and arcanes** the label shows two prices: `12p · max 45p` = rank 0 price (what you buy at the
vendor) and **max-rank** price. The volume is the total of the trades of all ranks.

## How it works
- **Starts active**: open a vendor and, when the screen settles, the overlay scans by itself.
- **Saved data** in `prices.json`: the last known values show up at once, then they are refreshed in the
  background. When a vendor opens, data older than 30 s is refreshed.
- **Every 180 seconds** prices and volumes of the vendors shown refresh by themselves.
- **Scrolling** with the mouse wheel: the labels vanish at once and come back ~0.5 s after scrolling stops.
  If the list changes in another way (dragged scrollbar, keyboard, vendor closed) the change is detected
  by comparing the pixels under the names.
- **Leaving the vendor**: the labels disappear as soon as you close the vendor or change page.
- **F7** opens/closes the **price list** · **F8** scan now (and resume if paused) · **F9** pause ·
  **F10** quit. The same actions are in the tray icon menu (click on the icon = price list).
- Warframe must run in **Borderless** windowed mode.

The OCR reads **only the Warframe window**, and only while it is the active window (Windows; setting *Read only the Warframe window*, turn it off if the game is not detected, e.g. cloud gaming). Labels are hidden when you switch to another window.

On the game screen, the **best items of the vendor you are looking at** (ranked among that vendor's own stock by platinum per standing, discounted by how rarely they trade; from the saved prices) get a small yellow *★ Recommended ★* tag above their name, and the very best one *★ Best here ★* (settings *Stars on recommended items* / *Recommended items marked*). The status line also names it: *Best buy at …*. The Recommendations tab has a *Best per vendor* box (one row per vendor).

Every tab shows a **player strip**: name (click to set it, the game files do not contain it), mastery rank, trades left, and a badge per syndicate with your rank and standing (hover for the daily standing left). Badges are drawn with the syndicate colours; to use the real logos put `<SyndicateTag>.png` files (e.g. `CetusSyndicate.png`) in the `icons` folder of the data folder. Nightwave series are not shown.

**Recognising the vendor screen.** After reading the names, the program checks which vendor's stock they belong to (from `vendors.json` and Baro's list). Labels appear only if at least 3 matched items (setting) and 60 % of everything matched belong to the **same vendor**; names that are not in that vendor's stock are dropped. This keeps labels off inventory, chat or codex pages that merely show some item names, and the overlay says which vendor it recognised. The program also **reads the vendor's name** on screen (only in the top 20 % of the game window, setting *Vendor name zone*; with several names the tallest text wins; a line equal to the vendor's name, e.g. *Cephalon Simaris*, *Red Veil*): when it is there and at least one item is that vendor's, labels are shown even with few items. *Require the vendor name* makes it mandatory (stricter, but vendors whose heading is not their name would never match). F8 writes everything it read to `last_scan.txt` in the data folder, to see why a vendor was or was not recognised. Turn it off with *Recognise the vendor screen*, or lower *Items needed* for vendors with very few tradable items.

## Price list window (F7)
The window **opens by itself when the program starts** (setting *Open the price list at start*). Six tabs. The overlay keeps working while the window is open: the window's own area is blanked before the OCR, so it never reads its own names.

### Price list
All the **tradable items that cost standing** (from `vendors.json`: vendors and syndicates), plus everything
sold by **Baro Ki'Teer**: they are all there from the start, even without data (price `–`, updated `never`).
Items that do not cost standing (and are not Baro's) are not listed. Columns: name, vendors that sell it, **standing cost**, type (Mod / Arcane / Other),
price, max-rank price (mods and arcanes), 24 h volume (coloured like the overlay), last update. Click the
headers to sort; search box and vendor/type filters.

- Standing cost comes from the game data. It is the base cost, without rank discounts. If an item costs
  standing at several vendors you see `min – max`; the tooltip shows vendor, cost and required rank.
- **Hover** an item name (or its standing cell): how many you can buy with your standing, per syndicate
  (`floor(standing / cost)`), and whether your rank is enough. It uses the numbers of the Profile tab.
- **Hide zero volume** hides the items with no trades in the last 24 hours (items without data stay visible).
- **Right-click** an item name (here and in Recommendations): open it on warframe.market, open its page on
  the Warframe wiki (a search that jumps straight to the page when the title exists), or copy the name.
- Only **tradable** items are listed: names are matched against the warframe.market catalog, so
  anything that cannot be traded is left out.
- **Update shown** refreshes price and volume of every visible row (filters included; it skips data newer
  than `refresh_skip_age` seconds). Filter by one vendor to update just its items.
- **Update selected** always refreshes the selected rows (Ctrl/Shift for several).
- **Stop** interrupts; a progress bar shows the update. The limit is 3 requests/s (2 per item): about
  2 minutes per 100 items, ~20 for the whole vendor catalog. Above `refresh_confirm_over` items it asks
  for confirmation. Closing the window stops any update. Data stays saved in `prices.json`.
- **Update Baro list**: Baro is not in the game data; his historical list is read from the wiki (and from
  his current inventory) and reloads by itself at startup every `baro_refresh_days` days.

### Inventory
Your items with their market prices, and one-click sell orders (inspired by AlecaFrame's Inventory tab).

- **Where the items come from.** Warframe keeps your inventory on DE's servers, not in a local file, so it
  cannot be read from disk (and this program never reads the game's memory or network traffic). You build
  it by **Import file…** (replaces the inventory), **Paste list…**, or **Add item…** / **Edit** by hand.
  Accepted files: a **`lastData.dat`** (the AlecaFrame-style encrypted inventory file; decrypted locally with the
  `cryptography` package; the Import dialog opens in `%LOCALAPPDATA%\AlecaFrame` if that folder exists),
  a *raw Warframe-style inventory* JSON (`MiscItems`, `RawUpgrades`, `Upgrades`, `Recipes`…
  with `ItemType` paths, resolved through the bundled `gamenames.json`), any JSON that pairs item names with
  quantities (`{"name": …, "count": …}` lists or `{"Serration": 2}`), and CSV/TXT lines such as
  `Serration, 2, 10` (name, quantity, optional rank), `3x Mirage Prime Set` or `Ash Prime Blueprint x2`.
  **Reload file** re-reads the last imported file, handy when another tool of yours refreshes it.
  Names are matched to the market catalog (small typos are tolerated); the ones that cannot be matched are
  listed after the import. Not tested against real game exports, only against files of those shapes.
- **Categories**: Sets, Warframe parts, Weapon parts, Mods, Arcanes, Relics, Other (derived from the
  warframe.market tags). **Filters** like AlecaFrame's: minimum platinum (5 / 10 / 15), more than one owned,
  part type (prime / normal), vaulted (when the market data says so), listed from here, plus
  **Exclude max-rank mods/arcanes** (they leave the list and the total).
- **Prices**: value = copies × rank 0 price + max-rank copies × max-rank price; **Update prices**
  refreshes the shown items. Right-click a name for the market / wiki page.
- **Sell…** places a **sell order** on warframe.market for every selected item. Sign in first (email and
  password, sent only to warframe.market; **only the session token is stored**, in `market_session.json`;
  *Sign out* deletes it). For each order a window shows quantity, rank (mods/arcanes), price (market price
  + `sell_price_offset`) and **the exact request that will be sent**; nothing is sent until you press
  *Place order*. The app remembers the orders it placed (*Listed* column); it does not read your other orders.
  **Caveat:** sign-in and order creation use the v1 REST API as documented by community client libraries and
  could not be tried against the live site while developing: check the first order on warframe.market.
  Accounts that sign in with Discord/Google may not work.

**Ducats and advice.** The *Ducats* column shows what each prime part gives when traded (from the game data). *Advice: ducats* lists your prime parts by ducats gained per platinum given up (`ducats / max(price × liquidity, 0.5)`, with `liquidity = min(1, volume / liquid volume)`); at or above the minimum ratio (default 10) it says *Ducats*, otherwise *Sell*. Totals use all your copies. *Advice: sell* ranks the rest by `price × copies you can expect to sell (≈ ¼ of the daily volume) × liquidity`, leaving out items worth less than the minimum price or with too little volume. Both can select the chosen rows in the table, ready for *Sell*. *Hide zero volume* also exists here. Thresholds are in Settings (Recommendations group).

### Recommendations
What is worth buying with standing, for every (item, vendor) pair that has a standing cost:

```
plat per 1000 standing = price / standing cost × 1000
score                  = plat per 1000 standing × min(1, volume / high-volume setting)
```
The score discounts items that rarely sell: a high price is worthless if nobody buys. Items traded less
than the **minimum volume** or cheaper than the **minimum price** (both editable in the tab) are left out.
Prices are the rank 0 ones (what the vendor actually sells). Filter by vendor or type. Items that have no
market data yet cannot be rated: **Fetch missing data** downloads them (pick one vendor first to keep it quick).
Hovering a row shows how many you can afford with your standing (Profile tab).

### Builds
Mod lists for a Warframe, weapon or companion, checked against your inventory. **Add from link…** takes an Overframe build link (`overframe.gg/build/…`): the page is downloaded once, from your PC and only when you ask, and the mod names written in it are picked out (abbreviations like *Arc. Flow* / *Trans. Fortitude* are expanded). **Add from list…** takes mod names pasted one per line. Either way a window shows what was found so you can uncheck wrong matches and add missing mods before saving. For each build the tab shows which mods you own (from the AlecaFrame file), which are owned but not at max rank (Endo only), and which are missing with their market price (max-rank price for ranked mods); builds are sorted by what is left to buy, so the ones you can already make come first. *Fetch missing prices* downloads the prices still unknown. Overframe's own mod-slot data is not read, only the mod names in the page text, so always check the list. Builds are stored in `builds.json`.

### Profile
Your standing and rank per syndicate, plus your mastery rank, **read from the AlecaFrame `lastData.dat`** (or the
companion-app JSON) with **Import standing from file…**; *Reload file* re-reads it after AlecaFrame refreshed it.
You can also type or correct any value by hand (kept until the next import). It is a snapshot: reload after spending
standing. The file is **found by itself** in `%LOCALAPPDATA%\AlecaFrame` (or `%APPDATA%\AlecaFrame`): no import needed, and your in-game name is taken from AlecaFrame's `lastUsername.txt` (a name you type yourself is never overwritten). The file is **re-read automatically** when it changes (checked every 10 s, setting *AlecaFrame file check*, 0 = off; restart to apply). AlecaFrame rewrites the file every time you enter or leave a mission, so standing and inventory update at the same moments (only while AlecaFrame is running). The *Left today* column is the standing you can still earn today (daily cap).
The file stores your *total* standing; the program subtracts the start of your current rank, so the numbers match the game (e.g. 68 195 / 132 000). Type values as the game shows them.
Negative standing means you are in the opposite faction (you can buy 0).

### World
Fissures, invasions, sortie, cycles and Baro Ki'Teer's current stock (with platinum prices when known), from the
community mirror `api.warframestat.us`. Refreshes while the tab is open (setting *World state refresh*).

*Not included:* full inventory/foundry (only the companion-app JSON exists, use the Inventory import), remaining daily standing, drop tables, EE.log parsing.

### Settings
Every setting of the program, grouped (general, hotkeys, detection, data, appearance, performance,
recommendations). **Save** applies and stores them in `config.json`; **Save and restart** also relaunches
the program. Settings marked ⟳ (language, hotkeys, OCR, start active, name threshold) need a restart;
the rest apply immediately. **Restore defaults** loads the default values (press Save to apply).

## Updates (current version 0.1.8)
At start the program looks (in the background, setting *Check for updates at start*) for a newer **GitHub release**
and asks if you want to install it (*Install now* / *Later* / *Skip this version*). If the release exists but its package is not ready yet (the automatic build still running or failed) it says so. In **Settings → Updates** you can check by hand and, if you agree, it downloads
`WFVendorOverlay-windows.zip`, verifies its SHA-256 against the `.sha256` file of the same release, and replaces
the program files after it exits, then restarts. Your settings and data (`%LOCALAPPDATA%\WFVendorOverlay`) are never touched.
The installer step writes `update.log` in the data folder (each step, and any copy error). If an update ever does nothing, that file says why; as a manual fallback close the program and unzip the release over its folder. Only the packaged Windows build updates itself; from source use `git pull`. The check only proves the download was not
corrupted: it trusts the repository's releases (the exe is not code-signed, so Windows SmartScreen may warn).

**Publishing a version** (maintainer): change `version.py`, commit, then `git tag v0.1.1 && git push origin v0.1.1`.
The workflow in `.github/workflows/release.yml` builds the Windows package and creates the release with the zip and checksum.

## Language
English by default. Change it in Settings → General → Language (English / Italiano) and restart.
The code, comments and both READMEs exist in English; the interface is fully translated.

## From source (Windows, 64-bit Python 3.12)
```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

## Building the executable
```
powershell -ExecutionPolicy Bypass -File build.ps1            # dist\WFVendorOverlay folder (recommended)
powershell -ExecutionPolicy Bypass -File build.ps1 -Console   # with a console (to see errors)
powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile   # single .exe (slower startup)
```
The OCR models are bundled. If Warframe runs as administrator, run the overlay as administrator too.

## Files and settings
Everything lives in `%LOCALAPPDATA%\WFVendorOverlay`:
- `config.json` settings · `prices.json` collected prices and volumes · `items_cache.json` market catalog ·
  `baro.json` Baro's list · `inventory.json` your inventory and the orders placed from the app ·
  `market_session.json` warframe.market session token · `vendors.json` / `gamenames.json` (optional, override
  the bundled ones) · `overlay.log` errors (useful with the exe).

| key | meaning (default) |
|---|---|
| `language` | `en` or `it` |
| `key_menu` / `key_scan` / `key_clear` / `key_quit` | hotkeys (`<f7>` `<f8>` `<f9>` `<f10>`) |
| `start_active` / `auto_detect` | start scanning at once / detect vendors by itself (true) |
| `refresh_interval` | seconds between automatic refreshes (180) |
| `open_max_age` | when a vendor opens, refresh data older than N s (30) |
| `show_cached_max_age` | show saved data newer than N s right away (3600) |
| `refresh_skip_age` / `refresh_confirm_over` / `baro_refresh_days` | update-shown skip age (300 s) / confirm above N items (150) / Baro refresh (7 days) |
| `volume_low` / `volume_high` | volume red up to `low`, green from `high` (10 / 50) |
| `volume_offset_y` / `show_volume` | distance of the volume label (2 px) / show it |
| `hide_zero_volume` | hide zero-volume items in the price list (false) |
| `match_threshold` | name similarity threshold (90) |
| `watch_interval`, `watch_interval_moving`, `auto_settle_polls`, `auto_motion_frac`, `auto_min_gap`, `scroll_debounce` | detection sensitivity |
| `ocr_threads`, `ocr_width`, `ocr_mask_panel`, `ocr_priority`, `publish_throttle`, `menu_refresh_ms` | performance |
| `inv_exclude_maxed`, `sell_price_offset` | inventory: leave out max-rank mods/arcanes / price offset when selling (0) |
| `rec_min_volume`, `rec_min_price`, `rec_top` | recommendations filters |

## Performance
The scan (OCR) is the heavy part. To avoid disturbing the game:
- OCR and name matching run in a **separate process** (`ocr_worker.py`) at "below normal" priority and with
  few threads (about 1/4 of the cores, 1 to 3); the main process (overlay, keys, mouse wheel) always stays
  responsive. A scan takes a few seconds longer, but without stealing CPU from the game.
- If the screen has not changed since the last scan, the result is reused without redoing the OCR.
- While playing, the screen is checked less often (`watch_interval_moving`), and the overlay redraws at
  most every `publish_throttle` seconds during updates.
- Still lagging? `ocr_priority` = `idle`, `ocr_threads` = 1, a higher `watch_interval` (1.0), or
  `auto_detect` off and scan only with F8.

## Source files
`main.py` startup · `scanner.py` scans, automatic detection, refreshes · `ocr_worker.py` OCR process ·
`version.py` · `updater.py` · `update_box.py` self-update · `ocr.py` capture and OCR · `winrect.py` game window position · `matcher.py` name matching · `market.py` catalog, prices, volumes, JSON store ·
`vendors.py` / `build_vendors.py` / `vendors.json` vendor catalog and standing costs ·
`menu.py` price-list window · `recommend.py` + `recommend_tab.py` recommendations ·
`inventory.py` + `inventory_tab.py` inventory and imports · `market_auth.py` sign-in and sell orders ·
`settings_tab.py` settings · `refresher.py` bulk updates · `uiutil.py` shared UI pieces ·
`overlay.py` graphics · `config.py` settings storage · `i18n.py` translations ·
`build.ps1` / `prepare_models.py` executable.

## Notes
- Volumes use the warframe.market v1 endpoint (deprecated but alive); if it stops working only the price is shown.
- Automatic detection checks the screen every 0.6 s (light, but not zero): raise `watch_interval` or set
  `auto_detect` to `false` if you notice slowdowns.
- Max-rank price = median of the 3 lowest sell orders from online users with that rank; if nobody sells
  at that rank it shows `–`.
- The vendor list comes from the game's public data: vendors missing from it (e.g. Varzia, Arbitrations
  honors) are not included. Regenerate with `python build_vendors.py` (a copy in
  `%LOCALAPPDATA%\WFVendorOverlay\vendors.json` takes precedence).
- Your own standing and inventory are not read from the game: Warframe keeps them on DE's servers, not in local files.
