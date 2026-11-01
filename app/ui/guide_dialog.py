"""Build planner ▸ Share ▸ Import from a guide: reads a guide page (Google Doc, arbi.guide, wfpedia, any page with builds
written as text), lists the builds found, and puts the chosen ones in the planner, or saves each as a plan. The pictures
of a build (guides often show the layout only as a screenshot) can be read with the planner's picture import."""
import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)

from app.core.config import APP_DIR
from app.core.i18n import t
from app.core.uiutil import role
from app.game import guideimport as GI


class _Sig(QObject):
    done = pyqtSignal(object)
    step = pyqtSignal(str)
    picture = pyqtSignal(object)


class GuideDialog(QDialog):
    def __init__(self, planner):
        super().__init__(planner)
        self.planner = planner
        self.setWindowTitle(t("guide.title"))
        self.resize(820, 620)
        self.known = QComboBox()
        self.known.addItem(t("guide.pick"), "")
        for label, url in GI.KNOWN:
            self.known.addItem(label, url)
        self.url = QLineEdit()
        self.url.setPlaceholderText(t("guide.url"))
        self.follow = QCheckBox(t("guide.follow"))
        self.follow.setToolTip(t("guide.follow.tip"))
        self.follow.setChecked(True)
        self.btn_read = QPushButton(t("guide.read"))
        role(self.btn_read, "primary")
        row = QHBoxLayout()
        row.addWidget(self.known)
        row.addWidget(self.url, 1)
        row.addWidget(self.btn_read)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("guide.col.build"), t("guide.col.what")])
        self.tree.setColumnWidth(0, 330)
        self.status = QLabel(t("guide.hint"))
        self.status.setWordWrap(True)
        role(self.status, "muted")
        self.btn_pics = QPushButton(t("guide.pictures"))
        self.btn_pics.setToolTip(t("guide.pictures.tip"))
        self.btn_plan = QPushButton(t("guide.toplan"))
        self.btn_plan.setToolTip(t("guide.toplan.tip"))
        self.btn_save = QPushButton(t("guide.save"))
        self.btn_save.setToolTip(t("guide.save.tip"))
        close = QPushButton(t("cost.close"))
        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_pics)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_save)
        bottom.addWidget(self.btn_plan)
        bottom.addWidget(close)
        note = QLabel(t("guide.note"))
        note.setWordWrap(True)
        role(note, "hint")
        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self.follow)
        lay.addWidget(self.tree, 1)
        lay.addWidget(self.status)
        lay.addWidget(note)
        lay.addLayout(bottom)
        self.sig = _Sig()
        self.sig.done.connect(self._done)
        self.sig.step.connect(lambda u: self.status.setText(t("guide.reading", url=u)))
        self.sig.picture.connect(self._picture_done)
        self.known.currentIndexChanged.connect(lambda _i: self.known.currentData() and self.url.setText(self.known.currentData()))
        self.btn_read.clicked.connect(self.read)
        self.url.returnPressed.connect(self.read)
        self.btn_plan.clicked.connect(self.to_plan)
        self.btn_save.clicked.connect(self.save_all)
        self.btn_pics.clicked.connect(self.read_pictures)
        close.clicked.connect(self.accept)
        self.builds = []
        self._buttons(False)

    def _buttons(self, on):
        for b in (self.btn_plan, self.btn_save, self.btn_pics):
            b.setEnabled(on)

    # ---------- reading the page ----------
    def read(self):
        url = self.url.text().strip()
        if not url:
            return
        self.btn_read.setEnabled(False)
        self.tree.clear()
        self.builds = []
        follow, sig = self.follow.isChecked(), self.sig

        def work():
            try:
                sig.done.emit(GI.read(url, follow, progress=sig.step.emit))
            except Exception as e:
                sig.done.emit(f"{type(e).__name__}: {e}" if not isinstance(e, GI.GuideError) else str(e))
        threading.Thread(target=work, daemon=True, name="guide-read").start()

    def _done(self, res):
        self.btn_read.setEnabled(True)
        if isinstance(res, str):
            self.status.setText(t("guide.error", err=res))
            return
        self.builds = res["builds"]
        self._fill()
        self.status.setText(t("guide.found", n=len(self.builds), pics=res["images"]) if self.builds else t("guide.none"))

    def _fill(self):
        self.tree.clear()
        for i, b in enumerate(self.builds):
            what = [t("guide.n.mods", n=len(b.get("mods") or []))]
            if b.get("arcanes"):
                what.append(t("guide.n.arcanes", n=len(b["arcanes"])))
            if b.get("shards"):
                what.append(t("guide.n.shards", n=len(b["shards"])))
            if b.get("images"):
                what.append(t("guide.n.pics", n=len(b["images"])))
            if b.get("from_picture"):
                what.append(t("guide.frompic"))
            it = QTreeWidgetItem([f"{b['item']}  ·  {t('builds.kind.' + b['kind'])}", ", ".join(what)])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked if (b.get("mods") or b.get("slots")) else Qt.CheckState.Unchecked)
            it.setData(0, Qt.ItemDataRole.UserRole, i)
            tip = [b.get("title") or ""]
            if b.get("slots"):
                tip.append(", ".join(f"{m[0]} R{m[1]}" for m in b["slots"] if m))
            else:
                tip.append(", ".join(f"{n}" + (f" R{r}" if r is not None else "") for n, r in b.get("mods") or []))
            if b.get("arcanes"):
                tip.append(", ".join(n for n, _r in b["arcanes"]))
            if b.get("notes"):
                tip.append(t("guide.notes", names=", ".join(b["notes"][:12])))
            it.setToolTip(0, "\n".join(x for x in tip if x))
            it.setToolTip(1, it.toolTip(0))
            for u in b.get("images") or []:
                ch = QTreeWidgetItem(["🖼 " + u.rsplit("/", 1)[-1][:60], ""])
                ch.setToolTip(0, u)
                it.addChild(ch)
            self.tree.addTopLevelItem(it)
        self._buttons(bool(self.builds))

    def _checked(self) -> list:
        out = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                out.append(self.builds[it.data(0, Qt.ItemDataRole.UserRole)])
        return out

    # ---------- into the planner ----------
    def to_plan(self):
        chosen = self._checked()
        if not chosen:
            return
        kinds = [b["kind"] for b in chosen]
        if len(set(kinds)) < len(kinds):
            QMessageBox.information(self, t("guide.title"), t("guide.samekind"))
        for b in chosen:
            self.planner.add_guide_build(b)
        self.status.setText(t("guide.added.n", n=len(chosen)))

    def save_all(self):
        """Each chosen build as its own saved plan ("<guide title> · <item>")."""
        chosen = self._checked()
        if not chosen:
            return
        pl = self.planner
        keep = (dict(pl.pieces), pl.kind, pl.name.text())
        n = 0
        for b in chosen:
            pl.pieces = {}
            pl.p = None
            pl.name.setText(f"{(b.get('title') or b['item'])[:40]} · {b['item']}" if b.get("title") and b["item"] not in
                            (b.get("title") or "") else (b.get("title") or b["item"])[:60])
            pl.add_guide_build(b)
            name = pl.name.text().strip()
            base, k = name, 2
            while name in pl.plans:
                name = f"{base} ({k})"
                k += 1
            pl.name.setText(name)
            pl._store_piece()
            pieces = {kk: dict(v, forma={str(i): p for i, p in v["forma"].items()},
                               configs=[dict(c, mods=[list(m) if m else None for m in c["mods"]]) for c in v["configs"]])
                      for kk, v in pl.pieces.items()}
            import time
            pl.plans[name] = {"v": 2, "kind": b["kind"], "pieces": pieces, "saved": int(time.time()),
                              "source": b.get("source") or ""}
            n += 1
        pl._write_plans()
        pl.pieces = keep[0]
        pl.name.setText(keep[2])
        pl._fill_saved()
        pl._show_piece(keep[1], keep[0].get(keep[1]))
        self.status.setText(t("guide.saved.n", n=n))

    # ---------- the pictures ----------
    def read_pictures(self):
        """The pictures of the selected build (or of every build): downloaded and read like Share ▸ Import from a
        picture; each one that is a build layout becomes a build of the list."""
        it = self.tree.currentItem()
        if it is not None and it.parent() is not None:
            it = it.parent()
        idxs = [it.data(0, Qt.ItemDataRole.UserRole)] if it is not None else range(len(self.builds))
        todo = [(i, u) for i in idxs for u in (self.builds[i].get("images") or [])][:30]
        if not todo:
            self.status.setText(t("guide.nopics"))
            return
        self.btn_pics.setEnabled(False)
        sig = self.sig
        folder = APP_DIR / "guide_images"
        hints = {i: (self.builds[i]["kind"], self.builds[i]["item"]) for i, _u in todo}

        def work():
            from app.game import buildocr
            for n, (i, url) in enumerate(todo, start=1):
                sig.step.emit(f"{n}/{len(todo)} {url}")
                try:
                    path = GI.download_image(url, folder)
                    lines, w, h = _ocr(path)
                    try:
                        from PIL import Image
                        img = Image.open(path).convert("RGB")
                        if img.size != (w, h):
                            img = img.resize((w, h))
                    except Exception:
                        img = None
                    try:
                        b = buildocr.parse(lines, w, h, image=img)
                    except ValueError:
                        kind, item = hints[i]                # the guide's item: the picture may not show its name
                        b = buildocr.parse(lines, w, h, kind_hint=kind, item_hint=item, image=img)
                    sig.picture.emit((i, url, b))
                except Exception as e:
                    sig.picture.emit((i, url, f"{type(e).__name__}: {e}"))
            sig.picture.emit(None)
        threading.Thread(target=work, daemon=True, name="guide-pictures").start()

    def _picture_done(self, res):
        if res is None:
            self.btn_pics.setEnabled(True)
            self._fill()
            self.status.setText(t("guide.pics.done", n=sum(1 for b in self.builds if b.get("from_picture"))))
            return
        i, url, b = res
        if isinstance(b, str):
            return
        src = self.builds[i]
        self.builds.append({"title": (src.get("title") or src["item"]) + " · " + t("guide.frompic"), "item": b["item"],
                            "kind": b["kind"], "mods": [], "slots": b["mods"], "pols": b.get("pols") or {},
                            "arcanes": [], "shards": src.get("shards") if b["item"] == src["item"] else [],
                            "helminth": src.get("helminth") if b["item"] == src["item"] else None,
                            "images": [], "notes": b.get("unplaced") or [], "from_picture": True, "source": url})


def _ocr(path):
    import app.scan.ocr_worker as OW
    if OW.CLIENT is not None:
        return OW.CLIENT.read_image(path)
    import numpy as np
    from PIL import Image
    from app.scan.ocr import make_engine, read_lines
    im = Image.open(path).convert("RGB")
    ls = read_lines(np.array(im)[:, :, ::-1].copy(), make_engine())
    return [(x.text, x.x, x.y, x.w, x.h, x.score) for x in ls], im.width, im.height
