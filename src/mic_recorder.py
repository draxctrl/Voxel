import io
import logging
import struct
import threading
import wave
from collections import deque
from typing import Optional

import pyaudio

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000  # Whisper's preferred rate
FALLBACK_RATES = [16000, 44100, 48000, 22050, 32000, 8000]
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_SIZE = 512  # ~32ms @ 16kHz - small for low latency
# Keep this much audio BEFORE the hotkey press
# (compensates for human reaction time + stream startup latency)
PREROLL_SECONDS = 0.6

#: RMS treated as "as loud as the display goes". Ordinary speech into a
#: desktop microphone lands around 1500-4000 on a 16-bit scale; using full
#: scale (32768) would leave the display flat for everything but a shout.
LEVEL_FULL_SCALE_RMS = 4000.0
#: How much of the previous level survives a quiet chunk. Attack is instant so
#: speech registers at once; decay is gentle so the display does not flicker
#: between syllables.
LEVEL_DECAY = 0.82


def find_preferred_host_api(pa) -> int | None:
    """Index of the WASAPI host API, or None.

    The settings list is built from WASAPI because it carries full device
    names, so device lookup must use the same host API or a saved name can
    resolve to the MME copy of the same physical microphone.
    """
    try:
        for h in range(pa.get_host_api_count()):
            if "WASAPI" in pa.get_host_api_info_by_index(h).get("name", ""):
                return h
    except Exception:
        pass
    return None


def find_input_device_by_name(pa, name: str, preferred_host_api: int | None = None) -> int | None:
    """Return the index of the input device called *name*, or None.

    Device indices are not stable — they renumber whenever audio devices are
    added or removed — so the name is what we persist and this is how we turn
    it back into an index at open time.

    Windows exposes the same physical microphone under several host APIs, so a
    match on *preferred_host_api* wins. Failing that, the lowest matching index
    wins, which keeps resolution deterministic when devices genuinely share a
    name (two identical USB mics, say). Picking one and saying which device is
    in use beats refusing to record.
    """
    if not name:
        return None
    try:
        count = pa.get_device_count()
    except Exception:
        return None

    fallback: int | None = None
    for i in range(count):
        try:
            info = pa.get_device_info_by_index(i)
        except Exception:
            continue
        if info.get("maxInputChannels", 0) <= 0:
            continue
        if info.get("name") != name:
            continue

        index = int(info.get("index", i))
        if preferred_host_api is not None and info.get("hostApi") == preferred_host_api:
            return index
        if fallback is None:
            fallback = index

    return fallback


