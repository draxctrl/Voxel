# src/main.py
import logging
import os
import platform
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

import pyautogui
import pyperclip
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from groq import Groq

from src.config import Config
from src.mic_recorder import MicRecorder
from src.transcriber import Transcriber
from src.text_cleaner import TextCleaner
from src.text_injector import TextInjector, InjectionResult
from src.hotkey_listener import HotkeyListener
from src.tray_app import TrayApp
from src.history import HistoryStore
from src.profiles import ProfileManager
from src.voice_commands import VoiceCommandProcessor
from src.app_detector import AppDetector
from src.ui_pyqt6.settings_ui import SettingsWindow
from src.ui_pyqt6.recording_overlay import RecordingOverlay
from src.ui_pyqt6.splash import SplashScreen
from src.ui_pyqt6.history_window import HistoryWindow
from src.ui_pyqt6.stats_window import StatsWindow

MIN_AUDIO_DURATION = 0.5
MAX_RECORDING_DURATION = 120
RECORDING_WARNING_TIME = 105
SILENCE_RMS_THRESHOLD = 200
UNDO_STALE_SECONDS = 60


def _setup_logging() -> None:
    if platform.system() == "Darwin":
        appdata = os.path.join(os.path.expanduser("~"), "Library", "Logs")
    elif platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        appdata = os.environ.get("XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state"))
    log_dir = os.path.join(appdata, "Voxel")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "voxel.log")

    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=1)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


logger = logging.getLogger(__name__)


def _get_assets_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "src", "assets")
    return os.path.join(os.path.dirname(__file__), "assets")


