# Changelog

From 0.2.1 on, every release lists its changes here (the release page on GitHub shows the section of its version).
Italian version: [CHANGELOG.it.md](CHANGELOG.it.md).

## 0.6.4
- **Weekly ▸ Tenet / Coda**: the wiki's bonuses are read again: its "Current Valence Bonuses" table has no date and
  the element and percentage in their own columns. The page is read every hour in the first 12 hours of a cycle.

## 0.6.3
- **Weapon stats as the game computes them** (checked on Kompressa Prime, Tenet Glaxion, Praedos screenshots): the
  Kuva / Tenet / Coda bonus is part of the base the mods' elements are a percentage of (Tenet Glaxion's Viral 97.8);
  *Total* is one shot with all its multishot (Kompressa Prime 70.7); slam, slide and heavy attacks get every mod,
  elements included (Praedos slam 2809); the explosion of weapons like Kompressa, Kuva Bramma, Lenz with its own damage,
  falloff and radius (1625.8); heavy attack section; Punch Through; numbers rounded like the game (3.8x, 1.8s, 8.33).
- **Planner ▸ warframe.market**: for a Riven, the search uses its stats (up to 3 positive and the negative one).

## 0.6.1
- **Build import from a picture, polarities and Rivens**: each card's drain colour gives its slot's polarity (green:
  the mod's, red: another one, white: none) and the game's green bubble an Omni Forma; when the drain number can be
  read, the rank (and polarity) that give it. Rivens are recognised by name ("Kuva Bramma Acri-critacan"), with their
  stats when the picture is one of this program's. Works on video frames too: on seven screenshots of the game the
  capacity comes out as in the game in six (the seventh is 1 off, a number not readable).
- **Capacity**: a mismatched polarity adds 25 % rounded, not rounded up (the game: Point Strike 9 -> 11).
- **Planner**: right click on a slot or a library card: *Search on warframe.market* (a Riven: the Riven auctions for
  its weapon); the tooltip says whether you own the mod / Arcane (when the game file was read).
- **Weekly ▸ Tenet / Coda**: Eleanor's group of Coda weapons was the other one (checked in the game); the bonus
  elements and percentages are the ones players report on the wiki ("Tenet Weapons", "Coda Weapons", read every 3
  hours) for the current cycle, with their date; where nobody reported one yet, "see in game".
- **Planner, Riven stats from a picture**: right click on a slot ▸ *Riven stats from a picture* (or *from the
  clipboard*): the game's Riven card or tooltip (a screenshot, a video frame) fills the slot with that Riven: name,
  stats (a faction "x0.62" is -38 %), MR and rerolls; the weapon's stats follow.
## 0.6.0
- **Planner: import a build from a picture** (Share ▸ *Import from a picture…* or *Import the picture in the clipboard*):
  a screenshot of the game's upgrade screen, or a picture shared by this program. The OCR reads it (in its own
  process) and the mods and Arcanes are placed by where they are: the item from the title (a renamed weapon too), the
  Aura / Stance / Exilus / Posture, the general slots in the game's order, the Arcanes and a gun's Exilus on the right;
  the mod library under the game's screen and the stats panel are left out. Mods at their maximum rank; ranks, Forma
  and Rivens are not read. Checked on six screenshots of the game (Warframe, primary, secondary, melee, companion,
  claws) and on a shared picture.
