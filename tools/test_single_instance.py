"""Self-check for the one-copy-only guard in main.py. Runs offscreen on a test name; never touches the real app.

    python tools/test_single_instance.py
"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import main  # noqa: E402  (main's app code only runs under __main__)

main.INSTANCE_KEY = "Intellijency-selftest"
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402


def first_copy():
    app = QApplication([])
    win = QWidget()
    shown = []
    win.showNormal = lambda: shown.append("show")
    main.listen_for_other_copies(win)
    QTimer.singleShot(4000, app.quit)
    app.exec()
    print("SHOWN", len(shown), flush=True)


def check():
    first = subprocess.Popen([sys.executable, __file__, "--first"], stdout=subprocess.PIPE, text=True)
    time.sleep(1.5)
    app = QApplication([])  # noqa: F841
    assert main.hand_off_to_running_copy(show=True), "second copy did not find the first"
    assert main.hand_off_to_running_copy(show=False), "background launch did not find the first"
    out, _ = first.communicate(timeout=10)
    assert "SHOWN 1" in out, f"first copy should show its window once (background launch stays hidden): {out!r}"
    assert not main.hand_off_to_running_copy(show=True), "a closed copy must not block a new start"
    print("single-instance guard OK")


if __name__ == "__main__":
    first_copy() if "--first" in sys.argv else check()
