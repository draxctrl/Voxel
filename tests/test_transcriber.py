import io
import pytest
from unittest.mock import MagicMock, patch

from src.transcriber import Transcriber


class TestTranscriber:
    def test_transcribe_returns_text(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="Hello world")

        t = Transcriber(client=mock_client, model="whisper-large-v3")
        result = t.transcribe(b"fake-audio-bytes", language="en")
        assert result == "Hello world"

    def test_transcribe_passes_correct_params(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="test")

        t = Transcriber(client=mock_client, model="whisper-large-v3")
        t.transcribe(b"audio-data", language="es")

        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs["model"] == "whisper-large-v3"
        assert call_kwargs.kwargs["language"] == "es"

    def test_transcribe_returns_empty_string_on_empty_response(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="")

        t = Transcriber(client=mock_client, model="whisper-large-v3")
        result = t.transcribe(b"audio", language="en")
        assert result == ""

    def test_transcribe_raises_on_api_error(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("API error")

        t = Transcriber(client=mock_client, model="whisper-large-v3")
        with pytest.raises(Exception, match="API error"):
            t.transcribe(b"audio", language="en")
