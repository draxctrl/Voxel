import pytest
from unittest.mock import MagicMock

from src.profiles import ProfileManager, resolve_effective_profile


def _make_config(data=None):
    config = MagicMock()
    store = {"active_profile": "grammar_tidy", "profiles": {}}
    if data:
        store.update(data)
    config.get = lambda key, default=None: store.get(key, default)

    def _set(key, value):
        store[key] = value

    config.set = _set
    config.save = MagicMock()
    return config


class TestProfileManagerBuiltins:
    def test_list_profiles_returns_all_builtins(self):
        pm = ProfileManager(_make_config())
        profiles = pm.list_profiles()
        assert "raw" in profiles
        assert "grammar_only" in profiles
        assert "grammar_tidy" in profiles
        assert "professional" in profiles
        assert "code" in profiles
        assert "technical" in profiles
        assert len(profiles) == len(ProfileManager.BUILTIN_PROFILES)

    def test_builtin_profiles_have_name_and_prompt(self):
        pm = ProfileManager(_make_config())
        for pid, profile in ProfileManager.BUILTIN_PROFILES.items():
            assert "name" in profile
            assert "prompt" in profile
            # The raw profile is a sentinel that skips the LLM entirely, so it
            # has no transcript placeholder to substitute into.
            if profile["prompt"] != "__RAW__":
                assert "{raw_transcript}" in profile["prompt"]

    def test_is_builtin_true_for_builtins(self):
        pm = ProfileManager(_make_config())
        assert pm.is_builtin("grammar_tidy") is True
        assert pm.is_builtin("professional") is True

    def test_is_builtin_false_for_custom(self):
        pm = ProfileManager(_make_config())
        assert pm.is_builtin("my_custom") is False


class TestActiveProfile:
    def test_default_active_profile(self):
        pm = ProfileManager(_make_config())
        profile = pm.get_active_profile()
        assert profile["name"] == "Grammar + tidy up"

    def test_get_active_prompt_returns_prompt_string(self):
        pm = ProfileManager(_make_config())
        prompt = pm.get_active_prompt()
        assert "{raw_transcript}" in prompt

    def test_set_active_changes_profile(self):
        config = _make_config()
        pm = ProfileManager(config)
        pm.set_active("professional")
        assert pm.get_active_profile()["name"] == "Professional Email"
        config.save.assert_called()

    def test_set_active_invalid_profile_raises(self):
        pm = ProfileManager(_make_config())
        with pytest.raises(ValueError, match="does not exist"):
            pm.set_active("nonexistent")

    def test_fallback_to_default_when_active_missing(self):
        config = _make_config({"active_profile": "deleted_profile"})
        pm = ProfileManager(config)
        profile = pm.get_active_profile()
        assert profile["name"] == "Grammar + tidy up"


class TestCustomProfiles:
    def test_add_custom_profile(self):
        config = _make_config()
        pm = ProfileManager(config)
        pm.add_profile("my_style", "My Style", "Clean: {raw_transcript}")
        profiles = pm.list_profiles()
        assert "my_style" in profiles
        assert profiles["my_style"]["name"] == "My Style"
        config.save.assert_called()

    def test_add_duplicate_raises(self):
        config = _make_config({"profiles": {"existing": {"name": "E", "prompt": "p"}}})
        pm = ProfileManager(config)
        with pytest.raises(ValueError, match="already exists"):
            pm.add_profile("existing", "E2", "p2")

    def test_add_conflicting_builtin_raises(self):
        pm = ProfileManager(_make_config())
        with pytest.raises(ValueError, match="built-in"):
            pm.add_profile("grammar_tidy", "Override", "prompt")

    def test_update_custom_profile(self):
        config = _make_config({"profiles": {"my_style": {"name": "Old", "prompt": "old"}}})
        pm = ProfileManager(config)
        pm.update_profile("my_style", "New Name", "new prompt {raw_transcript}")
        profiles = pm.list_profiles()
        assert profiles["my_style"]["name"] == "New Name"
        config.save.assert_called()

    def test_update_builtin_raises(self):
        pm = ProfileManager(_make_config())
        with pytest.raises(ValueError, match="built-in"):
            pm.update_profile("grammar_tidy", "New", "prompt")

    def test_update_nonexistent_raises(self):
        pm = ProfileManager(_make_config())
        with pytest.raises(ValueError, match="does not exist"):
            pm.update_profile("nope", "N", "p")

    def test_delete_custom_profile(self):
        config = _make_config({"profiles": {"tmp": {"name": "Tmp", "prompt": "p"}}})
        pm = ProfileManager(config)
        pm.delete_profile("tmp")
        assert "tmp" not in pm.list_profiles()
        config.save.assert_called()

    def test_delete_builtin_raises(self):
        pm = ProfileManager(_make_config())
        with pytest.raises(ValueError, match="built-in"):
            pm.delete_profile("grammar_tidy")

    def test_delete_nonexistent_raises(self):
        pm = ProfileManager(_make_config())
        with pytest.raises(ValueError, match="does not exist"):
            pm.delete_profile("nope")

    def test_delete_active_profile_resets_to_default(self):
        config = _make_config({
            "active_profile": "tmp",
            "profiles": {"tmp": {"name": "Tmp", "prompt": "p"}},
        })
        pm = ProfileManager(config)
        pm.delete_profile("tmp")
        assert pm.get_active_profile()["name"] == "Grammar + tidy up"

    def test_custom_profiles_merge_with_builtins(self):
        config = _make_config({"profiles": {"extra": {"name": "Extra", "prompt": "p"}}})
        pm = ProfileManager(config)
        profiles = pm.list_profiles()
        assert len(profiles) == len(ProfileManager.BUILTIN_PROFILES) + 1
        assert "extra" in profiles
        assert "grammar_tidy" in profiles


