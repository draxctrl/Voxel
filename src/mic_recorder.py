import io
import logging
import struct
import threading
import wave
from typing import Optional

import pyaudio

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_SIZE = 1024


class MicRecorder:
    def __init__(self, device_index: int | None = None) -> None:
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._frames: list[bytes] = []
        self._recording: bool = False
        self._record_thread: Optional[threading.Thread] = None
        self._device_index = device_index

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if self._recording:
            return

        self._frames = []
        self._recording = True

        self._pa = pyaudio.PyAudio()
        open_kwargs = dict(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        if self._device_index is not None:
            open_kwargs["input_device_index"] = self._device_index
        self._stream = self._pa.open(**open_kwargs)

        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        logger.info("Recording started")

    def _record_loop(self) -> None:
        while self._recording and self._stream is not None:
            stream = self._stream
            if not stream.is_active():
                break
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if isinstance(data, bytes):
                    self._frames.append(data)
                elif isinstance(data, bytearray):
                    self._frames.append(bytes(data))
            except Exception as e:
                logger.error("Recording error: %s", e)
                break

    def stop(self) -> Optional[bytes]:
        if not self._recording:
            return None

        self._recording = False

        if self._record_thread is not None:
            self._record_thread.join(timeout=2.0)

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

        if not self._frames:
            return None

        logger.info("Recording stopped, %d frames captured", len(self._frames))
        return self._frames_to_wav()

    def get_rms(self) -> float:
        """Calculate RMS volume of recorded audio. Returns 0.0 if no frames."""
        if not self._frames:
            return 0.0
        raw = b"".join(self._frames)
        count = len(raw) // 2
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", raw)
        mean_sq = sum(s * s for s in samples) / count
        return mean_sq ** 0.5

    def _frames_to_wav(self) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(self._frames))
        return buf.getvalue()
