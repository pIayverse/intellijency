"""Render the Intellijency trailer (MP4, 1920x1080, 30 fps) without showing any window.

    python tools/make_trailer.py OUT.mp4

The app is rendered in demo mode (simulated devices, throwaway settings) on a controlled clock, so every frame is
exact and nothing touches real hardware or settings. Needs: pip install imageio-ffmpeg
"""
import math, os, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ajazz_app import demo  # noqa: E402

demo.prepare(os.path.join(tempfile.gettempdir(), "intellijency-trailer"))

import imageio_ffmpeg  # noqa: E402
from PySide6.QtCore import Qt, QRectF, QPointF  # noqa: E402
from PySide6.QtGui import (QImage, QPainter, QColor, QFont, QPainterPath, QLinearGradient, QRadialGradient,  # noqa: E402
                           QPen, QConicalGradient, QBrush, QFontMetricsF)
from PySide6.QtWidgets import QApplication  # noqa: E402

W, H, FPS, DURATION = 1920, 1080, 30, 30.0
VIOLET, BLUE, WHITE, MUTED = QColor("#7c5cff"), QColor("#5b8cff"), QColor("#f4f5fb"), QColor("#a9acb8")
SPECTRUM = ["#7c5cff", "#2fb8ff", "#2effa8", "#ffd23d", "#ff8c1a", "#ff3d7f", "#7c5cff"]
FONT = "Segoe UI Variable Display"


# ---------- clock & easing ----------
class FakeClock:
    """Stands in for time.monotonic and QElapsedTimer so the app animates on the trailer's timeline."""
    t = 0.0

    def monotonic(self):
        return FakeClock.t

    def elapsed(self):
        return int(FakeClock.t * 1000)

    def start(self):
        pass

    restart = start


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def window(t, start, end, fade=0.35):
    """Opacity of a scene that runs from start to end, fading at both edges."""
    if t < start or t > end:
        return 0.0
    return clamp(min((t - start) / fade, (end - t) / fade))


# ---------- drawing helpers ----------
def font(size, weight=QFont.Bold):
    f = QFont(FONT)
    f.setPixelSize(int(size))
    f.setWeight(weight)
    return f


def text(p, s, x, y, size, color=WHITE, weight=QFont.Bold, align="left", alpha=1.0, gradient=None):
    """Draw s with its baseline at y; x is the left edge, centre or right edge per `align`."""
    f = font(size, weight)
    fm = QFontMetricsF(f)
    w = fm.horizontalAdvance(s)
    x0 = x - w / 2 if align == "center" else (x - w if align == "right" else x)
    path = QPainterPath()
    path.addText(QPointF(x0, y), f, s)
    p.save()
    p.setOpacity(p.opacity() * alpha)
    p.setPen(Qt.NoPen)
    if gradient:
        g = QLinearGradient(QPointF(x0, y - size), QPointF(x0 + w, y))
        for i, c in enumerate(gradient):
            g.setColorAt(i / (len(gradient) - 1), QColor(c))
        p.setBrush(QBrush(g))
    else:
        p.setBrush(color)
    p.drawPath(path)
    p.restore()
    return w


def background(p, t, strength=1.0):
    p.fillRect(0, 0, W, H, QColor("#07070b"))
    blobs = [(VIOLET, 0.25 + 0.08 * math.sin(t * 0.35), 0.3 + 0.1 * math.cos(t * 0.27), 900),
             (BLUE, 0.78 + 0.07 * math.cos(t * 0.31), 0.25 + 0.08 * math.sin(t * 0.22), 820),
             (QColor("#00d4a0"), 0.55 + 0.1 * math.sin(t * 0.19 + 1), 0.95, 760)]
    for c, fx, fy, r in blobs:
        g = QRadialGradient(QPointF(W * fx, H * fy), r)
        cc = QColor(c)
        cc.setAlpha(int(60 * strength))
        g.setColorAt(0, cc)
        cc.setAlpha(0)
        g.setColorAt(1, cc)
        p.fillRect(0, 0, W, H, g)


