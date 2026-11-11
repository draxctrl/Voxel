import io
import struct
import wave
import pytest
from unittest.mock import MagicMock, patch, call

from src.mic_recorder import (
    MicRecorder,
    TARGET_SAMPLE_RATE,
    CHANNELS,
    SAMPLE_WIDTH,
    find_input_device_by_name,
)


class TestMicRecorder:
    def test_constants(self):
        assert TARGET_SAMPLE_RATE == 16000
        assert CHANNELS == 1
        assert SAMPLE_WIDTH == 2

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_start_opens_stream(self, mock_pyaudio_cls):
        mock_pa = MagicMock()
        # Must be a real dict: int(MagicMock()) is 1, which would make
        # _find_supported_rate choose a 1 Hz stream.
        mock_pa.get_default_input_device_info.return_value = {
            "index": 0, "maxInputChannels": 1, "defaultSampleRate": 16000,
        }
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
        mock_pa.get_default_input_device_info.return_value = {
            "index": 0, "maxInputChannels": 1, "defaultSampleRate": 16000,
        }
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


class _FakePA:
    """Minimal stand-in for pyaudio.PyAudio for device-resolution tests."""

    def __init__(self, devices):
        # devices: list of (name, max_input_channels)
        self._devices = devices

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, index):
        entry = self._devices[index]
        name, channels = entry[0], entry[1]
        host_api = entry[2] if len(entry) > 2 else 0
        return {
            "index": index,
            "name": name,
            "maxInputChannels": channels,
            "defaultSampleRate": 16000,
            "hostApi": host_api,
        }


class TestFindInputDeviceByName:
    def test_finds_device_index_by_exact_name(self):
        pa = _FakePA([("Realtek Mic", 1), ("Blue Yeti", 1)])
        assert find_input_device_by_name(pa, "Blue Yeti") == 1

    def test_returns_none_when_name_absent(self):
        pa = _FakePA([("Realtek Mic", 1)])
        assert find_input_device_by_name(pa, "Blue Yeti") is None

    def test_ignores_output_only_devices(self):
        pa = _FakePA([("Speakers", 0), ("Blue Yeti", 1)])
        assert find_input_device_by_name(pa, "Speakers") is None

    def test_duplicate_names_resolve_to_lowest_index(self):
        pa = _FakePA([("USB Audio", 1), ("USB Audio", 1)])
        assert find_input_device_by_name(pa, "USB Audio") == 0

    def test_returns_none_for_empty_name(self):
        pa = _FakePA([("Blue Yeti", 1)])
        assert find_input_device_by_name(pa, "") is None


def _mock_pa_with_devices(devices, default_index=0):
    """MagicMock PyAudio exposing *devices* as [(name, channels), ...]."""
    fake = _FakePA(devices)
    mock_pa = MagicMock()
    mock_pa.get_device_count.side_effect = fake.get_device_count
    mock_pa.get_device_info_by_index.side_effect = fake.get_device_info_by_index
    mock_pa.get_default_input_device_info.return_value = fake.get_device_info_by_index(default_index)
    return mock_pa


class TestMicRecorderDeviceSelection:
    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_opens_device_matching_saved_name(self, mock_pyaudio_cls):
        mock_pa = _mock_pa_with_devices([("Realtek Mic", 1), ("Blue Yeti", 1)])
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder(device_name="Blue Yeti")

        assert recorder.active_device_name == "Blue Yeti"
        assert recorder.requested_device_missing is False
        assert mock_pa.open.call_args.kwargs["input_device_index"] == 1
        recorder.close()

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_name_wins_over_stale_index(self, mock_pyaudio_cls):
        # Saved index 0 is now Realtek; the saved name must still win.
        mock_pa = _mock_pa_with_devices([("Realtek Mic", 1), ("Blue Yeti", 1)])
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder(device_name="Blue Yeti", device_index=0)

        assert mock_pa.open.call_args.kwargs["input_device_index"] == 1
        recorder.close()

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_missing_name_falls_back_to_default_and_flags_it(self, mock_pyaudio_cls):
        mock_pa = _mock_pa_with_devices([("Realtek Mic", 1)])
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder(device_name="Blue Yeti")

        assert recorder.requested_device_missing is True
        assert recorder.active_device_name == "Realtek Mic"
        recorder.close()

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_no_saved_name_is_not_a_missing_device(self, mock_pyaudio_cls):
        mock_pa = _mock_pa_with_devices([("Realtek Mic", 1)])
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder()

        assert recorder.requested_device_missing is False
        recorder.close()

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_flag_survives_fallback_when_open_fails(self, mock_pyaudio_cls):
        # The device exists but the stream won't open; after falling back to the
        # default device the user must still be told their choice wasn't used.
        mock_pa = _mock_pa_with_devices([("Realtek Mic", 1), ("Blue Yeti", 1)])
        mock_pa.open.side_effect = [OSError("device busy"), MagicMock()]
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder(device_name="Blue Yeti")

        assert recorder.requested_device_missing is True
        recorder.close()