class TestConsolidatedProfiles:
    def test_grammar_modes_exist_and_are_separate(self):
        builtins = ProfileManager.BUILTIN_PROFILES
        assert "grammar_only" in builtins
        assert "grammar_tidy" in builtins
        assert builtins["grammar_only"]["prompt"] != builtins["grammar_tidy"]["prompt"]

    def test_grammar_only_keeps_filler_words(self):
        prompt = ProfileManager.BUILTIN_PROFILES["grammar_only"]["prompt"]
        assert "{raw_transcript}" in prompt
        # It must tell the model to KEEP filler words, not remove them.
        assert "filler" in prompt.lower()
        assert "keep" in prompt.lower()

    def test_grammar_tidy_removes_filler_words(self):
        prompt = ProfileManager.BUILTIN_PROFILES["grammar_tidy"]["prompt"]
        assert "{raw_transcript}" in prompt
        assert "remov" in prompt.lower()

    def test_overlapping_legacy_profiles_are_gone(self):
        assert "default" not in ProfileManager.BUILTIN_PROFILES
        assert "casual" not in ProfileManager.BUILTIN_PROFILES

    def test_raw_profile_survives_consolidation(self):
        assert ProfileManager.BUILTIN_PROFILES["raw"]["prompt"] == "__RAW__"


class TestProfileMigration:
    def test_removed_ids_map_to_replacements(self):
        assert ProfileManager.migrate_profile_id("default") == "grammar_tidy"
        assert ProfileManager.migrate_profile_id("casual") == "grammar_only"

    def test_surviving_ids_pass_through(self):
        assert ProfileManager.migrate_profile_id("professional") == "professional"
        assert ProfileManager.migrate_profile_id("raw") == "raw"

    def test_unknown_custom_id_passes_through(self):
        assert ProfileManager.migrate_profile_id("my_custom") == "my_custom"


class TestEffectiveProfileResolution:
    """Which mode actually runs for a given dictation."""

    PROFILES = {
        "raw": {"name": "Raw (no cleanup)", "prompt": "__RAW__"},
        "grammar_tidy": {"name": "Grammar + tidy up", "prompt": "tidy {raw_transcript}"},
        "professional": {"name": "Professional Email", "prompt": "pro {raw_transcript}"},
    }

    def test_auto_profile_off_always_uses_active_profile(self):
        pid, prof = resolve_effective_profile(
            self.PROFILES, "grammar_tidy", {"Code.exe": "professional"},
            auto_profile=False, app_name="Code.exe",
        )
        assert pid == "grammar_tidy"

    def test_mapped_app_wins_when_auto_profile_on(self):
        pid, prof = resolve_effective_profile(
            self.PROFILES, "grammar_tidy", {"Code.exe": "professional"},
            auto_profile=True, app_name="Code.exe",
        )
        assert pid == "professional"
        assert prof["name"] == "Professional Email"

    def test_unmapped_app_falls_back_to_active_profile(self):
        # The sticky bug: after one mapped app, every later dictation kept that
        # profile. An unmapped app must return to the user's chosen mode.
        pid, _ = resolve_effective_profile(
            self.PROFILES, "grammar_tidy", {"Code.exe": "professional"},
            auto_profile=True, app_name="Notepad.exe",
        )
        assert pid == "grammar_tidy"

    def test_app_mapped_to_raw_resolves_to_raw(self):
        pid, prof = resolve_effective_profile(
            self.PROFILES, "grammar_tidy", {"Code.exe": "raw"},
            auto_profile=True, app_name="Code.exe",
        )
        assert pid == "raw"
        assert prof["prompt"] == "__RAW__"

    def test_mapping_to_deleted_profile_falls_back_to_active(self):
        pid, _ = resolve_effective_profile(
            self.PROFILES, "grammar_tidy", {"Code.exe": "gone"},
            auto_profile=True, app_name="Code.exe",
        )
        assert pid == "grammar_tidy"

    def test_missing_active_profile_falls_back_to_default(self):
        pid, _ = resolve_effective_profile(
            self.PROFILES, "also_gone", {}, auto_profile=False, app_name=None,
        )
        assert pid == ProfileManager.DEFAULT_PROFILE_ID

    def test_unknown_app_name_is_safe(self):
        pid, _ = resolve_effective_profile(
            self.PROFILES, "grammar_tidy", {"Code.exe": "professional"},
            auto_profile=True, app_name=None,
        )
        assert pid == "grammar_tidy"