- **Archon mods** have a light red glow.
- **Weekly ▸ Tenet / Coda weapons**: Ergo Glast's 5 Tenet weapons and Eleanor's 7 Coda weapons with their bonus element
  and percentage, with pictures, the time left and the next cycle (every 4 days). Computed (DE's vendor data, the
  game's random generator as reconstructed by OpenWF), not read from the game: the page says so.
- **Weekly ▸ Duviri Circuit**: this week's Warframes and Incarnon Genesis adapters with pictures, and a calendar of the
  next 12 weeks (fixed cycles, aligned on the world state's choices).
- **Wallpapers from the Warframe wiki** as the background: Settings ▸ Theme, the button in *Background picture* opens a
  gallery; only the wallpaper chosen is downloaded.

## 0.5.9
- **The Warframe's figure is whole**: the picture was not cut by the screen but is itself a close-up (DE's store icon
  of Cyte-09 is a piece of helmet). The Warframe's figure is now looked for among the pictures of its wiki article:
  those named after it (not icons, abilities, skins, helmets…), the tallest standing one. A close-up is never used
  for a Warframe: no picture rather than a cut one.
- **Mod names easier to read** over the art: slightly bolder, on a soft dark band, with a dark outline.

## 0.5.8
- **The Warframe's whole figure** in the background: the wiki article's main picture (DE's store icon, a close-up for
  some Warframes, stays the fallback and the picture of weapons and companions).
- **Omni Forma**: a slot polarized with an Omni Forma shows the game's green bubble (in place of the polarity).
- **Card frames**: the art is cut to the inside of each frame (under the top bar, between the solid sides, measured on
  every rarity's pieces): nothing shows outside Galvanized, Amalgam and the others any more.
- **Companion stats**: health, shields and armor at rank 30 (DE's values) with the companion mods (Enhanced Vitality,
  Calculated Redirection, Metal Fiber…), checked against the game (Pharaoh Predasite 710 / 1066 / 300).
- **Beasts' claws by owner**: "Claws (Pharaoh Predasite)" in the list and the title, and the companion's figure behind
  them. Their damage / critical / status are in no public data: only their capacity is computed.

## 0.5.7
- **Warframe abilities** under the stats (Builds and planner), as on the game's screen: the passive and the four
  abilities with DE's icons; the tooltip gives the description, the energy cost with the build's efficiency (Seek 25 ->
  38.75 at 45 %) and the build's strength, duration and range. The Helminth ability shows in the slot it replaces.
- **Planner: Helminth**: pick the ability to replace and the Helminth / subsumed ability (copied from your loadouts and
  kept in shared builds); new mods fill the slots from the top left, as in the game.
- **Incarnon evolutions**: a tooltip on every perk with its effect (from the weapon's wiki page) and whether it is
  chosen or not unlocked yet.
- **The item's figure in the background** of the Builds and planner screen (the whole Warframe, the weapon…), also in
  shared pictures: DE's picture, downloaded once. Setting *Builds: the item's figure in the background* (Theme).
- Drop-down menus have their arrow again (gone since 0.5.0: Type and Item in the planner looked like text fields).
- Card frames: the art fills the frame to its edges.

## 0.5.6
- **Card frames at the right size**: each part is cut to its visible area before it is stretched to the card's width
  (most sit on a larger transparent canvas, Galvanized and Peculiar on twice the size): the frames are as wide as the
  card, as in the game, and Galvanized has its proportions.
- **Beasts' claws capacity**: claws have an innate Penjaga Posture slot and one Madurai slot (no public data has them;
  checked in the game: Panzer Vulpaphyla claws 2/70 with 2 Forma).

## 0.5.5
- **Card frames like the game's**: laid out on the real wiki files: the FrameTop (the rarity's ornament) across the top,
  the FrameBottom (the curved tray) across the bottom, their legs making the sides, the art inside, the drain on the
  game's box, the rank pips on the rank line. The parts are asked for by their names (Bronze / Silver / Gold /
  Legendary / Riven / Galvanized / Peculiar…); Railjack's Avionic frames and the side / corner lights are no longer
  used. The parts downloaded by 0.5.3–0.5.4 are replaced once.

## 0.5.4
- **Card frames now show up**: the parts are recognised by their caption on the wiki page ("Rare Mod Top Border"…), not
  only by their file name, and the cards on screen are drawn again as soon as they arrive. The Console says what was
  found and saved ("mod frames…"); after a failure it tries again an hour later.

## 0.5.3
- **Builds: mods in the game's order.** The game numbers the eight slots from the bottom right (its file's last slot is
  top left): the cards were drawn turned round. Checked on a real build (Cyte-09). The first Arcane is now level with
  the Aura / Stance row, as in the game.
- **Capacity**: 39 mods were missing from the data (they counted 0 drain): Cull the Weak and the other new claw mods,
  the Banes and Primed Banes, Mark of the Beast… Polarity, base drain and max rank now come from the game's own export
  (DE Public Export via public-export-plus): Quick Thinking (10 / rank 5), Maglev (rank 5) and Pressure Point (rank 5)
  were wrong.
