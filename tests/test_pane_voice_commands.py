"""The Voice commands pane: say a phrase, get a block of text."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.config import DEFAULT_CONFIG
from src.ui_pyqt6.panes import all_panes
from src.ui_pyqt6.panes.voice_commands import VoiceCommandsPane

#: Keys the config holds that are not a control anyone sees: stored data
#: (the user's own profiles, per-app mappings) and model ids Voxel chooses.
NOT_USER_FACING = {
    "profiles",
    "app_profiles",
    "mic_device",
    "llm_model",
    "whisper_model",
    "offline_model",
    # Whether this user has been through the first run. Deliberately
    # not a setting: nobody wants a switch that replays the wizard,
    # and "have they got a key" cannot answer it for someone who
    # chose to work offline and has no key at all.
    "onboarding_complete",
}


class TestEverySettingHasAHome:
    """With the last pane in place, no setting is left without a screen."""

    def test_no_config_key_is_orphaned(self):
        homed = set().union(*(p.OWNS for p in all_panes()))
        unowned = set(DEFAULT_CONFIG) - homed - NOT_USER_FACING
        assert unowned == set(), f"settings with no pane: {sorted(unowned)}"


class TestEditingCommands:
    def test_existing_commands_are_listed(self, qapp, ctx):
        ctx.config.set("voice_commands", {"brb": "be right back", "sig": "Thanks,"})
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        assert pane.commands() == {"brb": "be right back", "sig": "Thanks,"}

    def test_an_empty_list_says_so_rather_than_showing_nothing(self, qapp, ctx):
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        assert pane.commands() == {}
        assert pane.empty_message() != ""

    def test_adding_a_pair_applies_the_whole_mapping(self, qapp, ctx):
        ctx.config.set("voice_commands", {"brb": "be right back"})
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.add_command("sig", "Thanks,")
        assert ctx.applied == [
            ("voice_commands", {"brb": "be right back", "sig": "Thanks,"})
        ]

    def test_deleting_a_pair_applies_the_whole_mapping(self, qapp, ctx):
        ctx.config.set("voice_commands", {"brb": "be right back", "sig": "Thanks,"})
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.delete_command("brb")
        assert ctx.applied == [("voice_commands", {"sig": "Thanks,"})]

    def test_deleting_one_that_is_not_there_changes_nothing(self, qapp, ctx):
        ctx.config.set("voice_commands", {"brb": "be right back"})
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.delete_command("nope")
        assert ctx.applied == []

    def test_editing_an_expansion_applies_the_whole_mapping(self, qapp, ctx):
        ctx.config.set("voice_commands", {"brb": "be right back"})
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.add_command("brb", "back in five")
        assert ctx.applied == [("voice_commands", {"brb": "back in five"})]


class TestWhatIsNotSaved:
    def test_a_blank_trigger_is_not_saved(self, qapp, ctx):
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.add_command("", "something")
        assert ctx.applied == []

    def test_a_whitespace_only_trigger_is_not_saved(self, qapp, ctx):
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.add_command("   ", "something")
        assert ctx.applied == []

    def test_a_blank_expansion_is_not_saved(self, qapp, ctx):
        """A trigger that expands to nothing would delete what you said."""
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.add_command("brb", "  ")
        assert ctx.applied == []

    def test_a_trigger_is_trimmed_and_lower_cased(self, qapp, ctx):
        """Speech comes back in whatever case the model picked, so a
        trigger saved as "BRB" would never match."""
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.add_command("  BRB  ", " be right back ")
        assert ctx.applied == [("voice_commands", {"brb": "be right back"})]

    def test_refreshing_applies_nothing(self, qapp, ctx):
        ctx.config.set("voice_commands", {"brb": "be right back"})
        pane = VoiceCommandsPane(ctx)
        pane.refresh()
        pane.refresh()
        assert ctx.applied == []


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_the_voice_commands(self):
        assert VoiceCommandsPane.OWNS == frozenset({"voice_commands"})
