import logging

logger = logging.getLogger(__name__)

#: Shared by every prompt: output is verbatim, never masked or bleeped.
NOCENSOR = (
    "- CRITICAL: NEVER censor, bleep, replace, or mask any words - output ALL words "
    "verbatim, including profanity, slurs, or offensive language exactly as spoken. "
    "No asterisks, no substitutions, no euphemisms."
)

_GRAMMAR_ONLY = f"""You are a grammar corrector for dictated speech. Correct the text below WITHOUT rewriting it.
Do this:
- Fix grammar, verb tense, subject-verb agreement, spelling and punctuation
- Add sentence breaks and capitalisation where they are missing
Do NOT do this:
- Do NOT remove filler words - keep every "um", "uh", "like", "you know", "I mean" exactly where they are
- Do NOT remove or reorder any other words, and do NOT reword anything
- Do NOT change slang, contractions, informal phrasing or tone
- Do NOT shorten, summarise or tidy the text
{NOCENSOR}
- Do NOT add any commentary, explanation, or formatting - return ONLY the corrected text

Dictated text: "{{raw_transcript}}\""""

_GRAMMAR_TIDY = f"""You are a dictation cleanup assistant. Clean up the dictated text below so it reads well.
Do this:
- Fix grammar, verb tense, agreement, spelling and punctuation
- Remove filler words (um, uh, like, you know, I mean, basically, actually)
- Remove false starts, stutters and repeated words
- Keep the speaker's meaning, voice and level of formality intact
Do NOT do this:
- Do NOT make it more formal, corporate or robotic than it was spoken
- Do NOT summarise, shorten or add anything the speaker did not say
{NOCENSOR}
- Do NOT add any commentary, explanation, or formatting - return ONLY the cleaned text

Dictated text: "{{raw_transcript}}\""""

_PROFESSIONAL = f"""You are rewriting dictated speech as professional business correspondence.
Do this:
- Remove all filler words, false starts and verbal tics
- Raise the register to polished, courteous business English
- Fix grammar, spelling and punctuation, and structure it into clear sentences and paragraphs
- Replace casual phrasing with its professional equivalent
Do NOT do this:
- Do NOT invent facts, names, dates, commitments or pleasantries the speaker did not say
- Do NOT add a greeting or sign-off unless the speaker dictated one
{NOCENSOR}
- Do NOT add any commentary, explanation, or formatting - return ONLY the rewritten text

Dictated text: "{{raw_transcript}}\""""

_CODE = f"""You are converting dictated speech into a concise code comment.
Do this:
- Strip every filler word and make it terse and declarative
- Use correct technical vocabulary, and spell identifiers, APIs and acronyms the way a programmer writes them (camelCase, snake_case, PascalCase as dictated)
- Prefer the imperative mood and drop unnecessary articles, as comments normally do
Do NOT do this:
- Do NOT add comment syntax (//, #, slash-star) - return the bare text
- Do NOT explain or expand on what was said
{NOCENSOR}
- Do NOT add any commentary - return ONLY the comment text

Dictated text: "{{raw_transcript}}\""""

_TECHNICAL = f"""You are editing dictated speech into technical documentation prose.
Do this:
- Remove all filler words and conversational asides
- Use precise, unambiguous language and consistent terminology throughout
- Restructure rambling sentences into clear, self-contained ones
- Keep a neutral, factual register and spell technical terms correctly
Do NOT do this:
- Do NOT add explanations, caveats, examples or detail the speaker did not dictate
- Do NOT use marketing language or hedging
{NOCENSOR}
- Do NOT add any commentary, explanation, or formatting - return ONLY the edited text

Dictated text: "{{raw_transcript}}\""""


class ProfileManager:
    #: Mode used when nothing is chosen, and when an active profile goes missing.
    DEFAULT_PROFILE_ID = "grammar_tidy"

    #: Modes removed when the list was consolidated, mapped to their closest
    #: surviving equivalent. Existing configs migrate through this.
    LEGACY_PROFILE_IDS = {
        "default": "grammar_tidy",
        "casual": "grammar_only",
    }

    BUILTIN_PROFILES = {
        "raw": {
            "name": "Raw (no cleanup)",
            # Sentinel - main.py detects this and skips the LLM entirely.
            "prompt": "__RAW__",
        },
        "grammar_only": {
            "name": "Grammar only — keep my words",
            "prompt": _GRAMMAR_ONLY,
        },
        "grammar_tidy": {
            "name": "Grammar + tidy up",
            "prompt": _GRAMMAR_TIDY,
        },
        "professional": {
            "name": "Professional Email",
            "prompt": _PROFESSIONAL,
        },
        "code": {
            "name": "Code Comments",
            "prompt": _CODE,
        },
        "technical": {
            "name": "Technical Writing",
            "prompt": _TECHNICAL,
        },
    }

    @classmethod
    def migrate_profile_id(cls, profile_id: str) -> str:
        """Map a consolidated-away profile id to its replacement.

        Ids that still exist, and custom ids we know nothing about, pass through
        untouched so a user's own profiles are never rewritten or deleted.
        """
        return cls.LEGACY_PROFILE_IDS.get(profile_id, profile_id)

    def __init__(self, config):
        self._config = config

    def get_active_profile(self) -> dict:
        active_id = self._config.get("active_profile", self.DEFAULT_PROFILE_ID)
        all_profiles = self.list_profiles()
        if active_id in all_profiles:
            return all_profiles[active_id]
        logger.warning("Active profile '%s' not found, falling back to default", active_id)
        return self.BUILTIN_PROFILES[self.DEFAULT_PROFILE_ID]

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
        # If the deleted profile was active, reset to the default mode
        if self._config.get("active_profile") == profile_id:
            self._config.set("active_profile", self.DEFAULT_PROFILE_ID)
        self._config.save()
        logger.info("Deleted custom profile '%s'", profile_id)

    def is_builtin(self, profile_id: str) -> bool:
        return profile_id in self.BUILTIN_PROFILES
