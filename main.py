import sys
import traceback
import os
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from ajazz_app.gui import AjazzWindow

def handle_exception(exc_type, exc_value, exc_tb):
    err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("\n=== CRASH LOG ===\n", err_text)
    with open("crash.log", "w", encoding="utf-8") as f:
        f.write(err_text)
    QMessageBox.critical(None, "Application error", err_text)

sys.excepthook = handle_exception

if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes  # own taskbar identity, so Windows shows this app's icon instead of Python's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Intellijency.App")
    app = QApplication(sys.argv)
    _bd = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for _p in (os.path.join(_bd, "assets", "intellijency.ico"), os.path.join(_bd, "intellijency.ico"), os.path.join(_bd, "assets", "icon.png"), os.path.join(_bd, "icon.png")):
        if os.path.exists(_p):
            app.setWindowIcon(QIcon(_p))
            break
    app.setStyle("Fusion")
    win = AjazzWindow()
    win.move(app.primaryScreen().availableGeometry().center() - win.rect().center())  # open centred, fully on screen
    if "--minimized" in sys.argv:  # used by the Windows startup shortcut
        win.showMinimized()
    else:
        win.show()
    QTimer.singleShot(1500, win.general_page.resume)  # restart a synced effect that was running last time
    sys.exit(app.exec())
