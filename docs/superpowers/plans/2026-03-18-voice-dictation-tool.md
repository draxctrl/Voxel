# Voxel Voice Dictation Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows system-tray voice dictation app that records speech on hotkey hold, transcribes via Groq Whisper, cleans up via Groq Llama 3, and pastes polished text into the focused application.

**Architecture:** Hold-to-talk pipeline: pynput hotkey listener → pyaudio mic capture → Groq Whisper transcription → Groq Llama 3 cleanup → clipboard paste via pyautogui. Runs as a system tray app with four threads (main/UI, hotkey, tray, worker). Communication via thread-safe queues.

**Tech Stack:** Python 3.11+, Groq SDK, PyAudio, pynput, pyautogui, pyperclip, pystray, Pillow, CustomTkinter, PyInstaller

**Spec:** `docs/specs/2026-03-18-voice-dictation-tool-design.md`

---

## File Structure

```
Voxel/
├── src/
│   ├── main.py              # Entry point — wires all components, starts threads
│   ├── config.py             # Config loading/saving to %APPDATA%\Voxel\config.json
│   ├── mic_recorder.py       # Audio capture from microphone into WAV buffer
│   ├── transcriber.py        # Groq Whisper API integration
│   ├── text_cleaner.py       # Groq Llama 3 text cleanup
│   ├── text_injector.py      # Clipboard paste into focused app + clipboard restore
│   ├── hotkey_listener.py    # Global hotkey detection via pynput
│   ├── tray_app.py           # System tray icon and menu via pystray
│   ├── settings_ui.py        # Settings window via CustomTkinter
│   └── assets/
│       ├── icon_idle.png
│       ├── icon_recording.png
│       ├── icon_processing.png
│       └── chime.wav
├── tests/
│   ├── test_config.py
│   ├── test_mic_recorder.py
│   ├── test_transcriber.py
│   ├── test_text_cleaner.py
│   ├── test_text_injector.py
│   ├── test_hotkey_listener.py
│   └── test_pipeline.py      # Integration test for the full pipeline
├── requirements.txt
└── build.spec
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `src/assets/` (directory)

- [ ] **Step 1: Create requirements.txt**

```
groq
pyaudio
pynput
pyautogui
pyperclip
pystray
Pillow
customtkinter
pyinstaller
```

- [ ] **Step 2: Create package init files and assets directory**

Create empty `src/__init__.py` and `tests/__init__.py`.
Create `src/assets/` directory.

- [ ] **Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 4: Create placeholder asset files**

Create simple colored 64x64 PNG icons for the three tray states using Pillow:

```python
# generate_assets.py (run once, then delete)
from PIL import Image

for name, color in [("icon_idle", (128, 128, 128)), ("icon_recording", (0, 200, 0)), ("icon_processing", (255, 200, 0))]:
    img = Image.new("RGBA", (64, 64), color + (255,))
    img.save(f"src/assets/{name}.png")
```

For `chime.wav`, generate a short sine-wave beep:

```python
import struct, wave, math

with wave.open("src/assets/chime.wav", "w") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(44100)
    frames = b"".join(
        struct.pack("<h", int(16000 * math.sin(2 * math.pi * 880 * i / 44100)))
        for i in range(int(44100 * 0.15))
    )
    f.writeframes(frames)
```

- [ ] **Step 5: Commit**

```bash
git init
git add requirements.txt src/__init__.py tests/__init__.py src/assets/
git commit -m "chore: scaffold project structure with dependencies and placeholder assets"
```

---

## Task 2: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config**

```python
# tests/test_config.py
import json
import os
import pytest
from unittest.mock import patch

from src.config import Config, DEFAULT_CONFIG


