"""Home dashboard: what's lighting up now, every device glowing live, and one-click scenes."""
import time
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QPen, QFont, QPainterPath, QRadialGradient
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout

from .general_rgb import SCENES, STREAMED, SPEEDS, effect_colour, PILL
from .pc_rgb import picture_for

GHOST = ("QPushButton { background: rgba(255,255,255,0.05); color: #e2e2e9; border: 1px solid #2e303c; "
         "border-radius: 17px; padding: 9px 20px; font-weight: 600; } QPushButton:hover { border-color: #7c5cff; }")


def _animating(widget):
    from . import demo
    w = widget.window()
    return widget.isVisible() and (demo.ENABLED or (w.isActiveWindow() and not w.isMinimized()))


def scene_colours(scene, t, stops):
    """`stops` colours across a scene's preview at time t (same maths the devices use)."""
    c1, c2, period = QColor(scene["c1"]), QColor(scene["c2"]), SPEEDS[scene["speed"]] / 2  # previews run 2x faster
    mode = STREAMED.get(scene["effect"])
    if scene["effect"] == "Off":
        return [QColor("#15161c")] * stops
    if mode == "rainbow":
        return [QColor.fromHsvF((t / period + i / stops * 0.35) % 1.0, 0.9, 1.0) for i in range(stops)]
    if mode is None:  # static
        return [c1] * stops
    return [effect_colour(mode, c1, c2, t, period, i, stops) for i in range(stops)]


class SceneTile(QWidget):
    clicked = Signal(dict)

    def __init__(self, scene):
        super().__init__()
        self.scene, self.active = scene, False
        self.setFixedHeight(96)
        self.setMinimumWidth(150)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{scene['name']}: {scene['effect']} on every device")
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.scene)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(r, 14, 14)
        p.setClipPath(clip)
        cols = scene_colours(self.scene, time.monotonic(), 6)
        g = QLinearGradient(r.topLeft(), r.topRight())
        for i, c in enumerate(cols):
            g.setColorAt(i / (len(cols) - 1), c)
        p.fillRect(r, g)
        shade = QLinearGradient(r.topLeft(), r.bottomLeft())  # darken toward the bottom so the label reads
        shade.setColorAt(0, QColor(10, 11, 15, 40))
        shade.setColorAt(1, QColor(10, 11, 15, 215))
        p.fillRect(r, shade)
        p.setClipping(False)
        p.setPen(QColor("#ffffff"))
        f = QFont(self.font())
        f.setPointSizeF(11.5)
        f.setBold(True)
        p.setFont(f)
        p.drawText(r.adjusted(14, 0, -14, -26), Qt.AlignLeft | Qt.AlignBottom, self.scene["name"])
        f.setBold(False)
        f.setPointSizeF(8.5)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 170))
        p.drawText(r.adjusted(14, 0, -14, -10), Qt.AlignLeft | Qt.AlignBottom, self.scene["effect"])
        if self.active:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 235))
            badge = QRectF(r.right() - 64, r.top() + 10, 54, 20)
            p.drawRoundedRect(badge, 10, 10)
            p.setPen(QColor("#121318"))
            f.setBold(True)
            f.setPointSizeF(7.5)
            p.setFont(f)
            p.drawText(badge, Qt.AlignCenter, "ACTIVE")
        border = QColor("#ffffff") if self.active else (QColor("#7c5cff") if self._hover else QColor(255, 255, 255, 28))
        p.setPen(QPen(border, 2 if (self.active or self._hover) else 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 14, 14)
        p.end()


class DeviceStrip(QWidget):
    """Every device, drawn in its live colour, side by side."""

    def __init__(self, devices, colour_of):
        super().__init__()
        self._devices, self._colour_of = devices, colour_of  # devices() -> list of (key, name, type, state, colour)
        self.setMinimumHeight(118)
        self._items = []

    def reload(self):
        self._items = self._devices()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        items = self._items
        if not items:
            p.setPen(QColor("#8a8d99"))
            p.drawText(self.rect(), Qt.AlignCenter, "No devices yet. Plug something in, or install OpenRGB.")
            return
        n = len(items)
        cell = min(150.0, self.width() / n)
        x0 = (self.width() - cell * n) / 2
        f = QFont(self.font())
        f.setPointSizeF(8)
        p.setFont(f)
        for i, (key, name, kind, state, colour) in enumerate(items):
            c = self._colour_of(key, state, colour)
            pm = picture_for(name, kind, c if c is not None else QColor(0, 0, 0), int(cell - 14), 74)
            x = x0 + i * cell
            p.drawPixmap(QPointF(x + 7, 8), pm)
            p.setPen(QColor("#a9acb8"))
            p.drawText(QRectF(x + 2, 88, cell - 4, 26), Qt.AlignHCenter | Qt.AlignTop,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, int(cell - 8)))
        p.end()


