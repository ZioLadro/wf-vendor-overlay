"""The standing plan behind the in-game "plan" overlay: what to buy with standing (the Recommendations' picks), how much
standing each one still needs, what to do to earn that standing, and which purchases are done.

An item leaves the list only when the game file confirms the purchase: the program remembers how many copies you owned
when the item entered the list ("baseline") and, every time AlecaFrame rewrites lastData.dat (the inventory is read
again), checks whether you own more. Ticking an item yourself only marks it "bought, waiting for confirmation".
Saved in goals.json in the data folder."""
import json
import time

from app.core.config import APP_DIR, CFG

PLAN_FILE = APP_DIR / "goals.json"

# What earns standing with each syndicate (short, for the overlay). English and Italian.
ACTIVITIES = {
    "en": {
        "_relay": ["Missions with the syndicate's sigil equipped (standing from affinity)",
                   "Syndicate missions (Navigation → Syndicates)",
                   "Offer the syndicate's Medallions found in those missions"],
        "CetusSyndicate": ["Plains of Eidolon bounties (Konzu)", "Fish, gems and Grandmother's tokens traded in Cetus"],
        "QuillsSyndicate": ["Eidolon shards and Cetus Wisps traded to Onkko's Quills"],
        "SolarisSyndicate": ["Orb Vallis bounties (Eudico)", "Fish and gems traded in Fortuna"],
        "VoxSyndicate": ["Toroids traded to Little Duck (Orb Vallis caves, Profit-Taker)"],
        "VentKidsSyndicate": ["K-Drive races and tricks (Roky's Ventkids)"],
        "EntratiSyndicate": ["Cambion Drift bounties (Mother)", "Entrati tokens traded at the Necralisk"],
        "NecraloidSyndicate": ["Isolation Vault bounties", "Orokin Matrices and Cyphers traded to Loid"],
        "ZarimanSyndicate": ["Zariman bounties (Quinn)", "Void Angels and Zariman missions"],
        "EntratiLabSyndicate": ["Sanctum Anatomica bounties", "Cavia tokens traded at the Sanctum"],
        "HexSyndicate": ["Höllvania bounties (The Hex)"],
        "LibrarySyndicate": ["Synthesis scans of Simaris' daily target"],
        "ConclaveSyndicate": ["Conclave (PvP) matches and challenges"],
        "KahlSyndicate": ["Kahl's weekly mission (Break Narmer)"],
        "_other": ["Missions and bounties of {name}"],
    },
    "it": {
        "_relay": ["Missioni con il sigillo del sindacato equipaggiato (standing dall'affinità)",
                   "Missioni del sindacato (Navigazione → Sindacati)",
                   "Offri i Medaglioni del sindacato trovati in quelle missioni"],
        "CetusSyndicate": ["Taglie delle Piane di Eidolon (Konzu)", "Pesci, gemme e gettoni della Nonna scambiati a Cetus"],
        "QuillsSyndicate": ["Frammenti di Eidolon e Cetus Wisp scambiati con le Quills di Onkko"],
        "SolarisSyndicate": ["Taglie di Orb Vallis (Eudico)", "Pesci e gemme scambiati a Fortuna"],
        "VoxSyndicate": ["Toroidi scambiati con Little Duck (grotte di Orb Vallis, Profit-Taker)"],
        "VentKidsSyndicate": ["Gare e acrobazie in K-Drive (Ventkids di Roky)"],
        "EntratiSyndicate": ["Taglie del Cambion Drift (Mother)", "Gettoni Entrati scambiati al Necralisk"],
        "NecraloidSyndicate": ["Taglie delle Isolation Vault", "Matrici e Cifrari Orokin scambiati con Loid"],
        "ZarimanSyndicate": ["Taglie dello Zariman (Quinn)", "Angeli del Vuoto e missioni dello Zariman"],
        "EntratiLabSyndicate": ["Taglie del Sanctum Anatomica", "Gettoni Cavia scambiati al Sanctum"],
        "HexSyndicate": ["Taglie di Höllvania (The Hex)"],
        "LibrarySyndicate": ["Scansioni di sintesi del bersaglio giornaliero di Simaris"],
        "ConclaveSyndicate": ["Partite e sfide del Conclave (PvP)"],
        "KahlSyndicate": ["Missione settimanale di Kahl (Break Narmer)"],
        "_other": ["Missioni e taglie di {name}"],
    },
}
RELAY = ("SteelMeridianSyndicate", "ArbitersSyndicate", "CephalonSudaSyndicate", "PerrinSyndicate", "RedVeilSyndicate",
         "NewLokaSyndicate")


