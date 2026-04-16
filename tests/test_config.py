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
        assert DEFAULT_CONFIG["llm_model"] == "llama-3.3-70b-versatile"

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
        assert cfg.get("hotkey") == "<ctrl>+<shift>+space"

    def test_load_handles_corrupt_file(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json{{{")
        cfg = Config(config_path=str(config_path))
        cfg.load()
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
