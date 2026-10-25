"""Scanning logic.

- a single thread runs the requests: "open" (new vendor / F8), "scroll", "refresh" (data only)
- every invalidation (scroll, screen change, F9) increments `gen`: stale results are discarded
- saved data shows up immediately, then is refreshed in the background
- a monitoring thread detects a vendor being opened, refreshes data every refresh_interval and
  hides the labels as soon as the vendor is closed (even while prices are still loading)
- the price list can stay open: its rectangle is blanked before the OCR (it must not read its own names)
"""
import threading
import time

import numpy as np

from config import CFG
from recommend import recommend
from i18n import t
from ocr import Grabber, screen_changed

PRIO = {"refresh": 1, "scroll": 2, "open": 3}


def fmt_price(it: dict) -> str:
    if not it["price_done"]:
        return "…"
    if it["price_err"]:
        return t("price.na")                      # network error / data unavailable
    text = f"{it['price']}p" if it["price"] is not None else "–"   # "–" = no seller online
    if it.get("ranked"):                                          # mods / arcanes: also show the max-rank price
        text += f" · max {it['pmax']}p" if it.get("pmax") is not None else " · max –"
    return text


class Scanner:
    """bridge must have .results/.status/.clear signals with an .emit() method; ocr has .scan()."""

    def __init__(self, market, bridge, screen_w: float, ocr):
        self.market, self.bridge, self.screen_w, self.ocr = market, bridge, screen_w, ocr
        self._last_pub = 0.0
        self.cv = threading.Condition()
        self.gen = 0
        self.active = bool(CFG["start_active"])
        self.pending = None
        self.manual = False
        self.busy = False
        self.suspended = False   # (legacy) True = no scanning at all
        self.exclude_provider = None   # returns the price list's rectangle in screen pixels (or None): not read
        self.items = []          # items currently shown
        self.ref = None          # data used to detect a screen change
        self.version = 0         # grows at every label publication
        self.scan_epoch = 0      # grows at every scan started
        self.last_refresh = 0.0
        self._timer = None
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()

    # ---------- API called by hotkeys / mouse ----------
    def scan_now(self):
        """F8: scan now (resumes if paused)."""
        self.active = True
        self._cancel_timer()
        with self.cv:
            self.gen += 1
        self._request("open", manual=True)

    def stop(self):
        """F9: pause."""
        self.active = False
        self._cancel_timer()
        with self.cv:
            self.pending = None
        self._invalidate()
        self.market.flush()
        self.bridge.status.emit(t("status.paused", key=CFG["key_scan"].strip("<>").upper()))

    def list_changed(self):
        """The price list opened/closed: rescan shortly so its area is excluded (or read again)."""
        if self.active:
            t = threading.Timer(0.5, lambda: self._request("open"))
            t.daemon = True
            t.start()

    def set_suspended(self, flag: bool):
        """Price list open: hides the labels and stops scanning; rescans when it closes."""
        if flag == self.suspended:
            return
        self.suspended = flag
        if flag:
            self._cancel_timer()
            with self.cv:
                self.pending = None
            self._invalidate()
        elif self.active:
            t = threading.Timer(0.5, lambda: self._request("open"))   # let the window disappear
            t.daemon = True
            t.start()

    def on_scroll(self):
        """Mouse wheel: hides the labels at once and rescans when scrolling stops."""
        if not self.active or self.suspended:
            return
        self._invalidate()
        self._cancel_timer()
        self._timer = threading.Timer(CFG["scroll_debounce"], lambda: self._request("scroll"))
        self._timer.daemon = True
        self._timer.start()

    # ---------- internals ----------
    def _invalidate(self):
        with self.cv:
            self.gen += 1
            self.ref = None
            self.items = []
        self.bridge.clear.emit()

    def _cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _request(self, kind: str, manual: bool = False):
        if not self.active or self.suspended:
            return
        with self.cv:
            if PRIO[kind] >= PRIO.get(self.pending, 0):
                self.pending = kind
            self.manual = self.manual or manual
            self.cv.notify()

    def _loop(self):
        while True:
            with self.cv:
                while self.pending is None:
                    self.cv.wait()
                kind, self.pending = self.pending, None
                manual, self.manual = self.manual, False
                gen = self.gen
                self.busy = True
            try:
                if kind == "refresh":
                    self._refresh(gen)
                else:
                    self._scan(gen, kind, manual)
            except Exception as e:
                self.bridge.status.emit(t("status.error", err=e))
            finally:
                self.busy = False

    def _publish(self, items, gen, force=False):
        """Redraws the overlay; while updating, at most once every publish_throttle seconds."""
        if self.gen != gen:
            return
        now = time.monotonic()
        if not force and now - self._last_pub < CFG["publish_throttle"]:
            return
        self._last_pub = now
        self.version += 1
        self.bridge.results.emit([dict(i) for i in items])

    def _mark_recommended(self, items):
        """Flags the items that are among the top recommended ones (from the saved market data)."""
        if not CFG["rec_overlay"]:
            return
        try:
            picks, _ = recommend(self.market.snapshot(), top=int(CFG["rec_overlay_top"]))
        except Exception:
            return
        top = {p["slug"] for p in picks}
        for it in items:
            it["rec"] = it["slug"] in top

    def _apply_cache(self, it):
        """Shows the last saved data right away (if not too old)."""
        e = self.market.cached(it["slug"])
        if not e:
            return
        now, lim = time.time(), CFG["show_cached_max_age"]
        if e.get("pt") and now - e["pt"] < lim:
            it["price"], it["pmax"], it["price_done"] = e.get("price"), e.get("pmax"), True
        if e.get("vt") and now - e["vt"] < lim:
            it["vol"] = e.get("vol")

    def _update(self, items, gen, max_age):
        """Updates prices and then volumes (only if older than max_age), publishing as it goes."""
        for it in items:
            if self.gen != gen:
                return False
            before = (it["label"], it["vol"])
            try:
                it["price"], it["pmax"] = self.market.prices(it["slug"], max_age)
                it["price_err"], it["price_done"] = False, True
            except Exception:
                if not it["price_done"]:
                    it["price_err"], it["price_done"] = True, True
            it["label"] = fmt_price(it)
            if (it["label"], it["vol"]) != before:
                self._publish(items, gen)
        if CFG["show_volume"]:
            for it in items:
                if self.gen != gen:
                    return False
                before = it["vol"]
                try:
                    it["vol"] = self.market.volume_24h(it["slug"], max_age)
                except Exception:
                    pass                      # keep the old value (or none)
                if it["vol"] != before:
                    self._publish(items, gen)
        self._mark_recommended(items)           # prices changed: the ranking may too
        self._publish(items, gen, force=True)   # the final state is always shown
        return True

    def _scan(self, gen: int, kind: str, manual: bool):
        if not self.active or self.suspended:
            return
        self.scan_epoch += 1
        if manual:
            self.bridge.status.emit(t("status.scanning"))
        self.bridge.clear.emit()
        time.sleep(0.12)                     # let the old labels disappear
        if self.gen != gen:
            return
        try:
            ex = self.exclude_provider() if self.exclude_provider else None
        except Exception:
            ex = None
        hits, mon_w, patches = self.ocr.scan(exclude=[ex] if ex else None)
        ox, oy = getattr(self.ocr, "origin", (0, 0))
        if self.gen != gen:
            return
        if not hits:
            self.items = []
            if manual:
                self.bridge.status.emit(t("status.nowindow") if getattr(self.ocr, "skipped", "") else t("status.none"))
            return

        ratio = self.screen_w / mon_w
        items = [
            {"x": (x + ox) * ratio, "y": (y + oy) * ratio, "w": w * ratio, "h": h * ratio,
             "slug": slug, "price": None, "pmax": None, "vol": None,
             "ranked": self.market.info(slug).get("max_rank", 0) > 0,
             "price_done": False, "price_err": False, "label": "…"}
            for x, y, w, h, slug, _score in hits
        ]
        for it in items:
            self._apply_cache(it)
            it["label"] = fmt_price(it)
        self._mark_recommended(items)
        self.items = items
        # reference to tell when the vendor is closed: crops of the scan's screenshot
        self.ref = {"gen": gen, "boxes": [(h[0], h[1], h[2], h[3]) for h in hits], "patches": patches}
        self._publish(items, gen, force=True)   # saved data first, then the update
        # on open, refresh data older than open_max_age; while scrolling, recent cache is enough
        max_age = CFG["open_max_age"] if kind == "open" else CFG["refresh_interval"]
        self._update(items, gen, max_age)
        self.last_refresh = time.time()
        self.market.flush()

    def _refresh(self, gen: int):
        items = list(self.items)
        if not items or self.gen != gen:
            return
        self._update(items, gen, max(1, CFG["refresh_interval"] - 5))
        self.last_refresh = time.time()
        self.market.flush()

    # ---------- monitoring ----------
    def _watch(self):
        """Every watch_interval: periodic data refresh and screen detection.

        - vendor shown: if the content under the names changes (scroll, vendor closed, other page)
          the labels are hidden at once. The check ALWAYS runs, even while prices are loading
        - no vendor shown: when the screen changes a lot and then settles -> automatic scan
        """
        nones = 0
        grab = Grabber(CFG["only_warframe"])
        prev, dirty, stable, last_auto, epoch, streak = None, True, 0, 0.0, self.scan_epoch, 0   # dirty: scan right away at startup
        while True:
            # while playing (constantly moving screen) check less often: only the moment it stops matters
            time.sleep(CFG["watch_interval_moving"] if streak >= 3 else CFG["watch_interval"])
            if not self.active or self.suspended:
                prev, dirty, stable, streak = None, False, 0, 0
                continue
            now = time.time()
            if self.items and not self.busy and now - self.last_refresh >= CFG["refresh_interval"]:
                self.last_refresh = now      # avoid duplicate requests while it is queued
                self._request("refresh")

            ref = self.ref
            showing = bool(ref and ref["patches"] and ref["gen"] == self.gen and self.items)
            if not showing and (not CFG["auto_detect"] or self.busy):
                continue
            try:
                img = grab.grab()
            except Exception:
                grab = Grabber(CFG["only_warframe"])
                continue
            if img is None:                  # Warframe is not the active window
                nones += 1
                if nones >= 4:               # a short flicker of the foreground window must not hide the labels
                    if showing:
                        self._invalidate()
                    prev, dirty, stable, streak = None, True, 0, 0
                continue
            nones = 0

            if showing:
                prev, streak = None, 0
                if screen_changed(img, ref["boxes"], ref["patches"]):
                    self._invalidate()       # vendor closed or list changed: drop the labels
                    dirty, stable = True, 0
                continue

            fp = img[::24, ::24, :3].mean(axis=2)
            moving = (prev is not None and prev.shape == fp.shape
                      and (np.abs(fp - prev) > 25).mean() > CFG["auto_motion_frac"])
            prev = fp
            streak = streak + 1 if moving else 0
            if epoch != self.scan_epoch:     # a scan started: start over
                epoch, dirty, stable = self.scan_epoch, False, 0

            # no vendor shown: wait for the screen to change and then settle
            if moving:
                dirty, stable = True, 0
            else:
                stable += 1
            if dirty and stable >= CFG["auto_settle_polls"] and now - last_auto >= CFG["auto_min_gap"]:
                dirty, last_auto = False, now
                self._request("open")