class MicRecorder:
    """Continuously captures audio into a ring buffer; freezes it on start() and
    keeps recording until stop(). This eliminates first-word cutoffs."""

    def __init__(self, device_name: str | None = None, device_index: int | None = None) -> None:
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._recording: bool = False
        self._active_frames: list[bytes] = []  # frames captured after start()
        self._preroll: deque = deque()  # rolling ring buffer of recent frames
        self._preroll_max_chunks: int = 20
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_running: bool = False
        self._device_name = device_name
        self._device_index = device_index
        self._active_device_name: str | None = None
        self._requested_device_missing: bool = False
        self._actual_rate: int = TARGET_SAMPLE_RATE
        #: Rolling loudness, 0..1, updated once per captured chunk. The UI
        #: reads it 60 times a second, so it must never depend on how long the
        #: recording has been running.
        self._level: float = 0.0
        self._lock = threading.Lock()
        # Try to start stream, but don't crash app if it fails
        try:
            self._start_stream()
        except Exception as e:
            logger.warning("Initial mic stream failed: %s. Will retry with default device.", e)
            # Fall back to default device, but remember that the chosen one
            # could not be opened so the UI can say so.
            if self._device_name is not None or self._device_index is not None:
                if self._device_name is not None:
                    self._requested_device_missing = True
                self._device_name = None
                self._device_index = None
                try:
                    self._start_stream()
                except Exception as e2:
                    logger.error("Default mic stream also failed: %s. Will retry on first record.", e2)

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def active_device_name(self) -> str | None:
        """Name of the device actually open, which may not be the one asked for."""
        return self._active_device_name

    @property
    def requested_device_missing(self) -> bool:
        """True when a device name was saved but no such device could be found."""
        return self._requested_device_missing

    def _resolve_device(self, pa: pyaudio.PyAudio) -> int | None:
        """Turn the saved name (preferred) or index into a live device index.

        Sets _requested_device_missing when a name was asked for and is gone, so
        callers can tell the user instead of silently recording from elsewhere.
        """
        if self._device_name:
            index = find_input_device_by_name(
                pa, self._device_name, preferred_host_api=find_preferred_host_api(pa)
            )
            if index is not None:
                self._requested_device_missing = False
                return index
            self._requested_device_missing = True
            logger.warning(
                "Saved microphone %r not found; falling back to the default device",
                self._device_name,
            )
            return None

        return self._device_index

    def _record_active_device(self, pa: pyaudio.PyAudio, index: int | None) -> None:
        """Remember the name of whatever device we actually opened."""
        try:
            info = pa.get_device_info_by_index(index) if index is not None \
                else pa.get_default_input_device_info()
            self._active_device_name = info.get("name")
        except Exception:
            self._active_device_name = None

    def _find_supported_rate(self, pa: pyaudio.PyAudio, device_index: int | None = None) -> int:
        try:
            if device_index is not None:
                info = pa.get_device_info_by_index(device_index)
            else:
                info = pa.get_default_input_device_info()
            default_rate = int(info.get("defaultSampleRate", 16000))
        except Exception:
            default_rate = 16000

        rates_to_try = [default_rate, TARGET_SAMPLE_RATE] + FALLBACK_RATES
        seen = set()
        unique_rates = [r for r in rates_to_try if not (r in seen or seen.add(r))]

        for rate in unique_rates:
            try:
                kwargs = dict(
                    input_format=pyaudio.paInt16,
                    input_channels=CHANNELS,
                )
                if device_index is not None:
                    kwargs["input_device"] = device_index
                if pa.is_format_supported(rate, **kwargs):
                    return rate
            except Exception:
                continue
        return default_rate

    def _start_stream(self) -> None:
        """Open the mic stream immediately and keep it running in the background.
        This way, when the user presses the hotkey, we already have 0.6s of audio ready."""
        try:
            self._pa = pyaudio.PyAudio()
            resolved_index = self._resolve_device(self._pa)
            self._actual_rate = self._find_supported_rate(self._pa, resolved_index)
            logger.info("Mic stream opening at %d Hz", self._actual_rate)

            open_kwargs = dict(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=self._actual_rate,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
            if resolved_index is not None:
                open_kwargs["input_device_index"] = resolved_index

            self._stream = self._pa.open(**open_kwargs)
            self._record_active_device(self._pa, resolved_index)

            # Size the preroll ring based on actual sample rate
            chunks_per_second = self._actual_rate / CHUNK_SIZE
            self._preroll_max_chunks = int(PREROLL_SECONDS * chunks_per_second)

            self._stream_running = True
            self._stream_thread = threading.Thread(target=self._continuous_loop, daemon=True)
            self._stream_thread.start()
            logger.info("Mic stream running (preroll: %.1fs = %d chunks)",
                       PREROLL_SECONDS, self._preroll_max_chunks)
        except Exception as e:
            logger.error("Failed to open mic stream: %s", e)
            self._cleanup_stream()
            raise

    def _continuous_loop(self) -> None:
        """Continuously read audio chunks into the preroll buffer (when idle)
        or into active frames (when recording)."""
        while self._stream_running and self._stream is not None:
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if not isinstance(data, bytes):
                    data = bytes(data)
                try:
                    self._note_level(data)
                except Exception as e:
                    # The level is cosmetic. A malformed chunk must cost one
                    # animation frame, never the capture loop: breaking out of
                    # here leaves the preroll empty and every later recording
                    # silent until the app is restarted.
                    logger.debug("Could not measure chunk level: %s", e)
                with self._lock:
                    if self._recording:
                        self._active_frames.append(data)
                    else:
                        self._preroll.append(data)
                        while len(self._preroll) > self._preroll_max_chunks:
                            self._preroll.popleft()
            except Exception as e:
                if self._stream_running:
                    logger.error("Stream read error: %s", e)
                break

    def start(self) -> None:
        """Mark recording as active. The preroll buffer is already capturing."""
        if self._recording:
            return

        # If the stream failed to open during init, retry now
        if self._stream is None or not self._stream_running:
            logger.info("Stream not running, attempting to open now")
            try:
                self._start_stream()
            except Exception as e:
                logger.error("Failed to open mic stream on demand: %s", e)
                return

        with self._lock:
            # Seed active frames with the preroll buffer so no words are lost
            self._active_frames = list(self._preroll)
            self._recording = True
            # Otherwise the display opens showing the loudness of whatever was
            # happening in the room before the hotkey was pressed.
            self._level = 0.0
        logger.info("Recording started (with %d preroll chunks)", len(self._active_frames))

    def stop(self) -> Optional[bytes]:
        """Stop recording and return the captured WAV bytes."""
        if not self._recording:
            return None

        with self._lock:
            self._recording = False
            frames = list(self._active_frames)
            self._active_frames = []

        if not frames:
            return None

        logger.info("Recording stopped, %d frames captured", len(frames))
        return self._frames_to_wav(frames)

    def close(self) -> None:
        """Shut down the mic stream entirely (call on app quit)."""
        self._stream_running = False
        self._recording = False
        if self._stream_thread is not None:
            self._stream_thread.join(timeout=1.0)
            self._stream_thread = None
        self._cleanup_stream()

    def _cleanup_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def _note_level(self, chunk: bytes) -> None:
        """Fold one freshly captured chunk into the rolling level.

        Only this chunk is measured, so the cost is fixed however long the
        recording runs - unlike get_rms(), which re-sums the whole buffer.
        """
        count = len(chunk) // 2
        if count == 0:
            return
        # An odd trailing byte would make unpack reject the whole buffer.
        samples = struct.unpack_from(f"<{count}h", chunk)
        rms = (sum(s * s for s in samples) / count) ** 0.5
        new = min(1.0, rms / LEVEL_FULL_SCALE_RMS)
        with self._lock:
            # Fast attack, slow decay.
            self._level = max(new, self._level * LEVEL_DECAY)

    def current_level(self) -> float:
        """Loudness right now, 0.0 to 1.0. Cheap enough to poll at 60fps."""
        with self._lock:
            return self._level

    def get_rms(self) -> float:
        """Calculate RMS volume of recorded audio. Returns 0.0 if no frames."""
        with self._lock:
            if not self._active_frames:
                return 0.0
            raw = b"".join(self._active_frames)
        count = len(raw) // 2
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", raw)
        mean_sq = sum(s * s for s in samples) / count
        return mean_sq ** 0.5

    def _frames_to_wav(self, frames: list[bytes]) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(self._actual_rate)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()
