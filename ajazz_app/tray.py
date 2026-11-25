"""System tray: Intellijency keeps running (and synced lighting keeps playing) when the window is closed."""
import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from . import startup
from .general_rgb import SCENES

HINT_FLAG = os.path.expanduser("~/.config/ajazz_studio/tray_hint_shown")
MENU_STYLE = ("QMenu { background: #17181f; color: #e2e2e9; border: 1px solid #2e303c; border-radius: 10px; padding: 6px; } "
              "QMenu::item { padding: 7px 26px 7px 14px; border-radius: 6px; } "
              "QMenu::item:selected { background: rgba(124, 92, 255, 0.22); } "
              "QMenu::separator { height: 1px; background: #2a2c36; margin: 5px 8px; } "
              "QMenu::indicator { width: 14px; height: 14px; }")


class Tray:
    def __init__(self, app, win, icon):
        self.app, self.win = app, win
        self.icon = QSystemTrayIcon(icon, app)
        self.icon.setToolTip("Intellijency")
        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction("Open Intellijency", self.show_window)
        menu.addSeparator()
        scenes = menu.addMenu("Scenes")
        scenes.setStyleSheet(MENU_STYLE)
        for scene in SCENES:
            scenes.addAction(scene["name"], lambda s=scene: win.general_page.apply_scene(s))
        self.act_pause = menu.addAction("Pause effects", self._toggle_pause)
        menu.addSeparator()
        self.act_start = menu.addAction("Start with Windows")
        self.act_start.setCheckable(True)
        self.act_start.toggled.connect(self._set_start)
        menu.addSeparator()
        menu.addAction("Quit", self.quit)
        menu.aboutToShow.connect(self._sync_menu)
        self.menu = menu  # keep a reference: the tray doesn't own the menu
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._activated)
        self.icon.show()

    def _sync_menu(self):
        self.act_pause.setText("Pause effects" if self.win.general_page.sync_now()[0] else "Resume effects")
        self.act_start.blockSignals(True)
        self.act_start.setChecked(startup.is_enabled())
        self.act_start.blockSignals(False)

    def _set_start(self, on):
        startup.set_enabled(on)
        chk = getattr(self.win, "chk_start", None)
        if chk is not None:
            chk.blockSignals(True)
            chk.setChecked(on)
            chk.blockSignals(False)

    def _toggle_pause(self):
        gp = self.win.general_page
        if gp.sync_now()[0]:
            gp.stop_sync()
        else:
            gp.apply(scene_name=gp.scene)

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self):
        self.win.showNormal()
        self.win.raise_()
        self.win.activateWindow()

    def hint_once(self):
        """First time the window is closed, explain that the app is still running."""
        if os.path.exists(HINT_FLAG):
            return
        self.icon.showMessage("Intellijency is still running",
                              "Your lighting keeps playing. Open it again from the tray icon, or quit from its menu.",
                              QSystemTrayIcon.Information, 6000)
        try:
            os.makedirs(os.path.dirname(HINT_FLAG), exist_ok=True)
            open(HINT_FLAG, "w").close()
        except OSError:
            pass

    def quit(self):
        self.win._quitting = True
        self.icon.hide()
        self.app.quit()
