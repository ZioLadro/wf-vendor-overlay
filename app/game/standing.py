"""Your standing per syndicate, and how much of an item it lets you buy.

Source: your AlecaFrame lastData.dat (or the companion-app JSON), or numbers typed by hand in the Profile tab.
The file is a snapshot: import it again to update.
"""
import json
import os
import time

from app.core.config import APP_DIR
from app.game.inventory import game_names

STANDING_FILE = APP_DIR / "standing.json"


class ProfileError(Exception):
    pass


HIDDEN_EVENT = "EventSyndicate"          # Operational Supply (Plague Star and other events): not running most of the time


def is_hidden(tag) -> bool:
    """Syndicates left out everywhere: Nightwave (its own system), and Operational Supply when the setting says so."""
    from app.core.config import CFG
    return bool(tag) and (is_nightwave(tag) or (tag == HIDDEN_EVENT and bool(CFG.get("hide_operational_supply", True))))


def is_nightwave(tag: str) -> bool:
    """Nightwave series and the like: not real syndicates, left out everywhere."""
    return str(tag).startswith(("RadioLegion", "Nightcap"))


def syndicate_name(tag: str) -> str:
    return game_names().get("syndicates", {}).get(tag) or tag


DAILY_ALIAS = {"Pvp": "ConclaveSyndicate", "Cavia": "EntratiLabSyndicate", "Ventkids": "VentKidsSyndicate"}
DAILY_SHARED = ("SteelMeridianSyndicate", "ArbitersSyndicate", "CephalonSudaSyndicate", "NewLokaSyndicate",
                "PerrinSyndicate", "RedVeilSyndicate")      # the six original syndicates share one daily cap


def parse_daily(res: dict) -> dict:
    """{tag: standing you can still earn today} from the DailyAffiliation* fields."""
    out = {}
    for k, v in res.items():
        if k.startswith("DailyAffiliation") and isinstance(v, (int, float)):
            suf = k[len("DailyAffiliation"):]
            if not suf:
                for tag in DAILY_SHARED:
                    out[tag] = int(v)
            else:
                out[DAILY_ALIAS.get(suf, suf + "Syndicate")] = int(v)
    return out


def parse_profile(data) -> dict:
    """{"mr": int|None, "factions": {tag: {"standing": int, "rank": int|None}}} from the profile JSON.
    Tolerant: looks for the first result and any list of {Tag, Standing, Title} affiliations."""
    res = data
    if isinstance(data, dict) and isinstance(data.get("Results"), list) and data["Results"]:
        res = data["Results"][0]
    if not isinstance(res, dict):
        raise ProfileError("unexpected profile format")
    mr = res.get("PlayerLevel")
    aff = res.get("Affiliations")
    if aff is None and isinstance(data, dict):
        aff = data.get("Affiliations")
    rank_min = game_names().get("rank_min", {})
    factions = {}
    for a in aff or []:
        if isinstance(a, dict) and a.get("Tag") and not is_nightwave(a["Tag"]):
            st, rk = a.get("Standing"), a.get("Title")
            st = int(st) if isinstance(st, (int, float)) else 0
            rk = int(rk) if isinstance(rk, (int, float)) else None
            # the file keeps the TOTAL standing; the game (and the vendor) shows it from the start of your rank
            base = rank_min.get(str(a["Tag"]), {}).get(str(rk), 0) if rk and rk > 0 else 0
            factions[str(a["Tag"])] = {"standing": st - base if st >= base else st, "rank": rk}
    for tag, left in parse_daily(res).items():
        if tag in factions:
            factions[tag]["daily"] = left
    tr = res.get("TradesRemaining")
    return {"mr": int(mr) if isinstance(mr, (int, float)) else None, "factions": factions,
            "trades": int(tr) if isinstance(tr, (int, float)) else None, "synced": sync_time(res),
            "wallet": wallet(res), "avatar": str(res.get("ActiveAvatarImageType") or "")}


