"""Auto-update from GitHub Releases through Velopack. Does nothing when the app runs from source (not installed)."""
import threading
from PySide6.QtCore import QObject, Signal

REPO_URL = "https://github.com/pIayverse/intellijency"

try:
    import velopack
except ImportError:  # running from source without velopack installed
    velopack = None


def current_version():
    """Installed version, e.g. '1.0.0'; None when running from source."""
    if velopack is None:
        return None
    try:
        return str(velopack.UpdateManager(velopack.GithubSource(REPO_URL)).get_current_version())
    except Exception:
        return None


class Updater(QObject):
    ready = Signal(str)  # emitted with the new version once it is downloaded

    def __init__(self):
        super().__init__()
        self._mgr = self._update = None

    def start(self):
        if velopack is not None:
            threading.Thread(target=self._check, daemon=True).start()  # network work off the UI thread

    def _check(self):
        try:
            mgr = velopack.UpdateManager(velopack.GithubSource(REPO_URL))
            info = mgr.check_for_updates()
            if not info:
                return
            mgr.download_updates(info)
            self._mgr, self._update = mgr, info
            self.ready.emit(str(info.TargetFullRelease.Version))
        except Exception:
            pass  # not installed, offline, or GitHub unreachable: try again next start

    def restart_now(self):
        self._mgr.apply_updates_and_restart(self._update)

    def apply_on_exit(self):
        self._mgr.wait_exit_then_apply_updates(self._update, silent=True, restart=False)
