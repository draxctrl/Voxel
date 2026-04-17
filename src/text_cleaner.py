import logging

logger = logging.getLogger(__name__)

CLEANUP_PROMPT_TEMPLATE = """You are a dictation cleanup assistant. The user dictated the following text using voice.
Clean it up by:
- Removing filler words (um, uh, like, you know, basically, actually)
- Fixing grammar, spelling, and punctuation
- Keeping the original meaning and tone intact
- Keeping it natural — do not make it overly formal or robotic
- Do NOT censor, replace, or remove any words — keep ALL words exactly as spoken, including profanity
- Do NOT add any commentary, explanation, or formatting — return ONLY the cleaned text

Dictated text: "{raw_transcript}" """


class TextCleaner:
    def __init__(self, client, model: str = "llama3-70b-8192", cleanup_prompt: str | None = None):
        self._client = client
        self._model = model
        self._prompt_template = cleanup_prompt or CLEANUP_PROMPT_TEMPLATE

    def set_prompt(self, prompt_template: str) -> None:
        self._prompt_template = prompt_template

    def clean(self, raw_transcript: str) -> str:
        logger.info("Sending transcript to LLM for cleanup (model=%s)", self._model)

        prompt = self._prompt_template.format(raw_transcript=raw_transcript)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )

        cleaned = response.choices[0].message.content.strip()
        logger.info("LLM cleanup result: %s", cleaned[:100])
        return cleaned
