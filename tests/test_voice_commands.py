"""Tests for the voice command processor."""

import re
from datetime import datetime
from unittest.mock import patch

import pytest

from src.voice_commands import VoiceCommandProcessor


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def processor():
    commands = {
        "sign off": "Best regards,\nDrax",
        "my email": "isuru.nuwan007@gmail.com",
        "today": "Today is {{date}}",
        "right now": "It is {{time}}",
        "full stamp": "{{datetime}}",
    }
    return VoiceCommandProcessor(commands)


# ------------------------------------------------------------------
# Matching
# ------------------------------------------------------------------

class TestMatch:
    def test_exact_match(self, processor):
        assert processor.match("sign off") == "Best regards,\nDrax"

    def test_case_insensitive(self, processor):
        assert processor.match("Sign Off") == "Best regards,\nDrax"
        assert processor.match("SIGN OFF") == "Best regards,\nDrax"
        assert processor.match("My Email") == "isuru.nuwan007@gmail.com"

    def test_strip_trailing_punctuation(self, processor):
        """Whisper frequently appends a period to short phrases."""
        assert processor.match("sign off.") == "Best regards,\nDrax"
        assert processor.match("sign off!") == "Best regards,\nDrax"
        assert processor.match("sign off?") == "Best regards,\nDrax"
        assert processor.match("sign off,") == "Best regards,\nDrax"
        assert processor.match("sign off;") == "Best regards,\nDrax"
        assert processor.match("sign off:") == "Best regards,\nDrax"

    def test_strip_whitespace(self, processor):
        assert processor.match("  sign off  ") == "Best regards,\nDrax"

    def test_no_match_returns_none(self, processor):
        assert processor.match("something else entirely") is None
        assert processor.match("") is None

    def test_empty_commands(self):
        p = VoiceCommandProcessor({})
        assert p.match("anything") is None


# ------------------------------------------------------------------
# Placeholder expansion
# ------------------------------------------------------------------

class TestExpand:
    @patch("src.voice_commands.datetime")
    def test_date_placeholder(self, mock_dt, processor):
        mock_dt.now.return_value = datetime(2026, 4, 17, 15, 45)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = processor.expand("Today is {{date}}")
        assert result == "Today is April 17, 2026"

    @patch("src.voice_commands.datetime")
    def test_time_placeholder(self, mock_dt, processor):
        mock_dt.now.return_value = datetime(2026, 4, 17, 15, 45)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = processor.expand("It is {{time}}")
        assert result == "It is 3:45 PM"

    @patch("src.voice_commands.datetime")
    def test_datetime_placeholder(self, mock_dt, processor):
        mock_dt.now.return_value = datetime(2026, 4, 17, 15, 45)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = processor.expand("{{datetime}}")
        assert result == "April 17, 2026 3:45 PM"

    @patch("src.voice_commands.VoiceCommandProcessor._get_clipboard", return_value="pasted text")
    def test_clipboard_placeholder(self, _mock_clip, processor):
        result = processor.expand("Clipboard: {{clipboard}}")
        assert result == "Clipboard: pasted text"

    def test_no_placeholders(self, processor):
        assert processor.expand("plain text") == "plain text"


# ------------------------------------------------------------------
# Reload
# ------------------------------------------------------------------

class TestReload:
    def test_reload_replaces_commands(self, processor):
        assert processor.match("sign off") is not None
        processor.reload({"greeting": "Hello!"})
        assert processor.match("sign off") is None
        assert processor.match("greeting") == "Hello!"

    def test_reload_to_empty(self, processor):
        processor.reload({})
        assert processor.match("sign off") is None
