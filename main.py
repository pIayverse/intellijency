import sys
import traceback
import os
import tempfile

if __name__ == "__main__":
    try:
        import velopack
        velopack.App().run()  # must run first: handles install / update / uninstall hooks and may exit
    except ImportError:
        pass  # running from source without velopack

DEMO = "--demo" in sys.argv  # simulated devices and a throwaway settings folder; never touches hardware
if DEMO:
    from ajazz_app import demo
    demo.prepare(os.path.join(tempfile.gettempdir(), "intellijency-demo"))  # before any settings path is read

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from ajazz_app.gui import AjazzWindow
from ajazz_app.updater import Updater, current_version
from ajazz_app import welcome
from ajazz_app.tray import Tray

CRASH_LOG = os.path.join(os.path.expanduser("~/.config/ajazz_studio"), "crash.log")


def handle_exception(exc_type, exc_value, exc_tb):
    err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("\n=== CRASH LOG ===\n", err_text)
    try:  # the app folder may be read-only (installed, or started by Windows), so log to the settings folder
        os.makedirs(os.path.dirname(CRASH_LOG), exist_ok=True)
        with open(CRASH_LOG, "w", encoding="utf-8") as f:
            f.write(err_text)
    except OSError:
        pass
    QMessageBox.critical(None, "Application error", err_text)


def offer_update(win, updater, version):
    if not win.isVisible() or win.isMinimized():  # running in the background: install quietly when the app closes
        updater.apply_on_exit()
        return
    box = QMessageBox(win)
    box.setWindowTitle("Update ready")
    box.setText(f"Intellijency {version} has been downloaded.")
    box.setInformativeText("Restart now to use it, or it will be installed when you quit the app.")
    now = box.addButton("Restart now", QMessageBox.AcceptRole)
    box.addButton("Later", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() is now:
        updater.restart_now()
    else:
        updater.apply_on_exit()


INSTANCE_KEY = "Intellijency-" + os.environ.get("USERNAME", os.environ.get("USER", "user"))


def hand_off_to_running_copy(show: bool) -> bool:
    """True when Intellijency is already running; asks that copy to show its window unless started in the background."""
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if not sock.waitForConnected(500):
        return False
    sock.write(b"show" if show else b"ping")
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


def listen_for_other_copies(win):
    """Later launches (desktop shortcut, Start with Windows) bring this window forward instead of starting a second app."""
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(win)
    QLocalServer.removeServer(INSTANCE_KEY)  # clears a stale socket left by a crash (no-op on Windows)

    def on_connect():
        conn = server.nextPendingConnection()
        if conn.waitForReadyRead(500) and bytes(conn.readAll()).startswith(b"show"):
            win.showNormal()
            win.raise_()
            win.activateWindow()
        conn.deleteLater()

    server.newConnection.connect(on_connect)
    server.listen(INSTANCE_KEY)
    return server


sys.excepthook = handle_exception

if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes  # own taskbar identity, so Windows shows this app's icon instead of Python's
        # same id as the installer's shortcuts, so a pinned shortcut and the running window share one taskbar icon
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "velopack.Intellijency" if getattr(sys, "frozen", False) else "Intellijency.App")
    app = QApplication(sys.argv)
    background = "--minimized" in sys.argv  # Start with Windows
    if not DEMO and hand_off_to_running_copy(show=not background):
        sys.exit(0)  # one copy only: two would fight over the keyboard and the lights
    icon = QIcon()
    _bd = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for _p in (os.path.join(_bd, "assets", "intellijency-logo.ico"), os.path.join(_bd, "assets", "icon.png")):
        if os.path.exists(_p):
            icon = QIcon(_p)
            app.setWindowIcon(icon)
            break
    app.setStyle("Fusion")
    if DEMO:
        demo.install()
    win = AjazzWindow()
    version = current_version()
    win.setWindowTitle(f"Intellijency {version}" if version else ("Intellijency (demo)" if DEMO else "Intellijency"))
    win.move(app.primaryScreen().availableGeometry().center() - win.rect().center())  # open centred, fully on screen
    if not DEMO:
        win._instance_server = listen_for_other_copies(win)

    if QSystemTrayIcon.isSystemTrayAvailable():
        win.tray = Tray(app, win, icon)
        app.setQuitOnLastWindowClosed(False)  # closing the window keeps the app (and its lighting) running
    if background and getattr(win, "tray", None) is not None:
        QTimer.singleShot(20000, win.release_memory)  # started into the tray: hand back start-up memory once lighting is restored
    if background and getattr(win, "tray", None) is None:
        win.showMinimized()
    elif not background:
        win.show()
        if welcome.needed():
            QTimer.singleShot(300, lambda: welcome.WelcomeDialog(win, win).exec())

    QTimer.singleShot(1500, win.general_page.resume)  # restart a synced effect that was running last time
    if not DEMO:
        updater = Updater()
        # queued: `ready` is emitted from the download thread, the dialog must open on the UI thread
        updater.ready.connect(lambda v: offer_update(win, updater, v), Qt.QueuedConnection)
        QTimer.singleShot(4000, updater.start)  # check GitHub for a newer version once the app has settled
    sys.exit(app.exec())
