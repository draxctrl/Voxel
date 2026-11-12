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
from src import taskbar_identity
from src.tray_app import TrayApp
from src.history import HistoryStore
from src.profiles import ProfileManager, resolve_effective_profile
from src.voice_commands import VoiceCommandProcessor
from src.app_detector import AppDetector
from src.ui_pyqt6.theme import load_fonts, apply_theme, current_palette
from src.ui_pyqt6.recording_overlay import RecordingOverlay
from src.ui_pyqt6.recording_styles import DEFAULT_STYLE
from src.ui_pyqt6.splash import SplashScreen
from src.ui_pyqt6.keys import pretty_hotkey
from src.ui_pyqt6.settings_window import SettingsWindow
from src.ui_pyqt6.panes import PaneContext

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
        # Before the application exists: Windows decides the taskbar
        # icon and the grouping from this, and once a window is up it
        # has already chosen. Without it Voxel wears the icon of
        # whatever launched it - the Python logo, run from source.
        taskbar_identity.claim()

        self._qapp = QApplication(sys.argv)
        self._qapp.setQuitOnLastWindowClosed(False)

        # Bundled Inter stands in for SF Pro, which can't be redistributed.
        # The stylesheet falls back to Segoe UI if this fails.
        assets_dir = _get_assets_dir()
        load_fonts(assets_dir)

        # The config comes first: the theme the user pinned lives in it, and
        # styling the application before reading it would always start in
        # whatever Windows is set to and ignore their choice.
        self._config = Config()
        self._config.load()

        # One stylesheet on the QApplication, so every window and every dialog
        # created later inherits it and a theme change restyles all of them.
        apply_theme(self._qapp, self._resolve_theme())
        self._watch_system_theme()

        # Set app icon globally
        ico_path = os.path.join(assets_dir, "icon.ico")
        if os.path.exists(ico_path):
            self._qapp.setWindowIcon(QIcon(ico_path))

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

        # UI - one window with a sidebar. History and Statistics are panes
        # in it, not windows of their own.
        self._settings_window: SettingsWindow | None = None
        self._build_settings_window()
        # The provider is a bound lambda rather than self._recorder.current_level,
        # because applying a microphone setting replaces the recorder: a bound
        # method would keep animating from the stream that was closed.
        self._overlay = RecordingOverlay(
            style=self._config.get("recording_style", DEFAULT_STYLE),
            level_provider=self._overlay_level,
        )
        # The splash names the user's own shortcut, not the default.
        self._splash = SplashScreen(
            shortcut=pretty_hotkey(self._config.get("hotkey", ""))
        )

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
        self._set_state("recording")
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
        self._set_state("idle")
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

        self._set_state("processing")
        self._overlay.show_processing()

        if duration < MIN_AUDIO_DURATION or not audio_bytes or rms < SILENCE_RMS_THRESHOLD:
            logger.debug("Recording skipped (duration=%.1fs, rms=%.0f)", duration, rms)
            self._set_state("idle")
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
                    self._set_state("error")
                    self._overlay.hide()
                    return
                raw_text = self._transcriber.transcribe(audio_bytes, language=language)

            if not raw_text or not raw_text.strip():
                logger.info("Empty transcript, skipping")
                self._set_state("idle")
                self._overlay.hide()
                return

            # Check voice commands FIRST
            expansion = self._voice_commands.match(raw_text)
            if expansion is not None:
                logger.info("Voice command matched: %s", raw_text.strip()[:50])
                result = self._injector.inject(expansion)
                self._history.add(raw_text, expansion, language or "auto", duration, profile="voice_command")
                self._overlay.hide()
                self._set_state("idle")
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

            self._set_state("idle")

        except Exception as e:
            logger.error("Processing failed: %s", e, exc_info=True)
            self._set_state("error")
            self._overlay.hide()
            threading.Timer(3.0, lambda: self._set_state("idle")).start()

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
                lambda _scheme: self._on_system_theme_changed()
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

        # The Microphone pane says this for itself, reading the same config
        # the recorder did, so there is nothing to push at the window here.

    def _resolve_profile(self, app_name: str | None) -> tuple[str, dict]:
        """Which dictation mode this utterance runs under."""
        return resolve_effective_profile(
            profiles=self._profiles.list_profiles(),
            active_id=self._config.get("active_profile", ProfileManager.DEFAULT_PROFILE_ID),
            app_profiles=self._config.get("app_profiles", {}) or {},
            auto_profile=self._config.get("auto_profile", False),
            app_name=app_name,
        )

    def _build_settings_window(self) -> None:
        """Create the settings window over a context of its own.

        `apply_setting` is the only route a pane has to the running app,
        which is what lets the window have no Save button.
        """
        self._settings_window = SettingsWindow(
            PaneContext(
                config=self._config,
                profiles=self._profiles,
                history=self._history,
                apply=self.apply_setting,
                palette=current_palette,
                recorder=self._recorder,
            )
        )

    def _show_settings(self) -> None:
        self._open_window_on("writing_style")

    def _show_stats(self) -> None:
        self._open_window_on("stats")

    def _show_history(self) -> None:
        self._open_window_on("history")

    def _open_window_on(self, pane_id: str) -> None:
        """Bring the window up with one pane showing."""
        if self._settings_window is None:
            self._build_settings_window()
        # The recorder is replaced whenever the microphone changes, so the
        # context is pointed at the current one before the pane reads it.
        self._settings_window.ctx.recorder = self._recorder
        self._settings_window.show_pane(pane_id)
        self._settings_window.show()

    def _set_state(self, state: str) -> None:
        """Tell both the tray and the window what Voxel is doing."""
        self._tray.set_state(state)
        # getattr, not an attribute read: recording can be driven before the
        # window exists, and the tray must still be told either way.
        window = getattr(self, "_settings_window", None)
        if window is not None:
            try:
                window.set_status(state)
            except Exception as e:
                logger.debug("Could not update the sidebar status: %s", e)

    # ------------------------------------------------------------------
    # Instant apply
    #
    # The settings window has no Save button, so a setting is written the
    # moment it is touched. Restarting everything on every toggle - which
    # is what _on_settings_saved does - would make the window unusable, so
    # each key knows the one subsystem it affects and nothing else moves.

    #: Settings that need the audio stream reopened.
    _MIC_KEYS = frozenset({"mic_device_name", "mic_device"})
    #: Settings the global hotkey listener is built from.
    _HOTKEY_KEYS = frozenset({"hotkey", "activation_mode"})
    #: Settings the text injector is built from.
    _INJECTOR_KEYS = frozenset({"mute_sound", "always_copy"})
    #: Settings that change which model or key the cleaner talks to.
    _CLEANER_KEYS = frozenset({"llm_model", "whisper_model", "api_key"})

    def apply_setting(self, key: str, value: object) -> None:
        """Write one setting and restart only what it affects.

        Every restart is guarded: a device that will not open, or a key
        that will not authenticate, must not throw away the choice the
        user just made - they would make it again and watch nothing
        happen.
        """
        self._config.set(key, value)
        self._config.save()
        logger.info("Applied setting %s", key)

        try:
            if key in self._MIC_KEYS:
                self._reopen_recorder()
            elif key in self._HOTKEY_KEYS:
                self._start_hotkey_listener()
            elif key in self._INJECTOR_KEYS:
                self._rebuild_injector()
            elif key in self._CLEANER_KEYS:
                started = self._init_groq()
                # A user who arrived with no API key never reached the
                # branch that starts the listener, so pressing the shortcut
                # did nothing until they restarted Voxel.
                if started and self._hotkey_listener is None:
                    self._start_hotkey_listener()
            elif key == "recording_style":
                self._overlay.set_style(value)
            elif key == "active_profile":
                if self._cleaner:
                    self._cleaner.set_prompt(self._profiles.get_active_prompt())
            elif key == "voice_commands":
                self._voice_commands.reload(value)
            elif key == "theme":
                apply_theme(self._qapp, self._resolve_theme())
                if self._settings_window is not None:
                    self._settings_window.restyle(current_palette())
        except Exception as e:
            logger.error("Setting '%s' was saved, but applying it failed: %s", key, e)

    def _reopen_recorder(self) -> None:
        """Close the current audio stream and open the chosen device."""
        try:
            self._recorder.close()
        except Exception:
            pass
        self._recorder = MicRecorder(
            device_name=self._config.get("mic_device_name", None),
            device_index=self._config.get("mic_device", None),
        )
        self._report_mic_fallback()

    def _rebuild_injector(self) -> None:
        assets_dir = _get_assets_dir()
        chime_path = os.path.join(assets_dir, "chime.wav")
        if self._config.get("mute_sound", False) or not os.path.exists(chime_path):
            chime_path = None
        self._injector = TextInjector(
            chime_path=chime_path,
            always_copy=self._config.get("always_copy", False),
        )

    def _on_system_theme_changed(self) -> None:
        """Windows switched light/dark.

        Follow it only if the user has not pinned a theme: dragging a
        pinned-Light window to dark at sunset is the bug, not the feature.
        """
        apply_theme(self._qapp, self._resolve_theme())
        if self._settings_window is not None:
            self._settings_window.restyle(current_palette())

    def _resolve_theme(self) -> str | None:
        """The theme to apply: the user's override, or None to follow Windows."""
        choice = self._config.get("theme", "system")
        return None if choice in (None, "", "system") else choice

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
        self._show_settings()

    def _startup_finish_no_key(self) -> None:
        """No API key yet: open on the pane that holds it.

        This is the whole of first-run behaviour for now - the same place
        the old window left a new user, in a window they can read.
        """
        self._splash.close_splash()
        # Choose the pane now and only delay the show, so what the user
        # lands on does not depend on a timer having fired.
        if self._settings_window is None:
            self._build_settings_window()
        self._settings_window.show_pane("general")
        QTimer.singleShot(100, self._settings_window.show)


def main():
    app = VoxelApp()
    app.run()


if __name__ == "__main__":
    main()
