"""Logica di scansione.

- thread unico che esegue le richieste: "open" (nuovo vendor / F8), "scroll", "refresh" (solo dati)
- ogni invalidazione (scroll, cambio schermo, F9) incrementa `gen`: i risultati vecchi vengono scartati
- i dati salvati compaiono subito, poi vengono aggiornati in background
- un thread di monitoraggio rileva l'apertura di un vendor, rinfresca i dati ogni refresh_interval e
  nasconde le etichette appena il vendor viene chiuso (anche mentre i prezzi si stanno ancora caricando)
- mentre il listino prezzi e' aperto le scansioni sono sospese (altrimenti leggerebbe i nomi del listino)
"""
import threading
import time

import numpy as np

from config import CFG
from ocr import Grabber, screen_changed

PRIO = {"refresh": 1, "scroll": 2, "open": 3}


def fmt_price(it: dict) -> str:
    if not it["price_done"]:
        return "…"
    if it["price_err"]:
        return "n/d"                      # errore di rete / dati non disponibili
    text = f"{it['price']}p" if it["price"] is not None else "–"   # "–" = nessun venditore online
    if it.get("ranked"):                                          # mod / arcane: aggiunge il rank massimo
        text += f" · max {it['pmax']}p" if it.get("pmax") is not None else " · max –"
    return text