- **The game's card frames** in Builds: borders, background, lights, the drain's backer and the rank pips per rarity
  (Common … Legendary, Riven, Galvanized, Amalgam, Peculiar), downloaded once from the wiki's
  [Mod/Assets](https://wiki.warframe.com/w/Mod/Assets) page. Setting *Builds: the game's card frames* (Theme); without
  them the simple cards stay.

## 0.5.2
- **Activities no longer takes stray clicks**: the mouse goes through it to the game until you press **Ctrl+F5** (as in
  AlecaFrame). Unlocked, it is outlined and shows its buttons; Ctrl+F5 again, or a few seconds after the mouse leaves it
  (never while one of its menus is open), it locks again. Pressed while Activities is hidden, the key shows it unlocked.
  Settings: *Activities and the mouse* (key combination / while a cursor is shown / always, also in ⚙ → Mouse),
  *Activities: unlock key*, *Activities: lock again after*. Who had turned off "clickable only with the cursor" keeps
  "always clickable".
- Settings refuse a hotkey that contains another one (Ctrl+F6 would also press F6).

## 0.5.1
- **Fix**: 0.5.0 did not start (it closed at once, without a message): the new fonts were loaded before the
  program's window system existed, which makes Qt crash. They are now loaded once it is ready.

## 0.5.0
- **New look**: the sections are a sidebar on the left (like AlecaFrame), cards with rounded corners, flat tabs
  underlined in the accent, slim scroll bars, ticked boxes in the accent; the game's text font **Noto Sans** and
  **Rajdhani** for titles, tabs and headers, both bundled (SIL Open Font License). Saved "Segoe UI" becomes Noto Sans.
- **27 themes** (was 13), each with an accent and a second accent: new ones for the Lotus, the Void, the Drifter, Arbiters
  of Hexis, Cephalon Suda, the Perrin Sequence, Solaris United, the Holdfasts, Duviri, Höllvania, Kuva Liches, the
  Murmur, Scaldra and the Stalker.
- **Share builds** (Builds tab and planner): a build code to paste, a `.wfbuild` file, a picture of the build screen
  (save or copy); import a code or a file into the planner.
- **Riven flip, from Quantframe**: riven trades read from the game's log go into the journal by themselves (bought /
  sold, with the platinum); wanted stat combinations per weapon (★, detail panel, filter).

## 0.4.10
- **Activities overlay: World activities** you follow (World tab > *Follow*): cycles, Baro, Sortie, Archon Hunt, the
  Arbitration now / the next one of a tier, kinds of Void Fissures, invasion rewards, with countdowns updated every second.
- **Weekly**: filter by kind of offer (several at once) and by name; select several offers to track / untrack them at once.
- **Acrithis' prices** (10 Pathos Clamps) and the other vendors whose price is drawn from a list (Necralisk's Hivemind,
  Railjack crew, Archimedean commissions…) are shown: the game data keeps them per "bin", not per offer. Daily offers
  show their reset.
- **Riven flip, live check**: an auction that no longer exists (warframe.market answers 400 "not_exist", not 404) is
  marked *no longer listed* instead of being asked again every 30 seconds; a check that fails waits its turn.
- **Builds**: arch-melee weapons were not read at all (their loadouts missed); Necramech mods now count in the capacity;
  the Necramechs' own weapons (Ironbride, Arquebex) are shown; arch-guns have two Arcane slots (Mausolon's second Arcane
  was shown as an Exilus) — a slot holding an Arcane is always read as one.

## 0.4.9
- **Weekly, purchases to identify**: what is already known is used before asking. Offers whose limit is below the number
  bought, already taken by another purchase of the vendor, or shown on sale after the purchase are ruled out (✗); a group
  of purchases that can only be a set of offers is assigned at once (your 4 purchases of 10 at Palladino = the four
  Requiem relics); offers seen bought out on screen and shop items named in the game's log count as evidence; "which one
  did you NOT buy?" answers a whole group; the header shows where the game's log puts you.
- **Builds: mod pictures**: inside the cards the mod's artwork (WFCD CDN), on hover the whole card (wiki). Pictures saved
  by 0.4.7-0.4.8 under the wrong kind are sorted out by themselves.
- **Mod data fixed**: when several mods share a name (Vital Sense, Intensify, Heavy Impact, Hell's Chamber… have Beginner /
  Expert variants in the game data) the variant's max rank was used (10 instead of 5), so these mods counted less than
  they do at their rank (82 mods). Damage tags in mod texts are named ("chance to apply Slash on Critical").