class TestConfig:
    def test_default_config_has_required_keys(self):
        assert "api_key" in DEFAULT_CONFIG
        assert "hotkey" in DEFAULT_CONFIG
        assert "language" in DEFAULT_CONFIG
        assert "auto_start" in DEFAULT_CONFIG
        assert "whisper_model" in DEFAULT_CONFIG
        assert "llm_model" in DEFAULT_CONFIG

    def test_default_values(self):
        assert DEFAULT_CONFIG["api_key"] == ""
        assert DEFAULT_CONFIG["hotkey"] == "<ctrl>+<shift>+space"
        assert DEFAULT_CONFIG["language"] == "en"
        assert DEFAULT_CONFIG["auto_start"] is False
        assert DEFAULT_CONFIG["whisper_model"] == "whisper-large-v3"
        assert DEFAULT_CONFIG["llm_model"] == "llama3-70b-8192"

    def test_load_creates_default_if_missing(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = Config(config_path=str(config_path))
        cfg.load()
        assert cfg.get("api_key") == ""
        assert cfg.get("hotkey") == "<ctrl>+<shift>+space"

    def test_save_and_load_roundtrip(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = Config(config_path=str(config_path))
        cfg.load()
        cfg.set("api_key", "test-key-123")
        cfg.save()

        cfg2 = Config(config_path=str(config_path))
        cfg2.load()
        assert cfg2.get("api_key") == "test-key-123"

    def test_set_updates_value(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = Config(config_path=str(config_path))
        cfg.load()
        cfg.set("language", "es")
        assert cfg.get("language") == "es"

    def test_load_preserves_unknown_keys(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"api_key": "k", "custom_field": "val"}))
        cfg = Config(config_path=str(config_path))
        cfg.load()
        assert cfg.get("custom_field") == "val"
        # defaults are filled in
        assert cfg.get("hotkey") == "<ctrl>+<shift>+space"

    def test_load_handles_corrupt_file(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json{{{")
        cfg = Config(config_path=str(config_path))
        cfg.load()
        # falls back to defaults
        assert cfg.get("api_key") == ""

    def test_is_configured_false_without_api_key(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = Config(config_path=str(config_path))
        cfg.load()
        assert cfg.is_configured() is False

    def test_is_configured_true_with_api_key(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = Config(config_path=str(config_path))
        cfg.load()
        cfg.set("api_key", "gsk_abc123")
        assert cfg.is_configured() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Implement config module**

```python
# src/config.py
import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "api_key": "",
    "hotkey": "<ctrl>+<shift>+space",
    "language": "en",
    "auto_start": False,
    "whisper_model": "whisper-large-v3",
    "llm_model": "llama3-70b-8192",
}


def _default_config_path() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "Voxel", "config.json")


class Config:
    def __init__(self, config_path: str | None = None):
        self._path = config_path or _default_config_path()
        self._data: dict = {}

    def load(self) -> None:
        self._data = dict(DEFAULT_CONFIG)
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    self._data.update(saved)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load config from %s: %s", self._path, e)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def is_configured(self) -> bool:
        return bool(self._data.get("api_key"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config module with load/save/defaults"
```

---

## Task 3: Transcriber Module (Groq Whisper)

**Files:**
- Create: `src/transcriber.py`
- Create: `tests/test_transcriber.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transcriber.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_transcriber.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement transcriber**

```python
# src/transcriber.py
import io
import logging

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, client, model: str = "whisper-large-v3"):
        self._client = client
        self._model = model

    def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        logger.info("Sending %d bytes to Whisper API (model=%s, lang=%s)",
                     len(audio_bytes), self._model, language)

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.wav"

        response = self._client.audio.transcriptions.create(
            file=audio_file,
            model=self._model,
            language=language,
            response_format="text",
        )

        text = response.text if hasattr(response, "text") else str(response)
        logger.info("Whisper returned: %s", text[:100])
        return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_transcriber.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/transcriber.py tests/test_transcriber.py
git commit -m "feat: add transcriber module for Groq Whisper API"
```

---

## Task 4: Text Cleaner Module (Groq Llama 3)

**Files:**
- Create: `src/text_cleaner.py`
- Create: `tests/test_text_cleaner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_text_cleaner.py
import pytest
from unittest.mock import MagicMock

from src.text_cleaner import TextCleaner, CLEANUP_PROMPT_TEMPLATE


class TestTextCleaner:
    def test_cleanup_prompt_contains_placeholder(self):
        assert "{raw_transcript}" in CLEANUP_PROMPT_TEMPLATE

    def test_clean_returns_cleaned_text(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello world."))]
        mock_client.chat.completions.create.return_value = mock_response

        cleaner = TextCleaner(client=mock_client, model="llama3-70b-8192")
        result = cleaner.clean("uh hello world um")
        assert result == "Hello world."

    def test_clean_passes_correct_model(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="cleaned"))]
        mock_client.chat.completions.create.return_value = mock_response

        cleaner = TextCleaner(client=mock_client, model="llama3-70b-8192")
        cleaner.clean("raw text")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama3-70b-8192"

    def test_clean_includes_raw_transcript_in_prompt(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="cleaned"))]
        mock_client.chat.completions.create.return_value = mock_response

        cleaner = TextCleaner(client=mock_client, model="llama3-70b-8192")
        cleaner.clean("my specific dictation")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msg = call_kwargs["messages"][-1]["content"]
        assert "my specific dictation" in user_msg

    def test_clean_strips_whitespace(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="  cleaned text  \n"))]
        mock_client.chat.completions.create.return_value = mock_response

        cleaner = TextCleaner(client=mock_client, model="llama3-70b-8192")
        result = cleaner.clean("raw")
        assert result == "cleaned text"

    def test_clean_raises_on_api_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit")

        cleaner = TextCleaner(client=mock_client, model="llama3-70b-8192")
        with pytest.raises(Exception, match="Rate limit"):
            cleaner.clean("text")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_text_cleaner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement text cleaner**

```python
# src/text_cleaner.py
import logging

logger = logging.getLogger(__name__)

CLEANUP_PROMPT_TEMPLATE = """You are a dictation cleanup assistant. The user dictated the following text using voice.
Clean it up by:
- Removing filler words (um, uh, like, you know, basically, actually)
- Fixing grammar, spelling, and punctuation
- Keeping the original meaning and tone intact
- Keeping it natural — do not make it overly formal or robotic
- Do NOT add any commentary, explanation, or formatting — return ONLY the cleaned text

Dictated text: "{raw_transcript}" """


class TextCleaner:
    def __init__(self, client, model: str = "llama3-70b-8192"):
        self._client = client
        self._model = model

    def clean(self, raw_transcript: str) -> str:
        logger.info("Sending transcript to LLM for cleanup (model=%s)", self._model)

        prompt = CLEANUP_PROMPT_TEMPLATE.format(raw_transcript=raw_transcript)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )

        cleaned = response.choices[0].message.content.strip()
        logger.info("LLM cleanup result: %s", cleaned[:100])
        return cleaned
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_text_cleaner.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/text_cleaner.py tests/test_text_cleaner.py
git commit -m "feat: add text cleaner module for Groq Llama 3 cleanup"
```

---

## Task 5: Text Injector Module

**Files:**
- Create: `src/text_injector.py`
- Create: `tests/test_text_injector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_text_injector.py
import pytest
from unittest.mock import patch, MagicMock, call

from src.text_injector import TextInjector


class TestTextInjector:
    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_pastes_text(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = "old clipboard"

        injector = TextInjector(chime_path=None)
        injector.inject("Hello world")

        mock_pyperclip.copy.assert_any_call("Hello world")
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "v")

    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_restores_clipboard(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = "original content"

        injector = TextInjector(chime_path=None)
        injector.inject("new text")

        # Last call to copy should restore original clipboard
        copy_calls = mock_pyperclip.copy.call_args_list
        assert copy_calls[-1] == call("original content")

    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_handles_empty_clipboard(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = ""

        injector = TextInjector(chime_path=None)
        injector.inject("text")

        # Should not raise
        mock_pyautogui.hotkey.assert_called_once()

    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_plays_chime_when_path_given(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = ""

        injector = TextInjector(chime_path="assets/chime.wav")
        injector.inject("text")

        mock_winsound.PlaySound.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_text_injector.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement text injector**

```python
# src/text_injector.py
import logging
import time

import pyautogui
import pyperclip

try:
    import winsound
except ImportError:
    winsound = None

logger = logging.getLogger(__name__)

# Small delay to let clipboard operations complete
_PASTE_DELAY = 0.05
_RESTORE_DELAY = 0.1


class TextInjector:
    def __init__(self, chime_path: str | None = None):
        self._chime_path = chime_path

    def inject(self, text: str) -> None:
        logger.info("Injecting %d chars into focused app", len(text))

        # Save current clipboard
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

        # Play chime
        if self._chime_path and winsound:
            try:
                winsound.PlaySound(self._chime_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                logger.warning("Failed to play chime: %s", e)

        # Copy text and paste
        pyperclip.copy(text)
        time.sleep(_PASTE_DELAY)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(_RESTORE_DELAY)

        # Restore clipboard
        try:
            pyperclip.copy(old_clipboard)
        except Exception as e:
            logger.warning("Failed to restore clipboard: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_text_injector.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/text_injector.py tests/test_text_injector.py
git commit -m "feat: add text injector with clipboard paste and restore"
```

---

## Task 6: Mic Recorder Module

**Files:**
- Create: `src/mic_recorder.py`
- Create: `tests/test_mic_recorder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mic_recorder.py
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
        assert SAMPLE_WIDTH == 2  # 16-bit PCM

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

        recorder.stop()  # cleanup

    @patch("src.mic_recorder.pyaudio.PyAudio")
    def test_stop_returns_wav_bytes(self, mock_pyaudio_cls):
        mock_pa = MagicMock()
        mock_stream = MagicMock()
        # Simulate one chunk of audio data (1024 frames of silence)
        mock_stream.read.return_value = b"\x00" * (1024 * 2)
        mock_stream.is_active.return_value = True
        mock_pa.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pa

        recorder = MicRecorder()
        recorder.start()
        # Simulate having captured some frames
        recorder._frames = [b"\x00" * (1024 * 2)]
        audio_bytes = recorder.stop()

        assert audio_bytes is not None
        assert len(audio_bytes) > 0

        # Verify it's valid WAV
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mic_recorder.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement mic recorder**

```python
# src/mic_recorder.py
import io
import logging
import threading
import wave

import pyaudio

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM
CHUNK_SIZE = 1024


class MicRecorder:
    def __init__(self):
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._frames: list[bytes] = []
        self._recording = False
        self._record_thread: threading.Thread | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if self._recording:
            return

        self._frames = []
        self._recording = True

        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        logger.info("Recording started")

    def _record_loop(self) -> None:
        while self._recording and self._stream and self._stream.is_active():
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._frames.append(data)
            except Exception as e:
                logger.error("Recording error: %s", e)
                break

    def stop(self) -> bytes | None:
        if not self._recording:
            return None

        self._recording = False

        if self._record_thread:
            self._record_thread.join(timeout=2.0)

        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._pa:
            self._pa.terminate()
            self._pa = None

        if not self._frames:
            return None

        logger.info("Recording stopped, %d frames captured", len(self._frames))
        return self._frames_to_wav()

    def _frames_to_wav(self) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(self._frames))
        return buf.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mic_recorder.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mic_recorder.py tests/test_mic_recorder.py
git commit -m "feat: add mic recorder with PyAudio capture to WAV"
```

---

## Task 7: Hotkey Listener Module

**Files:**
- Create: `src/hotkey_listener.py`
- Create: `tests/test_hotkey_listener.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hotkey_listener.py
import time
import pytest
from unittest.mock import MagicMock, patch

from src.hotkey_listener import HotkeyListener


class TestHotkeyListener:
    def test_parses_hotkey_string(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(),
            on_release=MagicMock(),
        )
        assert listener._modifier_keys == {"ctrl_l", "ctrl_r", "shift", "shift_r"}
        assert listener._trigger_key is not None

    def test_min_hold_duration_default(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(),
            on_release=MagicMock(),
        )
        assert listener._min_hold_duration == 0.3

    def test_tap_too_short_does_not_trigger(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press,
            on_release=on_release,
            min_hold_duration=0.3,
        )

        # Simulate press then immediate release (< 300ms)
        listener._handle_press()
        listener._press_time = time.time() - 0.1  # pretend it was 100ms ago
        listener._handle_release()

        on_press.assert_called_once()
        # on_release should NOT be called for taps
        on_release.assert_not_called()

    def test_hold_long_enough_triggers_release(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press,
            on_release=on_release,
            min_hold_duration=0.3,
        )

        listener._handle_press()
        listener._press_time = time.time() - 0.5  # pretend 500ms hold
        listener._handle_release()

        on_press.assert_called_once()
        on_release.assert_called_once()

    def test_ignores_repeated_press_events(self):
        on_press = MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press,
            on_release=MagicMock(),
        )

        listener._handle_press()
        listener._handle_press()  # key repeat
        listener._handle_press()  # key repeat

        on_press.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hotkey_listener.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement hotkey listener**

```python
# src/hotkey_listener.py
import logging
import time
import threading
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)

# Maps hotkey string tokens to pynput key names
_MODIFIER_MAP = {
    "<ctrl>": ("ctrl_l", "ctrl_r"),
    "<shift>": ("shift", "shift_r"),
    "<alt>": ("alt_l", "alt_r"),
}


def _parse_hotkey(hotkey_str: str):
    """Parse hotkey string like '<ctrl>+<shift>+space' into modifier keys and trigger key."""
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    modifiers = set()
    trigger = None

    for part in parts:
        if part in _MODIFIER_MAP:
            modifiers.update(_MODIFIER_MAP[part])
        else:
            # It's the trigger key
            try:
                trigger = keyboard.Key[part] if hasattr(keyboard.Key, part) else keyboard.KeyCode.from_char(part)
            except (KeyError, ValueError):
                trigger = keyboard.KeyCode.from_char(part)

    return modifiers, trigger


class HotkeyListener:
    def __init__(
        self,
        hotkey_str: str,
        on_press: Callable,
        on_release: Callable,
        min_hold_duration: float = 0.3,
    ):
        self._on_press_cb = on_press
        self._on_release_cb = on_release
        self._min_hold_duration = min_hold_duration

        self._modifier_keys, self._trigger_key = _parse_hotkey(hotkey_str)
        self._pressed_modifiers: set[str] = set()
        self._is_held = False
        self._press_time: float = 0.0
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey listener started")

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("Hotkey listener stopped")

    def _key_name(self, key) -> str | None:
        if hasattr(key, "name"):
            return key.name
        return None

    def _on_key_press(self, key) -> None:
        name = self._key_name(key)
        if name and name in self._modifier_keys:
            self._pressed_modifiers.add(name)

        if key == self._trigger_key and self._modifiers_active():
            self._handle_press()

    def _on_key_release(self, key) -> None:
        name = self._key_name(key)
        if name and name in self._modifier_keys:
            self._pressed_modifiers.discard(name)

        if key == self._trigger_key:
            self._handle_release()

    def _modifiers_active(self) -> bool:
        # For each modifier group (ctrl, shift, alt), at least one variant must be pressed
        for token, variants in _MODIFIER_MAP.items():
            needed = set(variants) & self._modifier_keys
            if needed and not (needed & self._pressed_modifiers):
                return False
        return True

    def _handle_press(self) -> None:
        if self._is_held:
            return  # Filter OS key-repeat
        self._is_held = True
        self._press_time = time.time()
        logger.info("Hotkey pressed")
        self._on_press_cb()

    def _handle_release(self) -> None:
        if not self._is_held:
            return
        self._is_held = False

        hold_duration = time.time() - self._press_time
        if hold_duration < self._min_hold_duration:
            logger.debug("Tap ignored (%.0fms < %dms)",
                         hold_duration * 1000, self._min_hold_duration * 1000)
            return

        logger.info("Hotkey released after %.0fms", hold_duration * 1000)
        self._on_release_cb()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hotkey_listener.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hotkey_listener.py tests/test_hotkey_listener.py
git commit -m "feat: add hotkey listener with hold-to-talk and tap filtering"
```

---

## Task 8: System Tray App

**Files:**
- Create: `src/tray_app.py`

- [ ] **Step 1: Implement tray app**

No unit tests for this module — it wraps pystray which requires a running desktop environment. Tested via manual integration testing.

```python
# src/tray_app.py
import logging
import os
import threading
from typing import Callable

from PIL import Image
import pystray

logger = logging.getLogger(__name__)


class TrayApp:
    """System tray icon with state management."""

    STATES = ("idle", "recording", "processing", "error")

    def __init__(
        self,
        assets_dir: str,
        on_settings: Callable,
        on_quit: Callable,
    ):
        self._assets_dir = assets_dir
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._icons: dict[str, Image.Image] = {}
        self._load_icons()

    def _load_icons(self) -> None:
        icon_map = {
            "idle": "icon_idle.png",
            "recording": "icon_recording.png",
            "processing": "icon_processing.png",
        }
        for state, filename in icon_map.items():
            path = os.path.join(self._assets_dir, filename)
            try:
                self._icons[state] = Image.open(path)
            except Exception as e:
                logger.warning("Failed to load icon %s: %s", path, e)
                self._icons[state] = Image.new("RGBA", (64, 64), (128, 128, 128, 255))

        # Error state uses a red icon
        self._icons["error"] = Image.new("RGBA", (64, 64), (255, 0, 0, 255))

    def start(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Settings", lambda: self._on_settings()),
            pystray.MenuItem("Quit", lambda: self._on_quit()),
        )
        self._icon = pystray.Icon(
            "Voxel",
            self._icons["idle"],
            "Voxel",
            menu,
        )
        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()
        logger.info("Tray app started")

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
            self._icon = None

    def set_state(self, state: str) -> None:
        if state not in self.STATES:
            logger.warning("Unknown tray state: %s", state)
            return
        if self._icon:
            self._icon.icon = self._icons[state]
            tooltip = {
                "idle": "Voxel — Ready",
                "recording": "Voxel — Recording...",
                "processing": "Voxel — Processing...",
                "error": "Voxel — Error",
            }
            self._icon.title = tooltip.get(state, "Voxel")
```

- [ ] **Step 2: Commit**

```bash
git add src/tray_app.py
git commit -m "feat: add system tray app with state icons and menu"
```

---

## Task 9: Settings UI

**Files:**
- Create: `src/settings_ui.py`

- [ ] **Step 1: Implement settings window**

No unit tests — UI module tested manually. Relies on CustomTkinter.

```python
# src/settings_ui.py
import logging
import threading
from typing import Callable

import customtkinter as ctk

logger = logging.getLogger(__name__)


class SettingsWindow:
    """Settings dialog built with CustomTkinter."""

    def __init__(self, config, on_save: Callable, on_validate_key: Callable | None = None):
        self._config = config
        self._on_save = on_save
        self._on_validate_key = on_validate_key
        self._window: ctk.CTkToplevel | None = None

    def show(self, root: ctk.CTk) -> None:
        if self._window and self._window.winfo_exists():
            self._window.focus()
            return

        self._window = ctk.CTkToplevel(root)
        self._window.title("Voxel Settings")
        self._window.geometry("450x400")
        self._window.resizable(False, False)

        # API Key
        ctk.CTkLabel(self._window, text="Groq API Key:").pack(pady=(20, 5), padx=20, anchor="w")
        self._api_key_var = ctk.StringVar(value=self._config.get("api_key", ""))
        api_entry = ctk.CTkEntry(self._window, textvariable=self._api_key_var, show="*", width=400)
        api_entry.pack(padx=20)

        # Validate button
        self._status_label = ctk.CTkLabel(self._window, text="")
        if self._on_validate_key:
            validate_btn = ctk.CTkButton(
                self._window, text="Validate Key", width=120,
                command=self._validate_key,
            )
            validate_btn.pack(pady=(5, 0), padx=20, anchor="w")
            self._status_label.pack(pady=(2, 0), padx=20, anchor="w")

        # Language
        ctk.CTkLabel(self._window, text="Language:").pack(pady=(15, 5), padx=20, anchor="w")
        self._lang_var = ctk.StringVar(value=self._config.get("language", "en"))
        lang_menu = ctk.CTkOptionMenu(
            self._window, variable=self._lang_var,
            values=["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"],
        )
        lang_menu.pack(padx=20, anchor="w")

        # Hotkey
        ctk.CTkLabel(self._window, text="Hotkey:").pack(pady=(15, 5), padx=20, anchor="w")
        self._hotkey_var = ctk.StringVar(value=self._config.get("hotkey", "<ctrl>+<shift>+space"))
        hotkey_entry = ctk.CTkEntry(self._window, textvariable=self._hotkey_var, width=400)
        hotkey_entry.pack(padx=20)

        # Auto-start
        self._autostart_var = ctk.BooleanVar(value=self._config.get("auto_start", False))
        autostart_cb = ctk.CTkCheckBox(self._window, text="Start with Windows", variable=self._autostart_var)
        autostart_cb.pack(pady=(15, 5), padx=20, anchor="w")

        # Save button
        save_btn = ctk.CTkButton(self._window, text="Save", command=self._save)
        save_btn.pack(pady=20)

    def _save(self) -> None:
        self._config.set("api_key", self._api_key_var.get().strip())
        self._config.set("language", self._lang_var.get())
        self._config.set("hotkey", self._hotkey_var.get().strip())
        self._config.set("auto_start", self._autostart_var.get())
        self._config.save()
        self._on_save()
        if self._window:
            self._window.destroy()
            self._window = None

    def _validate_key(self) -> None:
        if not self._on_validate_key:
            return
        key = self._api_key_var.get().strip()
        if not key:
            self._status_label.configure(text="Please enter an API key", text_color="orange")
            return

        self._status_label.configure(text="Validating...", text_color="gray")

        def _check():
            try:
                ok = self._on_validate_key(key)
                if ok:
                    self._status_label.configure(text="Valid!", text_color="green")
                else:
                    self._status_label.configure(text="Invalid key", text_color="red")
            except Exception as e:
                self._status_label.configure(text=f"Error: {e}", text_color="red")

        threading.Thread(target=_check, daemon=True).start()
```

- [ ] **Step 2: Commit**

```bash
git add src/settings_ui.py
git commit -m "feat: add settings UI window with CustomTkinter"
```

---

## Task 10: Main Entry Point — Wire Everything Together

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Implement main.py**

```python
# src/main.py
import logging
import os
import queue
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

import customtkinter as ctk
from groq import Groq

from src.config import Config
from src.mic_recorder import MicRecorder
from src.transcriber import Transcriber
from src.text_cleaner import TextCleaner
from src.text_injector import TextInjector
from src.hotkey_listener import HotkeyListener
from src.tray_app import TrayApp
from src.settings_ui import SettingsWindow

# Minimum audio duration in seconds to send to API
MIN_AUDIO_DURATION = 0.5
# Maximum recording duration in seconds
MAX_RECORDING_DURATION = 120
# Warning before max recording
RECORDING_WARNING_TIME = 105


def _setup_logging() -> None:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(appdata, "Voxel")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "voxel.log")

    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=1)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


