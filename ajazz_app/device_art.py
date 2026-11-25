"""Drawn device pictures (no product photos are bundled): one illustration per device type, lit in the device's colour."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath, QRadialGradient, QLinearGradient

BODY, EDGE, DETAIL, DARK = QColor("#262833"), QColor("#4b4e5b"), QColor("#363846"), QColor("#121318")
W, H = 160.0, 100.0  # drawing grid; scaled to the requested size


def _glow(p, rect: QRectF, col: QColor):
    g = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.75)
    c = QColor(col)
    c.setAlpha(55)
    g.setColorAt(0, c)
    c.setAlpha(0)
    g.setColorAt(1, c)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(rect.center(), rect.width() * 0.66, rect.height() * 0.8)


def _body(p, rect, r=6.0, fill=BODY):
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0, fill.lighter(118))
    grad.setColorAt(1, fill)
    p.setPen(QPen(EDGE, 1.2))
    p.setBrush(grad)
    p.drawRoundedRect(rect, r, r)


def _lit(col, alpha=255):
    c = QColor(col)
    c.setAlpha(alpha)
    return c


def _keyboard(p, c):
    body = QRectF(14, 26, 132, 50)
    _glow(p, body, c)
    _body(p, body, 7)
    p.setPen(Qt.NoPen)
    for row in range(4):
        y = 31 + row * 10.5
        x, keys = 19.0, 12 if row < 3 else 9
        for k in range(keys):
            w = 8.6 if not (row == 3 and k == 4) else 8.6 * 4
            p.setBrush(DETAIL)
            p.drawRoundedRect(QRectF(x, y, w, 7.5), 1.6, 1.6)
            x += w + 1.9
    p.setBrush(_lit(c, 220))
    p.drawRoundedRect(QRectF(18, 74, 124, 2.2), 1, 1)  # underglow strip


def _mouse(p, c):
    path = QPainterPath()
    path.addRoundedRect(QRectF(58, 14, 44, 74), 22, 22)
    _glow(p, QRectF(58, 14, 44, 74), c)
    grad = QLinearGradient(QPointF(58, 14), QPointF(102, 88))
    grad.setColorAt(0, BODY.lighter(125))
    grad.setColorAt(1, BODY)
    p.setPen(QPen(EDGE, 1.2))
    p.setBrush(grad)
    p.drawPath(path)
    p.setPen(QPen(DARK, 1.4))
    p.drawLine(QPointF(80, 16), QPointF(80, 42))
    p.setPen(Qt.NoPen)
    p.setBrush(_lit(c, 235))
    p.drawRoundedRect(QRectF(77.5, 24, 5, 11), 2.5, 2.5)  # wheel
    p.drawRoundedRect(QRectF(66, 76, 28, 3), 1.5, 1.5)    # logo light


def _gpu(p, c):
    body = QRectF(12, 30, 130, 42)
    _glow(p, body, c)
    _body(p, body, 6)
    p.setBrush(DETAIL)
    p.setPen(QPen(EDGE, 1))
    p.drawRect(QRectF(142, 26, 6, 52))  # bracket
    for cx in (48, 104):
        p.setPen(QPen(EDGE, 1.2))
        p.setBrush(DARK)
        p.drawEllipse(QPointF(cx, 51), 16, 16)
        p.setPen(QPen(DETAIL, 2.2))
        for a in range(0, 360, 60):
            path = QPainterPath()
            path.moveTo(cx, 51)
            path.arcTo(QRectF(cx - 13, 38, 26, 26), a, 40)
            p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(DETAIL.lighter(130))
        p.drawEllipse(QPointF(cx, 51), 4, 4)
    p.setBrush(_lit(c, 230))
    p.drawRoundedRect(QRectF(20, 32, 114, 2.4), 1, 1)  # top light bar


def _motherboard(p, c):
    board = QRectF(34, 8, 92, 84)
    _glow(p, board, c)
    _body(p, board, 4, QColor("#20222b"))
    p.setPen(QPen(EDGE, 1))
    p.setBrush(DETAIL)
    p.drawRect(QRectF(56, 22, 26, 26))           # CPU socket
    for i in range(4):
        p.drawRect(QRectF(92 + i * 6, 16, 3.4, 40))  # memory slots
    for i in range(3):
        p.drawRect(QRectF(42, 60 + i * 9, 62, 3.4))  # expansion slots
    p.setPen(Qt.NoPen)
    p.setBrush(_lit(c, 230))
    p.drawRoundedRect(QRectF(37, 12, 3, 30), 1.5, 1.5)  # edge lighting
    p.drawRoundedRect(QRectF(108, 62, 14, 22), 3, 3)    # chipset cover light


def _cooler(p, c):
    _glow(p, QRectF(48, 18, 64, 64), c)
    p.setPen(QPen(EDGE, 1.2))
    p.setBrush(BODY)
    p.drawEllipse(QPointF(80, 50), 30, 30)
    p.setPen(QPen(_lit(c, 240), 4))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(80, 50), 23, 23)   # pump ring
    p.setPen(Qt.NoPen)
    p.setBrush(DARK)
    p.drawEllipse(QPointF(80, 50), 17, 17)   # screen / cap
    p.setPen(QPen(DETAIL, 5, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(108, 40), QPointF(140, 22))  # tubes
    p.drawLine(QPointF(108, 60), QPointF(140, 78))


def _fan_strip(p, c):
    for cx in (40, 80, 120):
        _glow(p, QRectF(cx - 18, 32, 36, 36), c)
        _body(p, QRectF(cx - 18, 32, 36, 36), 6)
        p.setPen(QPen(_lit(c, 235), 2.4))
        p.setBrush(DARK)
        p.drawEllipse(QPointF(cx, 50), 13, 13)
        p.setPen(QPen(DETAIL, 2))
        for a in range(0, 360, 72):
            path = QPainterPath()
            path.moveTo(cx, 50)
            path.arcTo(QRectF(cx - 11, 39, 22, 22), a, 45)
            p.drawPath(path)


def _dram(p, c):
    for i, x in enumerate((44, 70, 96)):
        stick = QRectF(x, 18, 18, 66)
        _glow(p, stick, c)
        _body(p, stick, 3)
        p.setPen(Qt.NoPen)
        p.setBrush(_lit(c, 235))
        p.drawRoundedRect(QRectF(x + 2, 20, 14, 8), 2, 2)
        p.setBrush(DETAIL)
        for k in range(4):
            p.drawRect(QRectF(x + 4, 34 + k * 11, 10, 7))


def _mousemat(p, c):
    mat = QRectF(14, 30, 132, 44)
    _glow(p, mat, c)
    p.setPen(QPen(_lit(c, 235), 2.4))
    p.setBrush(DARK)
    p.drawRoundedRect(mat, 8, 8)


def _headset(p, c):
    _glow(p, QRectF(36, 20, 88, 70), c)
    p.setPen(QPen(BODY.lighter(130), 7, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(42, 12, 76, 76), 20 * 16, 140 * 16)
    for x in (36, 104):
        _body(p, QRectF(x, 50, 20, 32), 9)
        p.setPen(Qt.NoPen)
        p.setBrush(_lit(c, 235))
        p.drawRoundedRect(QRectF(x + 6, 58, 8, 16), 4, 4)


def _speaker(p, c):
    for x in (46, 94):
        box = QRectF(x, 18, 22, 66)
        _glow(p, box, c)
        _body(p, box, 4)
        p.setPen(QPen(_lit(c, 230), 2))
        p.setBrush(DARK)
        p.drawEllipse(QPointF(x + 11, 60), 8, 8)
        p.drawEllipse(QPointF(x + 11, 34), 4, 4)


def _case(p, c):
    box = QRectF(52, 8, 56, 84)
    _glow(p, box, c)
    _body(p, box, 5)
    p.setPen(QPen(EDGE, 1))
    p.setBrush(DARK)
    p.drawRoundedRect(QRectF(58, 14, 30, 72), 3, 3)  # glass panel
    for y in (26, 50, 74):
        p.setPen(QPen(_lit(c, 230), 2))
        p.drawEllipse(QPointF(98, y), 5, 5)


def _generic(p, c):
    chip = QRectF(56, 26, 48, 48)
    _glow(p, chip, c)
    p.setPen(QPen(EDGE, 1.4))
    for i in range(5):  # pins on all four sides
        p.drawLine(QPointF(60 + i * 10, 20), QPointF(60 + i * 10, 26))
        p.drawLine(QPointF(60 + i * 10, 74), QPointF(60 + i * 10, 80))
        p.drawLine(QPointF(50, 30 + i * 10), QPointF(56, 30 + i * 10))
        p.drawLine(QPointF(104, 30 + i * 10), QPointF(110, 30 + i * 10))
    _body(p, chip, 5)
    p.setPen(Qt.NoPen)
    p.setBrush(_lit(c, 235))
    p.drawEllipse(QPointF(80, 50), 7, 7)


DRAW = {"KEYBOARD": _keyboard, "KEYPAD": _keyboard, "MOUSE": _mouse, "GPU": _gpu, "MOTHERBOARD": _motherboard,
        "COOLER": _cooler, "LEDSTRIP": _fan_strip, "DRAM": _dram, "MOUSEMAT": _mousemat, "HEADSET": _headset,
        "HEADSET_STAND": _headset, "SPEAKER": _speaker, "CASE": _case}


def device_picture(kind: str, accent: QColor, width: int, height: int) -> QPixmap:
    """kind: an OpenRGB device type name ('GPU', 'MOUSE', ...); accent: the device's current light colour."""
    dpr = 2
    pm = QPixmap(width * dpr, height * dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = min(width * dpr / W, height * dpr / H)
    p.translate((width * dpr - W * s) / 2, (height * dpr - H * s) / 2)
    p.scale(s, s)
    col = accent if accent.isValid() and accent.value() > 20 else QColor("#7c5cff")  # off / black -> brand violet
    DRAW.get(kind, _generic)(p, col)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm
