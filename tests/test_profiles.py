import pytest
from unittest.mock import MagicMock

from src.profiles import ProfileManager


def _make_config(data=None):
    config = MagicMock()
    store = {"active_profile": "default", "profiles": {}}
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
        assert "default" in profiles
        assert "professional" in profiles
        assert "casual" in profiles
        assert "code" in profiles
        assert "technical" in profiles
        assert len(profiles) >= 5

    def test_builtin_profiles_have_name_and_prompt(self):
        pm = ProfileManager(_make_config())
        for pid, profile in ProfileManager.BUILTIN_PROFILES.items():
            assert "name" in profile
            assert "prompt" in profile
            assert "{raw_transcript}" in profile["prompt"]

    def test_is_builtin_true_for_builtins(self):
        pm = ProfileManager(_make_config())
        assert pm.is_builtin("default") is True
        assert pm.is_builtin("professional") is True

    def test_is_builtin_false_for_custom(self):
        pm = ProfileManager(_make_config())
        assert pm.is_builtin("my_custom") is False


class TestActiveProfile:
    def test_default_active_profile(self):
        pm = ProfileManager(_make_config())
        profile = pm.get_active_profile()
        assert profile["name"] == "Default"

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
        assert profile["name"] == "Default"


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
            pm.add_profile("default", "Override", "prompt")

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
            pm.update_profile("default", "New", "prompt")

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
            pm.delete_profile("default")

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
        assert pm.get_active_profile()["name"] == "Default"

    def test_custom_profiles_merge_with_builtins(self):
        config = _make_config({"profiles": {"extra": {"name": "Extra", "prompt": "p"}}})
        pm = ProfileManager(config)
        profiles = pm.list_profiles()
        assert len(profiles) == 6  # 5 builtins + 1 custom
        assert "extra" in profiles
        assert "default" in profiles
