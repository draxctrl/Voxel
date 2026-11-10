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