def mark(p, cx, cy, size, progress=1.0, glow=1.0):
    """The Intellijency mark: a spectrum ring drawn in by `progress`, the 'i' and its lit dot."""
    s = size / 160.0
    p.save()
    p.translate(cx, cy)
    p.scale(s, s)
    ring = QConicalGradient(QPointF(0, 0), 60)
    for i, hx in enumerate(SPECTRUM):
        ring.setColorAt(i / (len(SPECTRUM) - 1), QColor(hx))
    p.setPen(QPen(QBrush(ring), 12, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    span = int(300 * 16 * ease_out(progress))
    if span > 0:
        p.drawArc(QRectF(-54, -54, 108, 108), 75 * 16, span)
    stem = ease_out((progress - 0.35) / 0.4)
    if stem > 0:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#f4f5fb"))
        h = 40 * stem
        p.drawRoundedRect(QRectF(-8.5, 32 - h, 17, h), 8.5, 8.5)
    dot = ease_out((progress - 0.7) / 0.3)
    if dot > 0:
        g = QRadialGradient(QPointF(0, -26), 32)
        c = QColor(VIOLET)
        c.setAlpha(int(170 * dot * glow))
        g.setColorAt(0, c)
        c.setAlpha(0)
        g.setColorAt(1, c)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, -26), 32, 32)
        core = QRadialGradient(QPointF(-3, -29), 13)
        core.setColorAt(0, QColor("#e9e3ff"))
        core.setColorAt(1, VIOLET)
        p.setBrush(core)
        p.drawEllipse(QPointF(0, -26), 10 * dot, 10 * dot)
    p.restore()


def rounded_image(p, img, rect: QRectF, radius=18, alpha=1.0, shadow=True):
    p.save()
    p.setOpacity(p.opacity() * alpha)
    if shadow:
        for i in range(6):  # soft drop shadow
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 22))
            grow = 8 + i * 8
            p.drawRoundedRect(rect.adjusted(-grow, -grow + 20, grow, grow + 20), radius + grow, radius + grow)
    clip = QPainterPath()
    clip.addRoundedRect(rect, radius, radius)
    p.setClipPath(clip)
    p.drawImage(rect, img)
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 30), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect, radius, radius)
    p.restore()


