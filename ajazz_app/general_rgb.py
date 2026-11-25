"""General Lighting page: one effect and colour for the keyboard and every OpenRGB device at once.

Synced effects (rainbow, gradient, breathing, wave) are driven by the app: it computes the colours on one clock and
streams them to every OpenRGB device. The keyboard is never streamed to (it saves every lighting write), so it runs
its own rainbow (followed by the other devices when calibrated) or holds Color 1.
"""
import json, math, os
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox

from .pc_rgb import TYPE_NAMES, apply_to_device, current_colour, status_swatch, _swatch, _find_mode

try:
    from openrgb.utils import RGBColor
except ImportError:
    RGBColor = None

# effect name -> how the app drives it (None: a one-off hardware setting)
STREAMED = {"Synced Rainbow": "rainbow", "Synced Gradient": "gradient", "Breathing": "breathing", "Wave": "wave"}
EFFECTS = ["Static", "Rainbow", "Synced Rainbow", "Synced Gradient", "Breathing", "Wave", "Off"]
SYNCED = tuple(STREAMED)
TWO_COLOURS = ("Synced Gradient", "Wave")
ONE_COLOUR = ("Static", "Breathing")
SPEEDS = {"Slow": 20.0, "Medium": 8.0, "Fast": 3.0}  # seconds per full cycle
FRAME_MS = 40  # 25 colour updates a second

# Ready-made looks. Colours are the scene's identity; the effect decides how they move.
SCENES = [
    {"name": "Rainbow", "effect": "Synced Rainbow", "c1": "#ff3d3d", "c2": "#2fb8ff", "speed": "Medium"},
    {"name": "Aurora", "effect": "Wave", "c1": "#00f5a0", "c2": "#7c5cff", "speed": "Slow"},
    {"name": "Sunset", "effect": "Synced Gradient", "c1": "#ff5e3a", "c2": "#ff2d95", "speed": "Medium"},
    {"name": "Cyberpunk", "effect": "Wave", "c1": "#ff00c8", "c2": "#00e5ff", "speed": "Medium"},
    {"name": "Ocean", "effect": "Wave", "c1": "#0047ff", "c2": "#00d4ff", "speed": "Slow"},
    {"name": "Lava", "effect": "Synced Gradient", "c1": "#ff2200", "c2": "#ff9900", "speed": "Fast"},
    {"name": "Ice", "effect": "Breathing", "c1": "#9be7ff", "c2": "#ffffff", "speed": "Slow"},
    {"name": "Forest", "effect": "Breathing", "c1": "#2ee66b", "c2": "#0b8f3c", "speed": "Medium"},
    {"name": "Lights off", "effect": "Off", "c1": "#000000", "c2": "#000000", "speed": "Medium"},
]

# Keyboard rainbow timing measured by calibrate_rainbow.py. The keyboard saves every lighting write, so it is never
# streamed to; instead the other devices follow its own rainbow and the keyboard is re-started (one write) to realign.
CAL_PATH = os.path.expanduser("~/.config/ajazz_studio/kb_rainbow.json")
REACTION_S = 0.25  # shortcut: typical delay between seeing red and pressing Space; re-run calibration if colours look off
REALIGN_MS = 10 * 60 * 1000
SETTINGS_PATH = os.path.expanduser("~/.config/ajazz_studio/general_lighting.json")


def _blend(a: QColor, b: QColor, f: float) -> QColor:
    return QColor(round(a.red() + (b.red() - a.red()) * f), round(a.green() + (b.green() - a.green()) * f),
                  round(a.blue() + (b.blue() - a.blue()) * f))


def gradient_colour(a: QColor, b: QColor, seconds: float, period: float) -> QColor:
    """Smooth back-and-forth fade a -> b -> a, one round trip per period."""
    return _blend(a, b, (1 - math.cos(2 * math.pi * seconds / period)) / 2)