- **Companion weapons**: 8 slots (an empty 9th showed), *Orokin Catalyst* instead of Reactor, the claws' slot is the
  *Posture*.
- **Riven flip**: more filters (price, fair price, profit, profit a day, score, in-game popularity, sales, re-rolls, days
  on sale, seller online now); fair price from rivens with the same stat combination first, one seller's copies count
  once; roll grade (S-D) of every stat in the detail panel.

## 0.4.8
Riven flip:
- **DE's weekly in-game riven trades** (official `weeklyRivensPC.json`, checked: still published every week; community
  archive as fallback): new *In game* column and a third part of the fair price.
- **Stat weights by weapon**: crit, status and slash weapons value their own stats; harmless negatives on minor
  physical damage types.
- **Profit a day** column and order (profit / expected days to sell).
- **Journal** of your flips: bought, listed (seen by the scans), sold (seen when your listing disappears, or by hand),
  profit and days; your resales correct the fair price.
- **Smarter scan order**: watched weapons rescanned within 2.5 days; weapons that sell, give deals or trade a lot sooner.
- **Alerts** (sound + Console) for deals above a profit whose seller is online; optional auctions to bid on.
- **Detail panel** (fair price parts, comparable rivens, price history chart), type / weapon filters, contacted mark,
  hide weapon / seller.
- **Fair price check**: how far off the fair price is on rivens that likely sold.

## 0.4.7
- **Where you are, from the game's log** (`EE.log`, read only): a vendor that lives in one place (Cetus, Fortuna, the
  Necralisk / Sanctum, the Chrysalith, Höllvania, Iron Wake, Duviri, the Drifter's camp, Simaris and Baro at a Relay) is
  no longer recognised by the OCR while you are elsewhere, for the prices and for the Weekly check; in a mission or an
  open world no automatic scan runs. Teshin, the Relay syndicates, Nightwave and events count everywhere.
- **Stricter vendor recognition**: 75 % of the items read must be one vendor's (was 60 %; new setting *Share of the
  items*), on top of the place check.
- **Riven flip, live check**: the 10 best deals are checked again on warframe.market every ~3 minutes, one request per
  deal: the *Seller* column shows whether the seller is in game / online now, and rivens no longer listed. Own limiter
  (6 a minute, never above 10), paused during riven scans; 15 minutes off after repeated "too many requests".
- **Builds: companion weapons**: Sentinel / MOA / Hound weapons were read as companions, beasts' claws were skipped:
  both now show with their mods (claws with the Posture slot).
- **Player strip**: credits tracked, a smaller Mastery Rank emblem in front of the MR, the profile picture in a box beside
  the name, the currencies from the box's left edge; Settings > General > *Currencies shown* picks which. "230k" no
  longer shows as "23k".