# ---------- the trailer ----------
class Trailer:
    def __init__(self, app):
        self.app = app
        from ajazz_app import gui, home, general_rgb
        from ajazz_app.device_art import device_picture
        from ajazz_app.home import scene_colours
        self.device_picture, self.scene_colours, self.SCENES = device_picture, scene_colours, general_rgb.SCENES
        clock = FakeClock()
        home.time, gui.time = clock, clock  # previews read the trailer's clock
        demo.install()
        self.win = gui.AjazzWindow()
        self.win.setAttribute(Qt.WA_DontShowOnScreen, True)
        self.win.resize(1360, 850)
        self.win.show()
        gp = self.win.general_page
        gp._clock = clock
        self.win._kb_rainbow_t0 = 0.0
        self._scene("Aurora")
        self.win._switch_page(8)
        self.settle()
        # static captures used later
        from ajazz_app.tray import Tray
        from PySide6.QtWidgets import QSystemTrayIcon
        QSystemTrayIcon.show = lambda s: None  # never put a real icon in the tray
        tray = Tray(app, self.win, app.windowIcon())
        tray.menu.setAttribute(Qt.WA_DontShowOnScreen, True)
        tray.menu.show()
        self.settle()
        self.tray_img = tray.menu.grab().toImage()
        self.win._switch_page(1)
        self.settle()
        self.switch_img = self.win.grab().toImage()
        self.win._switch_page(8)
        self.settle()  # let the page fade-in finish, or every app frame is captured half transparent
        self._current = "Aurora"

    def settle(self, seconds=0.8):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)

    def _scene(self, name):
        gp = self.win.general_page
        gp.apply_scene(next(s for s in self.SCENES if s["name"] == name))
        gp._clock = FakeClock()

    def app_frame(self, t, scene=None):
        FakeClock.t = t
        if scene and scene != self._current:
            self._scene(scene)
            self._current = scene
            self.win.home_page.refresh()
            self.app.processEvents()  # let layouts catch up with the new status text before grabbing
        return self.win.grab().toImage()

    # --- scenes (each draws onto p at time t) ---
    def intro(self, p, t):
        a = window(t, 0.0, 3.4, 0.4)
        if not a:
            return
        p.setOpacity(a)
        prog = clamp(t / 1.6)
        mark(p, W / 2, H / 2 - 60, 260 + 20 * ease_out(prog), prog)
        word = ease_out((t - 1.5) / 0.8)
        if word > 0:
            text(p, "Intellijency", W / 2, H / 2 + 150 + 20 * (1 - word), 96, alpha=word, align="center")
        p.setOpacity(1)

    def tagline(self, p, t):
        a = window(t, 3.4, 6.6)
        if not a:
            return
        p.setOpacity(a)
        l1 = ease_out((t - 3.5) / 0.6)
        text(p, "Every light on your desk.", W / 2, H / 2 - 20 + 30 * (1 - l1), 84, alpha=l1, align="center")
        l2 = ease_out((t - 4.7) / 0.6)
        text(p, "One app.", W / 2, H / 2 + 110 + 30 * (1 - l2), 112, alpha=l2, align="center",
             gradient=["#9d86ff", "#5b8cff", "#2fb8ff"])
        p.setOpacity(1)

    def showcase(self, p, t):
        a = window(t, 6.6, 12.8)
        if not a:
            return
        scene = "Aurora" if t < 9.0 else ("Cyberpunk" if t < 11.0 else "Sunset")
        img = self.app_frame(t - 6.6, scene)
        k = ease_in_out((t - 6.6) / 6.2)
        scale = 0.86 + 0.06 * k
        w, h = img.width() * scale, img.height() * scale
        rect = QRectF((W - w) / 2, 205 + (1 - ease_out((t - 6.6) / 0.8)) * 60, w, h)
        p.setOpacity(a)
        text(p, "One click. Every device. In sync.", W / 2, 140, 58, align="center")
        rounded_image(p, img, rect)
        p.setOpacity(1)

    def lineup(self, p, t):
        a = window(t, 12.8, 17.6)
        if not a:
            return
        p.setOpacity(a)
        kinds = [("KEYBOARD", "Keyboard"), ("MOUSE", "Mouse"), ("HEADSET", "Headset"), ("MOUSEMAT", "Mousepad"),
                 ("GPU", "Graphics card"), ("COOLER", "Liquid cooler"), ("LEDSTRIP", "Fans & strips"), ("MOTHERBOARD", "Motherboard")]
        from ajazz_app.general_rgb import effect_colour
        local = t - 12.8
        for i, (kind, label) in enumerate(kinds):
            row, col = divmod(i, 4)
            appear = ease_out((local - 0.15 * i) / 0.5)
            if appear <= 0:
                continue
            c = QColor.fromHsvF((local / 4.0 - i / 8.0) % 1.0, 0.85, 1.0)  # a rainbow rolling across the lineup
            pm = self.device_picture(kind, c, 340, 210)
            x = 150 + col * 410
            y = 250 + row * 330 + 40 * (1 - appear)
            p.save()
            p.setOpacity(p.opacity() * appear)
            p.drawPixmap(QPointF(x, y), pm)
            text(p, label, x + 170, y + 250, 30, MUTED, QFont.DemiBold, align="center")
            p.restore()
        text(p, "Keyboards, mice, PC parts. Any brand.", W / 2, 165, 58, align="center")
        p.setOpacity(1)

    def scenes(self, p, t):
        a = window(t, 17.6, 22.6, 0.25)
        if not a:
            return
        names = ["Aurora", "Cyberpunk", "Sunset", "Ocean", "Lava"]
        local = t - 17.6
        idx = min(4, int(local / 1.0))
        scene = next(s for s in self.SCENES if s["name"] == names[idx])
        cols = self.scene_colours(scene, local * 1.5, 7)
        g = QLinearGradient(QPointF(0, 0), QPointF(W, H * 0.4))
        for i, c in enumerate(cols):
            g.setColorAt(i / (len(cols) - 1), c)
        p.setOpacity(a)
        p.fillRect(0, 0, W, H, g)
        shade = QLinearGradient(QPointF(0, 0), QPointF(0, H))
        shade.setColorAt(0, QColor(7, 7, 11, 40))
        shade.setColorAt(1, QColor(7, 7, 11, 200))
        p.fillRect(0, 0, W, H, shade)
        cut = local - idx * 1.0
        pop = ease_out(cut / 0.35)
        text(p, "SCENES", 140, 420, 30, QColor(255, 255, 255, 190), QFont.Bold)
        text(p, names[idx], 132, 560 + 25 * (1 - pop), 170, alpha=pop)
        text(p, scene["effect"], 140, 640, 38, QColor(255, 255, 255, 200), QFont.DemiBold, alpha=pop)
        p.setOpacity(1)

    def features(self, p, t):
        a = window(t, 22.6, 26.8)
        if not a:
            return
        p.setOpacity(a)
        local = t - 22.6
        text(p, "Built to stay out of your way.", W / 2, 150, 58, align="center")
        cards = [("Lives in your tray", "Lighting keeps playing\nwhile you game.", self.tray_img, 1.0),
                 ("Rapid Trigger", "Per-key actuation down\nto 0.01 mm.", self.switch_img, 0.0),
                 ("Updates itself", "New features arrive\nautomatically.", None, 0.0)]
        cw, ch, gap = 500, 560, 60
        x0 = (W - (3 * cw + 2 * gap)) / 2
        for i, (title, body, img, _) in enumerate(cards):
            appear = ease_out((local - 0.25 * i) / 0.6)
            if appear <= 0:
                continue
            r = QRectF(x0 + i * (cw + gap), 250 + 50 * (1 - appear), cw, ch)
            p.save()
            p.setOpacity(p.opacity() * appear)
            p.setPen(QPen(QColor(255, 255, 255, 26), 1.5))
            bg = QLinearGradient(r.topLeft(), r.bottomRight())
            bg.setColorAt(0, QColor(30, 27, 52, 235))
            bg.setColorAt(1, QColor(18, 19, 26, 235))
            p.setBrush(bg)
            p.drawRoundedRect(r, 26, 26)
            art = QRectF(r.left() + 30, r.top() + 30, cw - 60, 300)
            if img is not None and img is self.tray_img:
                scale = min(art.width() / img.width(), art.height() / img.height()) * 0.95
                iw, ih = img.width() * scale, img.height() * scale
                rounded_image(p, img, QRectF(art.center().x() - iw / 2, art.center().y() - ih / 2, iw, ih), 12, shadow=False)
            elif img is not None:  # crop the Rapid Trigger dials from the Switches page
                sw = img.width() * 0.40
                sh = sw * art.height() / art.width()
                src = QRectF(img.width() * 0.355 - sw / 2, img.height() * 0.76 - sh / 2, sw, sh)
                p.save()
                clip = QPainterPath()
                clip.addRoundedRect(art, 14, 14)
                p.setClipPath(clip)
                p.drawImage(art, img, src)
                p.restore()
            else:  # update arrows
                cx, cy = art.center().x(), art.center().y()
                spin = local * 90
                p.save()
                p.translate(cx, cy)
                p.rotate(spin)
                ring = QConicalGradient(QPointF(0, 0), 0)
                ring.setColorAt(0, VIOLET)
                ring.setColorAt(0.5, BLUE)
                ring.setColorAt(1, VIOLET)
                p.setPen(QPen(QBrush(ring), 16, Qt.SolidLine, Qt.RoundCap))
                p.setBrush(Qt.NoBrush)
                p.drawArc(QRectF(-90, -90, 180, 180), 20 * 16, 140 * 16)
                p.drawArc(QRectF(-90, -90, 180, 180), 200 * 16, 140 * 16)
                p.restore()
                text(p, "v2.0", cx, cy + 22, 64, align="center", gradient=["#9d86ff", "#5b8cff"])
            text(p, title, r.left() + 34, r.top() + 400, 40)
            for j, line in enumerate(body.split("\n")):
                text(p, line, r.left() + 34, r.top() + 455 + j * 40, 28, MUTED, QFont.Normal)
            p.restore()
        p.setOpacity(1)

    def outro(self, p, t):
        a = clamp((t - 26.8) / 0.4)
        if not a:
            return
        p.setOpacity(a)
        local = t - 26.8
        mark(p, W / 2, H / 2 - 130, 230, 1.0, 0.8 + 0.2 * math.sin(local * 3))
        text(p, "Intellijency", W / 2, H / 2 + 80, 104, align="center")
        text(p, "Free for Windows", W / 2, H / 2 + 150, 36, MUTED, QFont.DemiBold, align="center")
        pill = QRectF(W / 2 - 330, H / 2 + 200, 660, 74)
        g = QLinearGradient(pill.topLeft(), pill.topRight())
        g.setColorAt(0, VIOLET)
        g.setColorAt(1, BLUE)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(pill, 37, 37)
        text(p, "github.com/pIayverse/intellijency", W / 2, pill.center().y() + 11, 30, align="center")
        p.setOpacity(1)

    def frame(self, t):
        img = QImage(W, H, QImage.Format_RGB888)
        p = QPainter(img)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        background(p, t)
        for part in (self.intro, self.tagline, self.showcase, self.lineup, self.scenes, self.features, self.outro):
            part(p, t)
        p.end()
        return img


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "trailer.mp4")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    trailer = Trailer(app)
    total = int(DURATION * FPS)
    writer = imageio_ffmpeg.write_frames(out, (W, H), fps=FPS, codec="libx264", pix_fmt_in="rgb24",
                                         output_params=["-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"],
                                         macro_block_size=8)
    writer.send(None)
    for i in range(total):
        img = trailer.frame(i / FPS)
        writer.send(bytes(img.constBits())[: W * H * 3])
        if i % 60 == 0:
            print(f"frame {i}/{total}", flush=True)
    writer.close()
    for t, name in ((1.2, "intro"), (5.5, "tagline"), (9.5, "showcase"), (15.5, "lineup"), (19.2, "scenes"),
                    (25.2, "features"), (29.0, "outro")):
        trailer.frame(t).save(out.replace(".mp4", f"_{name}.png"))
    print("done", out, flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
