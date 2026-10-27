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
- **Rank up…** tells you which mods are worth ranking up to max rank to sell them. For every mod you own below max
  rank it computes the platinum gained per copy (max-rank price − current price), for as many copies as sell in about a
  day (a quarter of the 24 h volume), and the Endo and Credits needed to finish them (`base × (2^max − 2^rank)`; Endo
  base 10/20/30/40 and Credits base 483/966/1449/1932 for common/uncommon/rare/legendary, per the
  [wiki](https://wiki.warframe.com/w/Fusion)). The score is the platinum gained per 1000 Endo, discounted for slow
  sellers; type the Endo you have and the best rows that fit are selected. Settings > Inventory: *Rank up: minimum gain*.
  Arcanes cannot be ranked with Endo, so they are not listed.
- **Exclude installed** leaves out the mods and Arcanes that sit in one of your loadouts (read from the `lastData.dat`
  at import time, so re-import or *Reload file* after changing a loadout). They are not counted in the value or in the
  advice, so you never get told to sell what you are using.
- **Item pictures.** Hovering an item name shows its picture, the one warframe.market publishes (downloaded once, one
  at a time, kept in the data folder; switch off in Settings). AlecaFrame's own image files are not read: they belong to
  that program and live on your PC in a format this program does not rely on.
- **Trades left** (top strip) comes from the `lastData.dat`, which the game only updates when AlecaFrame syncs
  (entering or leaving a mission, logging in again): trades made since are not counted yet. A ⚠ appears when the last
  sync is from before the daily reset (00:00 UTC), when the real number is probably higher; the tooltip shows the sync time.
- **Price trend in the advice.** Together with the 24 h volume, the program now keeps the volume-weighted average closed
  price over 7, 30 and 90 days (taken from the same statistics answer: no extra request; for mods, separately for rank 0
  and max rank). The three advice windows show a *vs 30 d* column (current price against the 30-day average; the tooltip
  has the 7/30/90-day averages), and a price above its 30-day average is pulled towards it by *Advice: trend weight*
  (default 50%, 0 = ignore the trend), so a short spike does not push an item to the top. Items refresh their averages
  at the next *Update prices*.
- **Icons folder (optional).** Settings > Inventory > *Icons folder*: point it at a folder of your own icons (for example
  the unpacked `assets` of AlecaFrame) and the Builds tab shows the Archon Shard pictures. The files are only read from
  where they are; they are not copied or shipped with the program.
- **Sell…** places a **sell order** on warframe.market for every selected item. Sign in first (email and
  password, sent only to warframe.market; **only the session token is stored**, in `market_session.json`;
  *Sign out* deletes it). For each order a window shows quantity, rank (mods/arcanes), price (market price
  + `sell_price_offset`) and **the exact request that will be sent**; nothing is sent until you press
  *Place order*. The app remembers the orders it placed (*Listed* column); it does not read your other orders.
  **Caveat:** sign-in and order creation use the v1 REST API as documented by community client libraries and
  could not be tried against the live site while developing: check the first order on warframe.market.
  Accounts that sign in with Discord/Google may not work.

**Ducats and advice.** The *Ducats* column shows what each prime part gives when traded (from the game data). *Advice: ducats* lists your prime parts by ducats gained per platinum given up (`ducats / max(price × liquidity, 0.5)`, with `liquidity = min(1, volume / liquid volume)`); at or above the minimum ratio (default 10) it says *Ducats*, otherwise *Sell*. Totals use all your copies. *Advice: sell* ranks the rest by `price × copies you can expect to sell (≈ ¼ of the daily volume) × liquidity`, leaving out items worth less than the minimum price or with too little volume. Both can select the chosen rows in the table, ready for *Sell*. *Hide zero volume* also exists here. Thresholds are in Settings (Recommendations group).

### Quantframe
The program can hand items to [Quantframe](https://github.com/Kenya-DK/quantframe-react) so you do not add them there by hand. Turn on Quantframe's local HTTP server (Settings > Advanced > HTTP Server; default `127.0.0.1:4808`, setting *Quantframe address* here). **Inventory > Send to Quantframe…** sends the selected rows (all shown rows if none is selected) to Quantframe's **stock**; ranked mods go per rank (copies at rank 0 and at max rank). **Builds > Missing → Quantframe** sends the mods you lack for the selected build to its **wish list**. A check window comes first (what, how many); items already sent are left unchecked because quantities add up. No purchase price is sent, so no transaction is recorded. Mind that Quantframe's Live Scraper may then list stock items for sale, and may place buy orders for wish-list items, depending on its own settings. Only addresses on this computer are accepted. **Inventory > Rivens → Quantframe…** sends your **revealed** rivens only (already assigned to a weapon; unrevealed ones are ignored) to Quantframe's riven stock. Weapon, name, rank, re-rolls, polarity and stats are read from your AlecaFrame file and the stat values are recomputed from the game's public data (`rivens.json`, regenerated with `build_rivens.py`); they can differ by a decimal from the game, and two old stat types the data does not cover are skipped and reported. The warframe.market attribute names are fetched once and cached. Check the result in Quantframe.

### Riven flip

**Riven flip > Scan the market** reads the riven listings of the next weapons on warframe.market (the least recently scanned first; *Weapons per scan* and *Only these weapons* in Settings > Riven flip) and lists the rivens priced **below what comparable ones are worth**, best profit first. Three criteria:

- **Price**: the listed direct-buy price against a *fair price* = median price of the comparable listings of the same weapon (stats score within ±15) × *Expected resale* (default 85 %, because asking prices are higher than what gets paid). At least 3 comparable listings are needed. warframe.market returns at most the **100 cheapest** listings per weapon (lists of weapons and stats come from its v2 API, listings from the only auction API left, v1), so for very popular weapons the comparison is made among the cheaper ones, which keeps the fair price on the cautious side.
- **Sales**: warframe.market does not publish riven sales, so this is an **estimate**: each scan remembers the listings seen, and listings that were there and are gone at the next scan (sold, withdrawn or expired) are counted over the last 7 days. It needs repeated scans (a gap longer than 3 days restarts the count); the column shows "–" until a weapon has been watched for a day. *Smallest estimated sales* hides slow weapons.
- **Stats**: a 0–100 score from how useful each stat is (weights: crit chance/damage, damage and multishot highest; zoom and recoil worth nothing; a negative on a worthless stat is a bonus) and how well it rolled (computed with the same formula as the Rivens → Quantframe feature). To change the weights create `riven_weights.json` in the program's data folder, e.g. `{"WeaponFireRateMod": 0.9, "WeaponStunChanceMod": 0.2}` (0 to 1; stat names are the keys of `rivens.json`).

**Request rate**: warframe.market's rules ask that auction (contract) searches stay around 10–20 per minute. Only the riven requests have their own limiter (*Riven requests per minute*, default 12, never above 20), so a scan of 20 weapons takes about 2 minutes; the weapon and stat lists are downloaded once a week. On a "too many requests" answer it waits (the server's `Retry-After`, or 20 s, 40 s) and stops the scan after three in a row; what was read is kept. The tab only reads: nothing is posted to warframe.market. riven.market is not used (it has no public API that I could find). Following warframe.market's rules, the program identifies itself with its own `User-Agent` (name, version, repository) and caches what it can. *Open the auction* opens the listing; *Copy whisper* copies the in-game message to the seller. Profit and fair price are estimates, not guarantees.

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
Your own in-game loadouts, shown like the game's loadout screen: Aura, Exilus and Stance slots, the eight mod slots with each mod's rank (n/max), equipped Arcanes, forma count, the **Archon Shards** installed on a Warframe (colour, tauforged or not, and the effect) and the **Helminth** ability that replaced one of its own ("Ability 4: Miasma → Roar"). Warframes, weapons, Archwing, Necramechs and companions are listed on the left, with a filter by name and by kind.

**Game loadouts** (the default view) follows the in-game loadout screen: your named loadouts with the Warframe, primary, secondary, melee and Exalted weapon, the companion, the Archwing and the Necramech, each with its rank (*Max Rank* from rank 30) and the mod configuration the loadout uses. Click a row to see that item's mods, Arcanes, Archon Shards and Helminth. *By item* is the plain list of every item's configurations. Focus school and K-Drive are not shown.

Mod and Arcane **pictures** are shown on the cards: they are taken as they are needed from warframe.market (item images) and, when it has none, from the Warframe wiki (wiki.warframe.com, standard MediaWiki API, one request at a time with this program's User-Agent), kept in the data folder and never downloaded twice; they appear a few seconds after the loadout opens. Switch off with *Item pictures in tooltips* in Settings.

Everything comes from your AlecaFrame `lastData.dat` (found by itself, same file as Inventory); *Reload from file* re-reads it after AlecaFrame refreshed it. Nothing is downloaded from any website. Mod, Arcane, ability and shard names come from the bundled `loadout_data.json` (rebuilt from the public game data with `build_loadouts.py`). Per-slot polarities and mod drain are not shown.

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

### Settings, themes and fonts

Settings has one sub-tab per category. **Theme and font** offers colour themes inspired by Warframe's factions, allies (Tenno, Ostron, Entrati, Steel Meridian, Red Veil, New Loka) and enemies (Grineer, Corpus, Infested, Orokin, Sentient, Narmer), plus the original *Classic*, and a font family and size. The choice is previewed at once in every window and kept only when you press Save (leaving the tab restores the saved look). The in-game overlay keeps its own colours. All themes are dark.

## Updates (current version 0.2.2)

See [CHANGELOG.md](CHANGELOG.md) for what changed in each version (from 0.2.1 on; the release page shows the same notes).

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
  the bundled ones) · `overlay.log` errors (useful with the exe) · `riven.log` Riven flip requests and errors.

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