class TestHostApiScoping:
    """Windows lists the same physical mic under several host APIs.

    The settings list only shows WASAPI devices, so resolving a saved name must
    prefer the WASAPI copy rather than the MME one that happens to share a name.
    """

    def test_prefers_match_on_the_preferred_host_api(self):
        # index 0 = MME copy (host api 0), index 1 = WASAPI copy (host api 2)
        pa = _FakePA([("Blue Yeti", 1, 0), ("Blue Yeti", 1, 2)])
        assert find_input_device_by_name(pa, "Blue Yeti", preferred_host_api=2) == 1

    def test_falls_back_to_any_host_api_when_preferred_has_no_match(self):
        pa = _FakePA([("Blue Yeti", 1, 0)])
        assert find_input_device_by_name(pa, "Blue Yeti", preferred_host_api=2) == 0

    def test_without_preference_lowest_index_still_wins(self):
        pa = _FakePA([("Blue Yeti", 1, 0), ("Blue Yeti", 1, 2)])
        assert find_input_device_by_name(pa, "Blue Yeti") == 0


class TestCurrentLevel:
    """The recording animation is driven by this, 60 times a second."""

    def _recorder(self):
        """A MicRecorder with no stream — the level path needs no hardware."""
        from unittest.mock import patch
        from src.mic_recorder import MicRecorder
        with patch.object(MicRecorder, "_start_stream", lambda self: None):
            return MicRecorder()

    def _chunk(self, amplitude: int, samples: int = 512) -> bytes:
        import struct
        return struct.pack(f"<{samples}h", *([amplitude, -amplitude] * (samples // 2)))

    def test_silence_reads_zero(self):
        assert self._recorder().current_level() == 0.0

    def test_a_loud_chunk_reads_high(self):
        from src.mic_recorder import LEVEL_FULL_SCALE_RMS
        rec = self._recorder()
        rec._note_level(self._chunk(int(LEVEL_FULL_SCALE_RMS)))
        assert rec.current_level() > 0.8

    def test_a_quiet_chunk_reads_low(self):
        rec = self._recorder()
        rec._note_level(self._chunk(40))
        assert rec.current_level() < 0.1

    def test_the_level_is_clamped_to_one(self):
        rec = self._recorder()
        rec._note_level(self._chunk(32000))
        assert rec.current_level() <= 1.0

    def test_it_measures_only_the_newest_chunk(self):
        """get_rms() sums every buffered frame, so it gets slower the longer
        you talk. The display reads the level 60 times a second and must not
        grow more expensive as the recording runs."""
        import time
        rec = self._recorder()
        chunk = self._chunk(2000)

        rec.start()
        for _ in range(20):
            rec._note_level(chunk)
            rec._active_frames.append(chunk)
        t0 = time.perf_counter()
        for _ in range(200):
            rec.current_level()
        short = time.perf_counter() - t0

        for _ in range(4000):
            rec._active_frames.append(chunk)
        t0 = time.perf_counter()
        for _ in range(200):
            rec.current_level()
        long = time.perf_counter() - t0

        assert long < short * 5 + 0.01, (
            f"reading the level got {long / max(short, 1e-9):.1f}x slower "
            "as the recording grew"
        )

    def test_level_decays_rather_than_snapping_to_zero(self):
        """A display that snaps to zero between syllables flickers."""
        rec = self._recorder()
        rec._note_level(self._chunk(8000))
        loud = rec.current_level()
        rec._note_level(self._chunk(0))
        after = rec.current_level()
        assert 0 < after < loud

    def test_a_loud_chunk_takes_effect_immediately(self):
        """Fast attack: speech must not fade in over several frames."""
        rec = self._recorder()
        rec._note_level(self._chunk(0))
        rec._note_level(self._chunk(6000))
        assert rec.current_level() > 0.5

    def test_starting_a_recording_clears_the_previous_level(self):
        rec = self._recorder()
        rec._note_level(self._chunk(8000))
        rec.start()
        assert rec.current_level() == 0.0
