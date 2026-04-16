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