TRACKED = {"steel": "/Lotus/Types/Items/MiscItems/SteelEssence", "pathos": "/Lotus/Types/Gameplay/Duviri/Resource/DuviriDragonDropItem",
           "sliver": "/Lotus/Types/Items/MiscItems/RivenFragment", "heartcell": "/Lotus/Types/Items/MiscItems/CodaWeaponBucks",
           "vitus": "/Lotus/Types/Items/MiscItems/Elitium"}


def wallet(res) -> dict:
    """What you hold: Endo (FusionPoints), platinum (paid + free), ducats (the PrimeBucks item), Aya (PrimeTokens), Regal Aya,
    credits. Missing values are left out."""
    out = {}
    if not isinstance(res, dict):
        return out
    num = lambda v: int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    if num(res.get("FusionPoints")) is not None:
        out["endo"] = num(res["FusionPoints"])
    if num(res.get("PremiumCredits")) is not None:
        out["plat"] = num(res["PremiumCredits"]) + (num(res.get("PremiumCreditsFree")) or 0)
    if num(res.get("RegularCredits")) is not None:
        out["credits"] = num(res["RegularCredits"])
    duc = sum(int(it.get("ItemCount") or 0) for it in res.get("MiscItems") or []
              if isinstance(it, dict) and str(it.get("ItemType", "")).endswith("/MiscItems/PrimeBucks"))
    out["ducats"] = duc
    counts = {}
    for it in res.get("MiscItems") or []:
        if isinstance(it, dict):
            counts[str(it.get("ItemType", ""))] = counts.get(str(it.get("ItemType", "")), 0) + int(it.get("ItemCount") or 0)
    for key, path in TRACKED.items():                 # Steel Essence, Pathos Clamps, Riven Slivers, Live Heartcells, Vitus Essence
        out[key] = counts.get(path, 0)
    if num(res.get("PrimeTokens")) is not None:
        out["aya"] = num(res["PrimeTokens"])
    if num(res.get("RegalCredits")):
        out["regal"] = num(res["RegalCredits"])
    return out


def sync_time(res):
    """When the game last sent this inventory (unix seconds), from the id in LastInventorySync (its first 4 bytes are a
    timestamp). None if the file has no such field. The trades left are only as fresh as this moment."""
    v = res.get("LastInventorySync") if isinstance(res, dict) else None
    oid = v.get("$oid") if isinstance(v, dict) else v
    try:
        return int(str(oid)[:8], 16)
    except (TypeError, ValueError):
        return None


def trades_stale(synced, now=None) -> bool:
    """True when the inventory was synced before the last daily reset (00:00 UTC): the trades left have been reset since."""
    if not synced:
        return False
    now = time.time() if now is None else now
    return synced < now - (now % 86400)


def read_raw(path: str) -> bytes:
    """The file's bytes (a few tries: AlecaFrame may be writing it). Raises ProfileError."""
    err = None
    for _ in range(3):
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError as e:
            err = e
            time.sleep(0.3)
    raise ProfileError(f"{type(err).__name__}: {err}")


def signature(raw: bytes) -> str:
    import hashlib
    return hashlib.md5(raw).hexdigest()


def read_file(path: str) -> dict:
    """Reads your standing from an inventory file (see parse_bytes). Raises ProfileError."""
    return parse_bytes(read_raw(path), path)


def parse_bytes(raw: bytes, path: str) -> dict:
    """AlecaFrame's lastData.dat or the companion-app JSON (both carry PlayerLevel and Affiliations)."""
    try:
        if path.lower().endswith(".dat"):
            from app.game.inventory import decrypt_last_data
            text = decrypt_last_data(raw)
        else:
            from app.game.inventory import unwrap_inventory
            text = unwrap_inventory(raw.decode("utf-8-sig"))
        data = json.loads(text)
    except ImportError:
        raise ProfileError("the 'cryptography' package is needed: pip install cryptography")
    except Exception:
        raise ProfileError("the file could not be decoded")
    prof = parse_profile(data)
    if not prof["factions"]:
        raise ProfileError("no syndicate standing found in the file")
    return prof


