"""Where you are in the game, read from Warframe's own log (EE.log in %LOCALAPPDATA%\\Warframe).

The game writes a line every time it loads a place:
  - "<level> generating layout with segments" (/Lotus/Levels/Proc/PlayerShip = the Orbiter,
    /Lotus/Levels/Proc/CivilianHubs/OstronTown = Cetus, /Lotus/Levels/Proc/Hub/RelayStationHubMain = a Relay…);
  - "ThemedSquadOverlay.lua: Host loading {"name":"CetusHub4…"}" with the star-chart node (CetusHub4, SolNode228…).
The last one tells the place: a hub (Relay, Cetus, Fortuna, Necralisk, Chrysalith, Höllvania…), the Orbiter, the
Drifter's camp, a mission, or "" when the line is not one we know (then nothing is ruled out).

What it is used for: a vendor that lives in one place (Cetus' Ostron, Fortuna's Nightcap, Archimedean Yonta in the
Chrysalith…) cannot be the screen read by the OCR while you are somewhere else; in a mission no automatic scan runs.
Vendors you can open from anywhere (Teshin, the Relay syndicates, Nightwave, events…) have no place.

Only the end of the file is read (the last 4 MB at first, then what was added since), in the scan thread."""
import os
import re
import threading
import time
from pathlib import Path

MAX_FIRST = 4 * 1024 * 1024
_LAYOUT = re.compile(r"(/Lotus/Levels/\S+?)\s+generating layout", re.I)
_HOST = re.compile(r"Host loading\s*\{[^}]*?\"name\"\s*:\s*\"([^\"]+)\"", re.I)
_NODE = re.compile(r"^([A-Za-z]*(?:Node|HUB|Hub)\d*[A-Za-z0-9]*)")
_STORE = re.compile(r"(/Lotus/StoreItems/[A-Za-z0-9_/]+)")      # an item of a shop named in a log line (a purchase?)
PLACE_NAMES = {"orbiter": "Orbiter", "camp": "Drifter's camp", "cetus": "Cetus", "fortuna": "Fortuna",
               "necralisk": "Necralisk / Sanctum", "chrysalith": "Chrysalith", "hollvania": "Höllvania",
               "ironwake": "Iron Wake", "hunhow": "Hunhow's hub", "relay": "Relay", "duviri": "Duviri", "dojo": "Dojo",
               "mission": "mission"}

# star-chart node / level path (regular expression, checked in order) -> place
NODE_PLACES = {"CetusHub4": "cetus", "SolarisUnitedHub1": "fortuna", "DeimosHub": "necralisk", "EntratiLabHub": "necralisk",
               "ZarimanHub": "chrysalith", "SolNode234": "chrysalith", "1999Hub": "hollvania", "IronwakeHUB3": "ironwake",
               "JadeShadows2HUB": "hunhow", "MercuryHUB": "relay", "EarthHUB": "relay", "TradeHUB1": "relay",
               "SaturnHUB": "relay", "PlutoHUB": "relay", "ErisHUB": "relay", "VenusHUB": "relay", "CeresHUB": "relay",
               "EuropaHUB": "relay", "JupiterHUB": "relay"}
LEVEL_PLACES = [(r"/PlayerShip\b", "orbiter"), (r"TNWDrifterCamp", "camp"), (r"OstronTown|CetusHub", "cetus"),
                (r"SolarisUnitedTown", "fortuna"), (r"Necralisk|EntratiSecretLab|EntratiLab", "necralisk"),
                (r"ZarimanHub", "chrysalith"), (r"TennoProtoRelayHUB|Hollvania|1999Hub", "hollvania"),
                (r"ForestSteelMeridianQuestBase|Ironwake", "ironwake"), (r"JS2MHub", "hunhow"),
                (r"RelayStationHub|/Hub/Relay", "relay"), (r"Dormizone|DuviriHub|Duviri/.*Hub", "duviri"),
                (r"/Lotus/Levels/Clan/|/Dojo", "dojo")]

# vendor (name in vendors.json / weekly.json, or its manifest path) -> where it is: regular expression -> place.
# The Relay syndicates, Teshin, Nightwave, events, Focus schools and the like are left out: no place.
VENDOR_PLACES = [(r"^Cetus\b|^Ostron\b|^The Quills|/Ostron/|/Cetus/", ("cetus",)),
                 (r"^Fortuna\b|^Solaris United|^Vox Solaris|^Ventkids|Nightcap|/Solaris/", ("fortuna",)),
                 (r"^Deimos\b|^Entrati$|^Necraloid|^Cavia|/Deimos/|/EntratiLabs/|/Entrati/", ("necralisk",)),
                 (r"Archimedean|^The Holdfasts|^Zariman\b|/Zariman/", ("chrysalith",)),
                 (r"^1999\b|^The Hex\b|/TheHex/", ("hollvania",)),
                 (r"^Ironwake|Ironwake", ("ironwake",)),
                 (r"Hunhow", ("hunhow",)),
                 (r"^Chipper|Kahl|/Drifter/", ("camp",)),
                 (r"^Acrithis|^Duviri\b|/Duviri/", ("duviri",)),
                 (r"^Cephalon Simaris|Perrin ?Sequence ?Weapon|Baro", ("relay",))]
