# src/main.py
import logging
import os
import platform
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
from src.history import HistoryStore
from src.profiles import ProfileManager, resolve_effective_profile
from src.voice_commands import VoiceCommandProcessor
from src.app_detector import AppDetector
from src.ui_pyqt6.theme import load_fonts, apply_theme
from src.ui_pyqt6.settings_ui import SettingsWindow
from src.ui_pyqt6.recording_overlay import RecordingOverlay
from src.ui_pyqt6.recording_styles import DEFAULT_STYLE
from src.ui_pyqt6.splash import SplashScreen
from src.ui_pyqt6.history_window import HistoryWindow
from src.ui_pyqt6.stats_window import StatsWindow

MIN_AUDIO_DURATION = 0.5
MAX_RECORDING_DURATION = 120
RECORDING_WARNING_TIME = 105
SILENCE_RMS_THRESHOLD = 200


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

        # Bundled Inter stands in for SF Pro, which can't be redistributed.
        # The stylesheet falls back to Segoe UI if this fails.
        assets_dir = _get_assets_dir()
        load_fonts(assets_dir)

        # One stylesheet on the QApplication, so every window and every dialog
        # created later inherits it and a theme change restyles all of them.
        apply_theme(self._qapp)
        self._watch_system_theme()

        # Set app icon globally
        ico_path = os.path.join(assets_dir, "icon.ico")
        if os.path.exists(ico_path):
            self._qapp.setWindowIcon(QIcon(ico_path))

        self._config = Config()
        self._config.load()

        # Core components
        self._recorder = MicRecorder(
            device_name=self._config.get("mic_device_name", None),
            device_index=self._config.get("mic_device", None),
        )
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
        # The provider is a bound lambda rather than self._recorder.current_level,
        # because _on_settings_saved replaces the recorder: a bound method would
        # keep animating from the stream that was closed.
        self._overlay = RecordingOverlay(
            style=self._config.get("recording_style", DEFAULT_STYLE),
            level_provider=self._overlay_level,
        )
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
        activation_mode = self._config.get("activation_mode", "hold")
        self._hotkey_listener = HotkeyListener(
            hotkey_str=hotkey,
            on_press=self._on_hotkey_trigger if activation_mode == "toggle"
            else self._on_hotkey_press,
            on_release=self._on_hotkey_release,
            on_cancel=self._cancel_recording,
            activation_mode=activation_mode,
        )
        self._hotkey_listener.start()

    def _on_hotkey_trigger(self) -> None:
        """Toggle activation: press to start, press again to stop.

        The state is read from the recorder rather than a flag of our own, so
        the MAX_RECORDING_DURATION auto-stop — which stops the recorder without
        the listener's knowledge — can never leave the next press reading as a
        'stop' when nothing is recording.
        """
        if self._recorder.is_recording:
            self._on_hotkey_release()
        else:
            self._on_hotkey_press()

    def _on_hotkey_press(self) -> None:
        if self._recorder.is_recording:
            # A recording is already running, so this press cannot be a start.
            # It is the user pressing the key again to get out of a recording
            # that did not stop when they let go.
            logger.info("Hotkey pressed while recording — cancelling")
            self._cancel_recording()
            return

        # Capture target window/app BEFORE showing overlay (otherwise overlay = foreground)
        self._target_is_desktop = self._injector.is_desktop_focused()
        self._target_app = self._app_detector.get_active_app()
        logger.info("Target app: %s, desktop: %s", self._target_app, self._target_is_desktop)

        self._recorder.start()
        self._recording_start_time = time.time()
        self._tray.set_state("recording")
        self._overlay.show_recording()

        self._max_record_timer = threading.Timer(MAX_RECORDING_DURATION, self._on_hotkey_release)
        self._max_record_timer.daemon = True
        self._max_record_timer.start()

    def _cancel_recording(self) -> None:
        """End a recording and throw the audio away.

        Used when a press was too short to mean anything, and when the user
        presses the key again to get out of a recording that is still running.
        Deliberately silent: there is nothing to confirm.
        """
        if self._max_record_timer:
            self._max_record_timer.cancel()
            self._max_record_timer = None

        if not self._recorder.is_recording:
            return

        try:
            self._recorder.stop()
        except Exception as e:
            logger.debug("Could not stop the recorder on cancel: %s", e)
        self._tray.set_state("idle")
        self._overlay.hide()
        logger.info("Recording cancelled")

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
                self._overlay.hide()
                self._tray.set_state("idle")
                return

            # Per-app profile switching (using captured app from press time)
            # One effective profile per dictation drives everything below: the
            # prompt, the raw check and the name recorded in history. Resolving
            # it once is what stops a per-app switch sticking to later dictations.
            profile_id, profile = self._resolve_profile(getattr(self, "_target_app", None))
            logger.info("Dictation using profile '%s'", profile_id)

            is_raw_profile = profile.get("prompt") == "__RAW__"

            if is_raw_profile or use_offline:
                # Skip LLM cleanup: use verbatim transcription
                cleaned_text = raw_text.strip()
            elif self._cleaner:
                self._cleaner.set_prompt(profile["prompt"])
                # The transcript is what the user said; cleanup is a polish
                # pass over it. A provider that retires a model, rate-limits
                # us or simply times out must cost the polish, not the words:
                # losing the whole dictation here reads to the user as the
                # microphone having failed, with no clue that it did not.
                try:
                    cleaned_text = self._cleaner.clean(raw_text)
                except Exception as e:
                    logger.error("Cleanup failed, using the raw transcript: %s", e)
                    cleaned_text = raw_text.strip()
            else:
                cleaned_text = raw_text.strip()

            # Save to history under the mode that actually ran
            self._history.add(
                raw_text, cleaned_text, language, duration,
                profile=profile.get("name", profile_id),
            )

            # Inject text
            result = self._injector.inject(cleaned_text)

            # Use captured target state (checked at hotkey press, before overlay)
            was_desktop = getattr(self, '_target_is_desktop', False)
            should_show_notice = (not result.pasted or was_desktop) and self._config.get("clipboard_notice", True)

            if should_show_notice:
                self._overlay.show_clipboard_notice()
            else:
                self._overlay.hide()

            self._tray.set_state("idle")

        except Exception as e:
            logger.error("Processing failed: %s", e, exc_info=True)
            self._tray.set_state("error")
            self._overlay.hide()
            threading.Timer(3.0, lambda: self._tray.set_state("idle")).start()

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

    def _watch_system_theme(self) -> None:
        """Re-apply the theme when Windows switches between light and dark.

        colorSchemeChanged arrived in Qt 6.5; if it isn't there the app simply
        keeps the theme it started with rather than failing to start.
        """
        try:
            from PyQt6.QtGui import QGuiApplication
            QGuiApplication.styleHints().colorSchemeChanged.connect(
                lambda _scheme: apply_theme(self._qapp)
            )
        except (AttributeError, TypeError) as e:
            logger.info("Live theme switching unavailable on this Qt build: %s", e)

    def _overlay_level(self) -> float:
        """Live microphone loudness for the recording display, 0.0 to 1.0.

        Read through self._recorder every time rather than bound once: settings
        changes replace the recorder, and a stale binding would animate from a
        closed stream.
        """
        recorder = getattr(self, "_recorder", None)
        if recorder is None:
            return 0.0
        try:
            return float(recorder.current_level())
        except Exception:
            return 0.0

    def _report_mic_fallback(self) -> None:
        """Warn when the chosen microphone is missing and another is in use.

        Falling back silently is what made a renumbered device look like a
        broken app, so a fallback is always visible: on the recording badge,
        where the user is looking while they talk, and in Settings. A
        microphone that is working is not announced anywhere.
        """
        active = getattr(self._recorder, "active_device_name", None)
        missing = getattr(self._recorder, "requested_device_missing", False)

        # Upgrading users have only a legacy device index. Record the name now
        # so the next device change can't silently move them to another mic.
        if not missing:
            try:
                self._config.backfill_mic_name(active)
            except Exception as e:
                logger.debug("Could not backfill mic name: %s", e)

        if not missing:
            # The badge is what the user looks at while they talk; naming a
            # working microphone there every time is noise. Clear it, in case
            # an earlier warning is still standing from a device that has
            # since come back.
            try:
                self._overlay.set_mic_text("")
            except Exception as e:
                logger.debug("Could not clear overlay mic text: %s", e)
            return

        wanted = self._config.get("mic_device_name") or "Saved microphone"
        using = active or "default microphone"
        logger.warning("Microphone %r not found; using %r", wanted, using)
        message = f"⚠ {wanted} not found — using {using}"

        try:
            self._overlay.set_mic_text(message)
        except Exception as e:
            logger.debug("Could not set overlay mic text: %s", e)

        try:
            self._settings_window.show_warning(message)
        except Exception as e:
            logger.debug("Could not show mic warning in settings: %s", e)

    def _resolve_profile(self, app_name: str | None) -> tuple[str, dict]:
        """Which dictation mode this utterance runs under."""
        return resolve_effective_profile(
            profiles=self._profiles.list_profiles(),
            active_id=self._config.get("active_profile", ProfileManager.DEFAULT_PROFILE_ID),
            app_profiles=self._config.get("app_profiles", {}) or {},
            auto_profile=self._config.get("auto_profile", False),
            app_name=app_name,
        )

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

        # Reinitialize recorder (close old stream first)
        try:
            self._recorder.close()
        except Exception:
            pass
        self._recorder = MicRecorder(
            device_name=self._config.get("mic_device_name", None),
            device_index=self._config.get("mic_device", None),
        )
        self._report_mic_fallback()

        # The chosen recording display may have changed.
        try:
            self._overlay.set_style(self._config.get("recording_style", DEFAULT_STYLE))
        except Exception as e:
            logger.warning("Could not switch recording display: %s", e)

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
        self._recorder.close()

        if self._hotkey_listener:
            self._hotkey_listener.stop()

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
        self._report_mic_fallback()
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
