"""Weekly rotations that are the same for every player and can be computed: the Duviri Circuit's choices and the Tenet /
Coda weapon offers.

Circuit: every Monday 00:00 UTC the normal Circuit offers 3 Warframes and the Steel Path Circuit 5 Incarnon Genesis
adapters, in fixed cycles (11 trios, 9 quintets). The live choices come from the world state (warframestat: the
duviriCycle's choices) when it is read; the cycle is then aligned on them, so the calendar of the next weeks follows the
game even if the cycles' starting point is off.

Tenet (Ergo Glast, Perrin Sequence) and Coda (Eleanor, Höllvania) weapons: offers renewed every 4 days. DE's vendor data
(public-export-plus ExportVendors, data/rotations.json) says what can be offered: Ergo Glast always all 5 Tenet weapons,
Eleanor one of two groups of 7 Coda weapons in turn. Each offer's bonus element and percentage come from a seed the
vendor draws with the game client's random generator, seeded by the vendor and the 4-day cycle. Generator, seeds and
order of draws as reconstructed by the open-source OpenWF server (SpaceNinjaServer, serversideVendorsService.ts and
rngService.ts): a computation, not a reading of the game: the program says so where it shows them."""
import json
import time
from datetime import datetime, timezone

from app.core.paths import DATA

WEEK = 7 * 86400
EPOCH = 1734307200                    # Monday 16 December 2024 00:00 UTC: Circuit week 0
CIRCUIT_NORMAL = [
    ["Nidus", "Octavia", "Harrow"], ["Gara", "Khora", "Revenant"], ["Garuda", "Baruuk", "Hildryn"],
    ["Excalibur", "Trinity", "Ember"], ["Loki", "Mag", "Rhino"], ["Ash", "Frost", "Nyx"],
    ["Saryn", "Vauban", "Nova"], ["Nekros", "Valkyr", "Oberon"], ["Hydroid", "Mirage", "Limbo"],
    ["Mesa", "Chroma", "Atlas"], ["Ivara", "Inaros", "Titania"]]
_HARD = [
    ["Boar", "Gammacor", "Angstrum", "Gorgon", "Anku"], ["Bo", "Latron", "Furis", "Furax", "Strun"],
    ["Lex", "Magistar", "Boltor", "Bronco", "Ceramic Dagger"], ["Torid", "Dual Toxocyst", "Dual Ichor", "Miter", "Atomos"],
    ["Ack & Brunt", "Soma", "Vasto", "Nami Solo", "Burston"], ["Zylok", "Sibear", "Dread", "Despair", "Hate"],
    ["Dera", "Sybaris", "Cestra", "Sicarus", "Okina"]]
_HARD_43 = ["Vectis", "Stug", "Ballistica", "Destreza", "Obex"]          # added with the game's 43.0
_HARD_LAST = ["Braton", "Lato", "Skana", "Paris", "Kunai"]
CIRCUIT_HARD = _HARD + [_HARD_43, _HARD_LAST]
CIRCUIT_HARD_OLD = _HARD + [_HARD_LAST]


def _norm(s) -> str:
    return "".join(c for c in str(s or "").lower() if c.isalnum())


