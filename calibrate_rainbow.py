"""Times the keyboard's built-in rainbow so the PC parts can follow it.

Start restarts the keyboard rainbow (one normal lighting write) and starts a clock. Press Space every time the whole
keyboard is pure red, then say which colour follows red. Saves period / first-red time / direction to
~/.config/ajazz_studio/kb_rainbow.json for the app's Synced Rainbow.
"""
import json, os, sys, time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ajazz_app.core import AjazzController, EFFECTS

SPEED = 3  # the speed the app uses when it follows the keyboard
OUT = os.path.expanduser("~/.config/ajazz_studio/kb_rainbow.json")


def fit(t0, presses):
    """Cycle length = average gap between reds; first red = time of the first press after start."""
    gaps = [b - a for a, b in zip(presses, presses[1:])]
    period = sum(gaps) / len(gaps)
    return period, presses[0] - t0


class Calib(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rainbow calibration")
        self.setStyleSheet("QWidget { background: #1b1d31; color: #e2e2e9; font-size: 14px; } "
                           "QPushButton { background: #282c48; border: 1px solid #3a3f66; border-radius: 8px; padding: 8px 16px; } "
                           "QPushButton:hover { border-color: #ff8c1a; }")
        self.ctrl, self.t0, self.presses, self.direction = AjazzController(), None, [], None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(14)
        self.info = QLabel("1. Click Start. The keyboard's rainbow restarts.\n"
                           "2. Every time the WHOLE keyboard is pure red, press SPACE (keep this window focused).\n"
                           "3. After 4 presses, pick which colour comes right after red.")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.count = QLabel("Presses: 0 / 4")
        self.count.setStyleSheet("font-size: 22px; font-weight: 800; color: #ff8c1a;")
        lay.addWidget(self.count)
        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self.start)
        lay.addWidget(self.btn_start)
        row = QHBoxLayout()
        self.btn_y = QPushButton("After red comes yellow / orange")
        self.btn_p = QPushButton("After red comes purple / pink")
        self.btn_y.clicked.connect(lambda: self.finish(+1))
        self.btn_p.clicked.connect(lambda: self.finish(-1))
        for b in (self.btn_y, self.btn_p):
            b.setEnabled(False)
            row.addWidget(b)
        lay.addLayout(row)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        lay.addWidget(self.result)
        self.resize(560, 300)

    def start(self):
        ok = self.ctrl.apply_light(mode=EFFECTS["Spectrum Cycle"], rainbow=1, brightness=5, speed=SPEED, direction=0)
        self.t0 = time.perf_counter()
        self.presses = []
        self.count.setText("Presses: 0 / 4")
        self.result.setText("" if ok else "Couldn't reach the keyboard. Close other RGB apps and try again.")
        self.setFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and self.t0 is not None and not e.isAutoRepeat() and len(self.presses) < 4:
            self.presses.append(time.perf_counter())
            self.count.setText(f"Presses: {len(self.presses)} / 4")
            if len(self.presses) == 4:
                self.btn_y.setEnabled(True)
                self.btn_p.setEnabled(True)
                self.info.setText("Now pick which colour comes right after red.")

    def finish(self, direction):
        period, first_red = fit(self.t0, self.presses)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump({"speed": SPEED, "period": period, "first_red": first_red, "direction": direction}, open(OUT, "w"), indent=2)
        self.result.setText(f"Saved. One cycle takes {period:.2f} s; first red after {first_red:.2f} s. You can close this window.")
        self.btn_y.setEnabled(False)
        self.btn_p.setEnabled(False)


if __name__ == "__main__":
    assert fit(0.0, [1.0, 9.0, 17.0, 25.0]) == (8.0, 1.0)  # self-check of the maths
    app = QApplication(sys.argv)
    w = Calib()
    w.show()
    sys.exit(app.exec())