def breathing_colour(c: QColor, seconds: float, period: float) -> QColor:
    """The colour fading down to a soft glow and back up, once per period."""
    f = 0.12 + 0.88 * (1 - math.cos(2 * math.pi * seconds / period)) / 2
    return QColor(round(c.red() * f), round(c.green() * f), round(c.blue() * f))


def effect_colour(mode, c1: QColor, c2: QColor, seconds: float, period: float, index=0, count=1, cal=None) -> QColor:
    """Colour of device `index` (of `count`) at `seconds` for a streamed effect."""
    if mode == "gradient":
        return gradient_colour(c1, c2, seconds, period)
    if mode == "breathing":
        return breathing_colour(c1, seconds, period)
    if mode == "wave":  # the same fade, each device a step later, so colour travels across the setup
        return gradient_colour(c1, c2, seconds - period * index / max(count, 1), period)
    if mode == "follow" and cal is not None:
        return QColor.fromHsvF(follow_hue(cal, seconds), 1.0, 1.0)
    return QColor.fromHsvF((seconds / period) % 1.0, 1.0, 1.0)


def load_calibration():
    try:
        with open(CAL_PATH, encoding="utf-8") as f:
            c = json.load(f)
        return c if c.get("period", 0) > 0 and c.get("direction") in (1, -1) else None
    except (OSError, ValueError):
        return None


def follow_hue(cal, seconds_since_restart):
    """Keyboard's hue (0..1, red = 0) this many seconds after its rainbow was restarted."""
    t = seconds_since_restart - (cal["first_red"] - REACTION_S)
    return (cal["direction"] * t / cal["period"]) % 1.0


PILL = ("QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c5cff, stop:1 #5b8cff); "
        "color: #ffffff; font-weight: 700; border: none; border-radius: 17px; padding: 9px 26px; } "
        "QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9378ff, stop:1 #78a2ff); } "
        "QPushButton:disabled { background-color: #16171d; color: #5f6368; }")
SECTION = "color: #c4c6d0; font-size: 12px; font-weight: 700;"


