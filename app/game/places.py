"""Where to buy a syndicate offering: the NPC and the place (shown in Activities next to "Buy …").

The NPC of the offerings sold by one specific vendor (Zaw parts at Hok, kitgun parts at Rude Zuud…) comes from
data/places.json (tools/build_places.py, by kind of item); every other offering gets its syndicate's own place
(DEFAULT). Vendors that are not a syndicate (Nightcap, Chipper, Teshin's Steel Path offers…) are named as they are."""
import json

from app.core.paths import DATA

# place key -> (English, Italian)
PLACES = {
    "relay": ("any Relay, the syndicate's room", "qualsiasi Relay, sala del sindacato"),
    "simaris": ("Cephalon Simaris, any Relay", "Cephalon Simaris, qualsiasi Relay"),
    "teshin": ("Teshin, any Relay (Conclave)", "Teshin, qualsiasi Relay (Conclave)"),
    "event": ("Operational Supply, any Relay (during the event)", "Operational Supply, qualsiasi Relay (durante l'evento)"),
    "cetus": ("Cetus (Earth)", "Cetus (Terra)"),
    "hok": ("Hok, Cetus", "Hok, Cetus"),
    "hailuk": ("Fisher Hai-Luk, Cetus", "Fisher Hai-Luk, Cetus"),
    "suumbaat": ("Old Man Suumbaat, Cetus", "Old Man Suumbaat, Cetus"),
    "teasonai": ("Master Teasonai, Cetus", "Master Teasonai, Cetus"),
    "onkko": ("Onkko, Cetus", "Onkko, Cetus"),
    "fortuna": ("Fortuna (Venus)", "Fortuna (Venere)"),
    "rudezuud": ("Rude Zuud, Fortuna", "Rude Zuud, Fortuna"),
    "legs": ("Legs, Fortuna", "Legs, Fortuna"),
    "business": ("The Business, Fortuna", "The Business, Fortuna"),
    "smokefinger": ("Smokefinger, Fortuna", "Smokefinger, Fortuna"),
    "littleduck": ("Little Duck, Fortuna", "Little Duck, Fortuna"),
    "roky": ("Roky, Fortuna", "Roky, Fortuna"),
    "necralisk": ("Necralisk (Deimos)", "Necralisk (Deimos)"),
    "father": ("Father, Necralisk", "Father, Necralisk"),
    "daughter": ("Daughter, Necralisk", "Daughter, Necralisk"),
    "son": ("Son, Necralisk", "Son, Necralisk"),
    "otak": ("Otak, Necralisk", "Otak, Necralisk"),
    "loid": ("Loid, Necralisk", "Loid, Necralisk"),
    "cavia": ("Sanctum Anatomica (Deimos)", "Sanctum Anatomica (Deimos)"),
    "holdfasts": ("Chrysalith (Zariman)", "Chrysalith (Zariman)"),
    "hex": ("Höllvania Central Mall (1999)", "Höllvania Central Mall (1999)"),
}
DEFAULT = {
    "SteelMeridianSyndicate": "relay", "ArbitersSyndicate": "relay", "CephalonSudaSyndicate": "relay",
    "PerrinSyndicate": "relay", "RedVeilSyndicate": "relay", "NewLokaSyndicate": "relay",
    "LibrarySyndicate": "simaris", "ConclaveSyndicate": "teshin", "EventSyndicate": "event",
    "CetusSyndicate": "cetus", "QuillsSyndicate": "onkko", "SolarisSyndicate": "fortuna", "VoxSyndicate": "littleduck",
    "VentKidsSyndicate": "roky", "EntratiSyndicate": "necralisk", "NecraloidSyndicate": "loid",
    "EntratiLabSyndicate": "cavia", "ZarimanSyndicate": "holdfasts", "HexSyndicate": "hex",
}
_items = None


def _norm(name) -> str:
    """Names compared without case and without " Blueprint" (the market and the game write some differently)."""
    n = str(name or "").lower().replace("’", "'").strip()
    return n[:-len(" blueprint")] if n.endswith(" blueprint") else n


def _data() -> dict:
    global _items
    if _items is None:
        try:
            raw = json.loads((DATA / "places.json").read_text(encoding="utf-8")).get("items") or {}
        except Exception:
            raw = {}
        _items = {tag: {_norm(n): k for n, k in d.items()} for tag, d in raw.items()}
    return _items


def where(tag, vendor, name) -> str:
    """Where to buy `name` (sold by `vendor` for `tag` standing), in the program's language; "" when unknown."""
    from app.core.config import CFG
    it = 1 if CFG.get("language") == "it" else 0
    key = _data().get(tag or "", {}).get(_norm(name)) or DEFAULT.get(tag or "")
    syndicate_vendor = not vendor or tag and DEFAULT.get(tag) and vendor in _syndicate_names()
    if key and syndicate_vendor:
        return PLACES[key][it]
    return vendor or (PLACES[key][it] if key else "")


_syn = None


def _syndicate_names():
    """The vendor names that are a syndicate itself (vendors.json lists syndicate offerings under its name)."""
    global _syn
    if _syn is None:
        try:
            g = json.loads((DATA / "gamenames.json").read_text(encoding="utf-8"))
            _syn = set((g.get("syndicates") or {}).values())
        except Exception:
            _syn = set()
        _syn |= {"Cavia", "Operational Supply"}
    return _syn
