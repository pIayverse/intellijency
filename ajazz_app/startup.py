"""Start with Windows: an entry in the current user's Run key (no admin rights needed)."""
import os, sys

try:
    import winreg
except ImportError:  # not Windows
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Intellijency"


def _command():
    if getattr(sys, "frozen", False):  # installed app; Velopack keeps this path stable across updates
        return f'"{sys.executable}" --minimized'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pythonw}" "{os.path.abspath(sys.argv[0])}" --minimized'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, NAME)
        return True
    except OSError:
        return False


def set_enabled(on: bool):
    if winreg is None:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass
