import logging
import os
import threading
from typing import Callable

from PIL import Image
import pystray
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt, Q_ARG

logger = logging.getLogger(__name__)


class _TraySignals(QObject):
    """Signals to marshal tray callbacks onto the Qt GUI thread."""
    settings_requested = pyqtSignal()
    history_requested = pyqtSignal()
    stats_requested = pyqtSignal()
    quit_requested = pyqtSignal()


class TrayApp:
    STATES = ("idle", "recording", "processing", "error")

    def __init__(self, assets_dir: str, on_settings: Callable, on_quit: Callable, on_history: Callable | None = None, on_stats: Callable | None = None):
        self._assets_dir = assets_dir
        self._icon: pystray.Icon | None = None
        self._icons: dict[str, Image.Image] = {}
        self._load_icons()

        # Use Qt signals so callbacks run on the GUI thread
        self._signals = _TraySignals()
        self._signals.settings_requested.connect(on_settings)
        if on_history:
            self._signals.history_requested.connect(on_history)
        if on_stats:
            self._signals.stats_requested.connect(on_stats)
        self._signals.quit_requested.connect(on_quit)

    def _load_icons(self) -> None:
        icon_map = {
            "idle": "icon_idle.png",
            "recording": "icon_recording.png",
            "processing": "icon_processing.png",
        }
        for state, filename in icon_map.items():
            path = os.path.join(self._assets_dir, filename)
            try:
                self._icons[state] = Image.open(path)
            except Exception as e:
                logger.warning("Failed to load icon %s: %s", path, e)
                self._icons[state] = Image.new("RGBA", (64, 64), (128, 128, 128, 255))

        self._icons["error"] = Image.new("RGBA", (64, 64), (255, 0, 0, 255))

    def start(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Settings", lambda: self._signals.settings_requested.emit(), default=True),
            pystray.MenuItem("History", lambda: self._signals.history_requested.emit()),
            pystray.MenuItem("Statistics", lambda: self._signals.stats_requested.emit()),
            pystray.MenuItem("Quit", lambda: self._signals.quit_requested.emit()),
        )
        self._icon = pystray.Icon(
            "Voxel",
            self._icons["idle"],
            "Voxel",
            menu,
        )
        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()
        logger.info("Tray app started")

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
            self._icon = None

    def set_state(self, state: str) -> None:
        if state not in self.STATES:
            logger.warning("Unknown tray state: %s", state)
            return
        if self._icon:
            self._icon.icon = self._icons[state]
            tooltip = {
                "idle": "Voxel — Ready",
                "recording": "Voxel — Recording...",
                "processing": "Voxel — Processing...",
                "error": "Voxel — Error",
            }
            self._icon.title = tooltip.get(state, "Voxel")
