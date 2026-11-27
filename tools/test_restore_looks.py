"""Self-check: PC parts get their colour back after a restart. Demo mode (simulated devices), offscreen.

    python tools/test_restore_looks.py
"""
import os, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from ajazz_app import demo  # noqa: E402

demo.prepare(tempfile.mkdtemp(prefix="intellijency-restore-"))
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main():
    app = QApplication([])
    from ajazz_app import gui, pc_rgb
    demo.install()
    win = gui.AjazzWindow()
    gp = win.general_page
    gp.stop_sync()
    gp.cb.setCurrentText("Static")  # a still look: the case that used to be forgotten
    assert win.pc_page._connect()
    devs = win.pc_page.client.devices
    red, cyan = QColor("#ff0000"), QColor("#00d4ff")
    pc_rgb.apply_and_remember(devs[0], "Static", red)
    pc_rgb.apply_and_remember(devs[1], "Static", cyan)
    pc_rgb.apply_and_remember(devs[2], "Off", QColor(0, 0, 0))

    for d in devs:  # "restart": the hardware falls back to its own colour
        d.active_mode = 0
        d.set_color(pc_rgb.RGBColor(1, 2, 3))

    gp.resume(attempts=3)
    end = time.monotonic() + 7  # resume waits one 5 s poll for the device list to settle
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)

    rgb = lambda d: (d.colors[0].red, d.colors[0].green, d.colors[0].blue)  # noqa: E731
    assert rgb(devs[0]) == (255, 0, 0), rgb(devs[0])
    assert rgb(devs[1]) == (0, 212, 255), rgb(devs[1])
    d2 = devs[2]
    assert "off" in d2.modes[d2.active_mode].name.lower() or rgb(d2) == (0, 0, 0), "Off wasn't restored"
    assert rgb(devs[3]) == (1, 2, 3), "a device with no saved look must be left alone"
    print("restore after restart OK", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
