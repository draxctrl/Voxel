import json
import logging
import os

logger = logging.getLogger(__name__)

import platform as _platform
_DEFAULT_HOTKEY = "<cmd>+<shift>+space" if _platform.system() == "Darwin" else "<ctrl>+<shift>+space"

DEFAULT_CONFIG = {
    "api_key": "",
    "hotkey": _DEFAULT_HOTKEY,
    "language": "en",
    "auto_start": False,
    "whisper_model": "whisper-large-v3",
    "llm_model": "llama-3.3-70b-versatile",
    "mute_sound": False,
}


def _default_config_path() -> str:
    import platform
    if platform.system() == "Darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    elif platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    return os.path.join(base, "Voxel", "config.json")


class Config:
    def __init__(self, config_path: str | None = None):
        self._path = config_path or _default_config_path()
        self._data: dict = {}

    def load(self) -> None:
        self._data = dict(DEFAULT_CONFIG)
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    self._data.update(saved)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load config from %s: %s", self._path, e)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def is_configured(self) -> bool:
        return bool(self._data.get("api_key"))
