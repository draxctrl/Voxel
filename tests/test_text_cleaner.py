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
