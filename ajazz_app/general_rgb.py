"""General Lighting page: one effect and colour for the keyboard and every OpenRGB device at once."""
import json, math, os
from PySide6.QtCore import Qt, QTimer, QElapsedTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox

from .pc_rgb import TYPE_NAMES, apply_to_device, current_colour, status_swatch, _swatch, _find_mode

try:
    from openrgb.utils import RGBColor
except ImportError:
    RGBColor = None

EFFECTS = ["Static", "Rainbow", "Synced Rainbow", "Synced Gradient", "Off"]
SYNCED = ("Synced Rainbow", "Synced Gradient")  # effects the app has to keep running
SPEEDS = {"Slow": 20.0, "Medium": 8.0, "Fast": 3.0}  # seconds per full colour cycle
FRAME_MS = 40  # 25 colour updates a second
# Keyboard rainbow timing measured by calibrate_rainbow.py. The keyboard saves every lighting write, so it is never
# streamed to; instead the PC parts follow its own rainbow and the keyboard is re-started (one write) to realign.
CAL_PATH = os.path.expanduser("~/.config/ajazz_studio/kb_rainbow.json")
REACTION_S = 0.25  # shortcut: typical delay between seeing red and pressing Space; re-run calibration if colours look off
REALIGN_MS = 10 * 60 * 1000
SETTINGS_PATH = os.path.expanduser("~/.config/ajazz_studio/general_lighting.json")


def gradient_colour(a: QColor, b: QColor, seconds: float, period: float) -> QColor:
    """Smooth back-and-forth fade a -> b -> a, one round trip per period."""
    f = (1 - math.cos(2 * math.pi * seconds / period)) / 2
    return QColor(round(a.red() + (b.red() - a.red()) * f), round(a.green() + (b.green() - a.green()) * f),
                  round(a.blue() + (b.blue() - a.blue()) * f))


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

PILL = ("QPushButton { background-color: #7c5cff; color: #ffffff; font-weight: 700; border: 1px solid #7c5cff; "
        "border-radius: 17px; padding: 8px 24px; } QPushButton:hover { background-color: #9378ff; } "
        "QPushButton:disabled { background-color: #16171d; border-color: #282a35; color: #5f6368; }")
SECTION = "color: #c4c6d0; font-size: 12px; font-weight: 700;"


