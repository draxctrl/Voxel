import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "api_key": "",
    "hotkey": "<ctrl>+<shift>+space",
    "language": "en",
    "auto_start": False,
    "whisper_model": "whisper-large-v3",
    "llm_model": "llama-3.3-70b-versatile",
    "mute_sound": False,
    "voice_commands": {},
    "active_profile": "grammar_tidy",
    "profiles": {},
    "auto_profile": False,
    "app_profiles": {},
    # Microphone is identified by name: PyAudio indices renumber whenever audio
    # devices are added or removed, so an index alone silently points at a
    # different mic. mic_device is kept only as a fallback hint for old configs.
    "mic_device_name": None,
    "mic_device": None,
    # "hold" = press and hold to record; "toggle" = press to start, press to stop.
    "activation_mode": "hold",
    "offline_mode": False,
    "offline_model": "base",
    "raw_mode": False,
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
        self._migrate_profile_ids()

    def _migrate_profile_ids(self) -> None:
        """Point old mode ids at their replacements after consolidation.

        Runs silently on load so an existing config keeps working rather than
        landing on a mode the user never chose. Custom profile ids are left
        alone; only ids we removed are rewritten.
        """
        from src.profiles import ProfileManager

        active = self._data.get("active_profile")
        if isinstance(active, str):
            migrated = ProfileManager.migrate_profile_id(active)
            if migrated != active:
                logger.info("Migrated active profile '%s' -> '%s'", active, migrated)
                self._data["active_profile"] = migrated

        app_profiles = self._data.get("app_profiles")
        if isinstance(app_profiles, dict):
            self._data["app_profiles"] = {
                app: ProfileManager.migrate_profile_id(pid) if isinstance(pid, str) else pid
                for app, pid in app_profiles.items()
            }

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def backfill_mic_name(self, active_device_name: str | None) -> bool:
        """Record the name of a device that was only ever saved as an index.

        Upgrading users have ``mic_device`` but no ``mic_device_name``, so they
        would keep the old behaviour — a renumbered index silently selecting a
        different microphone — until they happened to re-save their settings.

        Deliberately does nothing when no device was ever chosen: that means
        "follow the system default", and pinning a name there would break the
        user when they change their Windows default. Returns True if it saved.
        """
        if not active_device_name:
            return False
        if self._data.get("mic_device_name"):
            return False
        if self._data.get("mic_device") is None:
            return False

        logger.info("Recording microphone name %r for a legacy index-only config",
                    active_device_name)
        self._data["mic_device_name"] = active_device_name
        self.save()
        return True

    def is_configured(self) -> bool:
        return bool(self._data.get("api_key"))
