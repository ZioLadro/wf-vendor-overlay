"""World strip under the player strip: Steel Path Omnia fissures now open, Earth / Cetus / Orb Vallis cycles, when Baro
Ki'Teer comes back (or leaves) and the next Prime Resurgence, with live countdowns.

Data: the community world-state mirror api.warframestat.us (same source as the World tab), read again every few minutes
in the background and as soon as a countdown reaches zero (at most once a minute)."""
import threading
import time
from datetime import datetime

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel

from config import CFG
from i18n import t
from uiutil import role

REFRESH = 300              # seconds between two downloads
RETRY = 60                 # after an error, or when a countdown ran out


def ts(value):
    """Epoch seconds of an ISO date ('2026-10-27T21:00:00.000Z'), or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def left(seconds) -> str:
    """'2d 3h', '1h 12m', '4m 05s'."""
    s = max(0, int(seconds))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s % 60:02d}s"


def summary(ws: dict) -> dict:
    """What the strip shows, from a world state: {"cycles": [(name, state, expiry)], "omnia": [(mission, node, enemy, expiry)],
    "baro": (active, location, activation, expiry), "resurgence": (active, activation, expiry, [items])}."""
    out = {"cycles": [], "omnia": [], "baro": None, "resurgence": None, "arbi": None}
    a = ws.get("arbitration")
    if isinstance(a, dict) and ts(a.get("expiry")) and not a.get("expired"):
        out["arbi"] = (str(a.get("node") or ""), str(a.get("nodeKey") or a.get("id") or ""), str(a.get("type") or ""),
                       str(a.get("enemy") or ""), ts(a.get("expiry")))
    for key, name in (("earthCycle", "earth"), ("cetusCycle", "cetus"), ("vallisCycle", "vallis")):
        c = ws.get(key)
        if isinstance(c, dict) and ts(c.get("expiry")):
            out["cycles"].append((name, str(c.get("state") or ""), ts(c.get("expiry"))))
    for f in ws.get("fissures") or []:
        if isinstance(f, dict) and f.get("isHard") and "omnia" in str(f.get("tier", "")).lower() and not f.get("expired"):
            out["omnia"].append((str(f.get("missionType") or ""), str(f.get("node") or ""), str(f.get("enemy") or ""),
                                 ts(f.get("expiry"))))
    b = ws.get("voidTrader")
    if isinstance(b, dict):
        out["baro"] = (str(b.get("location") or ""), ts(b.get("activation")), ts(b.get("expiry")))
    v = ws.get("vaultTrader")
    if isinstance(v, dict):
        items = [str(i.get("item") or "") for i in (v.get("inventory") or []) if isinstance(i, dict) and i.get("item")]
        out["resurgence"] = (ts(v.get("activation")), ts(v.get("expiry")), items)
    return out


TIER_COLOR = {"S": "#e8c547", "A": "#4fbf6a", "B": "#5aa9e6", "C": "#b48ce0", "D": "#9aa4b2", "F": "#e0584a",
              "Special": "#e08a3a"}


class _Bus(QObject):
    done = pyqtSignal(object, str)


class WorldStrip(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.data, self._fetched, self._busy, self._err = None, 0.0, False, ""
        self.lay = QGridLayout(self)
        self.lay.setContentsMargins(8, 4, 8, 4)
        self.lay.setHorizontalSpacing(22)
        self.lay.setVerticalSpacing(2)
        self.labels = {}
        for key in ("omnia", "arbi", "earth", "cetus", "vallis", "baro", "resurgence"):
            lab = QLabel("")
            lab.setTextFormat(Qt.TextFormat.RichText)
            self.labels[key] = lab
        # first row: the Steel Path Omnia fissures; second row: cycles, Baro, Prime Resurgence
        self.lay.addWidget(self.labels["omnia"], 0, 0, 1, 3)
        self.labels["arbi"].setOpenExternalLinks(True)
        self.lay.addWidget(self.labels["arbi"], 0, 3, 1, 2)
        self.tiers = None
        for col, key in enumerate(("earth", "cetus", "vallis", "baro", "resurgence")):
            self.lay.addWidget(self.labels[key], 1, col)
        self.status = QLabel("")
        role(self.status, "hint")
        self.lay.addWidget(self.status, 0, 5, Qt.AlignmentFlag.AlignRight)
        self.lay.setColumnStretch(5, 1)
        self.bus = _Bus()
        self.bus.done.connect(self._done)
        self._timer = QTimer(self, interval=1000, timeout=self._tick)
        self.setVisible(bool(CFG.get("world_strip", True)))

    def showEvent(self, e):
        super().showEvent(e)
        self._timer.start()
        self._tick()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()

    # ---------- data ----------
    def _fetch(self):
        if self._busy:
            return
        self._busy = True

        def run():
            from world import fetch_world
            try:
                import arbi
                self.tiers = arbi.tierlist()            # arbi.guide (cached 15 min; last good copy if it is down)
            except Exception:
                pass
            try:
                self.bus.done.emit(fetch_world(CFG["language"]), "")
            except Exception as e:
                import logbus
                logbus.error("world", f"strip: {type(e).__name__}: {e}")
                self.bus.done.emit(None, type(e).__name__)
        threading.Thread(target=run, daemon=True, name="world-strip").start()

    def _done(self, ws, err):
        self._busy, self._fetched, self._err = False, time.time(), err
        if ws is not None:
            try:
                self.data = summary(ws)
            except Exception as e:
                self._err = type(e).__name__
        self._tick()

    # ---------- showing ----------
    def _tick(self):
        now = time.time()
        due = now - self._fetched > (REFRESH if self.data and not self._err else RETRY)
        expired = self.data and any(exp and exp < now for _n, _s, exp in self.data["cycles"])
        if due or (expired and now - self._fetched > RETRY):
            self._fetch()
        d = self.data
        self.status.setText(t("strip.error", err=self._err) if self._err else ("" if d else t("strip.loading")))
        if not d:
            return
        lab = self.labels
        if d["omnia"]:
            parts = [f"{m} – {n} ({left(e - now)})" for m, n, _en, e in d["omnia"] if e and e > now]
            lab["omnia"].setText(f"<b>{t('strip.omnia')}</b> " + ("; ".join(parts) if parts else "–"))
            lab["omnia"].setToolTip("\n".join(f"{m} · {n} · {en}" for m, n, en, _e in d["omnia"]))
        else:
            lab["omnia"].setText(f"<b>{t('strip.omnia')}</b> " + t("strip.none"))
        for name, state, exp in d["cycles"]:
            txt = left(exp - now) if exp > now else "…"
            lab[name].setText(f"<b>{t('strip.' + name)}</b> {t('cycle.' + state) if state else '?'} · {txt}")
        loc, act, exp = d["baro"] or ("", None, None)
        if act and exp and act <= now < exp:
            lab["baro"].setText(f"<b>{t('strip.baro')}</b> " + t("strip.baro.here", loc=loc, left=left(exp - now)))
        elif act and act > now:
            lab["baro"].setText(f"<b>{t('strip.baro')}</b> " + t("strip.baro.in", left=left(act - now), loc=loc))
        else:
            lab["baro"].setText(f"<b>{t('strip.baro')}</b> –")
        self._arbitration(now)
        act, exp, items = d["resurgence"] or (None, None, [])
        if act and exp and act <= now < exp:
            lab["resurgence"].setText(f"<b>{t('strip.resurgence')}</b> " + t("strip.res.now", left=left(exp - now)))
        elif act and act > now:
            lab["resurgence"].setText(f"<b>{t('strip.resurgence')}</b> " + t("strip.res.in", left=left(act - now)))
        else:
            lab["resurgence"].setText(f"<b>{t('strip.resurgence')}</b> –")
        lab["resurgence"].setToolTip("\n".join(items[:40]))


    def _arbitration(self, now):
        """The current Arbitration with its arbi.guide tier (the tier links back to the guide, as it asks)."""
        import arbi
        lab = self.labels["arbi"]
        a = (self.data or {}).get("arbi")
        if not a or not a[4] or a[4] <= now:
            lab.setText(f"<b>{t('strip.arbi')}</b> –")
            return
        node, key, mtype, enemy, exp = a
        tier, saryn, _n = arbi.tier_of(self.tiers, key, node)
        col = TIER_COLOR.get(tier, "#9aa4b2")
        tier_txt = (f"<a href='{arbi.SITE}' style='color:{col}; text-decoration:none'><b>{t('strip.arbi.tier', tier=tier)}"
                    f"{' *' if saryn else ''}</b></a>") if tier and self.tiers else ""
        lab.setText(f"<b>{t('strip.arbi')}</b> {mtype} – {node} {tier_txt} · {left(exp - now)}")
        tip = [f"{mtype} · {node} · {enemy}"]
        if self.tiers:
            ve = arbi.TIER_INFO.get(tier)
            tip.append(t("strip.arbi.tip.ve", tier=tier, ve=ve) if ve else t("strip.arbi.tip." + ("special" if tier == "Special" else "f")))
            if saryn:
                tip.append(t("strip.arbi.tip.saryn"))
            tip.append(t("strip.arbi.tip.src"))
        lab.setToolTip("\n".join(tip))
