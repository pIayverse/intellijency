"""First-run setup: welcome, devices found (with OpenRGB help), pick a scene, start with Windows."""
import os
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices, QPainter, QColor
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QGridLayout, QCheckBox, QFrame)

from . import startup
from .general_rgb import SCENES, PILL
from .home import SceneTile, DeviceStrip, GHOST, _animating

DONE_FLAG = os.path.expanduser("~/.config/ajazz_studio/welcome_done")
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def needed() -> bool:
    return not os.path.exists(DONE_FLAG)


def mark_done():
    try:
        os.makedirs(os.path.dirname(DONE_FLAG), exist_ok=True)
        open(DONE_FLAG, "w").close()
    except OSError:
        pass


def _title(text):
    t = QLabel(text)
    t.setStyleSheet("color: #f4f5fb; font-size: 24px; font-weight: 800; background: transparent;")
    t.setWordWrap(True)
    return t


def _body(text):
    b = QLabel(text)
    b.setStyleSheet("color: #a9acb8; font-size: 13px; background: transparent;")
    b.setWordWrap(True)
    b.setOpenExternalLinks(True)
    return b


class _Steps(QWidget):
    """Progress dots."""
    def __init__(self, count):
        super().__init__()
        self.count, self.index = count, 0
        self.setFixedSize(count * 22, 10)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for i in range(self.count):
            p.setBrush(QColor("#7c5cff") if i == self.index else QColor("#363846"))
            w = 16 if i == self.index else 8
            p.drawRoundedRect(i * 22, 1, w, 8, 4, 4)
        p.end()