class VoxelApp:
    def __init__(self):
        self._qapp = QApplication(sys.argv)
        self._qapp.setQuitOnLastWindowClosed(False)

        # Set app icon globally
        assets_dir = _get_assets_dir()
        ico_path = os.path.join(assets_dir, "icon.ico")
        if os.path.exists(ico_path):
            self._qapp.setWindowIcon(QIcon(ico_path))

        self._config = Config()
        self._config.load()

        # Core components
        self._recorder = MicRecorder(device_index=self._config.get("mic_device", None))
        self._groq_client: Groq | None = None
        self._transcriber: Transcriber | None = None
        self._cleaner: TextCleaner | None = None

        # History
        self._history = HistoryStore()

        # Profiles
        self._profiles = ProfileManager(self._config)

        # Voice commands
        self._voice_commands = VoiceCommandProcessor(self._config.get("voice_commands", {}))

        # App detector (for per-app profiles)
        self._app_detector = AppDetector()

        # Offline transcriber (lazy loaded)
        self._offline_transcriber = None

        # Injector
        chime_path = os.path.join(assets_dir, "chime.wav")
        if self._config.get("mute_sound", False) or not os.path.exists(chime_path):
            chime_path = None
        self._injector = TextInjector(
            chime_path=chime_path,
            always_copy=self._config.get("always_copy", False),
        )

        # Undo state
        self._last_injection: InjectionResult | None = None
        self._last_injection_time: float = 0.0
        self._undo_lock = threading.Lock()

        # Tray
        self._tray = TrayApp(
            assets_dir=assets_dir,
            on_settings=self._show_settings,
            on_quit=self._quit,
            on_history=self._show_history,
            on_stats=self._show_stats,
        )

        # Hotkey listeners
        self._hotkey_listener: HotkeyListener | None = None
        self._undo_listener: HotkeyListener | None = None
        self._recording_start_time: float = 0.0
        self._max_record_timer: threading.Timer | None = None
        self._running = True

        # UI
        self._settings_window = SettingsWindow(
            config=self._config,
            on_save=self._on_settings_saved,
            on_validate_key=self._validate_api_key,
            on_quit=self._quit,
            on_history=self._show_history,
            on_stats=self._show_stats,
        )
        self._history_window = HistoryWindow(self._history)
        self._stats_window = StatsWindow(self._history)
        self._overlay = RecordingOverlay()
        self._splash = SplashScreen()

    def _init_groq(self) -> bool:
        api_key = self._config.get("api_key", "")
        if not api_key:
            return False
        self._groq_client = Groq(api_key=api_key)
        self._transcriber = Transcriber(
            client=self._groq_client,
            model=self._config.get("whisper_model", "whisper-large-v3"),
        )

        # Use active profile's prompt
        prompt = self._profiles.get_active_prompt()
        self._cleaner = TextCleaner(
            client=self._groq_client,
            model=self._config.get("llm_model", "llama-3.3-70b-versatile"),
            cleanup_prompt=prompt,
        )
        return True

    def _start_hotkey_listener(self) -> None:
        if self._hotkey_listener:
            self._hotkey_listener.stop()

        hotkey = self._config.get("hotkey", "<ctrl>+<shift>+space")
        self._hotkey_listener = HotkeyListener(
            hotkey_str=hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )
        self._hotkey_listener.start()

        # Start undo hotkey listener
        self._start_undo_listener()

    def _start_undo_listener(self) -> None:
        if self._undo_listener:
            self._undo_listener.stop()

        undo_hotkey = self._config.get("undo_hotkey", "<ctrl>+<shift>+z")
        if undo_hotkey:
            self._undo_listener = HotkeyListener(
                hotkey_str=undo_hotkey,
                on_press=self._on_undo_press,
                on_release=lambda: None,
                min_hold_duration=0.0,
            )
            self._undo_listener.start()
            logger.info("Undo hotkey listener started: %s", undo_hotkey)

    def _on_hotkey_press(self) -> None:
        if self._recorder.is_recording:
            return
        self._recorder.start()
        self._recording_start_time = time.time()
        self._tray.set_state("recording")
        self._overlay.show_recording()

        self._max_record_timer = threading.Timer(MAX_RECORDING_DURATION, self._on_hotkey_release)
        self._max_record_timer.daemon = True
        self._max_record_timer.start()

    def _on_hotkey_release(self) -> None:
        if self._max_record_timer:
            self._max_record_timer.cancel()
            self._max_record_timer = None

        if not self._recorder.is_recording:
            return

        # Play chime immediately on release as confirmation
        self._injector.play_chime()

        rms = self._recorder.get_rms()
        audio_bytes = self._recorder.stop()
        duration = time.time() - self._recording_start_time

        self._tray.set_state("processing")
        self._overlay.show_processing()

        if duration < MIN_AUDIO_DURATION or not audio_bytes or rms < SILENCE_RMS_THRESHOLD:
            logger.debug("Recording skipped (duration=%.1fs, rms=%.0f)", duration, rms)
            self._tray.set_state("idle")
            self._overlay.hide()
            return

        thread = threading.Thread(
            target=self._process_audio,
            args=(audio_bytes, duration),
            daemon=True,
        )
        thread.start()

    def _process_audio(self, audio_bytes: bytes, duration: float) -> None:
        try:
            # Determine transcription method
            use_offline = self._config.get("offline_mode", False)
            language = self._config.get("language", "en")

            if use_offline:
                raw_text = self._transcribe_offline(audio_bytes, language)
            else:
                if not self._transcriber or not self._cleaner:
                    logger.error("Groq client not initialized")
                    self._tray.set_state("error")
                    self._overlay.hide()
                    return
                raw_text = self._transcriber.transcribe(audio_bytes, language=language)

            if not raw_text or not raw_text.strip():
                logger.info("Empty transcript, skipping")
                self._tray.set_state("idle")
                self._overlay.hide()
                return

            # Check voice commands FIRST
            expansion = self._voice_commands.match(raw_text)
            if expansion is not None:
                logger.info("Voice command matched: %s", raw_text.strip()[:50])
                result = self._injector.inject(expansion)
                self._history.add(raw_text, expansion, language or "auto", duration, profile="voice_command")
                with self._undo_lock:
                    self._last_injection = result
                    self._last_injection_time = time.time()
                self._overlay.hide()
                self._tray.set_state("idle")
                return

            # Per-app profile switching
            if self._config.get("auto_profile", False):
                app_name = self._app_detector.get_active_app()
                app_profiles = self._config.get("app_profiles", {})
                if app_name in app_profiles:
                    profile_id = app_profiles[app_name]
                    profiles = self._profiles.list_profiles()
                    if profile_id in profiles:
                        prompt = profiles[profile_id]["prompt"]
                        self._cleaner.set_prompt(prompt)
                        logger.info("Auto-switched to profile '%s' for app '%s'", profile_id, app_name)

            # Normal cleanup flow (skip if offline mode without API)
            if not use_offline and self._cleaner:
                active_profile = self._profiles.get_active_profile()
                cleaned_text = self._cleaner.clean(raw_text)
            else:
                # Offline mode without LLM cleanup - use raw text with basic cleanup
                active_profile = {"name": "Offline"}
                cleaned_text = raw_text.strip()

            # Save to history
            self._history.add(
                raw_text, cleaned_text, language, duration,
                profile=active_profile.get("name", "Default"),
            )

            # Inject text
            result = self._injector.inject(cleaned_text)

            # Store for undo
            with self._undo_lock:
                self._last_injection = result
                self._last_injection_time = time.time()

            if not result.pasted and self._config.get("clipboard_notice", True):
                self._overlay.show_clipboard_notice()
            else:
                self._overlay.hide()

            self._tray.set_state("idle")

        except Exception as e:
            logger.error("Processing failed: %s", e, exc_info=True)
            self._tray.set_state("error")
            self._overlay.hide()
            threading.Timer(3.0, lambda: self._tray.set_state("idle")).start()

    def _on_undo_press(self) -> None:
        """Undo the last dictation paste."""
        with self._undo_lock:
            last = self._last_injection
            if last is None:
                logger.debug("Nothing to undo")
                return

            age = time.time() - self._last_injection_time
            if age > UNDO_STALE_SECONDS:
                logger.debug("Undo too stale (%.0fs ago)", age)
                self._last_injection = None
                return

            self._last_injection = None

        logger.info("Undoing last dictation")

        if last.pasted:
            undo_modifier = "command" if platform.system() == "Darwin" else "ctrl"
            pyautogui.hotkey(undo_modifier, "z")
            time.sleep(0.05)

        # Restore clipboard
        try:
            pyperclip.copy(last.old_clipboard)
        except Exception as e:
            logger.warning("Failed to restore clipboard on undo: %s", e)

    def _transcribe_offline(self, audio_bytes: bytes, language: str | None) -> str:
        """Transcribe using local Whisper model."""
        if self._offline_transcriber is None:
            from src.offline_transcriber import OfflineTranscriber
            model_size = self._config.get("offline_model", "base")
            self._offline_transcriber = OfflineTranscriber(model_size=model_size)
        if not self._offline_transcriber.is_loaded():
            logger.info("Loading offline Whisper model...")
            self._offline_transcriber.load_model()
        return self._offline_transcriber.transcribe(audio_bytes, language=language)

    def _show_settings(self) -> None:
        self._settings_window.show()

    def _show_stats(self) -> None:
        self._stats_window.refresh()
        self._stats_window.show()
        self._stats_window.raise_()
        self._stats_window.activateWindow()

    def _show_history(self) -> None:
        self._history_window.refresh()
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()

    def _on_settings_saved(self) -> None:
        logger.info("Settings saved, reinitializing")
        self._config.load()
        self._init_groq()
        self._start_hotkey_listener()

        # Reinitialize injector
        assets_dir = _get_assets_dir()
        chime_path = os.path.join(assets_dir, "chime.wav")
        if self._config.get("mute_sound", False) or not os.path.exists(chime_path):
            chime_path = None
        self._injector = TextInjector(
            chime_path=chime_path,
            always_copy=self._config.get("always_copy", False),
        )

        # Reinitialize recorder
        self._recorder = MicRecorder(device_index=self._config.get("mic_device", None))

        # Reload voice commands
        self._voice_commands.reload(self._config.get("voice_commands", {}))

        # Reload profile prompt
        prompt = self._profiles.get_active_prompt()
        if self._cleaner:
            self._cleaner.set_prompt(prompt)

    def _validate_api_key(self, key: str) -> bool:
        try:
            client = Groq(api_key=key)
            client.models.list()
            return True
        except Exception:
            return False

    def _quit(self) -> None:
        logger.info("Quitting Voxel")
        self._running = False

        if self._recorder.is_recording:
            self._recorder.stop()

        if self._hotkey_listener:
            self._hotkey_listener.stop()

        if self._undo_listener:
            self._undo_listener.stop()

        self._tray.stop()
        self._settings_window._quitting = True
        self._qapp.quit()

    def run(self) -> None:
        _setup_logging()
        logger.info("Voxel starting")

        self._splash.show()

        QTimer.singleShot(50, self._startup_stage_1)
        self._qapp.exec()

    def _startup_stage_1(self) -> None:
        self._splash.set_status("Loading system tray...")
        self._tray.start()
        QTimer.singleShot(50, self._startup_stage_2)

    def _startup_stage_2(self) -> None:
        self._splash.set_status("Connecting to Groq API...")
        if not self._init_groq():
            logger.info("No API key configured, showing settings")
            self._splash.set_status("No API key found")
            QTimer.singleShot(50, self._startup_finish_no_key)
        else:
            QTimer.singleShot(50, self._startup_stage_3)

    def _startup_stage_3(self) -> None:
        self._splash.set_status("Starting hotkey listener...")
        self._start_hotkey_listener()
        QTimer.singleShot(50, self._startup_finish)

    def _startup_finish(self) -> None:
        self._splash.set_status("Ready! Hold Ctrl+Shift+Space to dictate")
        QTimer.singleShot(400, self._finish_and_show_taskbar)

    def _finish_and_show_taskbar(self) -> None:
        self._splash.close_splash()
        self._settings_window.show()

    def _startup_finish_no_key(self) -> None:
        self._splash.close_splash()
        QTimer.singleShot(100, self._settings_window.show)


def main():
    app = VoxelApp()
    app.run()


if __name__ == "__main__":
    main()
