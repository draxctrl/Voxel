"""Integration test: mock external APIs, verify full pipeline flow."""
from unittest.mock import MagicMock, patch
import pytest

from src.transcriber import Transcriber
from src.text_cleaner import TextCleaner
from src.text_injector import TextInjector


class TestFullPipeline:
    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_end_to_end_transcribe_clean_inject(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        """Simulate: audio bytes -> transcription -> cleanup -> paste."""
        mock_pyperclip.paste.return_value = ""

        mock_client = MagicMock()

        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="um so basically I think we should uh refactor the code"
        )

        mock_llm_response = MagicMock()
        mock_llm_response.choices = [
            MagicMock(message=MagicMock(content="I think we should refactor the code."))
        ]
        mock_client.chat.completions.create.return_value = mock_llm_response

        transcriber = Transcriber(client=mock_client, model="whisper-large-v3")
        cleaner = TextCleaner(client=mock_client, model="llama3-70b-8192")
        injector = TextInjector(chime_path=None)

        raw = transcriber.transcribe(b"fake-audio", language="en")
        assert "basically" in raw

        cleaned = cleaner.clean(raw)
        assert cleaned == "I think we should refactor the code."

        injector.inject(cleaned)
        mock_pyperclip.copy.assert_any_call("I think we should refactor the code.")
        mock_pyautogui.hotkey.assert_called_with("ctrl", "v")

    def test_empty_transcript_skipped(self):
        """If Whisper returns empty string, cleanup should not be called."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="")

        transcriber = Transcriber(client=mock_client, model="whisper-large-v3")
        raw = transcriber.transcribe(b"silence", language="en")

        assert raw == ""


class TestMicFallbackStillRecords:
    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_missing_requested_mic_still_records_and_flags_fallback(self, mock_pyaudio_cls):
        """A missing mic must warn but keep working, not block dictation."""
        from src.mic_recorder import MicRecorder

        devices = [("Realtek Mic", 1)]
        mock_pa = MagicMock()
        mock_pa.get_device_count.return_value = len(devices)
        mock_pa.get_device_info_by_index.side_effect = lambda i: {
            "index": i, "name": devices[i][0],
            "maxInputChannels": devices[i][1], "defaultSampleRate": 16000,
        }
        mock_pa.get_default_input_device_info.return_value = {
            "index": 0, "name": "Realtek Mic",
            "maxInputChannels": 1, "defaultSampleRate": 16000,
        }
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"\x00" * (512 * 2)
        mock_pa.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder(device_name="Blue Yeti")
        assert recorder.requested_device_missing is True
        assert recorder.active_device_name == "Realtek Mic"

        recorder.start()
        recorder._active_frames = [b"\x00" * (512 * 2)]
        audio = recorder.stop()
        recorder.close()

        assert audio is not None and len(audio) > 0


class TestUndoHotkeyRemoved:
    """The undo hotkey sent a blind Ctrl+Z to whatever had focus. It's gone."""

    def test_undo_hotkey_config_key_is_gone(self):
        from src.config import DEFAULT_CONFIG
        assert "undo_hotkey" not in DEFAULT_CONFIG

    def test_undo_handler_is_gone(self):
        from src.main import VoxelApp
        assert not hasattr(VoxelApp, "_on_undo_press")
        assert not hasattr(VoxelApp, "_start_undo_listener")


class TestToggleActivationState:
    """Toggle state is derived from the recorder, never mirrored in a flag.

    These drive the real VoxelApp._on_hotkey_trigger. An earlier version of
    this test reimplemented the logic and asserted against its own copy, so it
    would have passed even if the production code regressed.
    """

    class _FakeRecorder:
        def __init__(self):
            self.is_recording = False
            self.starts = 0

        def start(self):
            self.is_recording = True
            self.starts += 1

        def stop(self):
            self.is_recording = False
            return None

        def get_rms(self):
            return 0.0

    def _make_app(self):
        """A VoxelApp with only the collaborators the hotkey path touches."""
        import time
        from src.main import VoxelApp

        app = VoxelApp.__new__(VoxelApp)
        app._recorder = self._FakeRecorder()
        app._injector = MagicMock()
        app._injector.is_desktop_focused.return_value = False
        app._app_detector = MagicMock()
        app._app_detector.get_active_app.return_value = "code"
        app._tray = MagicMock()
        app._overlay = MagicMock()
        app._max_record_timer = None
        app._recording_start_time = time.time()
        return app

    def _cleanup(self, app):
        if getattr(app, "_max_record_timer", None) is not None:
            app._max_record_timer.cancel()

    def test_press_starts_then_press_stops(self):
        app = self._make_app()
        try:
            app._on_hotkey_trigger()
            assert app._recorder.is_recording is True
            app._on_hotkey_trigger()
            assert app._recorder.is_recording is False
            assert app._recorder.starts == 1
        finally:
            self._cleanup(app)

    def test_press_after_max_duration_autostop_starts_again(self):
        """The 2-minute cap stops the recorder behind the listener's back; the
        next press must START, not be swallowed as a 'stop'."""
        app = self._make_app()
        try:
            app._on_hotkey_trigger()          # user starts
            app._recorder.stop()              # MAX_RECORDING_DURATION fires
            assert app._recorder.is_recording is False

            app._on_hotkey_trigger()          # next press
            assert app._recorder.is_recording is True
            assert app._recorder.starts == 2
        finally:
            self._cleanup(app)


class TestActivationModeConfig:
    def test_defaults_to_hold(self):
        from src.config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["activation_mode"] == "hold"


class TestVoxelAppMethodsResolve:
    """Every self.<name>() call in main.py must resolve on VoxelApp.

    A removal that deletes a method but leaves its call sites passes import
    checks and every unit test, then aborts at runtime inside a Qt slot. That
    happened once; this makes it impossible to repeat quietly.
    """

    def test_every_self_call_in_main_resolves(self):
        import ast
        import inspect
        import src.main as main_mod
        from src.main import VoxelApp

        source = inspect.getsource(main_mod)
        tree = ast.parse(source)

        called = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                called.add(node.func.attr)

        missing = sorted(
            name for name in called
            if not hasattr(VoxelApp, name) and not name.startswith("__")
        )
        assert missing == [], f"main.py calls self.{missing} which VoxelApp does not define"
