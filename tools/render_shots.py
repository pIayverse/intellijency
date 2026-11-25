"""Render app screenshots in demo mode without ever showing a window.

    python tools/render_shots.py OUT_DIR [--size 1280x800]

Uses simulated devices and a throwaway settings folder (see ajazz_app/demo.py): no hardware, settings or screen.
"""
import os, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ajazz_app import demo  # noqa: E402

demo.prepare(os.path.join(tempfile.gettempdir(), "intellijency-demo"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

PAGES = {"home": 8, "general": 7, "devices": 6, "effects": 0, "switches": 1}


def settle(app, seconds=0.3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def make_window(size=(1280, 800)):
    from ajazz_app.gui import AjazzWindow
    demo.install()
    win = AjazzWindow()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)  # rendered, never shown
    win.resize(*size)
    win.show()
    return win


def main():
    out = sys.argv[1]
    size = (1280, 800)
    if "--size" in sys.argv:
        size = tuple(int(v) for v in sys.argv[sys.argv.index("--size") + 1].split("x"))
    os.makedirs(out, exist_ok=True)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    win = make_window(size)
    settle(app, 0.5)
    win.general_page.apply_scene(next(s for s in __import__("ajazz_app.general_rgb", fromlist=["SCENES"]).SCENES if s["name"] == "Aurora"))
    for name, idx in PAGES.items():
        win._switch_page(idx)
        settle(app, 0.6)
        win.grab().save(os.path.join(out, f"{name}.png"))
        print("saved", name)

    from ajazz_app.welcome import WelcomeDialog
    dlg = WelcomeDialog(win)
    dlg.setAttribute(Qt.WA_DontShowOnScreen, True)
    dlg.show()
    for i in range(4):
        dlg._go(i)
        settle(app, 0.5)
        dlg.grab().save(os.path.join(out, f"welcome{i + 1}.png"))
        print("saved welcome", i + 1)

    from PySide6.QtWidgets import QSystemTrayIcon
    QSystemTrayIcon.show = lambda self: None  # never put a real icon in the user's tray
    from ajazz_app.tray import Tray
    tray = Tray(app, win, app.windowIcon())
    tray._sync_menu()
    tray.menu.setAttribute(Qt.WA_DontShowOnScreen, True)
    tray.menu.show()
    settle(app, 0.3)
    tray.menu.grab().save(os.path.join(out, "tray.png"))
    print("saved tray")
    os._exit(0)


if __name__ == "__main__":
    main()
