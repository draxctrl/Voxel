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