HUBS = {"relay", "cetus", "fortuna", "necralisk", "chrysalith", "hollvania", "ironwake", "hunhow", "camp", "duviri", "dojo"}


def log_path() -> Path:
    from app.core.config import CFG
    own = str(CFG.get("ee_log_path") or "").strip()
    if own:
        return Path(own)
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Warframe" / "EE.log"


def vendor_places(vendor: str) -> tuple:
    """Where a vendor can be opened: a tuple of places, () = anywhere / not known."""
    v = str(vendor or "")
    for rx, places in VENDOR_PLACES:
        if re.search(rx, v, re.I):
            return places
    return ()


def place_of_level(level: str) -> str:
    for rx, place in LEVEL_PLACES:
        if re.search(rx, level or "", re.I):
            return place
    return ""


def place_of_node(node: str) -> str:
    """A star-chart node: its hub, or "mission" for an ordinary node (SolNode…, ClanNode…)."""
    m = _NODE.match(node or "")
    n = m.group(1) if m else (node or "")
    if n in NODE_PLACES:
        return NODE_PLACES[n]
    if re.match(r"^(SolNode|ClanNode)\d+$", n):
        return "mission"
    return ""


def parse_line(line: str):
    """(place, what) from one log line, or None when the line does not say where you are."""
    m = _HOST.search(line)
    if m:
        return place_of_node(m.group(1)), m.group(1)
    m = _LAYOUT.search(line)
    if m:
        return place_of_level(m.group(1)), m.group(1)
    return None


_PLAT = re.compile(r"^Platinum x (\d+)$", re.I)
_ITEM = re.compile(r"^(.+?)(?: x (\d+))?$")
_RIVEN = re.compile(r"^(?P<weapon>.+) (?P<name>[A-Za-z]+-[a-z]+(?:-[a-z]+)?)(?: \((?P<var>[^)]*)\))?$")


class TradeParser:
    """A trade in the game's log (the way Quantframe reads it): the confirmation dialog
      Script [Info]: Dialog.lua: Dialog::CreateOkCancel(description=Are you sure you want to accept this trade? You are offering
      <item lines>
      and will receive from <player> the following:
      <item lines>
      , leftItem=/Menu/Confirm_Item_Ok, rightItem=/Menu/Confirm_Item_Cancel)
    then "description=The trade was successful!" (or failed / was cancelled). feed() takes the log lines one by one and
    returns {"player","offered","received","plat_in","plat_out","rivens_in","rivens_out"} when a trade succeeded."""
    START = "Are you sure you want to accept this trade? You are offering"
    RECEIVE = "and will receive from "
    END = "leftItem=/Menu/Confirm_Item_Ok"

    def __init__(self):
        self.lines, self.collecting, self.pending = [], False, None

    def feed(self, line: str):
        if self.START in line:
            self.collecting, self.lines = True, [line.split(self.START, 1)[1]]
            if self.END in line:
                self._close()
            return None
        if self.collecting:
            self.lines.append(line)
            if self.END in line or len(self.lines) > 60:
                self._close()
            return None
        if self.pending and "Dialog::CreateOk" in line:
            if "The trade was successful" in line:
                done, self.pending = self.pending, None
                return done
            if "The trade failed" in line or "The trade was cancelled" in line:
                self.pending = None
        return None

    def _close(self):
        self.collecting = False
        text = "\n".join(self.lines).split(", leftItem=", 1)[0].split(", title=", 1)[0]
        if self.RECEIVE not in text:
            self.pending = None
            return
        give, rest = text.split(self.RECEIVE, 1)
        player, _sep, get = rest.partition(" the following:")
        player = "".join(c for c in player if not 0xE000 <= ord(c) <= 0xF8FF).strip()
        offered = [x.strip() for x in give.split("\n") if x.strip()]
        received = [x.strip() for x in get.split("\n") if x.strip()]
        self.pending = {"player": player, "offered": offered, "received": received,
                        "plat_out": self._plat(offered), "plat_in": self._plat(received),
                        "rivens_out": self._rivens(offered), "rivens_in": self._rivens(received)}

    @staticmethod
    def _plat(items):
        return sum(int(m.group(1)) for m in (_PLAT.match(x) for x in items) if m)

    @staticmethod
    def _rivens(items):
        """[(weapon, riven name)] of the revealed rivens among the items ("Torid Crita-visitis (RIVEN RANK 8)")."""
        out = []
        for x in items:
            m = _RIVEN.match(x)
            if m and not _PLAT.match(x):
                out.append((m.group("weapon").strip(), m.group("name")))
        return out