class GeneralLightingPage(QWidget):
    changed = Signal()  # effect started / stopped; listeners refresh their "now playing"

    def __init__(self, pc_page, pick_color, apply_keyboard, keyboard_now, log):
        """pc_page: PcLightingPage (owns the OpenRGB connection).
        apply_keyboard(effect, QColor, speed=None) -> bool sets the keyboard; keyboard_now() -> (effect name, QColor | None, connected)."""
        super().__init__()
        self.pc, self._pick, self._apply_kb, self._kb_now, self._log = pc_page, pick_color, apply_keyboard, keyboard_now, log
        self.colour = QColor(255, 140, 26)
        self.colour2 = QColor(155, 92, 255)
        self.scene = None  # name of the last scene applied, for the Home page
        self._mode = None  # streamed effect while running: rainbow / follow / gradient / breathing / wave
        self.skip = set()  # targets the user unticked: "keyboard" or an OpenRGB device id
        self._sync_devs = []
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._sync_tick)
        self.kb_cal = load_calibration()
        self._realign = QTimer(self)
        self._realign.setInterval(REALIGN_MS)
        self._realign.timeout.connect(self._realign_keyboard)
        pc_page.before_change = self.stop_sync  # a manual change on the Devices tab ends the sync

        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        outer.addStretch(1)

        title = QLabel("General Lighting <span style='color:#9aa0a6; font-weight:500;'>· one look for every device</span>")
        title.setObjectName("card_title")
        lay.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("Effect:"))
        self.cb = QComboBox()
        self.cb.addItems(EFFECTS)
        self.cb.currentTextChanged.connect(self._effect_changed)
        row.addWidget(self.cb)
        self.cb_speed = QComboBox()
        self.cb_speed.addItems(list(SPEEDS))
        self.cb_speed.setCurrentText("Medium")
        self.cb_speed.setToolTip("How fast the colours move")
        self.cb_speed.currentTextChanged.connect(lambda _: self._clock.restart() if self._timer.isActive() and self._mode != "follow" else None)
        self.cb_speed.hide()
        row.addWidget(self.cb_speed)
        self.btn_col = QPushButton("Pick Color")
        self.btn_col.setIcon(_swatch(self.colour))
        self.btn_col.clicked.connect(self._pick_colour)
        row.addWidget(self.btn_col)
        self.btn_col2 = QPushButton("Color 2")
        self.btn_col2.setIcon(_swatch(self.colour2))
        self.btn_col2.setToolTip("Second colour")
        self.btn_col2.clicked.connect(self._pick_colour2)
        self.btn_col2.hide()
        row.addWidget(self.btn_col2)
        row.addStretch()
        self.btn_apply = QPushButton("Apply to Everything")
        self.btn_apply.setStyleSheet(PILL)
        self.btn_apply.clicked.connect(lambda: self.apply())
        row.addWidget(self.btn_apply)
        lay.addLayout(row)
        self.lbl_sync = QLabel()
        self.lbl_sync.setWordWrap(True)
        self.lbl_sync.setStyleSheet("color: #9aa0a6;")
        self.lbl_sync.hide()
        lay.addWidget(self.lbl_sync)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("border: none; background-color: #282a35;")
        lay.addSpacing(6)
        lay.addWidget(line)
        lay.addSpacing(6)
        head = QHBoxLayout()
        sec = QLabel("Applies to")
        sec.setStyleSheet(SECTION)
        head.addWidget(sec)
        head.addStretch()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip("Reload the device list and their current colours")
        self.btn_refresh.clicked.connect(self.refresh)
        head.addWidget(self.btn_refresh)
        lay.addLayout(head)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(8)
        lay.addLayout(self.rows)
        self.load_settings()
        self._effect_changed(self.cb.currentText())
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    # ---------- list ----------
    def _row(self, key, name, kind, colour, now_text):
        w = QFrame()
        w.setObjectName("devrow")
        w.setStyleSheet("QFrame#devrow { background-color: #1d1f27; border: 1px solid #282a35; border-radius: 10px; }")
        r = QHBoxLayout(w)
        r.setContentsMargins(12, 8, 12, 8)
        r.setSpacing(10)
        chk = QCheckBox()
        chk.setChecked(key not in self.skip)
        chk.setToolTip("Include in Apply to Everything")
        chk.toggled.connect(lambda on, k=key: self.skip.discard(k) if on else self.skip.add(k))
        r.addWidget(chk)
        dot = QLabel()
        dot.setPixmap(status_swatch(now_text, colour or QColor(0, 0, 0)).pixmap(16, 16))
        r.addWidget(dot)
        text = QVBoxLayout()
        text.setSpacing(0)
        n = QLabel(name)
        n.setStyleSheet("font-weight: 600; color: #e2e2e9;")
        k = QLabel(f"{kind} · now: {now_text}")
        k.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        text.addWidget(n)
        text.addWidget(k)
        r.addLayout(text, 1)
        return w

    def refresh(self):
        while self.rows.count():
            it = self.rows.takeAt(0)
            if it.widget():
                it.widget().hide()  # gone from view now; freed by deleteLater on the next loop
                it.widget().deleteLater()
        effect, col, connected = self._kb_now()
        kb_now = (effect + (f" {col.name().upper()}" if col is not None and effect != "Off" else "")) if connected else "not connected"
        self.rows.addWidget(self._row("keyboard", "Ajazz AK820 Max HE", "Keyboard", col, kb_now))
        if self.pc._connect():
            name, synced = self.sync_now()
            for dev in self.pc.client.devices:
                c = current_colour(dev)
                mode = name if dev.id in synced else (dev.modes[dev.active_mode].name if dev.modes else "?")
                self.rows.addWidget(self._row(dev.id, dev.name, TYPE_NAMES.get(dev.type.name, dev.type.name.title()), c,
                                              mode + (f" {c.name().upper()}" if mode.lower() in ("static", "direct") else "")))
        else:
            note = QLabel("Other devices aren't available: OpenRGB isn't running. Install it free from <a href='https://openrgb.org' style='color:#9d86ff;'>openrgb.org</a> for lighting on most brands.")
            note.setOpenExternalLinks(True)
            note.setStyleSheet("color: #9aa0a6;")
            note.setWordWrap(True)
            self.rows.addWidget(note)

    # ---------- streamed effects ----------
    def _effect_changed(self, e):
        two = e in TWO_COLOURS
        self.btn_col.setEnabled(e in ONE_COLOUR or two)
        self.btn_col.setText("Color 1" if two else "Pick Color")
        self.btn_col2.setVisible(two)
        self.cb_speed.setVisible(e in SYNCED)

    def period(self):
        return SPEEDS[self.cb_speed.currentText()]

    def frame_colour(self, secs, index=0, count=1):
        return effect_colour(self._mode, self.colour, self.colour2, secs, self.period(), index, count, self.kb_cal)

    def current_colour(self, dev_id=None):
        """Colour a streamed device shows right now (the first one if no id); None when nothing is streaming."""
        if not self._timer.isActive():
            return None
        ids = [d.id for d in self._sync_devs]
        i = ids.index(dev_id) if dev_id in ids else 0
        return self.frame_colour(self._clock.elapsed() / 1000.0, i, len(ids))

    def _sync_tick(self):
        secs, n = self._clock.elapsed() / 1000.0, len(self._sync_devs)
        for i, dev in enumerate(list(self._sync_devs)):
            c = self.frame_colour(secs, i, n)
            try:
                dev.set_color(RGBColor(c.red(), c.green(), c.blue()), fast=True)  # fast: no state re-read per frame
            except Exception:
                self._sync_devs.remove(dev)
                self._log(f"✕ Sync stopped for {dev.name}", False)
        if not self._sync_devs:
            self.stop_sync()

    def start_sync(self, devices, mode):
        """mode 'follow': the keyboard rainbow was just restarted and the clock started with it; match its colour."""
        self._sync_devs = []
        for dev in devices:
            m = _find_mode(dev, ("direct",)) or _find_mode(dev, ("static",))
            if m:
                dev.set_mode(m)
                self._sync_devs.append(dev)
        if not self._sync_devs:
            return
        self._mode = mode
        if mode != "follow":
            self._clock.start()
        self._timer.start()
        n = len(self._sync_devs)
        parts = f"{n} device{'s' if n != 1 else ''}"
        msg = {"follow": f"Following the keyboard's rainbow on {parts}; realigns every 10 minutes.",
               "rainbow": f"Synced rainbow running on {parts}."}.get(
            mode, f"{self.cb.currentText()} running on {parts}; the keyboard shows Color 1.")
        self.lbl_sync.setText(msg + " Runs while this app is open, and resumes when it starts.")
        self.lbl_sync.show()
        if mode == "follow":
            self._realign.start()

    def sync_now(self):
        """(effect name, ids of devices being streamed to) while an effect is streaming, else (None, set())."""
        if not self._timer.isActive():
            return None, set()
        name = "Synced Rainbow" if self._mode in ("rainbow", "follow") else self.cb.currentText()
        return name, {dv.id for dv in self._sync_devs}

    def stop_sync(self):
        was = self._timer.isActive()
        self._timer.stop()
        self._realign.stop()
        self._mode = None
        self._sync_devs = []
        self.lbl_sync.hide()
        if was:
            self.changed.emit()

    def _restart_keyboard_rainbow(self) -> bool:
        ok = self._apply_kb("Rainbow", self.colour, self.kb_cal["speed"])
        self._clock.start()  # time zero = the moment the keyboard's rainbow restarted
        return ok

    def _realign_keyboard(self):
        if not self._restart_keyboard_rainbow():
            self._log("✕ Couldn't realign the keyboard rainbow", False)

    # ---------- actions ----------
    def _pick_colour(self):
        c = self._pick(self.colour)
        if c is not None:
            self.colour = c
            self.btn_col.setIcon(_swatch(c))

    def _pick_colour2(self):
        c = self._pick(self.colour2)
        if c is not None:
            self.colour2 = c
            self.btn_col2.setIcon(_swatch(c))

    def set_look(self, effect, c1=None, c2=None, speed=None):
        """Load an effect and colours into the controls (without applying)."""
        self.cb.setCurrentText(effect)
        for attr, btn, val in (("colour", self.btn_col, c1), ("colour2", self.btn_col2, c2)):
            c = QColor(val) if val else None
            if c is not None and c.isValid():
                setattr(self, attr, c)
                btn.setIcon(_swatch(c))
        if speed in SPEEDS:
            self.cb_speed.setCurrentText(speed)

    def apply_scene(self, scene: dict) -> bool:
        self.set_look(scene["effect"], scene["c1"], scene["c2"], scene["speed"])
        ok = self.apply(scene_name=scene["name"])
        return ok

    # ---------- remember and resume ----------
    def save_settings(self):
        data = {"effect": self.cb.currentText(), "colour": self.colour.name(), "colour2": self.colour2.name(),
                "speed": self.cb_speed.currentText(), "skip": [k for k in self.skip if isinstance(k, str)],
                "scene": self.scene}
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_settings(self):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            return None
        self.set_look(s.get("effect") if s.get("effect") in EFFECTS else "Static", s.get("colour"), s.get("colour2"), s.get("speed"))
        self.skip = set(s.get("skip", []))  # only "keyboard" is kept: OpenRGB device ids can change between starts
        self.scene = s.get("scene")
        return s

    def resume(self, attempts=12):
        """At startup: restart a streamed effect that was running, waiting for OpenRGB (it may start after us)."""
        if self.cb.currentText() not in SYNCED:
            return
        if self.pc._connect() and self.pc.client.devices:
            self.apply(scene_name=self.scene)
        elif attempts > 0:
            QTimer.singleShot(5000, lambda: self.resume(attempts - 1))

    def apply(self, scene_name=None) -> bool:
        self.stop_sync()
        effect, failed, done = self.cb.currentText(), [], 0
        self.scene = scene_name
        self.kb_cal = load_calibration()
        mode = STREAMED.get(effect)
        if mode == "rainbow" and "keyboard" not in self.skip and self.kb_cal is not None:
            mode = "follow"
        if "keyboard" not in self.skip:
            # the keyboard can't be streamed to safely: in Synced Rainbow it runs its own rainbow (others follow it if
            # calibrated); in the other streamed effects it holds Color 1
            kb_effect = "Rainbow" if mode in ("rainbow", "follow") else ("Static" if mode else effect)
            ok = self._restart_keyboard_rainbow() if mode == "follow" else self._apply_kb(kb_effect, self.colour)
            if ok:
                done += 1
            else:
                failed.append("keyboard")
        if self.pc._connect():
            targets = [dev for dev in self.pc.client.devices if dev.id not in self.skip]
            if mode:
                try:
                    self.start_sync(targets, mode)
                    done += len(self._sync_devs)
                except Exception as e:
                    failed.append(f"devices ({e})")
            else:
                for dev in targets:
                    try:
                        apply_to_device(dev, effect, self.colour)
                        done += 1
                    except Exception:
                        failed.append(dev.name)
        self.save_settings()
        what = scene_name or effect
        if failed:
            self._log(f"✕ Couldn't update: {', '.join(failed)}", False)
        else:
            self._log(f"✓ {what} applied to {done} device{'s' if done != 1 else ''}", True)
        self.refresh()
        self.changed.emit()
        return not failed