class StandingStore:
    def __init__(self):
        self.name = ""
        self.path = ""
        self.mtime = 0
        self.sig = ""          # fingerprint of the last file read (the modification time is unreliable while another
        self.trades = None     # program keeps the file open)
        self.wallet = {}       # Endo, platinum, ducats, Aya... (see wallet)
        self.avatar = ""       # the profile glyph chosen in the game (item path)
        self.synced = None     # when the game last synced the inventory (see sync_time)
        self.mr = None
        self.fetched = None
        self.factions = {}     # tag -> {"standing": int, "rank": int|None, "manual": bool}
        self.version = 0       # grows at every change (lets tables know when to rebuild)
        self.load()

    def load(self):
        try:
            d = json.loads(STANDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        self.name, self.mr, self.fetched = d.get("name", ""), d.get("mr"), d.get("fetched")
        self.path = d.get("path", "")
        self.factions = {k: v for k, v in (d.get("factions") or {}).items() if isinstance(v, dict) and not is_nightwave(k)}
        self.trades, self.synced = d.get("trades"), d.get("synced")
        self.wallet = d.get("wallet") or {}
        self.avatar = d.get("avatar") or ""

    def save(self):
        tmp = STANDING_FILE.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"name": self.name, "trades": self.trades, "synced": self.synced, "wallet": self.wallet, "avatar": self.avatar, "path": self.path, "mr": self.mr, "fetched": self.fetched,
                                       "factions": self.factions}, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, STANDING_FILE)
        except OSError:
            pass

    def apply_profile(self, path: str, profile: dict):
        try:
            self.mtime = os.path.getmtime(path)
        except OSError:
            self.mtime = 0
        self.path, self.mr, self.fetched = path, profile["mr"], int(time.time())
        self.trades, self.synced = profile.get("trades"), profile.get("synced")
        self.wallet = profile.get("wallet") or {}
        self.avatar = profile.get("avatar") or self.avatar
        self.factions = {k: v for k, v in self.factions.items() if not is_nightwave(k)}
        for tag, f in profile["factions"].items():
            self.factions[tag] = {"standing": f["standing"], "rank": f["rank"], "manual": False,
                                  "daily": f.get("daily")}
        self.version += 1
        self.save()

    def set_manual(self, tag: str, standing: int, rank=None):
        cur = self.factions.get(tag, {})
        self.factions[tag] = {"standing": max(0, int(standing)),
                              "rank": cur.get("rank") if rank is None else rank, "manual": True,
                              "daily": cur.get("daily")}
        self.version += 1
        self.save()

    def get(self, tag):
        return self.factions.get(tag) if tag else None


def affordability(entries, store: StandingStore) -> list:
    """For each standing entry of an item: how many you can buy with the standing you have.

    Returns [{"vendor","tag","cost","req_rank","have","rank","count","rank_ok"}]; `have`/`count` are None
    when nothing is known about that syndicate."""
    out = []
    for e in entries:
        f = store.get(e.get("t"))
        have = f["standing"] if f else None
        rank = f.get("rank") if f else None
        req = e.get("r") or 0
        out.append({"vendor": e["v"], "tag": e.get("t"), "cost": e["s"], "req_rank": req, "have": have,
                    "rank": rank, "count": (max(0, have) // e["s"]) if (have is not None and e["s"] > 0) else None,
                    "rank_ok": (rank >= req) if rank is not None else None})
    return out


_STORE = None


def get_store() -> StandingStore:
    global _STORE
    if _STORE is None:
        _STORE = StandingStore()
    return _STORE


def afford_text(entries, store=None) -> str:
    """Tooltip: how many of the item you can buy with your standing, per faction."""
    from app.core.i18n import t
    store = store or get_store()
    lines = []
    for a in affordability(entries, store):
        syn = syndicate_name(a["tag"]) if a["tag"] else a["vendor"]
        if a["count"] is None:
            lines.append(t("aff.unknown", vendor=a["vendor"], syn=syn))
            continue
        line = t("aff.line", vendor=a["vendor"], syn=syn, count=a["count"], have=f"{a['have']:,}".replace(",", " "),
                 cost=f"{a['cost']:,}".replace(",", " "))
        if a["rank_ok"] is False:
            line += t("aff.rank_low", req=a["req_rank"], rank=a["rank"])
        lines.append(line)
    return "\n".join(lines)
