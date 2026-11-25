"""Drawn device pictures (no product photos are bundled): one illustration per device type, lit in the device's colour.

Every drawing uses a 160 x 100 grid and the same parts: a dark body with a soft top-down gradient, lit elements in the
device's current colour, and a pool of light underneath. `None` as the colour draws the device switched off.
"""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath, QRadialGradient, QLinearGradient

BODY, EDGE, DETAIL, DARK = QColor("#262833"), QColor("#4b4e5b"), QColor("#363846"), QColor("#121318")
METAL, GOLD, OFF = QColor("#3a3d49"), QColor("#a8873a"), QColor("#3a3c48")
W, H = 160.0, 100.0  # drawing grid; scaled to the requested size


# ---------- shared parts ----------
def _lit(c, alpha=255) -> QColor:
    col = QColor(c) if c is not None else QColor(OFF)
    col.setAlpha(alpha)
    return col


def _mix(a: QColor, c, f: float) -> QColor:
    """Blend base colour `a` toward the light colour `c` by f (0..1); unlit when c is None."""
    if c is None:
        return QColor(a)
    return QColor(round(a.red() + (c.red() - a.red()) * f), round(a.green() + (c.green() - a.green()) * f),
                  round(a.blue() + (c.blue() - a.blue()) * f))


def _floor(p, cx, cy, w, h, c, alpha=80):
    """Light pooling on the surface under the device."""
    if c is None:
        return
    p.save()
    p.translate(cx, cy)
    p.scale(1.0, h / w)
    g = QRadialGradient(QPointF(0, 0), w / 2)
    g.setColorAt(0, _lit(c, alpha))
    g.setColorAt(1, _lit(c, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(0, 0), w / 2, w / 2)
    p.restore()


def _halo(p, rect: QRectF, c, alpha=38):
    """Faint light spilling around the device."""
    if c is None:
        return
    p.save()
    p.translate(rect.center())
    rx, ry = rect.width() * 0.62, rect.height() * 0.72
    p.scale(1.0, ry / rx)
    g = QRadialGradient(QPointF(0, 0), rx)
    g.setColorAt(0, _lit(c, alpha))
    g.setColorAt(1, _lit(c, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(0, 0), rx, rx)
    p.restore()


def _body(p, rect, r=6.0, fill=BODY, edge=EDGE):
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0, fill.lighter(122))
    grad.setColorAt(1, fill)
    p.setPen(QPen(edge, 1.1))
    p.setBrush(grad)
    p.drawRoundedRect(rect, r, r)


def _bar(p, rect, c, alpha=240):
    """A lit strip with a little bloom."""
    if c is not None:
        p.setPen(Qt.NoPen)
        p.setBrush(_lit(c, 60))
        p.drawRoundedRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5), rect.height(), rect.height())
    p.setPen(Qt.NoPen)
    p.setBrush(_lit(c, alpha))
    p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)


