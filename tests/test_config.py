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
        assert DEFAULT_CONFIG["llm_model"] == "openai/gpt-oss-120b"

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


class TestMicDeviceConfig:
    def test_mic_device_name_defaults_to_none(self):
        assert "mic_device_name" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["mic_device_name"] is None

    def test_legacy_integer_mic_device_is_preserved_as_hint(self, tmp_path):
        # A config written by the current shipped version: an index, no name.
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"mic_device": 3}), encoding="utf-8")

        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.get("mic_device") == 3
        assert cfg.get("mic_device_name") is None


class TestProfileIdMigration:
    def test_active_profile_is_migrated_on_load(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"active_profile": "default"}), encoding="utf-8")

        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.get("active_profile") == "grammar_tidy"

    def test_casual_migrates_to_grammar_only(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"active_profile": "casual"}), encoding="utf-8")

        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.get("active_profile") == "grammar_only"

    def test_app_profile_values_are_migrated_on_load(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"app_profiles": {"Code.exe": "casual", "OUTLOOK.EXE": "professional"}}),
            encoding="utf-8",
        )

        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.get("app_profiles") == {
            "Code.exe": "grammar_only",
            "OUTLOOK.EXE": "professional",
        }

    def test_custom_profile_id_is_left_alone(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"active_profile": "my_own", "profiles": {"my_own": {"name": "Mine", "prompt": "p"}}}),
            encoding="utf-8",
        )

        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.get("active_profile") == "my_own"


class TestMicNameBackfill:
    """An upgrading user has only a legacy index. Without a name, the whole
    point of the change — surviving device renumbering — never reaches them."""

    def test_backfills_name_when_only_a_legacy_index_exists(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"mic_device": 3}), encoding="utf-8")
        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.backfill_mic_name("Blue Yeti") is True
        assert cfg.get("mic_device_name") == "Blue Yeti"

    def test_does_not_overwrite_an_existing_name(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"mic_device": 3, "mic_device_name": "Blue Yeti"}), encoding="utf-8"
        )
        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.backfill_mic_name("Realtek Mic") is False
        assert cfg.get("mic_device_name") == "Blue Yeti"

    def test_does_not_pin_a_user_who_never_chose_a_device(self, tmp_path):
        # No index and no name means "just use the system default" — pinning a
        # name here would break them when they change their Windows default.
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({}), encoding="utf-8")
        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.backfill_mic_name("Realtek Mic") is False
        assert cfg.get("mic_device_name") is None

    def test_ignores_an_empty_active_name(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"mic_device": 3}), encoding="utf-8")
        cfg = Config(config_path=str(config_path))
        cfg.load()

        assert cfg.backfill_mic_name(None) is False
        assert cfg.get("mic_device_name") is None


class TestARetiredCleanupModelIsMigrated:
    """Groq retires model ids. A config still naming one made every dictation
    fail with a 404 after transcription had already succeeded — the user saw
    nothing appear and read it as 'the microphone is not working'."""

    def test_a_retired_model_id_loads_as_the_current_default(self, tmp_path):
        import json
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"llm_model": "llama-3.3-70b-versatile"}))

        cfg = Config(config_path=str(path))
        cfg.load()

        assert cfg.get("llm_model") == DEFAULT_CONFIG["llm_model"]

    def test_a_model_we_did_not_retire_is_left_alone(self, tmp_path):
        import json
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"llm_model": "some/custom-model"}))

        cfg = Config(config_path=str(path))
        cfg.load()

        assert cfg.get("llm_model") == "some/custom-model"