class HomePage(QWidget):
    def __init__(self, general_page, devices, colour_of, keyboard_ready, open_page):
        """devices() -> [(key, name, type, state, colour)]; colour_of(key, state, colour) -> live QColor;
        keyboard_ready() -> bool; open_page(index) switches the main window's page."""
        super().__init__()
        self.gp, self._kb_ready = general_page, keyboard_ready
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        # --- hero ---
        hero = QFrame()
        hero.setObjectName("hero")
        hero.setStyleSheet("QFrame#hero { border-radius: 18px; border: 1px solid #2a2c38; "
                           "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1d1a33, stop:0.55 #15161c, stop:1 #121a2a); }")
        h = QVBoxLayout(hero)
        h.setContentsMargins(24, 20, 24, 16)
        h.setSpacing(4)
        self.lbl_hello = QLabel()
        self.lbl_hello.setStyleSheet("color: #9d86ff; font-size: 12px; font-weight: 700; background: transparent;")
        h.addWidget(self.lbl_hello)
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("color: #f4f5fb; font-size: 26px; font-weight: 800; background: transparent;")
        h.addWidget(self.lbl_title)
        self.lbl_now = QLabel()
        self.lbl_now.setStyleSheet("color: #a9acb8; font-size: 13px; background: transparent;")
        h.addWidget(self.lbl_now)
        h.addSpacing(8)
        self.strip = DeviceStrip(devices, colour_of)
        self.strip.setStyleSheet("background: transparent;")
        h.addWidget(self.strip)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.btn_pause = QPushButton("Pause effects")
        self.btn_pause.setStyleSheet(GHOST)
        self.btn_pause.clicked.connect(self._toggle_pause)
        actions.addWidget(self.btn_pause)
        btn_custom = QPushButton("Customise")
        btn_custom.setStyleSheet(GHOST)
        btn_custom.clicked.connect(lambda: open_page(7))
        actions.addWidget(btn_custom)
        btn_dev = QPushButton("Devices")
        btn_dev.setStyleSheet(GHOST)
        btn_dev.clicked.connect(lambda: open_page(6))
        actions.addWidget(btn_dev)
        actions.addStretch()
        h.addLayout(actions)
        outer.addWidget(hero)

        # --- scenes ---
        head = QLabel("Scenes <span style='color:#6b6e7a; font-weight:500;'>· one click lights every device</span>")
        head.setStyleSheet("color: #f4f5fb; font-size: 15px; font-weight: 800;")
        outer.addWidget(head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self.tiles = []
        for i, scene in enumerate(SCENES):
            t = SceneTile(scene)
            t.clicked.connect(self._apply_scene)
            grid.addWidget(t, i // 3, i % 3)
            self.tiles.append(t)
        for col in range(3):
            grid.setColumnStretch(col, 1)
        outer.addLayout(grid)
        outer.addStretch(1)

        self._anim = QTimer(self)
        self._anim.setInterval(66)
        self._anim.timeout.connect(self._tick)
        self._anim.start()
        self.gp.changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def _apply_scene(self, scene):
        self.gp.apply_scene(scene)

    def _toggle_pause(self):
        if self.gp.sync_now()[0]:
            self.gp.stop_sync()
        else:
            self.gp.apply(scene_name=self.gp.scene)
        self.refresh()

    def refresh(self):
        hour = datetime.now().hour
        self.lbl_hello.setText(("Good morning" if 5 <= hour < 12 else "Good afternoon" if hour < 18 else "Good evening").upper())
        self.strip.reload()
        n = len(self.strip._items)
        running, ids = self.gp.sync_now()
        look = self.gp.scene or (running or self.gp.cb.currentText())
        self.lbl_title.setText(f"Your setup is glowing" if running else "Your setup")
        state = f"Now playing <b style='color:#f4f5fb'>{look}</b>" if running else "Effects paused"
        self.lbl_now.setText(f"{state} &nbsp;·&nbsp; {n} device{'s' if n != 1 else ''}"
                             + (" &nbsp;·&nbsp; keyboard connected" if self._kb_ready() else ""))
        self.btn_pause.setText("Pause effects" if running else "Resume effects")
        for t in self.tiles:
            t.active = t.scene["name"] == self.gp.scene and (bool(running) or t.scene["effect"] == "Off")
            t.update()

    def _tick(self):
        if not _animating(self):
            return
        self.strip.update()
        for t in self.tiles:
            t.update()