def week_index(t=None) -> int:
    return int(((t or time.time()) - EPOCH) // WEEK)


def week_start(i: int) -> float:
    return EPOCH + i * WEEK


def _align(cycle, live) -> int | None:
    """The position of the live choices in a cycle (None: not found)."""
    want = sorted(_norm(x) for x in live or [])
    for i, c in enumerate(cycle):
        if sorted(_norm(x) for x in c) == want:
            return i
    return None


def _live():
    """(normal choices, hard choices) of this week from the last world state read, or (None, None)."""
    try:
        from app.game import world
        d = world.last()[1] or {}
    except Exception:
        d = {}
    dc = d.get("duviriCycle") or {}
    normal = hard = None
    for c in dc.get("choices") or []:
        cat = str(c.get("categoryKey") or c.get("category") or "").lower()
        if "normal" in cat:
            normal = c.get("choices")
        elif "hard" in cat:
            hard = [x.replace("Incarnon Genesis", "").strip() for x in c.get("choices") or []]
    return normal, hard


def circuit(weeks: int = 12, now=None) -> list:
    """[{start, end, normal: [3 Warframes], hard: [5 Incarnon weapons], live: bool}] from this week on."""
    now = now or time.time()
    w = week_index(now)
    live_n, live_h = _live()
    off_n = off_h = 0
    hard = CIRCUIT_HARD
    if live_n:
        i = _align(CIRCUIT_NORMAL, live_n)
        if i is not None:
            off_n = i - w % len(CIRCUIT_NORMAL)
    if live_h:
        for cyc in (CIRCUIT_HARD, CIRCUIT_HARD_OLD):
            i = _align(cyc, live_h)
            if i is not None:
                hard, off_h = cyc, i - w % len(cyc)
                break
    out = []
    for k in range(weeks):
        i = w + k
        out.append({"start": week_start(i), "end": week_start(i + 1),
                    "normal": CIRCUIT_NORMAL[(i + off_n) % len(CIRCUIT_NORMAL)],
                    "hard": hard[(i + off_h) % len(hard)],
                    "live": k == 0 and bool(live_n or live_h)})
    return out


# ---------- the game client's random generator (OpenWF's SRng) ----------
M64 = (1 << 64) - 1


def _i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def mix_seeds(a: int, b: int) -> int:
    """JavaScript: seed = a ^ b; seed ^= seed >>> 21; seed ^= seed << 35 (a shift of 3 in JS); seed ^= seed >>> 4;
    return seed >>> 0."""
    s = _i32(a) ^ _i32(b)
    s = _i32(s ^ ((s & 0xFFFFFFFF) >> 21))
    s = _i32(s ^ _i32(s << 3))
    s = _i32(s ^ ((s & 0xFFFFFFFF) >> 4))
    return s & 0xFFFFFFFF


class SRng:
    def __init__(self, seed: int):
        self.state = seed & M64

    def _step(self):
        self.state = (0x5851F42D4C957F2D * self.state + 0x14057B7EF767814F) & M64

    def randint(self, lo: int, hi: int) -> int:
        if hi != lo:
            self._step()
            lo += ((self.state >> 32) & 0x3FFFFFFF) % (hi - lo + 1)
        return lo

    def element(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def randfloat(self) -> float:
        self._step()
        return ((self.state >> 38) & 0xFFFFFF) * 0.000000059604645


ELEMENTS = [("Electricity", "InnateElectricityDamage"), ("Cold", "InnateFreezeDamage"), ("Heat", "InnateHeatDamage"),
            ("Impact", "InnateImpactDamage"), ("Magnetic", "InnateMagDamage"), ("Radiation", "InnateRadDamage"),
            ("Toxin", "InnateToxinDamage")]


def bonus(seed: int) -> tuple:
    """(element, percentage) of a Tenet / Coda weapon bought with this offer's seed (25 % to 60 %)."""
    r = SRng(seed)
    el = r.element(ELEMENTS)[0]
    v = r.randfloat()
    if v >= 0.941428:
        v = 1.0
    return el, round(25 + 35 * v, 1)


_data = None


def data() -> dict:
    global _data
    if _data is None:
        try:
            _data = json.loads((DATA / "rotations.json").read_text(encoding="utf-8"))
        except Exception:
            _data = {}
    return _data


def offers(vendor: str, now=None) -> dict:
    """{"vendor", "start", "end", "items": [{"path", "name", "element", "pct"}]} of Ergo Glast ("tenet") or Eleanor
    ("coda") for the 4-day cycle running at `now`."""
    v = (data().get("vendors") or {}).get(vendor)
    if not v:
        return {}
    now = now or time.time()
    dur = int(v["cycle"])
    idx = int((now - int(v["offset"])) // dur)
    start = int(v["offset"]) + idx * dur
    rng = SRng(mix_seeds(int(v["seed"]), idx))
    if v.get("one_bin"):
        items = [it for it in v["items"] if it["bin"] == idx % 2]
    else:                                              # every offer, each new one put first: the reverse order
        items = list(reversed(v["items"]))[:int(v.get("count") or len(v["items"]))]
    out = []
    for it in items:
        rng.randint(0, 0xFFFFFFFF)                     # the offer's id
        low = rng.randint(0, 0xFFFFFFFF)
        high = rng.randint(0, 0xFFFFFFFF)
        el, pct = bonus((high << 32) | (low & 0xFFFFFFFF))
        out.append({"path": it["path"], "name": it["name"], "element": el, "pct": pct})
    return {"vendor": vendor, "start": start, "end": start + dur, "items": out}


def fmt_day(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%d/%m")
