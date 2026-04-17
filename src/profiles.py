import logging

logger = logging.getLogger(__name__)


class ProfileManager:
    BUILTIN_PROFILES = {
        "default": {
            "name": "Default",
            "prompt": "You are a dictation cleanup assistant. The user dictated the following text using voice.\nClean it up by:\n- Removing filler words (um, uh, like, you know, basically, actually)\n- Fixing grammar, spelling, and punctuation\n- Keeping the original meaning and tone intact\n- Keeping it natural - do not make it overly formal or robotic\n- Do NOT censor, replace, or remove any words - keep ALL words exactly as spoken, including profanity\n- Do NOT add any commentary, explanation, or formatting - return ONLY the cleaned text\n\nDictated text: \"{raw_transcript}\"",
        },
        "professional": {
            "name": "Professional Email",
            "prompt": "You are a dictation cleanup assistant for professional emails. The user dictated the following text using voice.\nClean it up by:\n- Removing all filler words\n- Using professional, polished language\n- Fixing grammar, spelling, and punctuation\n- Keeping the meaning intact but making it appropriate for business communication\n- Do NOT add any commentary, explanation, or formatting - return ONLY the cleaned text\n\nDictated text: \"{raw_transcript}\"",
        },
        "casual": {
            "name": "Casual",
            "prompt": "You are a dictation cleanup assistant for casual messages. The user dictated the following text using voice.\nClean it up lightly by:\n- Removing obvious filler words (um, uh) but keeping casual language\n- Fixing only major grammar issues\n- Keeping slang, informal tone, and personality\n- Do NOT make it formal or robotic\n- Do NOT add any commentary - return ONLY the cleaned text\n\nDictated text: \"{raw_transcript}\"",
        },
        "code": {
            "name": "Code Comments",
            "prompt": "You are a dictation cleanup assistant for code comments. The user dictated the following text using voice.\nClean it up by:\n- Converting to concise, clear code comment style\n- Using technical vocabulary where appropriate\n- Removing all filler words\n- Keeping it brief and to the point\n- Do NOT add comment syntax (// or #) - return ONLY the cleaned text\n\nDictated text: \"{raw_transcript}\"",
        },
        "technical": {
            "name": "Technical Writing",
            "prompt": "You are a dictation cleanup assistant for technical documentation. The user dictated the following text using voice.\nClean it up by:\n- Using precise, clear technical language\n- Removing all filler words\n- Fixing grammar and punctuation\n- Structuring sentences for clarity\n- Do NOT add any commentary, explanation, or formatting - return ONLY the cleaned text\n\nDictated text: \"{raw_transcript}\"",
        },
    }

    def __init__(self, config):
        self._config = config

    def get_active_profile(self) -> dict:
        active_id = self._config.get("active_profile", "default")
        all_profiles = self.list_profiles()
        if active_id in all_profiles:
            return all_profiles[active_id]
        logger.warning("Active profile '%s' not found, falling back to default", active_id)
        return self.BUILTIN_PROFILES["default"]

    def get_active_prompt(self) -> str:
        return self.get_active_profile()["prompt"]

    def set_active(self, profile_id: str) -> None:
        all_profiles = self.list_profiles()
        if profile_id not in all_profiles:
            raise ValueError(f"Profile '{profile_id}' does not exist")
        self._config.set("active_profile", profile_id)
        self._config.save()
        logger.info("Active profile set to '%s'", profile_id)

    def list_profiles(self) -> dict[str, dict]:
        profiles = dict(self.BUILTIN_PROFILES)
        custom = self._config.get("profiles", {})
        if isinstance(custom, dict):
            profiles.update(custom)
        return profiles

    def add_profile(self, profile_id: str, name: str, prompt: str) -> None:
        if profile_id in self.BUILTIN_PROFILES:
            raise ValueError(f"Cannot add profile '{profile_id}': conflicts with built-in profile")
        custom = self._config.get("profiles", {}) or {}
        if profile_id in custom:
            raise ValueError(f"Profile '{profile_id}' already exists")
        custom[profile_id] = {"name": name, "prompt": prompt}
        self._config.set("profiles", custom)
        self._config.save()
        logger.info("Added custom profile '%s'", profile_id)

    def update_profile(self, profile_id: str, name: str, prompt: str) -> None:
        if self.is_builtin(profile_id):
            raise ValueError(f"Cannot update built-in profile '{profile_id}'")
        custom = self._config.get("profiles", {}) or {}
        if profile_id not in custom:
            raise ValueError(f"Custom profile '{profile_id}' does not exist")
        custom[profile_id] = {"name": name, "prompt": prompt}
        self._config.set("profiles", custom)
        self._config.save()
        logger.info("Updated custom profile '%s'", profile_id)

    def delete_profile(self, profile_id: str) -> None:
        if self.is_builtin(profile_id):
            raise ValueError(f"Cannot delete built-in profile '{profile_id}'")
        custom = self._config.get("profiles", {}) or {}
        if profile_id not in custom:
            raise ValueError(f"Custom profile '{profile_id}' does not exist")
        del custom[profile_id]
        self._config.set("profiles", custom)
        # If the deleted profile was active, reset to default
        if self._config.get("active_profile") == profile_id:
            self._config.set("active_profile", "default")
        self._config.save()
        logger.info("Deleted custom profile '%s'", profile_id)

    def is_builtin(self, profile_id: str) -> bool:
        return profile_id in self.BUILTIN_PROFILES
