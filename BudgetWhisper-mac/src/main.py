# src/main.py
import logging
import os
import queue
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from groq import Groq

from src.config import Config
from src.mic_recorder import MicRecorder
from src.transcriber import Transcriber
from src.text_cleaner import TextCleaner
from src.text_injector import TextInjector
from src.hotkey_listener import HotkeyListener
from src.tray_app import TrayApp
from src.ui_pyqt6.settings_ui import SettingsWindow
from src.ui_pyqt6.recording_overlay import RecordingOverlay
from src.ui_pyqt6.splash import SplashScreen

MIN_AUDIO_DURATION = 0.5
MAX_RECORDING_DURATION = 120
RECORDING_WARNING_TIME = 105
SILENCE_RMS_THRESHOLD = 200


def _setup_logging() -> None:
    import platform
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
        self._qapp.setQuitOnLastWindowClosed(False)  # keep running when windows close

        # Set app icon globally
        assets_dir = _get_assets_dir()
        ico_path = os.path.join(assets_dir, "icon.ico")
        if os.path.exists(ico_path):
            self._qapp.setWindowIcon(QIcon(ico_path))

        self._config = Config()
        self._config.load()

        self._recorder = MicRecorder()

        self._groq_client: Groq | None = None
        self._transcriber: Transcriber | None = None
        self._cleaner: TextCleaner | None = None

        chime_path = os.path.join(assets_dir, "chime.wav")
        if self._config.get("mute_sound", False) or not os.path.exists(chime_path):
            chime_path = None
        self._injector = TextInjector(
            chime_path=chime_path,
            always_copy=self._config.get("always_copy", False),
        )

        self._tray = TrayApp(
            assets_dir=assets_dir,
            on_settings=self._show_settings,
            on_quit=self._quit,
        )

        self._hotkey_listener: HotkeyListener | None = None
        self._recording_start_time: float = 0.0
        self._max_record_timer: threading.Timer | None = None
        self._running = True

        self._settings_window = SettingsWindow(
            config=self._config,
            on_save=self._on_settings_saved,
            on_validate_key=self._validate_api_key,
            on_quit=self._quit,
        )

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
        self._cleaner = TextCleaner(
            client=self._groq_client,
            model=self._config.get("llm_model", "llama-3.3-70b-versatile"),
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
        self._tray.set_state("processing")
        self._overlay.show_processing()

        duration = time.time() - self._recording_start_time
        if duration < MIN_AUDIO_DURATION or not audio_bytes or rms < SILENCE_RMS_THRESHOLD:
            logger.debug("Recording skipped (duration=%.1fs, rms=%.0f)", duration, rms)
            self._tray.set_state("idle")
            self._overlay.hide()
            return

        thread = threading.Thread(target=self._process_audio, args=(audio_bytes,), daemon=True)
        thread.start()

    def _process_audio(self, audio_bytes: bytes) -> None:
        try:
            if not self._transcriber or not self._cleaner:
                logger.error("Groq client not initialized")
                self._tray.set_state("error")
                self._overlay.hide()
                return

            language = self._config.get("language", "en")
            raw_text = self._transcriber.transcribe(audio_bytes, language=language)

            if not raw_text.strip():
                logger.info("Empty transcript, skipping")
                self._tray.set_state("idle")
                self._overlay.hide()
                return

            cleaned_text = self._cleaner.clean(raw_text)
            self._overlay.hide()
            pasted = self._injector.inject(cleaned_text)
            if not pasted and self._config.get("clipboard_notice", True):
                self._overlay.show_clipboard_notice()
            self._tray.set_state("idle")

        except Exception as e:
            logger.error("Processing failed: %s", e, exc_info=True)
            self._tray.set_state("error")
            self._overlay.hide()
            threading.Timer(3.0, lambda: self._tray.set_state("idle")).start()

    def _show_settings(self) -> None:
        self._settings_window.show()

    def _on_settings_saved(self) -> None:
        logger.info("Settings saved, reinitializing")
        self._config.load()
        self._init_groq()
        self._start_hotkey_listener()
        # Reinitialize injector with updated settings
        assets_dir = _get_assets_dir()
        chime_path = os.path.join(assets_dir, "chime.wav")
        if self._config.get("mute_sound", False) or not os.path.exists(chime_path):
            chime_path = None
        self._injector = TextInjector(
            chime_path=chime_path,
            always_copy=self._config.get("always_copy", False),
        )

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

        self._tray.stop()
        # Allow the settings window to actually close on quit
        self._settings_window._quitting = True
        self._qapp.quit()

    def run(self) -> None:
        _setup_logging()
        logger.info("Voxel starting")

        # Show splash
        self._splash.show()

        # Staged startup — minimal delays just to let UI render
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
        # Show settings so user sees the app UI
        self._settings_window.show()

    def _startup_finish_no_key(self) -> None:
        self._splash.close_splash()
        # No API key — open settings fully so user can configure
        QTimer.singleShot(100, self._settings_window.show)


def main():
    app = VoxelApp()
    app.run()


if __name__ == "__main__":
    main()