- **World > Arbitrations**: the next 72 hours (browse.wf's schedule) with node, mission, faction and arbi.guide tier,
  filter by tier.
- **Settings reorganised**: *Overlay* and *Overlays* are one tab; every tab split in named boxes; many names made
  clearer (the Overlay labels lose their "Price overlay:" / "Activities:" prefixes, now box titles).
- **Item pictures from cdn.warframestat.us** (WFCD images): one request per picture, tried before the wiki for the Builds
  tab and when warframe.market has no picture.

## 0.4.6
- **Warframe stats at rank 30**: health, shields and energy started from the rank-0 values of the public data; the
  rank gains are now added (+100 health, +100 shields, +50 energy at rank 30, spread over the ranks below). Cyte-09
  with your build: 325 / 235 / 150 / 655, 226 % / 45 % / 34 % / 298 %, as in the game.
- **Mods below max rank**: a mod gives (rank + 1) / (max rank + 1) of its effect, as in the game (Serration +15 % at
  rank 0); it was counted as rank / max rank (0 at rank 0, too low at every rank below max). Builds and planner.
- **Flat values**: Primed Reach and the like (+3 range) now add to the melee range.
- Stats are cut, not rounded, like the game shows them (655.5 -> 655).
- **Archon Shards in the stats**: Crimson (strength, duration +10 %) with the mods, Azure (health / shields / armor
  +150, energy +50) after every other bonus, Tauforged ×1.5; no shields for Inaros / Nidus / Kullervo, no energy for
  Hildryn / Lavos. Builds and planner (5 shard slots under the options; *Copy from my loadout* brings yours).
- **Incarnon perks in the weapon stats**: the chosen perks of Evolution II and up are read from the weapon's wiki page
  (damage, crit / status chance, crit multiplier, fire rate, magazine, reload, range…, per-variant values such as
  "(Prisma)" picked); effects with a condition (on headshot, after a kill…) are left out. The stats panel lists the
  perks counted.

## 0.4.5
- **Capacity fixed for slots marked `AP_UNIVERSAL`**: the game file writes it on slots without a polarity (an Exilus
  slot never Forma'd), and it was counted as a universal polarity that halves every mod's drain. Only `AP_ANY` (the Aura
  Forma) is universal. Cyte-09 with Sure Footed rank 3 in the Exilus: 6 / 74 as in the game (it said 10).

## 0.4.4
- **AlecaFrame's icons in the build screen** (icons folder, `img/builds` and `img/damageTypes`): an icon for every stat
  (health, shields, armor, energy, sprint, ability stats, fire rate, multishot, magazine, reload, critical, status) and
  every damage type, the bonus element's icon; Forma, Orokin Reactor / Catalyst, Exilus and Arcane adapter pictures by
  the title (faded when not installed) and on the planner's switches; empty Aura / Exilus / Stance slots show their
  picture and an empty Arcane slot AlecaFrame's empty-Arcane outline; Archon Shards and Helminth headings with their
  icon. Steel Essence and Pathos Clamp icons in the player strip. Without the folder everything looks as before.

## 0.4.3
- **Aya counted like AlecaFrame does**: the Aya item among your resources (`SchismKey`); what was shown as Aya before
  (the `PrimeTokens` field) is Regal Aya and is now shown as such. *Aya (typed by hand)* is used only when the file has
  none.
- **Activities: fold a category**: a click on the title of a syndicate, Weekly, Nightwave, the Calendar, Daily and
  weekly or Bought lately folds it to its title (▸) or opens it again (▾); remembered between sessions.
- **Capacity**: the Exilus slot's own polarity of the Warframes that have one (Gauss, Hildryn, Baruuk, Inaros…) is now
  counted. The capacity's tooltip lists every slot: polarity and where it comes from (Forma in the game file or the
  item's own), mod, rank, drain. **Copy data for a capacity check** (Builds) copies what the game file says about the
  item and how it was read, to report a capacity that differs from the game's.
- Aya icon in the player strip.

## 0.4.2
- **Arcanes drawn as in the game** (Builds and planner): no card, the generic picture of the Arcane's rarity, the name
  centred under it, the rank as ◈ / ◇. Only the Arcane slots the item can have; an empty slot shows the outline of an
  Arcane, with a 🔒 when it is not unlocked (a weapon without its Arcane adapter, from the game file).
- **Tooltips with the effect at the rank** on every mod and Arcane (slots and library): what it does at its rank and at
  max rank, from the wiki's data modules (read once in the background, kept in `wiki_mods.json`); lower ranks worked out
  from the game data, which is also used until the wiki has been read.

## 0.4.1
- **Weekly: vendor screen check tuned on real screens** (Palladino, Archimedean Yonta, Acrithis, Kaya Velasco, Flare
  Varleon, Teshin): an offer showing **PURCHASE LIMIT REACHED** on its card is read as bought out (the game keeps it in
  the list); amounts written before the name are understood ("35.000 X Kuva", "150,000 Credits", "6.000 Endo"); names on
  two lines and words the OCR glues together ("Requiem IRelic") are matched; the Requiem relics are recognised under
  their screen name (also in the Weekly tab); close names (Requiem I / II Relic) are no longer confused; the vendor named
  in the header (read loosely, the OCR often keeps only part of it) decides which vendor's offers are looked for.
- **Incarnon**: Evolution V is shown only on weapons that have it (Incarnon built in); Genesis weapons show their four
  tiers (the wiki's table decides when it was read). The planner's evolution tier follows.

## 0.4.0
- **Builds: laid out like the game's upgrade screen.** *UPGRADES / ITEM [rank]* with the Forma count, configuration
  tabs (Config A, B, C…), the capacity bar (left / total, as the game shows it) and the stats on the left, Aura / Stance /
  Exilus on top of the eight mods, the Arcanes (and the Exilus of guns) on the right, the *Unique trait* row of Kuva /
  Tenet / Coda weapons. Cards are landscape like the game's: art behind the name, drain and polarity, rank pips, a frame
  in the rarity's colour.
- **Weapon stats** in Builds and in the planner: fire rate / attack speed, multishot, magazine, reload, critical chance
  and damage, status, every damage type with the elements combined in mod order (the Kuva / Tenet / Coda bonus element
  counted as the weapon's own), total and an approximate damage per second, *base ▸ modded*.
- **Build planner: a simulator.** A mod library under the build (search, polarity filter, sort, *Only mods I own* with
  the copies you have); click a slot then a mod, or drag a mod onto a slot; mods the game does not let you combine are
  refused. Right-click a slot for rank, polarity (Forma) and removal. Switches for the Orokin Reactor / Catalyst,
  Exilus and Arcane adapters (locked slots show 🔒), the Kuva / Tenet / Coda bonus element and percentage (Valence
  Fusion), the Incarnon Genesis and its evolution tier, with the perk of each tier chosen on the evolution path.
  Configurations A, B, C… per item; *Actions*: copy / rename / delete a configuration, remove every Forma, Forma every
  slot to its mod's polarity. Exilus slots take only Exilus mods. Companion weapons (robotic weapons, beasts' claws with
  their posture) can be planned too. Plans of older versions open as they were.
- **Simulate in the planner** (Builds): opens the item shown, with all its configurations, in the planner.
- **Incarnon**: the evolution tiers drawn as a path (every perk, the chosen ones lit and joined). Perk names are read
  from the wiki page's evolution table itself (rendered page first, then the wikitext), *EVO1…* rows as well as
  *Evolution I…* rows, a tier label spanning several rows included; tier I of built-in weapons (no perk name on the
  wiki) is shown as the Incarnon form. Pages read by the old reader are read again by themselves, so the remaining
  "option 1 / 2" go away.
- **Weekly: check on the vendor screen.** While a vendor is scanned, the limited offers it lists are read too: an
  offer you bought out disappears from the list. A still-listed offer is ruled out for a purchase being identified (and a
  purchase wrongly taken for it is asked again); one that vanished since an earlier look this period (not a scroll: the
  rest of the list stayed put) identifies the purchase, or shows as bought **(OCR)** until the game file catches up.
- **Activities: what you can buy before the reset.** The standing you can still earn today (daily cap, never past what
  your rank holds) is spent like the standing you have: *Before the reset: buy 2× Martyr Symbiosis (earn 13,000 more)*,
  in light blue, with the time left to 00:00 UTC. Colour and on/off in Settings.
- **Kuva** in the player strip, with its icon.

## 0.3.9
- **Incarnon perks read again**: the wiki's evolution table (rows *EVO1…EVO5*) is now understood, so the Builds tab
  names the perk chosen in each tier (Torid: Incarnon Form, Final Fusillade…); pages that failed before are read again.
- **Builds: the right weapon for each companion**: every companion showed the same weapon; now Sentinels / MOAs show
  their robotic weapon and beasts their claws.
- **Player strip: more currencies, with icons**, under name and MR: Pathos Clamps, Riven Slivers, Live Heartcells and
  Vitus Essence next to Steel Essence, each with its game icon (AlecaFrame's icons folder, else browse.wf).
- **Weekly: your currencies** for the vendors shown (Steel Essence for Teshin, Pathos Clamps for Acrithis, Riven Slivers
  for Palladino…).
- **Sounds**: optional sound when a vendor, riven or price scan starts (Settings → Sounds).
- **Riven flip: Copy whisper** (right click): `/w <seller> Hi, I would like to buy <weapon> <riven> for <price>
  platinum`, template editable in Settings.

## 0.3.8
- **Activities: buy with all your standing**: each syndicate's standing is spent on its best items, as many copies as
  it pays for (*Buy 2× Martyr Symbiosis (20,000 standing)* with 27,000), the rest on the next item, never more copies
  than the market takes in a day. A bought item stays on the list for tomorrow (setting *Activities: keep an item after
  buying it*).
- **Activities purchases → Quantframe**: every purchase Activities confirms from the game file is kept; *Bought
  (Activities) → Quantframe…* (Weekly tab, and Activities' ⚙ menu) sends the ones not sent yet to Quantframe's stock.
  (The Weekly button of 0.3.6, which sent every weekly purchase, is replaced by this.)
- **Build planner: whole loadouts**: Warframe, weapons, companion, Archwing, Arch-gun and Arch-melee in one plan, saved
  together; *Copy from my loadout…* copies a whole in-game loadout. Companion, Archwing, Arch-gun and Arch-melee items and
  mods added to the bundled data.
- **Builds: more from the game file**: your item names, Focus lens, Kuva / Tenet / Coda bonus element and percentage,
  gilded, Exilus / Arcane slot unlocked, Valence Fusion.
- **Weekly: event vendors only while the event runs** (Jade Shadows, Duviri Murmur, Triad…, from DE's world state;
  *Show ended events* to see them anyway); their offers leave Activities too.
- **Steel Essence** in the player strip.
- **Riven auto scan on by default** (every 6 hours) and **never at the same time as a price update**: the second one
  waits for the first (an automatic one simply tries later), so warframe.market's limits are not exceeded.
- **Profile moved into Settings** (a page of it), and a new **Overlays** page: price overlay label sizes, background,
  colours; Activities background, font, colours and contents.

## 0.3.7
- **Blueprints are no longer priced as the finished item**: a vendor that sells a blueprint (Purified Heciphron
  Blueprint, Zymos Blueprint…) was matched to the finished item on warframe.market when the blueprint itself is not
  traded, so it was recommended at the item's price. Now a blueprint counts only as itself, both in the vendor lists and
  in your inventory; only Prime parts (whose market items are the blueprints) keep the item name as an alternative.
- **Builds: Incarnon** section: Genesis adapter installed / built in / on another variant, evolution tier reached and
  the perk chosen in each tier (from the game file), perk names and picture from the weapon's wiki page; the tier is also
  shown under the title.
- **No more white windows**: the world strip was shown before being put in the window, so it opened for a moment as a
  separate (white) window; widgets taken out of a layout are now hidden before being deleted instead of being detached.
- Incarnon perk names: when the page's wikitext only calls a template, the rendered page is read instead; a page that
  still cannot be understood is saved in the `incarnon_debug` folder of the data folder.

## 0.3.6
- **AlecaFrame's file read once, in the background**: every tab used to watch, decrypt and parse `lastData.dat` on its
  own on the window's thread each time AlecaFrame rewrote it. Now one watcher waits until the file has finished
  changing, a background thread decrypts and parses it once (skipped when the content is identical) and does each tab's
  work (inventory matching, standing, loadouts, weekly purchases) there; the window only shows the results. The Console
  says how long it took.
- **Weekly: Bought → Quantframe…** sends what you bought at the limited vendors this period to Quantframe's stock.
- **Player strip: profile glyph and Mastery Rank emblem** (pictures from browse.wf, downloaded once).
- **Activities: trades left today** in the daily and weekly section.
- **Max-rank prices that mean nothing are dropped**: mods with only 3 ranks whose max rank sells for at most 3p more
  than rank 0, and max ranks traded less than *Max-rank price: smallest trades a day* (7-day average, default 0.5): the
  max-rank price is not shown nor counted (overlay, price list, inventory value, rank-up and sell advice).
- **Old prices refreshed by themselves**: rows of the price list and recommendations older than 2 hours (setting
  *Refresh data older than (hours)*) are updated automatically, 150 at a time, recommended and oldest first.
- **Recommendations and sell advice with trading signals** (`signals.py`): expected sale price from the 30-day
  average, an EMA 7 / EMA 30 trend, the item's own backtest calibration and the best buy order online (bid); *Trend*
  column with *sell now* (falling or a Bollinger spike) / *wait* (rising), and a *Signal* column in the sell advice.
- **Riven flip: listing age**: *On sale for* column (creation date on warframe.market); listings older than 14 days
  (setting) are not shown as deals and those older than 28 are left out of the fair price, which now counts offline
  sellers' listings too.

## 0.3.5
- **Nightwave completion read from the right place**: the game file's *SeasonChallengeHistory* lists every challenge you
  are given (this week's elite ones are there before you do them), so it marked everything done. Completion now comes
  from the challenge counters (*ChallengeProgress*) against the amount each challenge requires; unfinished ones show
  their progress (14/15). The Console lists what was read.
- **Nightwave daily challenges** (☼) are listed too, with the time left; the Calendar's active challenge shows its
  progress.
- **Netracells** in the daily and weekly section (done of 5 this week, from the game file).

## 0.3.4
- **Nightwave completion fixed**: a challenge counts as done when its id is in the game file's history, or when the same
  challenge is there with an id of the same season and week (the world state and the file can write ids differently;
  `$id` ids are read too). The Console says how many active challenges were found completed and which ids were compared.
- **Activities: daily and weekly** section: Sortie and Archon Hunt (missions done of 3, from the missions the game file
  lists as completed), Elite Deep / Temporal Archimedea (started and score; whether it is finished the file does not say:
  (?), right-click to tick it by hand until the reset) and Descendia (floors reached, normal and Steel Path). Setting
  *Activities: Sortie, Archon Hunt, Archimedea, Descendia* and ⚙ option.

## 0.3.3
- **Riven flip: price history and trend.** Every scan now records, per weapon and per day, the median asking price,
  the cheapest one and the number of listings (180 days), shown in the new *Trend* column (7 / 30 days). A weapon whose
  prices are falling gets its fair price lowered by the fall (⚠), so crashing weapons are not shown as deals.
- **Riven flip: fair price from likely sales.** Listings that disappear within 5 days of being listed are kept with
  their price and stats (30 days); with at least 3 comparable ones the fair price leans on them (✔, tooltip with both
  figures and how long rivens of that weapon stay listed).
- **Riven flip: scheduled scans** every N hours while the program runs (setting *Scan by itself every (hours)*, 0 = off;
  the tab shows when the next one is due).
- **Activities: where to buy.** Under every item to buy, the NPC and place that sell it (⌖ *Hok, Cetus* for Zaw parts
  and Exodia arcanes, *Rude Zuud, Fortuna* for kitgun parts and Pax arcanes, *Father, Necralisk* for Entrati weapons,
  *any Relay* for the faction syndicates…). Setting *Activities: where to buy* and ⚙ option.
- **Activities: Nightwave and Calendar goals at a glance.** Each challenge shows its goal on a short line under its
  name (*Kill 1,000 Enemies on The Steel Path*), in the program's language (Italian names and descriptions from the game's
  own Italian text).

## 0.3.2
- **Activities: clickable with the game's cursor.** In many menus Warframe hides the Windows cursor and draws its own,
  so the overlay thought you were in a mission and let every click through. Now it also becomes clickable when the cursor
  moves onto it freely (in a mission the camera keeps the hidden cursor still and confined, so clicks still go to the
  game there).
- **Nightwave and 1999 Calendar read again**: Digital Extremes moved its world state to
  `api.warframe.com/cdn/worldState.php` (the old address answers 404); the old one stays as a fallback, and the Console
  names the error of each.
- **Source code reorganised** into folders: `app/core`, `app/scan`, `app/trade`, `app/game`, `app/ui`, with the bundled
  data in `data/`, the icon in `assets/` and the data builders in `tools/` (see the README's *Project layout*). Nothing
  changes for you: same program, same data folder.

## 0.3.1
- **Update window shows what changed**: every version between the one you have and the new one (newest first, from
  the changelog in your language), in a scrollable list above Install / Later / Skip.
- **Overlay stars**: *★ Best here ★* is now the best purchase among **all** the items of the vendor you are looking at
  (not only the rows on screen; the status line names it if it is scrolled away), and *★ Recommended ★* marks the
  items among the best purchases **across all vendors** (the Recommendations ranking).
- **Standing plan renamed *Activities*** (overlay title, settings, tray, hotkey label).
- **Activities: Nightwave and 1999 Calendar**: this week's Nightwave challenges (elite ones marked ★, standing shown,
  open dailies counted) and the current 1999 Calendar season's challenges (the one in progress marked), read from
  Digital Extremes' public world state (content.warframe.com, every 10 minutes, saved copy when offline). Completion is
  read from lastData.dat: Nightwave by the challenge id in *SeasonChallengeHistory* (exact), the Calendar from
  *CalendarProgress* (days up to the last completed one). Setting *Activities: Nightwave and 1999 Calendar* and ⚙ option.
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
  not say which offer was bought, the program looks at what AlecaFrame recorded as gained in **deltas.dat** (the last
  mission or visit, item by item: an offer whose item came in exactly in its amount wins, e.g. Kuva +10,000 = the ×10,000
  offer) and at your inventory against the previous sync, and assigns it when only one offer fits; otherwise it asks you, with the offers whose item went up
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
