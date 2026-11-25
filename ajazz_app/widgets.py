import math
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QEvent
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class _MaterialDial(QWidget):
    changed = Signal(int)

    def __init__(self, min_i: int, max_i: int, val_i: int):
        super().__init__()
        self.min_i, self.max_i, self.val_i = min_i, max_i, val_i
        self.fine_mode = False
        self._last_y = None
        self.setFixedSize(88, 88)
        self.setCursor(Qt.PointingHandCursor)

    def set_val(self, v: int):
        v = max(self.min_i, min(self.max_i, v))
        if v != self.val_i:
            self.val_i = v
            self.update()
            self.changed.emit(v)

    def mousePressEvent(self, e):
        if self.isEnabled() and e.button() == Qt.LeftButton:
            self._last_y = e.position().y()

    def mouseMoveEvent(self, e):
        if self.isEnabled() and self._last_y is not None:
            dy = self._last_y - e.position().y()
            thresh = 5 if self.fine_mode else 2
            step = 1 if self.fine_mode else max(1, (self.max_i - self.min_i) // 60)
            if abs(dy) >= thresh:
                self.set_val(self.val_i + (step if dy > 0 else -step))
                self._last_y = e.position().y()

    def mouseReleaseEvent(self, e):
        self._last_y = None

    def wheelEvent(self, e):
        if self.isEnabled():
            self.set_val(self.val_i + (1 if e.angleDelta().y() > 0 else -1))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(10, 10, 68, 68)
        ratio = (self.val_i - self.min_i) / max(1, (self.max_i - self.min_i))
        enabled = self.isEnabled()
        accent = QColor("#ff8c1a") if enabled else QColor("#4d5380")

        p.setPen(QPen(QColor("#333861"), 6, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, -270 * 16)

        p.setPen(QPen(accent, 6, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, int(-270 * ratio * 16))

        p.setPen(QPen(QColor("#444a75") if enabled else QColor("#333861"), 1.5))
        p.setBrush(QColor("#262a45") if enabled else QColor("#202339"))
        p.drawEllipse(QRectF(20, 20, 48, 48))

        angle_rad = math.radians(225 - 270 * ratio)
        dot_x = 44 + 16 * math.cos(angle_rad)
        dot_y = 44 - 16 * math.sin(angle_rad)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QPointF(dot_x, dot_y), 3.5, 3.5)

class RotaryKnob(QWidget):
    valueChanged = Signal(float)

    def __init__(self, title: str, min_val: float, max_val: float, default: float, step: float = 0.05, suffix: str = "", decimals: int = 2):
        super().__init__()
        self.min_val, self.max_val = min_val, max_val
        self.min_val, self.max_val = min_val, max_val
        self.min_val, self.max_val, self.default_val = min_val, max_val, default
        self.step, self.suffix, self.decimals = step, suffix, decimals
        self.setFixedWidth(135)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignCenter)

        self.lbl_t = QLabel(title)
        self.lbl_t.setAlignment(Qt.AlignCenter)

        self.canvas = _MaterialDial(int(round(min_val / step)), int(round(max_val / step)), int(round(default / step)))
        self.canvas.changed.connect(self._on_change)
        self.canvas.mouseDoubleClickEvent = lambda e: self.setValue(self.default_val) if (self.isEnabled() and e.button() == Qt.LeftButton) else None

        self.lbl_v = QLabel()
        self.lbl_v.setAlignment(Qt.AlignCenter)
        self._update_text(self.canvas.val_i)
        self._sync_style()

        lay.addWidget(self.lbl_t)
        lay.addWidget(self.canvas, 0, Qt.AlignCenter)
        lay.addWidget(self.lbl_v)

    def _sync_style(self):
        en = self.isEnabled()
        self.canvas.setCursor(Qt.PointingHandCursor if en else Qt.ArrowCursor)
        self.lbl_t.setStyleSheet(f"color: {'#9aa0a6' if en else '#5f6368'}; font-size: 12px; font-weight: 500; background: transparent;")
        self.lbl_v.setStyleSheet(f"color: {'#e3e2e6' if en else '#5f6368'}; font-weight: 600; font-size: 13px; background: transparent;")
        self.canvas.update()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.EnabledChange:
            self._sync_style()

    def _update_text(self, raw_i: int):
        val = raw_i * self.step
        self.lbl_v.setText(f"{int(round(val))}{self.suffix}" if self.decimals == 0 else f"{val:.{self.decimals}f}{self.suffix}")

    def _on_change(self, raw_i: int):
        self._update_text(raw_i)
        self.valueChanged.emit(raw_i * self.step)

    def set_step(self, new_step: float):
        cur = self.value()
        self.step = new_step
        self.canvas.fine_mode = (new_step <= 0.015)
        self.canvas.min_i = int(round(self.min_val / new_step))
        self.canvas.max_i = int(round(self.max_val / new_step))
        self.canvas.val_i = max(self.canvas.min_i, min(self.canvas.max_i, int(round(cur / new_step))))
        self._update_text(self.canvas.val_i)
        self.canvas.update()

    def set_step(self, new_step: float):
        cur = self.value()
        self.step = new_step
        self.canvas.fine_mode = (new_step <= 0.015)
        self.canvas.min_i = int(round(self.min_val / new_step))
        self.canvas.max_i = int(round(self.max_val / new_step))
        self.canvas.val_i = max(self.canvas.min_i, min(self.canvas.max_i, int(round(cur / new_step))))
        self._update_text(self.canvas.val_i)
        self.canvas.update()

    def set_step(self, new_step: float):
        cur = self.value()
        self.step = new_step
        self.canvas.fine_mode = (new_step <= 0.015)
        self.canvas.min_i = int(round(self.min_val / new_step))
        self.canvas.max_i = int(round(self.max_val / new_step))
        self.canvas.val_i = max(self.canvas.min_i, min(self.canvas.max_i, int(round(cur / new_step))))
        self._update_text(self.canvas.val_i)
        self.canvas.update()

    def value(self) -> float:
        return self.canvas.val_i * self.step

    def setValue(self, val: float):
        self.canvas.set_val(int(round(val / self.step)))
