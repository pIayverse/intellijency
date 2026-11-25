"""PC Lighting page: controls motherboard, GPU, cooler and fan RGB through OpenRGB's local SDK server."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QPainter, QIcon
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox)

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
except ImportError:  # app still runs without the library; the page explains what's missing
    OpenRGBClient = None

HOST, PORT = "127.0.0.1", 6742
EFFECTS = ["Static", "Rainbow", "Off"]
RAINBOW_MODES = ("rainbow", "rainbow wave", "spectrum cycle", "color cycle", "colour cycle", "synced rainbow")
TYPE_NAMES = {"MOTHERBOARD": "Motherboard", "GPU": "Graphics card", "COOLER": "CPU cooler",
              "LEDSTRIP": "LED strip", "DRAM": "Memory", "KEYBOARD": "Keyboard", "MOUSE": "Mouse",
              "MOUSEMAT": "Mousepad", "HEADSET": "Headset", "SPEAKER": "Speaker", "CASE": "Case",
              "LIGHT": "Light", "UNKNOWN": "Device"}


def _swatch(col: QColor, size=14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(col)
    p.setPen(QColor("#4d5380"))
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(pm)


def _rainbow_swatch(size=14) -> QIcon:
    from PySide6.QtGui import QConicalGradient
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QConicalGradient(size / 2, size / 2, 90)
    for i, hx in enumerate(("#ff3d3d", "#ffd23d", "#2effa8", "#2fb8ff", "#9b5cff", "#ff3d7f", "#ff3d3d")):
        g.setColorAt(i / 6, QColor(hx))
    p.setBrush(g)
    p.setPen(QColor("#4d5380"))
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(pm)


def status_swatch(mode_name: str, col: QColor, size=16) -> QIcon:
    """Dot for a device's current state: a rainbow for cycling effects, else its colour."""
    name = mode_name.lower()
    return _rainbow_swatch(size) if any(name.startswith(m) for m in RAINBOW_MODES) else _swatch(col, size)


def _find_mode(dev, names):
    for m in dev.modes:
        if m.name.lower() in names:
            return m.name
    return None


def current_colour(dev) -> QColor:
    """The colour a device shows now. Modes like ASUS 'Static' keep it in the mode, not in the per-LED list."""
    if dev.modes:
        m = dev.modes[dev.active_mode]
        if getattr(m, "colors", None):
            c = m.colors[0]
            return QColor(c.red, c.green, c.blue)
    if dev.colors:
        c = dev.colors[0]
        return QColor(c.red, c.green, c.blue)
    return QColor(0, 0, 0)


def apply_to_device(dev, effect: str, col: QColor):
    """Set one OpenRGB device to Static colour, Rainbow, or Off."""
    if effect == "Off":
        off = _find_mode(dev, ("off",))
        if off:
            dev.set_mode(off)
            return
        effect, col = "Static", QColor(0, 0, 0)
    if effect == "Rainbow":
        mode = _find_mode(dev, RAINBOW_MODES)
        if mode:
            dev.set_mode(mode)
            return
        effect = "Static"  # device has no rainbow effect; fall back to the chosen colour
    mode = _find_mode(dev, ("static",)) or _find_mode(dev, ("direct",))
    if mode:
        dev.set_mode(mode)
    dev.set_color(RGBColor(col.red(), col.green(), col.blue()))


