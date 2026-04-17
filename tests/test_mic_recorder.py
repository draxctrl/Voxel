import io
import struct
import wave
import pytest
from unittest.mock import MagicMock, patch, call

from src.mic_recorder import MicRecorder, SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH


class TestMicRecorder:
    def test_constants(self):
        assert SAMPLE_RATE == 16000
        assert CHANNELS == 1
        assert SAMPLE_WIDTH == 2

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_start_opens_stream(self, mock_pyaudio_cls):
        mock_pa = MagicMock()
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder()
        recorder.start()

        mock_pa.open.assert_called_once()
        call_kwargs = mock_pa.open.call_args.kwargs
        assert call_kwargs["rate"] == 16000
        assert call_kwargs["channels"] == 1

        recorder.stop()

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_stop_returns_wav_bytes(self, mock_pyaudio_cls):
        mock_pa = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"\x00" * (1024 * 2)
        mock_stream.is_active.return_value = True
        mock_pa.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder()
        recorder.start()
        recorder._frames = [b"\x00" * (1024 * 2)]
        audio_bytes = recorder.stop()

        assert audio_bytes is not None
        assert len(audio_bytes) > 0

        wav_file = wave.open(io.BytesIO(audio_bytes), "rb")
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 16000
        assert wav_file.getsampwidth() == 2

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_stop_without_start_returns_none(self, mock_pyaudio_cls):
        recorder = MicRecorder()
        result = recorder.stop()
        assert result is None

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_is_recording(self, mock_pyaudio_cls):
        mock_pa = MagicMock()
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder()
        assert recorder.is_recording is False
        recorder.start()
        assert recorder.is_recording is True
        recorder.stop()
        assert recorder.is_recording is False
