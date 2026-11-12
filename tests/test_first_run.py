"""The first run: four screens that end with the user having dictated."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.first_run import STEPS, FirstRunWindow, needs_first_run


class TestWhoSeesIt:
    """Today "configured" means "has an API key", which would hand the
    wizard to an offline-only user on every single launch."""

    def test_a_brand_new_config_gets_the_first_run(self, ctx):
        assert needs_first_run(ctx.config) is True

    def test_somebody_upgrading_with_a_working_key_never_sees_it(self, ctx):
        ctx.config.set("api_key", "gsk_whatever")
        assert needs_first_run(ctx.config) is False

    def test_somebody_upgrading_with_offline_on_never_sees_it(self, ctx):
        ctx.config.set("offline_mode", True)
        assert needs_first_run(ctx.config) is False

    def test_once_finished_it_does_not_come_back(self, ctx):
        ctx.config.set("onboarding_complete", True)
        assert needs_first_run(ctx.config) is False

    def test_an_empty_key_is_not_a_key(self, ctx):
        ctx.config.set("api_key", "   ")
        assert needs_first_run(ctx.config) is True


class TestTheFourSteps:
    def test_there_are_four_of_them_in_order(self):
        assert [s.key for s in STEPS] == ["welcome", "listening", "microphone", "try"]

    def test_it_opens_on_the_welcome_screen(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        assert win.current_step() == "welcome"
        assert win.step_number() == 1

    def test_continue_moves_forward_and_back_moves_back(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.go_next()
        assert win.current_step() == "listening"
        win.go_back()
        assert win.current_step() == "welcome"

    def test_it_cannot_go_back_past_the_first_screen(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.go_back()
        assert win.current_step() == "welcome"

    def test_every_screen_says_which_one_it_is(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        seen = []
        for _ in range(len(STEPS)):
            seen.append(win.step_label())
            if win.current_step() == "listening":
                # The second screen will not let anyone past until they
                # have chosen how Voxel listens, which is the point of it.
                win.choose_listening("offline")
            win.go_next()
        assert seen == ["STEP 1 OF 4", "STEP 2 OF 4", "STEP 3 OF 4", "STEP 4 OF 4"]


class TestChoosingHowVoxelListens:
    def test_choosing_groq_needs_a_key_before_continuing(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.go_next()
        win.choose_listening("groq")
        assert win.can_continue() is False, "it let the user past without a key"

    def test_choosing_private_needs_no_key(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.go_next()
        win.choose_listening("offline")
        assert win.can_continue() is True

    def test_choosing_private_turns_offline_mode_on(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.go_next()
        win.choose_listening("offline")
        assert ("offline_mode", True) in ctx.applied

    def test_a_key_that_works_is_saved_and_said_so(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.check_key = lambda key: True
        win.go_next()
        win.choose_listening("groq")
        win.submit_key("gsk_good")
        assert ("api_key", "gsk_good") in ctx.applied
        assert "works" in win.key_message().lower()
        assert win.can_continue() is True

    def test_a_key_that_does_not_work_is_not_saved(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.check_key = lambda key: False
        win.go_next()
        win.choose_listening("groq")
        win.submit_key("gsk_bad")
        written = [key for key, _value in ctx.applied]
        assert "api_key" not in written, "a bad key was written to the config"
        assert win.key_message() != ""
        assert win.can_continue() is False

    def test_the_failure_is_in_plain_words(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.check_key = lambda key: False
        win.go_next()
        win.choose_listening("groq")
        win.submit_key("gsk_bad")
        words = win.key_message().lower()
        for jargon in ("401", "exception", "traceback", "http", "unauthorized"):
            assert jargon not in words, "%r is not plain words" % jargon


class TestTheTestDictation:
    """Step 4's dictation is shown in the box on that screen - not typed
    into whatever app is behind Voxel, and not written to History."""

    def test_the_result_lands_on_the_screen(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.show_dictation("I have a car.")
        assert "I have a car." in win.dictation_text()

    @staticmethod
    def _walk_to_the_end(win):
        for _ in range(3):
            if win.current_step() == "listening":
                win.choose_listening("offline")
            win.go_next()

    def test_it_is_diverted_while_the_last_screen_is_open(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        self._walk_to_the_end(win)
        assert win.current_step() == "try"
        assert win.wants_the_dictation() is True

    def test_it_is_not_diverted_anywhere_else(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        assert win.wants_the_dictation() is False

    def test_it_stops_wanting_it_once_the_window_is_done(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        self._walk_to_the_end(win)
        win.finish()
        assert win.wants_the_dictation() is False


class TestFinishing:
    def test_finishing_marks_the_flag(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        win.finish()
        assert ("onboarding_complete", True) in ctx.applied

    def test_finishing_tells_whoever_is_listening(self, qapp, ctx):
        win = FirstRunWindow(ctx)
        done = []
        win.finished.connect(lambda: done.append(True))
        win.finish()
        assert done == [True]

    def test_closing_the_window_early_still_marks_it(self, qapp, ctx):
        """Someone who closes the wizard has made their choice. Showing it
        again every launch would be nagging, not helping."""
        win = FirstRunWindow(ctx)
        win.close()
        assert ("onboarding_complete", True) in ctx.applied


class TestHowTheAppUsesIt:
    """Wiring, checked by reading main.py rather than by starting it: the
    app needs a Groq key before it starts the hotkey listener today, so a
    user who chooses the private option would reach step 4 and find that
    holding the shortcut does nothing."""

    @staticmethod
    def _main_source() -> str:
        import inspect

        import src.main as main

        return inspect.getsource(main)

    def test_the_first_run_is_what_a_new_user_gets(self):
        source = self._main_source()
        assert "needs_first_run" in source, (
            "main.py never asks whether this is a first run"
        )
        assert "FirstRunWindow" in source

    def test_the_shortcut_works_without_a_groq_key(self):
        """Otherwise step 4 silently does nothing for the private option."""
        source = self._main_source()
        assert "_start_hotkey_listener" in source
        marker = "offline_mode"
        start = source.index("def _startup_stage_2")
        end = source.index("def _startup_finish")
        stage = source[start:end]
        assert marker in stage or "needs_first_run" in stage, (
            "startup still starts the listener only when a Groq key exists"
        )

    def test_the_test_dictation_is_diverted(self):
        source = self._main_source()
        assert "wants_the_dictation" in source, (
            "the dictation path never asks the first-run window for it"
        )


class TestTheConfigKnowsTheFlag:
    def test_the_flag_has_a_default(self):
        from src.config import DEFAULT_CONFIG

        assert DEFAULT_CONFIG.get("onboarding_complete") is False
