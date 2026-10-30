"""Official Warframe wallpapers from the Warframe wiki as the program's background.

The list is asked of the wiki (the standard MediaWiki API): the files of its "Wallpapers" categories and the files with
"wallpaper" in their name, landscape and at least 1280 pixels wide. Previews are small copies made by the wiki; only the
wallpaper you choose is downloaded (at most 2560 pixels wide) into the data folder (wallpapers/) and set as the
background picture (Theme: picture, dimmed by "Background strength"). Nothing is shipped with the program: the
pictures stay DE's, on the wiki."""
import json
import re
import threading
import time

from PyQt6.QtCore import QObject, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QListView, QListWidget, QListWidgetItem, QVBoxLayout,
)

from app.core.config import APP_DIR
from app.core.i18n import t

API = "https://wiki.warframe.com/api.php"
DIR = APP_DIR / "wallpapers"
LIST = DIR / "list.json"
MAX_AGE = 7 * 86400
CATEGORIES = ("Category:Wallpapers", "Category:Wallpaper", "Category:Official Wallpapers", "Category:Desktop Wallpapers")


def _headers():
    from app.trade.market import HEADERS
    return {"User-Agent": HEADERS["User-Agent"]}


def _infos(requests, titles) -> list:
    out = []
    for i in range(0, len(titles), 40):
        q = requests.get(API, headers=_headers(), timeout=20, params={
            "action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|size",
            "iiurlwidth": 320, "titles": "|".join(titles[i:i + 40])})
        for p in ((q.json().get("query") or {}).get("pages") or {}).values():
            info = (p.get("imageinfo") or [{}])[0]
            w, h = int(info.get("width") or 0), int(info.get("height") or 0)
            if info.get("url") and w >= 1280 and w > h * 1.2:
                out.append({"title": p.get("title", ""), "url": info["url"], "thumb": info.get("thumburl") or info["url"],
                            "w": w, "h": h})
    return out


def fetch_list() -> list:
    """[{title, url, thumb, w, h}] of the wiki's wallpapers (cached a week)."""
    try:
        d = json.loads(LIST.read_text(encoding="utf-8"))
        if time.time() - d.get("t", 0) < MAX_AGE and d.get("items"):
            return d["items"]
    except Exception:
        pass
    import requests
    titles = []
    for cat in CATEGORIES:
        cont = {}
        for _ in range(5):
            q = requests.get(API, headers=_headers(), timeout=20, params=dict({
                "action": "query", "format": "json", "list": "categorymembers", "cmtitle": cat, "cmtype": "file",
                "cmlimit": 200}, **cont))
            j = q.json()
            titles += [m["title"] for m in (j.get("query") or {}).get("categorymembers") or []]
            cont = j.get("continue") or {}
            if not cont:
                break
    q = requests.get(API, headers=_headers(), timeout=20, params={
        "action": "query", "format": "json", "list": "search", "srsearch": "wallpaper", "srnamespace": 6,
        "srlimit": 200})
    titles += [m["title"] for m in (q.json().get("query") or {}).get("search") or []]
    titles = list(dict.fromkeys(x for x in titles if re.search(r"\.(png|jpe?g|webp)$", x, re.I)))
    items = _infos(requests, titles) if titles else []
    DIR.mkdir(parents=True, exist_ok=True)
    LIST.write_text(json.dumps({"t": time.time(), "items": items}), encoding="utf-8")
    return items


def _safe(title: str) -> str:
    return re.sub(r"[^\w.-]", "_", title.split(":", 1)[-1])


def download(item: dict) -> str:
    """The wallpaper on disk (at most 2560 pixels wide), its path."""
    import requests
    DIR.mkdir(parents=True, exist_ok=True)
    out = DIR / _safe(item["title"])
    if out.exists():
        return str(out)
    url = item["url"]
    if item.get("w", 0) > 2560:                            # a smaller copy made by the wiki
        q = requests.get(API, headers=_headers(), timeout=20, params={
            "action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 2560,
            "titles": item["title"]})
        for p in ((q.json().get("query") or {}).get("pages") or {}).values():
            url = ((p.get("imageinfo") or [{}])[0]).get("thumburl") or url
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    out.write_bytes(r.content)
    return str(out)