logger = logging.getLogger(__name__)


class VoxelApp:
    def __init__(self):
        self._config = Config()
        self._config.load()

        self._recorder = MicRecorder()
        self._work_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()

        self._groq_client: Groq | None = None
        self._transcriber: Transcriber | None = None
        self._cleaner: TextCleaner | None = None

        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        chime_path = os.path.join(assets_dir, "chime.wav")
        self._injector = TextInjector(chime_path=chime_path if os.path.exists(chime_path) else None)

        self._tray = TrayApp(
            assets_dir=assets_dir,
            on_settings=self._show_settings,
            on_quit=self._quit,
        )

        self._hotkey_listener: HotkeyListener | None = None
        self._recording_start_time: float = 0.0
        self._max_record_timer: threading.Timer | None = None
        self._running = True

        # Hidden root for CustomTkinter (must be on main thread)
        self._root = ctk.CTk()
        self._root.withdraw()

        self._settings_window = SettingsWindow(
            config=self._config,
            on_save=self._on_settings_saved,
            on_validate_key=self._validate_api_key,
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
        self._cleaner = TextCleaner(
            client=self._groq_client,
            model=self._config.get("llm_model", "llama3-70b-8192"),
        )
        return True

    def _start_hotkey_listener(self) -> None:
        if self._hotkey_listener:
            self._hotkey_listener.stop()

        hotkey = self._config.get("hotkey", "<ctrl>+<shift>+space")
        self._hotkey_listener = HotkeyListener(
            hotkey_str=hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )
        self._hotkey_listener.start()

    def _on_hotkey_press(self) -> None:
        if self._recorder.is_recording:
            return
        self._recorder.start()
        self._recording_start_time = time.time()
        self._tray.set_state("recording")

        # Auto-stop timer at max duration
        self._max_record_timer = threading.Timer(MAX_RECORDING_DURATION, self._on_hotkey_release)
        self._max_record_timer.daemon = True
        self._max_record_timer.start()

    def _on_hotkey_release(self) -> None:
        if self._max_record_timer:
            self._max_record_timer.cancel()
            self._max_record_timer = None

        if not self._recorder.is_recording:
            return

        audio_bytes = self._recorder.stop()
        self._tray.set_state("processing")

        # Check minimum audio duration
        duration = time.time() - self._recording_start_time
        if duration < MIN_AUDIO_DURATION or not audio_bytes:
            logger.debug("Recording too short (%.1fs), discarding", duration)
            self._tray.set_state("idle")
            return

        # Process in worker thread
        thread = threading.Thread(target=self._process_audio, args=(audio_bytes,), daemon=True)
        thread.start()

    def _process_audio(self, audio_bytes: bytes) -> None:
        try:
            if not self._transcriber or not self._cleaner:
                logger.error("Groq client not initialized")
                self._tray.set_state("error")
                return

            language = self._config.get("language", "en")
            raw_text = self._transcriber.transcribe(audio_bytes, language=language)

            if not raw_text.strip():
                logger.info("Empty transcript, skipping")
                self._tray.set_state("idle")
                return

            cleaned_text = self._cleaner.clean(raw_text)
            self._injector.inject(cleaned_text)
            self._tray.set_state("idle")

        except Exception as e:
            logger.error("Processing failed: %s", e, exc_info=True)
            self._tray.set_state("error")
            # Reset to idle after 3 seconds
            threading.Timer(3.0, lambda: self._tray.set_state("idle")).start()

    def _show_settings(self) -> None:
        self._root.after(0, lambda: self._settings_window.show(self._root))

    def _on_settings_saved(self) -> None:
        logger.info("Settings saved, reinitializing")
        self._init_groq()
        self._start_hotkey_listener()

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

        if self._hotkey_listener:
            self._hotkey_listener.stop()

        self._tray.stop()
        self._root.after(0, self._root.quit)

    def run(self) -> None:
        _setup_logging()
        logger.info("Voxel starting")

        self._tray.start()

        if not self._init_groq():
            logger.info("No API key configured, showing settings")
            self._root.after(100, lambda: self._settings_window.show(self._root))
        else:
            self._start_hotkey_listener()

        # Poll for results on main thread (Tk mainloop)
        self._root.mainloop()


def main():
    app = VoxelApp()
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all tests to verify nothing is broken**

Run: `python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: add main entry point wiring all components together"
```

---

## Task 11: Integration Test — Full Pipeline

**Files:**
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_pipeline.py
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
        """Simulate: audio bytes → transcription → cleanup → paste."""
        mock_pyperclip.paste.return_value = ""

        # Mock Groq client
        mock_client = MagicMock()

        # Whisper returns raw transcript
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="um so basically I think we should uh refactor the code"
        )

        # Llama returns cleaned text
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [
            MagicMock(message=MagicMock(content="I think we should refactor the code."))
        ]
        mock_client.chat.completions.create.return_value = mock_llm_response

        # Run pipeline
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
        # In the real app, main.py checks for empty before calling cleaner
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (config, transcriber, cleaner, injector, mic_recorder, hotkey_listener, pipeline).

- [ ] **Step 3: Commit**

```bash
git add tests/test_pipeline.py
git commit -m "test: add integration test for full transcription pipeline"
```

---

## Task 12: Build Configuration

**Files:**
- Create: `build.spec`

- [ ] **Step 1: Create PyInstaller build spec**

```python
# build.spec
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/assets/icon_idle.png', 'src/assets'),
        ('src/assets/icon_recording.png', 'src/assets'),
        ('src/assets/icon_processing.png', 'src/assets'),
        ('src/assets/chime.wav', 'src/assets'),
    ],
    hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Voxel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window — tray app only
    icon='src/assets/icon_idle.png',
)
```

- [ ] **Step 2: Commit**

```bash
git add build.spec
git commit -m "chore: add PyInstaller build spec"
```

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Project scaffolding | — |
| 2 | Config module | 9 tests |
| 3 | Transcriber (Groq Whisper) | 4 tests |
| 4 | Text cleaner (Groq Llama 3) | 6 tests |
| 5 | Text injector (clipboard paste) | 4 tests |
| 6 | Mic recorder (PyAudio) | 5 tests |
| 7 | Hotkey listener (pynput) | 5 tests |
| 8 | System tray app (pystray) | manual |
| 9 | Settings UI (CustomTkinter) | manual |
| 10 | Main entry point | — |
| 11 | Integration test | 2 tests |
| 12 | Build config (PyInstaller) | — |

**Total: 12 tasks, ~35 automated tests**