def activities(tag: str, name: str) -> list:
    lang = "it" if str(CFG.get("language", "en")).startswith("it") else "en"
    a = ACTIVITIES[lang]
    rows = a["_relay"] if tag in RELAY else a.get(tag) or a["_other"]
    return [r.replace("{name}", name) for r in rows]


def daily_cap(mr) -> int | None:
    """Standing you can earn per day with a syndicate: 16,000 + 500 × Mastery Rank."""
    return 16000 + 500 * int(mr) if mr is not None else None


def earnable_today(f: dict, store) -> int | None:
    """Standing still earnable today with a syndicate: what the game file said at the last sync, or the whole daily cap
    if that sync was before today's reset (00:00 UTC)."""
    from app.game.standing import trades_stale
    if trades_stale(store.synced):
        return daily_cap(store.mr)
    return f.get("daily")


def days_to(need: int, today, cap) -> int | None:
    """Days to earn `need` standing at the daily cap: 0 = already there, 1 = today, 2 = by tomorrow…"""
    if not need:
        return 0
    if today is not None and need <= today:
        return 1
    if not cap:
        return None
    rest = need - max(0, today or 0)
    return 1 + -(-rest // cap)


def owned(inv, slug: str) -> int:
    e = (inv.items or {}).get(slug) or {}
    return int(e.get("n", 0)) + int(e.get("m", 0))


class Plan:
    """The tracked purchases: {slug|vendor: {"slug","name","vendor","tag","cost","rank","price","baseline","added",
    "ticked","hidden"}}, plus the purchases confirmed lately (shown for a while, then dropped)."""

    def __init__(self):
        self.items, self.done, self.hidden, self.bought = {}, [], set(), set()
        try:
            d = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
            self.items = {k: v for k, v in (d.get("items") or {}).items() if isinstance(v, dict)}
            self.done = [x for x in d.get("done") or [] if isinstance(x, dict)]
            self.hidden = set(d.get("hidden") or [])
            self.bought = set(d.get("bought") or [])
        except Exception:
            pass

    def save(self):
        text = json.dumps({"items": self.items, "done": self.done[-30:], "hidden": sorted(self.hidden),
                           "bought": sorted(self.bought)}, ensure_ascii=False, indent=1)
        if text == getattr(self, "_saved", None):
            return                                     # nothing changed: no disk write (the overlay checks every few seconds)
        try:
            PLAN_FILE.write_text(text, encoding="utf-8")
            self._saved = text
        except OSError:
            pass

    @staticmethod
    def key(p) -> str:
        return f"{p['slug']}|{p['vendor']}"

    def sync(self, picks: list, inv, store) -> list:
        """Brings the tracked list in line with the current picks and the inventory just read. Returns the purchases
        confirmed now ([{"name","vendor","n"}]). Items still in the picks are added (with their baseline); tracked items
        no longer recommended stay until bought or hidden only if ticked, otherwise they are dropped."""
        from app.core import logbus
        confirmed = []
        now = int(time.time())
        wanted = {}
        for p in picks:
            k = self.key(p)
            if k in self.hidden or k in self.bought:      # hidden by you, or already bought (until you reset the list)
                continue
            wanted[k] = p
        # purchases: you own more copies than when the item entered the list
        for k, e in list(self.items.items()):
            have = owned(inv, e["slug"])
            if not e.get("stamp") and inv.imported:      # tracked before any inventory was read: count from now
                e["baseline"], e["stamp"] = have, inv.imported
                continue
            if have > int(e.get("baseline", 0)):
                n = have - int(e.get("baseline", 0))
                confirmed.append({"name": e["name"], "vendor": e["vendor"], "n": n, "t": now})
                logbus.add("plan", f"{e['name']} ({e['vendor']}): purchase confirmed by the game file (+{n})", "ok")
                del self.items[k]
                self.bought.add(k)
                continue
            if have < int(e.get("baseline", 0)):       # sold or used some: the purchase is measured from the new count
                e["baseline"] = have
            if k not in wanted and not e.get("ticked"):
                del self.items[k]
        for k, p in wanted.items():
            if k in self.bought:                         # just confirmed above
                continue
            if k in self.items:
                self.items[k].update(cost=p["cost"], price=p["price"], vol=p["vol"], rank=p.get("rank", 0), ppk=p["ppk"])
            else:
                self.items[k] = {"slug": p["slug"], "name": p["name"], "vendor": p["vendor"], "tag": p.get("tag"),
                                 "cost": p["cost"], "rank": p.get("rank", 0), "price": p["price"], "vol": p["vol"],
                                 "ppk": p["ppk"], "baseline": owned(inv, p["slug"]), "stamp": inv.imported, "added": now,
                                 "ticked": False}
        self.done = (self.done + confirmed)[-30:]
        self.save()
        return confirmed

    def tick(self, key: str, on: bool):
        if key in self.items:
            self.items[key]["ticked"] = bool(on)
            self.save()

    def hide(self, key: str):
        self.hidden.add(key)
        self.items.pop(key, None)
        self.save()

    def reset(self):
        """Shows again the items you hid and the ones already bought."""
        self.hidden.clear()
        self.bought.clear()
        self.save()


def build(plan: Plan, market, inv, store) -> dict:
    """Everything the overlay shows: {"groups": [{"tag","name","standing","rank","daily","items":[...],"activities":[...],
    "short": standing still missing for the cheapest item}], "done": [...], "confirmed": [...]}."""
    from app.trade.recommend import recommend
    from app.game.standing import syndicate_name
    picks, _missing = recommend(market.snapshot(), top=int(CFG.get("goals_items", 8)) * 4,
                                per_vendor=1 if CFG.get("goals_per_vendor", True) else None)
    picks = [p for p in picks if p.get("tag")][:int(CFG.get("goals_items", 8))]
    confirmed = plan.sync(picks, inv, store)
    groups = {}
    for k, e in plan.items.items():
        tag = e.get("tag") or ""
        f = store.get(tag) or {}
        g = groups.setdefault(tag, {"tag": tag, "name": syndicate_name(tag) if tag else e["vendor"],
                                    "standing": f.get("standing"), "rank": f.get("rank"),
                                    "daily": earnable_today(f, store) if f else None,
                                    "cap": daily_cap(store.mr), "items": [], "activities": []})
        have = f.get("standing")
        can = (max(0, have) // e["cost"]) if have is not None and e["cost"] else None
        need = None if have is None else max(0, e["cost"] - max(0, have))
        g["items"].append(dict(e, key=k, can=can, need=need,
                               days=None if need is None else days_to(need, g["daily"], g["cap"]),
                               rank_ok=None if f.get("rank") is None else f["rank"] >= int(e.get("rank") or 0)))
    out = []
    for g in groups.values():
        # what you can buy now first, then what you can reach soonest with the standing still earnable
        g["items"].sort(key=lambda x: (x["days"] if x["days"] is not None else 99, -(x.get("ppk") or 0)))
        needs = [x["need"] for x in g["items"] if x["need"]]
        g["short"] = min(needs) if needs else 0
        if g["short"] or g["standing"] is None:
            g["activities"] = activities(g["tag"], g["name"])
        out.append(g)
    soon = lambda g: min([x["days"] for x in g["items"] if x["days"] is not None] or [99])
    out.sort(key=lambda g: (soon(g), g["name"].lower()))
    return {"groups": out, "done": plan.done, "confirmed": confirmed}