class GeneralLightingPage(QWidget):
    def __init__(self, pc_page, pick_color, apply_keyboard, keyboard_now, log):
        """pc_page: PcLightingPage (owns the OpenRGB connection).
        apply_keyboard(effect, QColor, speed=None) -> bool sets the keyboard; keyboard_now() -> (effect name, QColor | None, connected)."""
        super().__init__()
        self.pc, self._pick, self._apply_kb, self._kb_now, self._log = pc_page, pick_color, apply_keyboard, keyboard_now, log
        self.colour = QColor(255, 140, 26)
        self.colour2 = QColor(155, 92, 255)
        self._gradient = False
        self.skip = set()  # targets the user unticked: "keyboard" or an OpenRGB device id
        self._sync_devs = []
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._sync_tick)
        self.kb_cal = load_calibration()
        self._follow = False  # PC parts are following the keyboard's own rainbow
        self._realign = QTimer(self)
        self._realign.setInterval(REALIGN_MS)
        self._realign.timeout.connect(self._realign_keyboard)
        pc_page.before_change = self.stop_sync  # a manual change on the PC Lighting tab ends the sync

        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        outer.addStretch(1)

        title = QLabel("General Lighting <span style='color:#9aa0a6; font-weight:500;'>· one look for your keyboard and every PC part</span>")
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
        self.cb_speed.setToolTip("How fast the synced colours move through the rainbow")
        self.cb_speed.currentTextChanged.connect(lambda _: self._clock.restart() if self._timer.isActive() else None)
        self.cb_speed.hide()
        row.addWidget(self.cb_speed)
        self.btn_col = QPushButton("Pick Color")
        self.btn_col.setIcon(_swatch(self.colour))
        self.btn_col.clicked.connect(self._pick_colour)
        row.addWidget(self.btn_col)
        self.btn_col2 = QPushButton("Color 2")
        self.btn_col2.setIcon(_swatch(self.colour2))
        self.btn_col2.setToolTip("Second gradient colour")
        self.btn_col2.clicked.connect(self._pick_colour2)
        self.btn_col2.hide()
        row.addWidget(self.btn_col2)
        row.addStretch()
        self.btn_apply = QPushButton("Apply to Everything")
        self.btn_apply.setStyleSheet(PILL)
        self.btn_apply.clicked.connect(self.apply)
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
                it.widget().deleteLater()
        effect, col, connected = self._kb_now()
        kb_now = (effect + (f" {col.name().upper()}" if col is not None and effect != "Off" else "")) if connected else "not connected"
        self.rows.addWidget(self._row("keyboard", "Ajazz AK820 Max HE", "Keyboard", col, kb_now))
        if self.pc._connect():
            synced = {s.id for s in self._sync_devs} if self._timer.isActive() else set()
            for dev in self.pc.client.devices:
                c = current_colour(dev)
                mode = ("Synced Gradient" if self._gradient else "Synced Rainbow") if dev.id in synced else (dev.modes[dev.active_mode].name if dev.modes else "?")
                self.rows.addWidget(self._row(dev.id, dev.name, TYPE_NAMES.get(dev.type.name, dev.type.name.title()), c,
                                              mode + (f" {c.name().upper()}" if mode.lower() in ("static", "direct") else "")))
        else:
            note = QLabel("PC parts aren't available: OpenRGB isn't running. Only the keyboard will change.")
            note.setStyleSheet("color: #9aa0a6;")
            note.setWordWrap(True)
            self.rows.addWidget(note)

    # ---------- synced rainbow ----------
    def _effect_changed(self, e):
        grad = e == "Synced Gradient"
        self.btn_col.setEnabled(e == "Static" or grad)
        self.btn_col.setText("Color 1" if grad else "Pick Color")
        self.btn_col2.setVisible(grad)
        self.cb_speed.setVisible(e in SYNCED)

    def _sync_tick(self):
        secs = self._clock.elapsed() / 1000.0
        if self._gradient:
            c = gradient_colour(self.colour, self.colour2, secs, SPEEDS[self.cb_speed.currentText()])
        elif self._follow:
            c = QColor.fromHsvF(follow_hue(self.kb_cal, secs), 1.0, 1.0)
        else:
            c = QColor.fromHsvF((secs / SPEEDS[self.cb_speed.currentText()]) % 1.0, 1.0, 1.0)
        rgb = RGBColor(c.red(), c.green(), c.blue())
        for dev in list(self._sync_devs):
            try:
                dev.set_color(rgb, fast=True)  # fast: don't re-read device state every frame
            except Exception:
                self._sync_devs.remove(dev)
                self._log(f"✕ Sync stopped for {dev.name}", False)
        if not self._sync_devs:
            self.stop_sync()

    def start_sync(self, devices, follow=False, gradient=False):
        """follow=True: the keyboard rainbow was just restarted and the clock started with it; match its colour."""
        self._sync_devs = []
        for dev in devices:
            mode = _find_mode(dev, ("direct",)) or _find_mode(dev, ("static",))
            if mode:
                dev.set_mode(mode)
                self._sync_devs.append(dev)
        if self._sync_devs:
            self._follow = follow
            self._gradient = gradient
            if not follow:
                self._clock.start()
            self._timer.start()
            n = len(self._sync_devs)
            parts = f"{n} PC part{'s' if n != 1 else ''}"
            if gradient:
                msg = f"Synced gradient running on {parts}; the keyboard shows Color 1 (it has no two-colour effect)."
            elif follow:
                msg = f"Following the keyboard's rainbow on {parts}; realigns every 10 minutes."
            else:
                msg = f"Synced rainbow running on {parts}."
            self.lbl_sync.setText(msg + " Runs while this app is open, and resumes when it starts.")
            self.lbl_sync.show()
            if follow:
                self._realign.start()

    def stop_sync(self):
        self._timer.stop()
        self._realign.stop()
        self._follow = False
        self._gradient = False
        self._sync_devs = []
        self.lbl_sync.hide()

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

    # ---------- remember and resume ----------
    def save_settings(self):
        data = {"effect": self.cb.currentText(), "colour": self.colour.name(), "colour2": self.colour2.name(),
                "speed": self.cb_speed.currentText(), "skip": [k for k in self.skip if isinstance(k, str)]}
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_settings(self):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            return None
        if s.get("effect") in EFFECTS:
            self.cb.setCurrentText(s["effect"])
        for attr, btn, key in (("colour", self.btn_col, "colour"), ("colour2", self.btn_col2, "colour2")):
            c = QColor(s.get(key, ""))
            if c.isValid():
                setattr(self, attr, c)
                btn.setIcon(_swatch(c))
        if s.get("speed") in SPEEDS:
            self.cb_speed.setCurrentText(s["speed"])
        self.skip = set(s.get("skip", []))  # only "keyboard" is kept: OpenRGB device ids can change between starts
        return s

    def resume(self, attempts=12):
        """At startup: restart a synced effect that was running, waiting for OpenRGB (it may start after us)."""
        if self.cb.currentText() not in SYNCED:
            return
        if self.pc._connect() and self.pc.client.devices:
            self.apply()
        elif attempts > 0:
            QTimer.singleShot(5000, lambda: self.resume(attempts - 1))

    def apply(self) -> bool:
        self.stop_sync()
        effect, failed, done = self.cb.currentText(), [], 0
        self.kb_cal = load_calibration()
        follow = effect == "Synced Rainbow" and "keyboard" not in self.skip and self.kb_cal is not None
        if "keyboard" not in self.skip:
            # the keyboard can't be streamed to safely: in Synced Rainbow it runs its own rainbow (PC parts follow it if
            # calibrated); in Synced Gradient it holds Color 1, as it has no two-colour effect
            kb_effect = {"Synced Rainbow": "Rainbow", "Synced Gradient": "Static"}.get(effect, effect)
            ok = self._restart_keyboard_rainbow() if follow else self._apply_kb(kb_effect, self.colour)
            if ok:
                done += 1
            else:
                failed.append("keyboard")
        if self.pc._connect():
            targets = [dev for dev in self.pc.client.devices if dev.id not in self.skip]
            if effect in SYNCED:
                try:
                    self.start_sync(targets, follow=follow, gradient=effect == "Synced Gradient")
                    done += len(self._sync_devs)
                except Exception as e:
                    failed.append(f"PC parts ({e})")
            else:
                for dev in targets:
                    try:
                        apply_to_device(dev, effect, self.colour)
                        done += 1
                    except Exception:
                        failed.append(dev.name)
        self.save_settings()
        if failed:
            self._log(f"✕ Couldn't update: {', '.join(failed)}", False)
        else:
            self._log(f"✓ {effect} applied to {done} device{'s' if done != 1 else ''}", True)
        self.refresh()
        return not failed
