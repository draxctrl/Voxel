"""Voice command processor for expanding trigger phrases into templates."""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class VoiceCommandProcessor:
    """Matches spoken trigger phrases and expands them into templates.

    Instead of sending every utterance through AI cleanup, users can define
    short trigger phrases that expand to fixed templates with optional
    placeholders ({{date}}, {{time}}, {{datetime}}, {{clipboard}}).
    """

    _TRAILING_PUNCT = re.compile(r"[.!?,;:]+$")

    def __init__(self, commands: dict[str, str]) -> None:
        self._commands: dict[str, str] = {}
        self._load(commands)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, raw_text: str) -> str | None:
        """Return the expanded template if *raw_text* matches a trigger, else None."""
        normalized = self._normalize(raw_text)
        template = self._commands.get(normalized)
        if template is None:
            return None
        return self.expand(template)

    def expand(self, template: str) -> str:
        """Replace placeholders in *template* with live values."""
        now = datetime.now()
        date_str = now.strftime("%B %d, %Y").replace(" 0", " ")
        time_str = now.strftime("%I:%M %p").lstrip("0")
        datetime_str = f"{date_str} {time_str}"

        result = template
        result = result.replace("{{date}}", date_str)
        result = result.replace("{{time}}", time_str)
        result = result.replace("{{datetime}}", datetime_str)

        if "{{clipboard}}" in result:
            result = result.replace("{{clipboard}}", self._get_clipboard())

        return result

    def reload(self, commands: dict[str, str]) -> None:
        """Replace the current command set with *commands*."""
        self._load(commands)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, commands: dict[str, str]) -> None:
        """Normalize trigger keys and store them."""
        self._commands = {
            self._normalize(trigger): template
            for trigger, template in commands.items()
        }

    @classmethod
    def _normalize(cls, text: str) -> str:
        """Lowercase, strip whitespace and trailing punctuation."""
        text = text.strip().lower()
        text = cls._TRAILING_PUNCT.sub("", text)
        return text

    @staticmethod
    def _get_clipboard() -> str:
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            logger.warning("Could not read clipboard")
            return ""