def _ring(p, centre: QPointF, r, c, width=2.4):
    if c is not None:
        p.setPen(QPen(_lit(c, 70), width + 2.4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(centre, r, r)
    p.setPen(QPen(_lit(c, 240), width))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(centre, r, r)


def _fan(p, cx, cy, r, c, blades=7):
    p.setPen(QPen(EDGE, 1))
    p.setBrush(DARK)
    p.drawEllipse(QPointF(cx, cy), r, r)
    _ring(p, QPointF(cx, cy), r - 1.6, c, 1.8)
    p.save()
    p.translate(cx, cy)
    p.setPen(Qt.NoPen)
    p.setBrush(_mix(METAL, c, 0.10))
    rb = r - 3.4
    for i in range(blades):
        p.save()
        p.rotate(i * 360.0 / blades)
        blade = QPainterPath()
        blade.moveTo(2.2, -1.6)
        blade.cubicTo(rb * 0.45, -rb * 0.62, rb * 0.85, -rb * 0.38, rb * 0.95, 0.0)
        blade.lineTo(rb * 0.78, rb * 0.16)
        blade.cubicTo(rb * 0.55, -rb * 0.18, rb * 0.30, -rb * 0.22, 2.2, 1.8)
        blade.closeSubpath()
        p.drawPath(blade)
        p.restore()
    p.setBrush(METAL.lighter(120))
    p.drawEllipse(QPointF(0, 0), r * 0.22, r * 0.22)
    p.restore()


# ---------- devices ----------
def _keys(p, plate: QRectF, rows, c, gap=0.9):
    """Keycaps laid out in units (1 = one standard key) across the plate."""
    units = max(sum(r) for r in rows)
    u = (plate.width() - gap * (units - 1)) / units
    kh = (plate.height() - gap * (len(rows) - 1)) / len(rows)
    for ri, row in enumerate(rows):
        x, y = plate.left(), plate.top() + ri * (kh + gap)
        for w in row:
            kw = w * u + (w - 1) * gap
            cap = QRectF(x, y, kw, kh)
            p.setPen(Qt.NoPen)
            p.setBrush(_mix(DETAIL, c, 0.30))  # cap skirt, lit from below
            p.drawRoundedRect(cap, 1.4, 1.4)
            p.setBrush(_mix(BODY.lighter(150), c, 0.10))  # cap top
            p.drawRoundedRect(cap.adjusted(0.8, 0.5, -0.8, -1.4), 1.1, 1.1)
            x += kw + gap


def _keyboard(p, c):
    _floor(p, 80, 82, 150, 20, c)
    case = QRectF(12, 22, 136, 54)
    p.setPen(Qt.NoPen)
    p.setBrush(DARK)
    p.drawRoundedRect(case.adjusted(1, 3, -1, 3), 8, 8)  # depth under the case
    _body(p, case, 8)
    plate = case.adjusted(5, 5, -5, -5)
    p.setPen(Qt.NoPen)
    p.setBrush(_mix(DARK, c, 0.28))  # light between the keys
    p.drawRoundedRect(plate.adjusted(-1, -1, 1, 1), 4, 4)
    _keys(p, plate, [[1] * 16, [1] * 13 + [2, 1], [1.5] + [1] * 12 + [1.5, 1], [1.75] + [1] * 11 + [2.25, 1],
                     [2.25] + [1] * 10 + [1.75, 1, 1], [1.25] * 3 + [6.25] + [1] * 6], c)
    _bar(p, QRectF(20, 76.5, 120, 1.8), c)  # front edge light


def _keypad(p, c):
    _floor(p, 80, 84, 90, 18, c)
    case = QRectF(48, 14, 64, 66)
    _body(p, case, 7)
    plate = case.adjusted(5, 5, -5, -5)
    p.setPen(Qt.NoPen)
    p.setBrush(_mix(DARK, c, 0.28))
    p.drawRoundedRect(plate, 3, 3)
    _keys(p, plate, [[1] * 4] * 5, c, gap=1.4)


def _mouse(p, c):
    _floor(p, 80, 90, 80, 14, c)
    shell = QPainterPath()
    shell.moveTo(80, 10)
    shell.cubicTo(96, 10, 104, 22, 104, 42)
    shell.lineTo(104, 66)
    shell.cubicTo(104, 82, 94, 90, 80, 90)
    shell.cubicTo(66, 90, 56, 82, 56, 66)
    shell.lineTo(56, 42)
    shell.cubicTo(56, 22, 64, 10, 80, 10)
    grad = QLinearGradient(QPointF(56, 10), QPointF(104, 90))
    grad.setColorAt(0, BODY.lighter(135))
    grad.setColorAt(1, BODY)
    p.setPen(QPen(EDGE, 1.1))
    p.setBrush(grad)
    p.drawPath(shell)
    p.setPen(QPen(DARK, 1.3))
    p.drawLine(QPointF(80, 10.5), QPointF(80, 40))  # button split
    split = QPainterPath()
    split.moveTo(57, 44)
    split.quadTo(80, 38, 103, 44)
    p.setBrush(Qt.NoBrush)
    p.drawPath(split)
    for x0, sweep in ((57.2, 1), (102.8, -1)):  # side light strips
        strip = QPainterPath()
        strip.moveTo(x0, 50)
        strip.cubicTo(x0, 66, x0 + 3 * sweep, 80, x0 + 10 * sweep, 86)
        if c is not None:
            p.setPen(QPen(_lit(c, 70), 4.2, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(strip)
        p.setPen(QPen(_lit(c, 235), 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(strip)
    p.setPen(QPen(DARK, 1))
    p.setBrush(_lit(c, 235))
    p.drawRoundedRect(QRectF(77.4, 18, 5.2, 13), 2.6, 2.6)  # scroll wheel
    _ring(p, QPointF(80, 70), 4.2, c, 1.6)  # logo


def _gpu(p, c):
    _floor(p, 76, 86, 140, 16, c)
    p.setPen(Qt.NoPen)
    p.setBrush(DARK)
    p.drawRoundedRect(QRectF(13, 30, 126, 44), 5, 5)  # backplate depth
    _body(p, QRectF(10, 25, 130, 46), 7)
    p.setBrush(GOLD)
    p.setPen(Qt.NoPen)
    p.drawRect(QRectF(46, 71, 42, 3.6))  # PCIe contacts
    p.setPen(QPen(EDGE, 1))
    p.setBrush(METAL)
    p.drawRect(QRectF(140, 21, 7, 60))  # bracket
    p.setPen(QPen(DARK, 1.2))
    for y in range(28, 76, 6):
        p.drawLine(QPointF(142, y), QPointF(145, y))
    _bar(p, QRectF(18, 27.6, 114, 2.2), c)  # top light bar
    for cx in (34, 75, 116):
        _fan(p, cx, 49, 17.5, c)


def _motherboard(p, c):
    _floor(p, 80, 93, 110, 12, c)
    board = QRectF(34, 6, 92, 86)
    _body(p, board, 4, QColor("#1e2029"))
    p.setPen(QPen(EDGE, 0.9))
    p.setBrush(METAL)
    p.drawRoundedRect(QRectF(39, 10, 34, 9), 2, 2)  # VRM heatsinks
    p.drawRoundedRect(QRectF(39, 10, 9, 36), 2, 2)
    _bar(p, QRectF(41.6, 14, 2.4, 28), c)  # IO cover light
    p.setPen(QPen(EDGE, 0.9))
    p.setBrush(DETAIL)
    p.drawRect(QRectF(54, 24, 22, 22))  # CPU socket
    p.setBrush(DARK)
    p.drawRect(QRectF(58, 28, 14, 14))
    p.setBrush(DETAIL)
    for i in range(4):  # memory slots
        p.drawRect(QRectF(84 + i * 5.6, 12, 3.2, 40))
    p.setBrush(METAL)
    p.drawRect(QRectF(118, 22, 5, 14))  # power connector
    for y, reinforced in ((57, True), (72, False), (84, False)):  # PCIe slots
        p.setBrush(METAL.lighter(130) if reinforced else DETAIL)
        p.drawRect(QRectF(40, y, 60, 3.6))
    p.setBrush(METAL)
    p.drawRoundedRect(QRectF(44, 63.5, 46, 5), 1.5, 1.5)  # M.2 cover
    p.drawRoundedRect(QRectF(104, 60, 18, 24), 3, 3)  # chipset heatsink
    _ring(p, QPointF(113, 72), 5.5, c, 1.6)


def _cooler(p, c):
    """All-in-one liquid cooler: pump head, tubes and a two-fan radiator."""
    _floor(p, 84, 94, 150, 12, c)
    p.setPen(QPen(QColor("#2b2d38"), 5.2, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    for y0, y1 in ((40, 26), (60, 74)):
        t = QPainterPath()
        t.moveTo(64, y0)
        t.cubicTo(82, y0, 84, y1, 102, y1)
        p.drawPath(t)
    _body(p, QRectF(100, 6, 46, 88), 4)  # radiator
    for cy in (28, 72):
        _fan(p, 123, cy, 19, c)
    head = QPointF(42, 50)
    _halo(p, QRectF(14, 22, 56, 56), c, 30)
    p.setPen(QPen(EDGE, 1.1))
    g = QLinearGradient(QPointF(16, 24), QPointF(68, 76))
    g.setColorAt(0, BODY.lighter(140))
    g.setColorAt(1, BODY)
    p.setBrush(g)
    p.drawEllipse(head, 26, 26)
    _ring(p, head, 21, c, 3.2)
    p.setPen(Qt.NoPen)
    p.setBrush(DARK)
    p.drawEllipse(head, 16, 16)  # display
    p.setBrush(_lit(c, 120))
    p.drawEllipse(head, 4, 4)


def _ledstrip(p, c):
    _floor(p, 80, 78, 150, 18, c)
    ribbon = QPainterPath()
    ribbon.moveTo(10, 62)
    ribbon.cubicTo(48, 26, 104, 84, 150, 42)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(DARK, 10, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(ribbon)
    p.setPen(QPen(BODY, 7, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(ribbon)
    p.setPen(Qt.NoPen)
    for i in range(14):
        pt = ribbon.pointAtPercent(0.04 + i * 0.92 / 13)
        if c is not None:
            p.setBrush(_lit(c, 70))
            p.drawEllipse(pt, 4.2, 4.2)
        p.setBrush(_lit(c, 245))
        p.drawEllipse(pt, 2.1, 2.1)


def _dram(p, c):
    _floor(p, 80, 92, 90, 12, c)
    for x in (56, 84):
        stick = QRectF(x, 14, 20, 74)
        p.setPen(Qt.NoPen)
        p.setBrush(GOLD)
        p.drawRect(QRectF(x + 2, 86, 16, 3))  # contacts
        _body(p, stick, 3)
        diff = QRectF(x + 1.5, 15.5, 17, 18)  # light diffuser on top
        g = QLinearGradient(diff.topLeft(), diff.bottomLeft())
        g.setColorAt(0, _lit(c, 250))
        g.setColorAt(1, _lit(c, 40 if c is not None else 255))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(diff, 2, 2)
        p.setPen(QPen(DARK, 1))
        for k in range(3):
            p.drawLine(QPointF(x + 4, 44 + k * 12), QPointF(x + 16, 44 + k * 12))


def _mousemat(p, c):
    _floor(p, 80, 84, 160, 16, c, 60)
    mat = QPainterPath()
    mat.moveTo(26, 36)
    mat.lineTo(134, 36)
    mat.lineTo(152, 80)
    mat.lineTo(8, 80)
    mat.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(DARK)
    p.drawPath(mat.translated(0, 2.5))  # thickness
    if c is not None:
        p.setPen(QPen(_lit(c, 70), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(mat)
    p.setPen(QPen(_lit(c, 240), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor("#17181f"))
    p.drawPath(mat)
    p.setPen(Qt.NoPen)
    p.setBrush(_lit(c, 150))
    p.drawEllipse(QPointF(132, 72), 2.4, 1.4)  # corner logo


def _headset(p, c):
    _floor(p, 80, 95, 120, 9, c)
    band = QRectF(36, 10, 88, 92)  # ellipse centred at (80, 56)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#2e303c"), 8, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(band, 15 * 16, 150 * 16)  # headband
    p.setPen(QPen(BODY.lighter(150), 1.8, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(band.adjusted(-3.5, -3.5, 3.5, 3.5), 30 * 16, 120 * 16)  # top highlight
    p.setPen(QPen(EDGE, 0.9))
    p.setBrush(METAL)
    for x in (34, 119):  # sliders
        p.drawRoundedRect(QRectF(x, 40, 7, 18), 2, 2)
    mic = QPainterPath()  # boom mic from the left cup
    mic.moveTo(33, 84)
    mic.quadTo(36, 96, 58, 94)
    p.setPen(QPen(BODY.lighter(140), 2.6, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawPath(mic)
    p.setPen(Qt.NoPen)
    p.setBrush(_lit(c, 235))
    p.drawEllipse(QPointF(60, 94), 2.6, 2.6)
    for x in (26, 110):  # ear cups
        cup = QRectF(x, 54, 24, 36)
        _halo(p, cup, c, 30)
        _body(p, cup, 11)
        p.setPen(QPen(_lit(c, 240), 2.4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cup.adjusted(4, 6, -4, -6))
        p.setPen(Qt.NoPen)
        p.setBrush(DARK)
        p.drawEllipse(cup.adjusted(7.5, 10.5, -7.5, -10.5))


def _headset_stand(p, c):
    _floor(p, 80, 92, 90, 10, c)
    _body(p, QRectF(50, 80, 60, 12), 6)  # base
    _bar(p, QRectF(54, 89, 52, 2), c)
    _body(p, QRectF(77, 22, 6, 60), 2)  # pole
    hook = QPainterPath()
    hook.moveTo(80, 24)
    hook.cubicTo(80, 10, 110, 10, 112, 24)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(BODY.lighter(130), 6, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(hook)
    p.setPen(QPen(_lit(c, 235), 1.8, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(hook)


def _speaker(p, c):
    _floor(p, 80, 92, 120, 12, c)
    for x in (40, 96):
        _body(p, QRectF(x, 14, 24, 74), 4)
        _ring(p, QPointF(x + 12, 62), 9, c, 2.2)
        p.setPen(Qt.NoPen)
        p.setBrush(DARK)
        p.drawEllipse(QPointF(x + 12, 62), 6.5, 6.5)
        p.setBrush(DETAIL)
        p.drawEllipse(QPointF(x + 12, 34), 5, 5)
        p.setBrush(_lit(c, 200))
        p.drawEllipse(QPointF(x + 12, 34), 1.8, 1.8)


def _case(p, c):
    _floor(p, 80, 96, 90, 8, c)
    body = QRectF(52, 4, 56, 92)
    _body(p, body, 5)
    p.setPen(Qt.NoPen)
    p.setBrush(DARK)
    p.drawRoundedRect(body.adjusted(4, 5, -4, -5), 3, 3)
    for cy in (22, 50, 78):
        _fan(p, 80, cy, 12.5, c, blades=5)
    _bar(p, QRectF(54.2, 10, 1.8, 80), c)  # edge light


def _gamepad(p, c):
    _floor(p, 80, 88, 120, 12, c)
    pad = QPainterPath()
    pad.addRoundedRect(QRectF(36, 30, 88, 34), 17, 17)
    for cx in (50, 110):
        grip = QPainterPath()
        grip.addEllipse(QPointF(cx, 64), 15, 18)
        pad = pad.united(grip)
    g = QLinearGradient(QPointF(0, 30), QPointF(0, 82))
    g.setColorAt(0, BODY.lighter(135))
    g.setColorAt(1, BODY)
    p.setPen(QPen(EDGE, 1.1))
    p.setBrush(g)
    p.drawPath(pad)
    _bar(p, QRectF(66, 31.5, 28, 2.2), c)  # light bar
    p.setPen(Qt.NoPen)
    p.setBrush(DARK)
    p.drawRect(QRectF(46, 44, 10, 3.4))  # d-pad
    p.drawRect(QRectF(49.3, 40.7, 3.4, 10))
    p.setBrush(_mix(DETAIL, c, 0.35))
    for dx, dy in ((0, -5), (5, 0), (0, 5), (-5, 0)):  # face buttons
        p.drawEllipse(QPointF(110 + dx, 46 + dy), 2.4, 2.4)
    for cx in (68, 92):  # sticks
        p.setBrush(DARK)
        p.drawEllipse(QPointF(cx, 58), 6, 6)
        p.setBrush(DETAIL)
        p.drawEllipse(QPointF(cx, 58), 3.6, 3.6)


def _microphone(p, c):
    _floor(p, 80, 93, 90, 10, c)
    _body(p, QRectF(54, 86, 52, 8), 4)  # base
    _body(p, QRectF(78, 60, 4, 27), 2)  # stem
    cap = QRectF(66, 8, 28, 52)
    _halo(p, cap, c, 30)
    _body(p, cap, 14)
    p.setPen(QPen(DARK, 1))
    for y in range(16, 44, 4):
        p.drawLine(QPointF(70, y), QPointF(90, y))
    _bar(p, QRectF(67, 46, 26, 2.6), c)


def _storage(p, c):
    _floor(p, 80, 80, 120, 14, c)
    drive = QRectF(30, 26, 100, 46)
    _body(p, drive, 5)
    p.setPen(Qt.NoPen)
    p.setBrush(METAL)
    p.drawRoundedRect(drive.adjusted(6, 6, -6, -18), 3, 3)  # label plate
    _bar(p, QRectF(36, 62, 88, 2.4), c)


def _light(p, c):
    _floor(p, 80, 80, 150, 22, c, 110)
    _body(p, QRectF(14, 40, 132, 14), 7)
    _bar(p, QRectF(20, 50, 120, 3), c)


def _generic(p, c):
    chip = QRectF(56, 26, 48, 48)
    _halo(p, chip, c)
    p.setPen(QPen(EDGE, 1.4))
    for i in range(5):  # pins on all four sides
        p.drawLine(QPointF(60 + i * 10, 20), QPointF(60 + i * 10, 26))
        p.drawLine(QPointF(60 + i * 10, 74), QPointF(60 + i * 10, 80))
        p.drawLine(QPointF(50, 30 + i * 10), QPointF(56, 30 + i * 10))
        p.drawLine(QPointF(104, 30 + i * 10), QPointF(110, 30 + i * 10))
    _body(p, chip, 5)
    _ring(p, QPointF(80, 50), 8, c, 2)


DRAW = {"KEYBOARD": _keyboard, "KEYPAD": _keypad, "MOUSE": _mouse, "GPU": _gpu, "MOTHERBOARD": _motherboard,
        "COOLER": _cooler, "LEDSTRIP": _ledstrip, "DRAM": _dram, "MOUSEMAT": _mousemat, "HEADSET": _headset,
        "HEADSET_STAND": _headset_stand, "SPEAKER": _speaker, "CASE": _case, "GAMEPAD": _gamepad,
        "MICROPHONE": _microphone, "STORAGE": _storage, "LIGHT": _light}


def device_picture(kind: str, accent: QColor, width: int, height: int) -> QPixmap:
    """kind: an OpenRGB device type name ('GPU', 'MOUSE', ...); accent: the device's light colour (black = off)."""
    dpr = 2
    pm = QPixmap(width * dpr, height * dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = min(width * dpr / W, height * dpr / H)
    p.translate((width * dpr - W * s) / 2, (height * dpr - H * s) / 2)
    p.scale(s, s)
    col = accent if accent is not None and accent.isValid() and accent.value() > 20 else None
    DRAW.get(kind, _generic)(p, col)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm
