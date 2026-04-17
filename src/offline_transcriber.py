# src/offline_transcriber.py
"""Offline transcription using faster-whisper (local Whisper model)."""
import io
import logging
import os
import platform
import tempfile

logger = logging.getLogger(__name__)

# Model sizes: tiny (75MB), base (145MB), small (488MB), medium (1.5GB), large-v3 (3GB)
AVAILABLE_MODELS = {
    "tiny": "Tiny (75MB - fast, less accurate)",
    "base": "Base (145MB - balanced)",
    "small": "Small (488MB - good accuracy)",
}


def _get_models_dir() -> str:
    """Get the directory where local Whisper models are stored."""
    if platform.system() == "Darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    elif platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
    path = os.path.join(base, "Voxel", "models")
    os.makedirs(path, exist_ok=True)
    return path


def is_model_downloaded(model_size: str = "base") -> bool:
    """Check if a local Whisper model is already downloaded."""
    models_dir = _get_models_dir()
    model_path = os.path.join(models_dir, f"faster-whisper-{model_size}")
    return os.path.isdir(model_path)


class OfflineTranscriber:
    """Transcribe audio locally using faster-whisper."""

    def __init__(self, model_size: str = "base"):
        self._model_size = model_size
        self._model = None
        self._models_dir = _get_models_dir()

    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:
        """Load the Whisper model. Downloads on first use."""
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading local Whisper model: %s", self._model_size)
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
                download_root=self._models_dir,
            )
            logger.info("Local Whisper model loaded successfully")
        except Exception as e:
            logger.error("Failed to load local Whisper model: %s", e)
            raise

    def transcribe(self, audio_bytes: bytes, language: str | None = "en") -> str:
        """Transcribe audio bytes using the local model."""
        if not self._model:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        logger.info("Transcribing %d bytes locally (model=%s, lang=%s)",
                     len(audio_bytes), self._model_size, language or "auto")

        # Write audio to temp file (faster-whisper needs a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            kwargs = {}
            if language and language != "auto":
                kwargs["language"] = language

            segments, info = self._model.transcribe(tmp_path, **kwargs)
            text = " ".join(seg.text.strip() for seg in segments)
            logger.info("Local Whisper returned: %s", text[:100])
            return text
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