class PcLightingPage(QWidget):
    def __init__(self, pick_color, log):
        """pick_color(QColor) -> QColor | None opens the app's colour picker; log(msg, ok) writes the status line."""
        super().__init__()
        self._pick, self._log = pick_color, log
        self.client = None
        self.before_change = lambda: None  # set by General Lighting to stop a running sync
        self.all_colour = QColor(255, 140, 26)
        self.dev_colours = {}

        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        outer.addStretch(1)  # spare height goes below the card, not between its rows

        head = QHBoxLayout()
        title = QLabel("PC Lighting")
        title.setObjectName("card_title")
        head.addWidget(title)
        head.addStretch()
        self.btn_rescan = QPushButton("Rescan")
        self.btn_rescan.setToolTip("Look for devices again, e.g. after installing new fans or a cooler")
        self.btn_rescan.clicked.connect(self.rescan)
        head.addWidget(self.btn_rescan)
        lay.addLayout(head)

        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(self.lbl_status)

        # --- all devices at once ---
        lay.addSpacing(6)
        sec = QLabel("All devices")
        sec.setStyleSheet("color: #c4c6d0; font-size: 12px; font-weight: 700;")
        lay.addWidget(sec)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("Effect:"))
        self.cb_all = QComboBox()
        self.cb_all.addItems(EFFECTS)
        self.cb_all.currentTextChanged.connect(lambda e: self.btn_all_col.setEnabled(e == "Static"))
        row.addWidget(self.cb_all)
        self.btn_all_col = QPushButton("Pick Color")
        self.btn_all_col.setIcon(_swatch(self.all_colour))
        self.btn_all_col.clicked.connect(self._pick_all)
        row.addWidget(self.btn_all_col)
        row.addStretch()
        self.btn_all = QPushButton("Apply to All")
        self.btn_all.setStyleSheet("QPushButton { background-color: #ff8c1a; color: #1a1205; font-weight: 700; border: 1px solid #ff8c1a; border-radius: 17px; padding: 8px 24px; } QPushButton:hover { background-color: #ffa64d; } QPushButton:disabled { background-color: #1f2238; border-color: #2f3352; color: #5f6368; }")
        self.btn_all.clicked.connect(self.apply_all)
        row.addWidget(self.btn_all)
        lay.addLayout(row)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("border: none; background-color: #2f3352;")
        lay.addSpacing(4)
        lay.addWidget(line)

        sec2 = QLabel("Devices")
        sec2.setStyleSheet("color: #c4c6d0; font-size: 12px; font-weight: 700;")
        lay.addWidget(sec2)
        self.dev_box = QVBoxLayout()
        self.dev_box.setSpacing(8)
        lay.addLayout(self.dev_box)

        self.rescan()

    # ---------- connection ----------
    def _connect(self) -> bool:
        if OpenRGBClient is None:
            self.lbl_status.setText("The openrgb-python library is missing. Run: python -m pip install openrgb-python")
            return False
        try:
            if self.client is None:
                self.client = OpenRGBClient(HOST, PORT, "Ajazz Control")
            else:
                self.client.update()
            return True
        except Exception:
            self.client = None
            self.lbl_status.setText("Can't reach OpenRGB. Make sure OpenRGB is running (its SDK server on port 6742), then click Rescan.")
            return False

    def rescan(self):
        while self.dev_box.count():
            it = self.dev_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        ok = self._connect()  # also refreshes device states
        self.btn_all.setEnabled(ok)
        if not ok:
            return
        devs = self.client.devices
        n = len(devs)
        self.lbl_status.setText(f"Connected to OpenRGB · {n} device{'s' if n != 1 else ''} found. "
                                "Close Armoury Crate's and NZXT CAM's lighting control so they don't override these settings.")
        if not devs:
            empty = QLabel("No RGB devices found. Install the hardware, restart OpenRGB, then click Rescan.")
            empty.setStyleSheet("color: #9aa0a6;")
            self.dev_box.addWidget(empty)
        for dev in devs:
            self.dev_box.addWidget(self._device_row(dev))

    # ---------- rows ----------
    def _device_row(self, dev):
        row_w = QFrame()
        row_w.setStyleSheet("QFrame#devrow { background-color: #262a45; border: 1px solid #2f3352; border-radius: 10px; }")
        row_w.setObjectName("devrow")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)

        now = current_colour(dev)
        mode_now = dev.modes[dev.active_mode].name if dev.modes else "?"
        dot = QLabel()
        dot.setPixmap(status_swatch(mode_now, now).pixmap(16, 16))
        dot.setToolTip(f"Current: {mode_now}, {now.name().upper()}")
        row.addWidget(dot)

        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel(dev.name)
        name.setStyleSheet("font-weight: 600; color: #e2e2e9;")
        kind = QLabel(f"{TYPE_NAMES.get(dev.type.name, dev.type.name.title())} · now: {mode_now}"
                      + (f" {now.name().upper()}" if mode_now.lower() in ('static', 'direct') else ""))
        kind.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        text.addWidget(name)
        text.addWidget(kind)
        row.addLayout(text, 1)

        col = self.dev_colours.get(dev.id, now if now != QColor(0, 0, 0) else QColor(self.all_colour))
        self.dev_colours[dev.id] = col
        cb = QComboBox()
        cb.addItems(EFFECTS)
        b_col = QPushButton("Color")
        b_col.setIcon(_swatch(col))

        def pick():
            c = self._pick(self.dev_colours[dev.id])
            if c is not None:
                self.dev_colours[dev.id] = c
                b_col.setIcon(_swatch(c))
        b_col.clicked.connect(pick)
        cb.currentTextChanged.connect(lambda e: b_col.setEnabled(e == "Static"))
        b_apply = QPushButton("Apply")

        def apply_one():
            self.before_change()
            try:
                apply_to_device(dev, cb.currentText(), self.dev_colours[dev.id])
                self._log(f"✓ {dev.name}: {cb.currentText()}", True)
            except Exception as e:
                self._log(f"✕ {dev.name}: {e}", False)
            self.rescan()
        b_apply.clicked.connect(apply_one)
        for w in (cb, b_col, b_apply):
            row.addWidget(w)
        return row_w

    # ---------- actions ----------
    def _pick_all(self):
        c = self._pick(self.all_colour)
        if c is not None:
            self.all_colour = c
            self.btn_all_col.setIcon(_swatch(c))

    def apply_all(self) -> bool:
        self.before_change()
        if not self._connect():
            return False
        ok = True
        for dev in self.client.devices:
            try:
                apply_to_device(dev, self.cb_all.currentText(), self.all_colour)
                self.dev_colours[dev.id] = QColor(self.all_colour)
            except Exception as e:
                ok = False
                self._log(f"✕ {dev.name}: {e}", False)
        if ok:
            self._log(f"✓ All PC lighting: {self.cb_all.currentText()}", True)
        self.rescan()
        return ok