class Location:
    def __init__(self):
        self.lock = threading.Lock()
        self.path, self.pos, self.size = None, 0, 0
        self.place, self.what, self.t = "", "", 0.0
        self.mtime = 0.0
        self.history = []                 # [(time, place, what)] of the places loaded (the last 60)
        self.trades = []                  # completed trades seen in the log (see TradeParser), the last 100
        self.trade_seq = 0
        self._trade = TradeParser()
        self._first = True                # the first read (the end of an old log): its trades are not new
        self.store_hits = []              # [(time, /Lotus/StoreItems/… path)] named in the log (the last 300)

    def _feed(self, text: str, quiet=False):
        before = self.place
        now = time.time()
        for line in text.splitlines():
            tr = self._trade.feed(line)
            if tr and not quiet:
                self.trade_seq += 1
                tr.update(seq=self.trade_seq, t=now)
                self.trades = (self.trades + [tr])[-100:]
                try:
                    from app.core import logbus
                    logbus.add("eelog", f"trade with {tr['player']}: gave {', '.join(tr['offered']) or '–'}; "
                                        f"got {', '.join(tr['received']) or '–'}", "ok")
                except Exception:
                    pass
            if "/Lotus/StoreItems/" in line:
                for m in _STORE.finditer(line):
                    self.store_hits.append((now, m.group(1)))
                self.store_hits = self.store_hits[-300:]
            r = parse_line(line)
            if r:
                if not r[0] and self.place == "mission" and "Host loading" not in line:
                    continue                    # a mission's own tiles: still the mission chosen on the star chart
                if r[0] != self.place or not self.history:
                    self.history = (self.history + [(now, r[0], r[1])])[-60:]
                self.place, self.what = r
                self.t = now
        if self.place != before and not quiet:
            try:
                from app.core import logbus
                logbus.add("eelog", f"location: {self.place or '?'} ({self.what})")
            except Exception:
                pass

    def poll(self):
        """Reads what the game added to its log since the last time (the end of it the first time)."""
        with self.lock:
            p = log_path()
            try:
                st = p.stat()
            except OSError:
                self.place, self.what, self.mtime = "", "", 0.0
                return
            if p != self.path or st.st_size < self.pos:        # another file, or the game started over (new log)
                self._first = self.path is None                # a new log of a running program: its trades are new
                self.path, self.pos = p, max(0, st.st_size - MAX_FIRST)
                self.place, self.what = "", ""
            self.mtime = st.st_mtime
            if st.st_size == self.pos:
                return
            try:
                with open(p, "rb") as f:
                    f.seek(self.pos)
                    data = f.read(st.st_size - self.pos)
            except OSError:
                return
            cut = data.rfind(b"\n")                            # a line still being written: next time
            if cut < 0:
                return
            self.pos += cut + 1
            first, self._first = self._first, False
            self._feed(data[:cut + 1].decode("utf-8", "replace"), quiet=first)

    def current(self) -> str:
        """The place you are in ("" = not known: no log, an old log, or a place we do not recognise)."""
        from app.core.config import CFG
        if not CFG.get("ee_log", True):
            return ""
        self.poll()
        if not self.mtime or time.time() - self.mtime > 6 * 3600:   # the game is not running (an old log)
            return ""
        return self.place

    def allows(self, vendor: str, name: str = "") -> bool:
        """False only when the log says you are somewhere this vendor cannot be opened (vendor: its name or manifest
        path; name: its name too, when vendor is the path)."""
        here = self.current()
        places = vendor_places(name) or vendor_places(vendor)
        return not here or not places or here in places

    def recent_places(self, since=0.0) -> list:
        """The places loaded since that time (the log read so far), oldest first, without repeats."""
        self.poll()
        out = []
        for t, p, _w in self.history:
            if t >= since and p and p not in out:
                out.append(p)
        return out

    def store_items(self) -> set:
        """Shop items (/Lotus/StoreItems/…) the game's log named since the program started reading it."""
        self.poll()
        return {p for _t, p in self.store_hits}

    def trades_since(self, seq: int) -> list:
        """Completed trades seen in the log after that number (TradeParser), oldest first."""
        self.poll()
        return [x for x in self.trades if x["seq"] > seq]

    def in_mission(self) -> bool:
        return self.current() == "mission"


LOCATION = Location()