class WelcomeDialog(QDialog):
    def __init__(self, win, parent=None):
        """win: the main window (for devices, OpenRGB and applying the chosen scene)."""
        super().__init__(parent)
        self.win, self.choice = win, next(s for s in SCENES if s["name"] == "Aurora")
        self.setWindowTitle("Welcome to Intellijency")
        self.setFixedSize(760, 520)
        self.setStyleSheet("QDialog { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b1830, stop:0.6 #121318, stop:1 #101622); }")
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 24)
        root.setSpacing(16)
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background: transparent;")
        root.addWidget(self.pages, 1)
        nav = QHBoxLayout()
        self.dots = _Steps(4)
        nav.addWidget(self.dots, 0, Qt.AlignVCenter)
        nav.addStretch()
        self.btn_back = QPushButton("Back")
        self.btn_back.setStyleSheet(GHOST)
        self.btn_back.clicked.connect(lambda: self._go(self.pages.currentIndex() - 1))
        nav.addWidget(self.btn_back)
        self.btn_next = QPushButton("Get started")
        self.btn_next.setStyleSheet(PILL)
        self.btn_next.clicked.connect(self._next)
        nav.addWidget(self.btn_next)
        root.addLayout(nav)

        self.pages.addWidget(self._page_welcome())
        self.pages.addWidget(self._page_devices())
        self.pages.addWidget(self._page_scenes())
        self.pages.addWidget(self._page_done())
        self._go(0)
        self._anim = QTimer(self)
        self._anim.setInterval(66)
        self._anim.timeout.connect(self._tick)
        self._anim.start()

    # ---------- pages ----------
    def _page_welcome(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        v.addStretch()
        logo = QLabel()
        pm = QPixmap(os.path.join(ASSETS, "icon.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setStyleSheet("background: transparent;")
        v.addWidget(logo)
        v.addSpacing(8)
        v.addWidget(_title("Welcome to Intellijency"))
        v.addWidget(_body("One place for every light on your desk. Your keyboard, mouse and PC parts, synced into one look "
                          "with a single click."))
        v.addStretch(2)
        return w

    def _page_devices(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        self.lbl_found = _title("")
        v.addWidget(self.lbl_found)
        self.lbl_found_body = _body("")
        v.addWidget(self.lbl_found_body)
        self.strip = DeviceStrip(self.win._home_devices, self.win._live_device_colour)
        v.addWidget(self.strip)
        self.orgb = QFrame()
        self.orgb.setObjectName("orgb")
        self.orgb.setStyleSheet("QFrame#orgb { background: rgba(124, 92, 255, 0.10); border: 1px solid #3b3270; border-radius: 12px; }")
        o = QHBoxLayout(self.orgb)
        o.setContentsMargins(16, 12, 16, 12)
        msg = _body("<b style='color:#f4f5fb'>Light up more devices.</b> Install OpenRGB (free) so Intellijency can "
                    "control PC parts, mice and other brands.")
        o.addWidget(msg, 1)
        b_get = QPushButton("Get OpenRGB")
        b_get.setStyleSheet(PILL)
        b_get.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://openrgb.org")))
        o.addWidget(b_get)
        b_again = QPushButton("Check again")
        b_again.setStyleSheet(GHOST)
        b_again.clicked.connect(self._scan)
        o.addWidget(b_again)
        v.addWidget(self.orgb)
        v.addStretch()
        return w

    def _page_scenes(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        v.addWidget(_title("Pick a look"))
        v.addWidget(_body("You can change it any time from Home or the tray icon."))
        grid = QGridLayout()
        grid.setSpacing(10)
        self.tiles = []
        for i, scene in enumerate(s for s in SCENES if s["effect"] != "Off"):
            t = SceneTile(scene)
            t.setFixedHeight(84)
            t.clicked.connect(self._choose)
            grid.addWidget(t, i // 4, i % 4)
            self.tiles.append(t)
        v.addLayout(grid)
        v.addStretch()
        self._choose(self.choice)
        return w

    def _page_done(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)
        v.addStretch()
        v.addWidget(_title("You're all set"))
        v.addWidget(_body("Intellijency lives in the tray by the clock, so your lighting keeps playing after you close "
                          "the window. Right-click the icon for scenes, pause and quit."))
        v.addSpacing(8)
        self.chk_start = QCheckBox("Start Intellijency with Windows")
        self.chk_start.setChecked(True)
        self.chk_start.setStyleSheet("QCheckBox { color: #e2e2e9; font-size: 13px; spacing: 10px; background: transparent; }")
        v.addWidget(self.chk_start)
        v.addStretch(2)
        return w

    # ---------- flow ----------
    def _scan(self):
        self.strip.reload()
        n = len(self.strip._items)
        ok = self.win.pc_page._connect()
        self.lbl_found.setText(f"We found {n} device{'s' if n != 1 else ''}" if n else "No devices found yet")
        self.lbl_found_body.setText("These will light up together. You can fine-tune each one later under Devices."
                                    if n else "Plug in your RGB gear, then check again.")
        self.orgb.setVisible(not ok)

    def _choose(self, scene):
        self.choice = scene
        for t in self.tiles:
            t.active = t.scene is scene
            t.update()

    def _go(self, i):
        i = max(0, min(self.pages.count() - 1, i))
        self.pages.setCurrentIndex(i)
        self.dots.index = i
        self.dots.update()
        self.btn_back.setVisible(i > 0)
        self.btn_next.setText(("Get started", "Next", "Next", "Finish")[i])
        if i == 1:
            self._scan()

    def _next(self):
        i = self.pages.currentIndex()
        if i < self.pages.count() - 1:
            self._go(i + 1)
            return
        startup.set_enabled(self.chk_start.isChecked())
        if getattr(self.win, "chk_start", None) is not None:
            self.win.chk_start.setChecked(self.chk_start.isChecked())
        self.win.general_page.apply_scene(self.choice)
        mark_done()
        self.accept()

    def reject(self):  # closing the window counts as "done": don't ask again on every start
        mark_done()
        super().reject()

    def _tick(self):
        if not _animating(self):
            return
        if self.pages.currentIndex() == 1:
            self.strip.update()
        elif self.pages.currentIndex() == 2:
            for t in self.tiles:
                t.update()
