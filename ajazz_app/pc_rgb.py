"""RGB Devices page: lighting for any OpenRGB-supported device (motherboards, GPUs, coolers, fans, and keyboards,
mice and headsets from brands such as Wooting, Razer, Corsair, Logitech and SteelSeries) via OpenRGB's SDK server."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPixmap, QPainter, QIcon
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox)
from .device_art import device_picture
import os, re
from PySide6.QtWidgets import QFileDialog

PICTURE_DIR = os.path.expanduser("~/.config/ajazz_studio/device_pictures")


def _picture_path(device_name: str) -> str:
    return os.path.join(PICTURE_DIR, re.sub(r"[^A-Za-z0-9._-]+", "_", device_name).strip("_") + ".png")


def picture_for(device_name: str, type_key: str, colour: QColor, w: int, h: int) -> QPixmap:
    """The user's own picture for this device if they set one, else the drawn picture for its type."""
    path = _picture_path(device_name)
    if os.path.exists(path):
        pm = QPixmap(path)
        if not pm.isNull():
            dpr = 2
            pm = pm.scaled(w * dpr, h * dpr, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            return pm
    return device_picture(type_key, colour, w, h)

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
    p.setPen(QColor("#4b4e5b"))
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
    p.setPen(QColor("#4b4e5b"))
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
        # set by the main window for keyboards the app drives itself: kb_apply(effect, QColor) -> bool,
        # kb_now() -> (effect name, QColor | None, connected)
        self.kb_apply, self.kb_now, self.kb_name = None, None, "Ajazz AK820 Max HE"
        # set by the main window: sync_now() -> (effect name, set of synced device ids) while a synced effect runs
        self.sync_now = lambda: (None, set())
        self.selected = None  # key of the device whose panel is open
        # set by the main window: live_colour(key, state, colour) -> QColor the device shows right now
        self.live_colour = lambda key, state, colour: colour
        self._live_pics = []  # (label, device name, type, key, state, colour, w, h) for pictures that animate
        self._anim = QTimer(self)
        self._anim.setInterval(80)
        self._anim.timeout.connect(self._animate)
        self._anim.start()
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
        title = QLabel("Devices <span style='color:#9aa0a6; font-weight:500;'>· keyboards, mice and PC parts from any supported brand</span>")
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
        self.lbl_status.setOpenExternalLinks(True)
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
        self.btn_all.setStyleSheet("QPushButton { background-color: #7c5cff; color: #ffffff; font-weight: 700; border: 1px solid #7c5cff; border-radius: 17px; padding: 8px 24px; } QPushButton:hover { background-color: #9378ff; } QPushButton:disabled { background-color: #16171d; border-color: #282a35; color: #5f6368; }")
        self.btn_all.clicked.connect(self.apply_all)
        row.addWidget(self.btn_all)
        lay.addLayout(row)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("border: none; background-color: #282a35;")
        lay.addSpacing(4)
        lay.addWidget(line)

        sec2 = QLabel("Devices <span style='color:#6b6e7a; font-weight:500;'>· click one to change it</span>")
        sec2.setStyleSheet("color: #c4c6d0; font-size: 12px; font-weight: 700;")
        lay.addWidget(sec2)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        lay.addLayout(self.grid)
        self.detail_box = QVBoxLayout()
        lay.addLayout(self.detail_box)

        self.rescan()

    def showEvent(self, e):
        super().showEvent(e)
        self.rescan()  # pick up devices plugged in since, and the keyboard hooks set after construction

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
            self.lbl_status.setText("Can't reach OpenRGB, which handles lighting for most brands. Install it free from <a href='https://openrgb.org' style='color:#9d86ff;'>openrgb.org</a> (or start it), then click Rescan.")
            return False

    def _devices(self):
        """Everything to show: (key, name, type key, kind label, colour now, state text, apply_fn)."""
        out = []
        sync_effect, synced = self.sync_now()
        if self.kb_now is not None:
            effect, col, connected = self.kb_now()
            if connected:
                txt = effect + (f" {col.name().upper()}" if col is not None and effect not in ("Off", "Rainbow", "Unknown") else "")
                out.append(("keyboard", self.kb_name, "KEYBOARD", "Keyboard", col or QColor(0, 0, 0), txt,
                            lambda e, c: self.kb_apply(e, c)))
        ok = self._connect()  # also refreshes device states
        if ok:
            for dev in self.client.devices:
                now = current_colour(dev)
                if dev.id in synced:
                    txt = sync_effect  # streamed by the app; the hardware only sees one frame at a time
                else:
                    mode = dev.modes[dev.active_mode].name if dev.modes else "?"
                    txt = mode + (f" {now.name().upper()}" if mode.lower() in ("static", "direct") else "")
                out.append((dev.id, dev.name, dev.type.name, TYPE_NAMES.get(dev.type.name, dev.type.name.title()), now, txt,
                            lambda e, c, dv=dev: apply_to_device(dv, e, c)))
        return out, ok

    def rescan(self):
        self._live_pics = []
        for box in (self.grid, self.detail_box):
            while box.count():
                it = box.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
        devs, ok = self._devices()
        self.btn_all.setEnabled(bool(devs))
        found = f"{len(devs)} device{'s' if len(devs) != 1 else ''} found."
        self.lbl_status.setText(
            f"{found} Close other RGB apps (Armoury Crate, NZXT CAM, Razer Synapse, iCUE, G HUB) so they don't override these settings."
            if ok else f"{found} OpenRGB isn't running, so only directly supported devices are listed. Install it free from <a href='https://openrgb.org' style='color:#9d86ff;'>openrgb.org</a> (or start it), then click Rescan.")
        if not devs:
            empty = QLabel("No RGB devices found. Plug in the device, make sure OpenRGB is running, then click Rescan.")
            empty.setStyleSheet("color: #9aa0a6;")
            self.grid.addWidget(empty, 0, 0)
            return
        keys = [x[0] for x in devs]
        if self.selected not in keys:
            self.selected = keys[0]
        for i, dv in enumerate(devs):
            self.grid.addWidget(self._card(dv), i // 3, i % 3)
        for col in range(3):
            self.grid.setColumnStretch(col, 1)
        self.detail_box.addWidget(self._detail(devs[keys.index(self.selected)]))

    # ---------- cards ----------
    def _card(self, dv):
        key, name_text, type_key, kind_text, now, state, _ = dv
        sel = key == self.selected
        card = QFrame()
        card.setObjectName("devcard")
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(
            "QFrame#devcard { background-color: %s; border: %s; border-radius: 12px; } QFrame#devcard:hover { border-color: #7c5cff; }"
            % ("#221d38" if sel else "#1d1f27", "1.5px solid #7c5cff" if sel else "1px solid #282a35"))
        card.mousePressEvent = lambda e, k=key: self._select(k)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(4)
        pic = QLabel()
        pic.setAlignment(Qt.AlignCenter)
        self._show_pic(pic, name_text, type_key, key, state, now, 150, 84)
        pic.setStyleSheet("background: transparent; border: none;")
        v.addWidget(pic)
        name = QLabel(name_text)
        name.setStyleSheet("font-weight: 600; color: #e2e2e9; background: transparent; border: none;")
        name.setToolTip(name_text)
        name.setMinimumWidth(10)
        name.setText(name.fontMetrics().elidedText(name_text, Qt.ElideRight, 170))  # long names end in "…", not mid-letter
        v.addWidget(name)
        row = QHBoxLayout()
        row.setSpacing(6)
        dot = QLabel()
        dot.setPixmap(status_swatch(state, now, 12).pixmap(12, 12))
        dot.setStyleSheet("background: transparent; border: none;")
        row.addWidget(dot)
        info = QLabel(f"{kind_text} · {state}")
        info.setStyleSheet("color: #9aa0a6; font-size: 11px; background: transparent; border: none;")
        info.setMinimumWidth(10)
        row.addWidget(info, 1)
        v.addLayout(row)
        return card

    def _set_picture(self, device_name):
        path, _ = QFileDialog.getOpenFileName(self, f"Picture for {device_name}", os.path.expanduser("~/Pictures"),
                                              "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            self._log("✕ That file isn't an image this app can read", False)
            return
        os.makedirs(PICTURE_DIR, exist_ok=True)
        pm.scaled(800, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(_picture_path(device_name), "PNG")
        self._log(f"✓ Picture set for {device_name}", True)
        self.rescan()

    def _clear_picture(self, device_name):
        try:
            os.remove(_picture_path(device_name))
        except OSError:
            pass
        self.rescan()

    def _moving(self, key, state):
        s = state.lower()
        return key == "keyboard" or any(s.startswith(m) for m in RAINBOW_MODES)

    def _show_pic(self, label, name, type_key, key, state, colour, w, h):
        label.setPixmap(picture_for(name, type_key, self.live_colour(key, state, colour) or QColor(0, 0, 0), w, h))
        if self._moving(key, state) and not os.path.exists(_picture_path(name)):  # own photos don't animate
            self._live_pics.append((label, name, type_key, key, state, colour, w, h))

    def _animate(self):
        if not self.isVisible():
            return
        for label, name, type_key, key, state, colour, w, h in self._live_pics:
            try:
                label.setPixmap(device_picture(type_key, self.live_colour(key, state, colour) or QColor(0, 0, 0), w, h))
            except RuntimeError:  # label deleted by a rescan in between
                pass

    def _select(self, key):
        self.selected = key
        self.rescan()

    # ---------- the open device ----------
    def _detail(self, dv):
        key, name_text, type_key, kind_text, now, state, apply_fn = dv
        panel = QFrame()
        panel.setObjectName("devdetail")
        panel.setStyleSheet("QFrame#devdetail { background-color: #1a1b22; border: 1px solid #282a35; border-radius: 12px; }")
        h = QHBoxLayout(panel)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(18)
        pic = QLabel()
        self._show_pic(pic, name_text, type_key, key, state, now, 190, 110)
        pic.setStyleSheet("background: transparent; border: none;")
        h.addWidget(pic)
        right = QVBoxLayout()
        right.setSpacing(6)
        title = QLabel(name_text)
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f4f5fb; background: transparent; border: none;")
        title.setWordWrap(True)
        right.addWidget(title)
        sub_l = QLabel(f"{kind_text} · now: {state}")
        sub_l.setStyleSheet("color: #9aa0a6; background: transparent; border: none;")
        right.addWidget(sub_l)
        right.addSpacing(6)

        if key not in self.dev_colours:
            self.dev_colours[key] = now if now != QColor(0, 0, 0) else QColor(self.all_colour)
        ctl = QHBoxLayout()
        ctl.setSpacing(8)
        ctl.addWidget(QLabel("Effect:"))
        cb = QComboBox()
        cb.addItems(EFFECTS)
        ctl.addWidget(cb)
        b_col = QPushButton("Color")
        b_col.setIcon(_swatch(self.dev_colours[key]))

        def pick():
            c = self._pick(self.dev_colours[key])
            if c is not None:
                self.dev_colours[key] = c
                b_col.setIcon(_swatch(c))
        b_col.clicked.connect(pick)
        cb.currentTextChanged.connect(lambda e: b_col.setEnabled(e == "Static"))
        ctl.addWidget(b_col)
        ctl.addStretch()
        b_apply = QPushButton("Apply")
        b_apply.setObjectName("primary")

        def apply_one():
            self.before_change()
            try:
                if apply_fn(cb.currentText(), self.dev_colours[key]) is False:
                    raise IOError("device didn't respond")
                self._log(f"✓ {name_text}: {cb.currentText()}", True)
            except Exception as e:
                self._log(f"✕ {name_text}: {e}", False)
            self.rescan()
        b_apply.clicked.connect(apply_one)
        ctl.addWidget(b_apply)
        right.addLayout(ctl)

        pic_row = QHBoxLayout()
        pic_row.setSpacing(8)
        b_pic = QPushButton("Set picture...")
        b_pic.setToolTip("Use your own image for this device (kept on this PC only)")
        b_pic.clicked.connect(lambda: self._set_picture(name_text))
        pic_row.addWidget(b_pic)
        if os.path.exists(_picture_path(name_text)):
            b_def = QPushButton("Use default")
            b_def.setToolTip("Go back to the drawn picture")
            b_def.clicked.connect(lambda: self._clear_picture(name_text))
            pic_row.addWidget(b_def)
        pic_row.addStretch()
        right.addLayout(pic_row)
        right.addStretch()
        h.addLayout(right, 1)
        return panel

    # ---------- actions ----------
    def _pick_all(self):
        c = self._pick(self.all_colour)
        if c is not None:
            self.all_colour = c
            self.btn_all_col.setIcon(_swatch(c))

    def apply_all(self) -> bool:
        self.before_change()
        ok = True
        if self.kb_apply is not None and self.kb_now is not None and self.kb_now()[2]:
            if self.kb_apply(self.cb_all.currentText(), self.all_colour) is False:
                ok = False
                self._log(f"✕ {self.kb_name}: didn't respond", False)
        if not self._connect():
            self.rescan()
            return ok
        for dev in self.client.devices:
            try:
                apply_to_device(dev, self.cb_all.currentText(), self.all_colour)
                self.dev_colours[dev.id] = QColor(self.all_colour)
            except Exception as e:
                ok = False
                self._log(f"✕ {dev.name}: {e}", False)
        if ok:
            self._log(f"✓ All devices: {self.cb_all.currentText()}", True)
        self.rescan()
        return ok