class _Sig(QObject):
    listed = pyqtSignal(object)
    thumb = pyqtSignal(int, bytes)
    got = pyqtSignal(object)


class WallpaperDialog(QDialog):
    """A gallery of the wiki's wallpapers; the chosen one becomes the background (returns its path in self.path)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("wall.title"))
        self.resize(900, 620)
        self.path = ""
        self.items = []
        self.sig = _Sig()
        self.sig.listed.connect(self._listed)
        self.sig.thumb.connect(self._thumb)
        self.sig.got.connect(self._got)
        lay = QVBoxLayout(self)
        self.msg = QLabel(t("wall.loading"))
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.view = QListWidget()
        self.view.setViewMode(QListView.ViewMode.IconMode)
        self.view.setIconSize(QSize(256, 144))
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setSpacing(8)
        self.view.setMovement(QListView.Movement.Static)
        self.view.itemDoubleClicked.connect(lambda _it: self._use())
        lay.addWidget(self.view, 1)
        note = QLabel(t("wall.note"))
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b93a3;")
        lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(t("wall.use"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(t("wall.cancel"))
        bb.accepted.connect(self._use)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        threading.Thread(target=self._load, daemon=True, name="wallpapers").start()

    def _load(self):
        try:
            self.sig.listed.emit(fetch_list())
        except Exception as e:
            self.sig.listed.emit(f"{type(e).__name__}: {e}")

    def _listed(self, items):
        if isinstance(items, str) or not items:
            self.msg.setText(t("wall.none", err=items if isinstance(items, str) else "–"))
            return
        self.items = items
        self.msg.setText(t("wall.count", n=len(items)))
        for it in items:
            name = re.sub(r"\.\w+$", "", it["title"].split(":", 1)[-1]).replace("_", " ")
            li = QListWidgetItem(name)
            li.setToolTip(f"{name}\n{it['w']}×{it['h']}")
            li.setSizeHint(QSize(270, 180))
            self.view.addItem(li)

        def thumbs():
            import requests
            for i, it in enumerate(items):
                try:
                    r = requests.get(it["thumb"], headers=_headers(), timeout=20)
                    if r.status_code == 200:
                        self.sig.thumb.emit(i, r.content)
                except Exception:
                    pass
                time.sleep(0.15)
        threading.Thread(target=thumbs, daemon=True, name="wallpaper-thumbs").start()

    def _thumb(self, i, data):
        pm = QPixmap()
        if pm.loadFromData(data) and i < self.view.count():
            self.view.item(i).setIcon(QIcon(pm))

    def _use(self):
        row = self.view.currentRow()
        if row < 0 or row >= len(self.items):
            return
        self.msg.setText(t("wall.downloading"))
        it = self.items[row]

        def work():
            try:
                self.sig.got.emit(download(it))
            except Exception as e:
                self.sig.got.emit(RuntimeError(f"{type(e).__name__}: {e}"))
        threading.Thread(target=work, daemon=True, name="wallpaper").start()

    def _got(self, res):
        if isinstance(res, Exception):
            self.msg.setText(t("wall.none", err=str(res)))
            return
        self.path = res
        self.accept()


def choose(parent=None) -> str:
    """Opens the gallery; the chosen wallpaper is set as the background at once. Its path, or ""."""
    dlg = WallpaperDialog(parent)
    if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.path:
        return ""
    from app.core import theme
    from app.core.config import save_config
    save_config({"backdrop": True, "backdrop_style": "image", "backdrop_image": dlg.path})
    theme.apply()
    return dlg.path