class Scanner:
    """bridge deve avere .results/.status/.clear con metodo .emit(); ocr ha .scan()."""

    def __init__(self, market, bridge, screen_w: float, ocr):
        self.market, self.bridge, self.screen_w, self.ocr = market, bridge, screen_w, ocr
        self._last_pub = 0.0
        self.cv = threading.Condition()
        self.gen = 0
        self.active = bool(CFG["start_active"])
        self.pending = None
        self.manual = False
        self.busy = False
        self.suspended = False   # True mentre il listino prezzi e' aperto
        self.items = []          # oggetti attualmente mostrati
        self.ref = None          # dati per rilevare il cambio schermo
        self.version = 0         # cresce a ogni pubblicazione di etichette
        self.scan_epoch = 0      # cresce a ogni scansione avviata
        self.last_refresh = 0.0
        self._timer = None
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()

    # ---------- API chiamata da hotkey / mouse ----------
    def scan_now(self):
        """F8: scansiona subito (riattiva se in pausa)."""
        self.active = True
        self._cancel_timer()
        with self.cv:
            self.gen += 1
        self._request("open", manual=True)

    def stop(self):
        """F9: pausa."""
        self.active = False
        self._cancel_timer()
        with self.cv:
            self.pending = None
        self._invalidate()
        self.market.flush()
        self.bridge.status.emit("In pausa: F8 per riprendere")

    def set_suspended(self, flag: bool):
        """Listino aperto: nasconde le etichette e ferma le scansioni; alla chiusura riscansiona."""
        if flag == self.suspended:
            return
        self.suspended = flag
        if flag:
            self._cancel_timer()
            with self.cv:
                self.pending = None
            self._invalidate()
        elif self.active:
            t = threading.Timer(0.5, lambda: self._request("open"))   # lascia sparire la finestra
            t.daemon = True
            t.start()

    def on_scroll(self):
        """Rotellina: nasconde subito le etichette e riscansiona a scroll finito."""
        if not self.active or self.suspended:
            return
        self._invalidate()
        self._cancel_timer()
        self._timer = threading.Timer(CFG["scroll_debounce"], lambda: self._request("scroll"))
        self._timer.daemon = True
        self._timer.start()

    # ---------- interni ----------
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
                self.bridge.status.emit(f"Errore: {e}")
            finally:
                self.busy = False

    def _publish(self, items, gen, force=False):
        """Ridisegna l'overlay; durante gli aggiornamenti al massimo ogni publish_throttle secondi."""
        if self.gen != gen:
            return
        now = time.monotonic()
        if not force and now - self._last_pub < CFG["publish_throttle"]:
            return
        self._last_pub = now
        self.version += 1
        self.bridge.results.emit([dict(i) for i in items])

    def _apply_cache(self, it):
        """Mostra subito gli ultimi dati salvati (se non troppo vecchi)."""
        e = self.market.cached(it["slug"])
        if not e:
            return
        now, lim = time.time(), CFG["show_cached_max_age"]
        if e.get("pt") and now - e["pt"] < lim:
            it["price"], it["pmax"], it["price_done"] = e.get("price"), e.get("pmax"), True
        if e.get("vt") and now - e["vt"] < lim:
            it["vol"] = e.get("vol")

    def _update(self, items, gen, max_age):
        """Aggiorna prezzi e poi volumi (solo se piu' vecchi di max_age), pubblicando man mano."""
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
                    pass                      # tiene il vecchio valore (o nessuno)
                if it["vol"] != before:
                    self._publish(items, gen)
        self._publish(items, gen, force=True)   # stato finale sempre mostrato
        return True

    def _scan(self, gen: int, kind: str, manual: bool):
        if not self.active or self.suspended:
            return
        self.scan_epoch += 1
        if manual:
            self.bridge.status.emit("Scansione…")
        self.bridge.clear.emit()
        time.sleep(0.12)                     # lascia sparire le vecchie etichette
        if self.gen != gen:
            return
        hits, mon_w, patches = self.ocr.scan()
        if self.gen != gen:
            return
        if not hits:
            self.items = []
            if manual:
                self.bridge.status.emit("Nessun oggetto riconosciuto")
            return

        ratio = self.screen_w / mon_w
        items = [
            {"x": x * ratio, "y": y * ratio, "w": w * ratio, "h": h * ratio,
             "slug": slug, "price": None, "pmax": None, "vol": None,
             "ranked": self.market.info(slug).get("max_rank", 0) > 0,
             "price_done": False, "price_err": False, "label": "…"}
            for x, y, w, h, slug, _score in hits
        ]
        for it in items:
            self._apply_cache(it)
            it["label"] = fmt_price(it)
        self.items = items
        # riferimento per capire quando il vendor viene chiuso: ritagli dello screenshot della scansione
        self.ref = {"gen": gen, "boxes": [(h[0], h[1], h[2], h[3]) for h in hits], "patches": patches}
        self._publish(items, gen, force=True)   # prima i dati salvati, poi l'aggiornamento
        # all'apertura aggiorna i dati piu' vecchi di open_max_age; durante lo scroll basta la cache recente
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

    # ---------- monitoraggio ----------
    def _watch(self):
        """Ogni watch_interval: rinfresco periodico dei dati e rilevamento dello schermo.

        - vendor mostrato: se il contenuto sotto i nomi cambia (scroll, vendor chiuso, altra pagina)
          nasconde subito le etichette. Il controllo c'e' SEMPRE, anche mentre i prezzi si caricano
        - nessun vendor: quando lo schermo cambia molto e poi si ferma -> scansione automatica
        """
        grab = Grabber()
        prev, dirty, stable, last_auto, epoch, streak = None, True, 0, 0.0, self.scan_epoch, 0   # dirty: scansiona subito all'avvio
        while True:
            # durante il gioco (schermo in continuo movimento) controlla meno spesso: conta solo quando si ferma
            time.sleep(CFG["watch_interval_moving"] if streak >= 3 else CFG["watch_interval"])
            if not self.active or self.suspended:
                prev, dirty, stable, streak = None, False, 0, 0
                continue
            now = time.time()
            if self.items and not self.busy and now - self.last_refresh >= CFG["refresh_interval"]:
                self.last_refresh = now      # evita richieste doppie mentre e' in coda
                self._request("refresh")

            ref = self.ref
            showing = bool(ref and ref["patches"] and ref["gen"] == self.gen and self.items)
            if not showing and (not CFG["auto_detect"] or self.busy):
                continue
            try:
                img = grab.grab()
            except Exception:
                grab = Grabber()
                continue

            if showing:
                prev, streak = None, 0
                if screen_changed(img, ref["boxes"], ref["patches"]):
                    self._invalidate()       # vendor chiuso o lista cambiata: via le etichette
                    dirty, stable = True, 0
                continue

            fp = img[::24, ::24, :3].mean(axis=2)
            moving = (prev is not None and prev.shape == fp.shape
                      and (np.abs(fp - prev) > 25).mean() > CFG["auto_motion_frac"])
            prev = fp
            streak = streak + 1 if moving else 0
            if epoch != self.scan_epoch:     # e' partita una scansione: riparti da zero
                epoch, dirty, stable = self.scan_epoch, False, 0

            # nessun vendor mostrato: aspetta che lo schermo cambi e poi si fermi
            if moving:
                dirty, stable = True, 0
            else:
                stable += 1
            if dirty and stable >= CFG["auto_settle_polls"] and now - last_auto >= CFG["auto_min_gap"]:
                dirty, last_auto = False, now
                self._request("open")
