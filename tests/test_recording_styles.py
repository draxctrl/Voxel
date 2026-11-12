"""The three recording displays. Runs headless via Qt's offscreen platform."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _render(widget):
    """Render a display to an image, over a sentinel background."""
    from PyQt6.QtGui import QPixmap, QColor
    size = widget.preferred_size()
    widget.resize(size)
    pm = QPixmap(size)
    pm.fill(QColor(0, 255, 0))
    widget.render(pm)
    return pm.toImage()


def _pixels(img):
    return [
        img.pixelColor(x, y).name()
        for y in range(0, img.height(), 3)
        for x in range(0, img.width(), 3)
    ]


class TestStyleRegistry:
    def test_the_default_is_the_orb(self):
        from src.ui_pyqt6.recording_styles import DEFAULT_STYLE
        assert DEFAULT_STYLE == "orb"

    def test_every_registered_style_builds(self, qapp):
        from src.ui_pyqt6.recording_styles import RECORDING_STYLES, build_display
        for style_id in RECORDING_STYLES:
            display = build_display(style_id)
            assert display.style_id == style_id

    def test_every_style_has_a_human_label(self):
        from src.ui_pyqt6.recording_styles import RECORDING_STYLES
        assert RECORDING_STYLES["orb"] == "Orb"
        assert all(label.strip() for label in RECORDING_STYLES.values())

    def test_an_unknown_style_falls_back_to_the_default(self, qapp):
        """A hand-edited or downgraded config must not break every dictation."""
        from src.ui_pyqt6.recording_styles import DEFAULT_STYLE, build_display
        assert build_display("spinning-pizza").style_id == DEFAULT_STYLE
        assert build_display("").style_id == DEFAULT_STYLE
        assert build_display(None).style_id == DEFAULT_STYLE


@pytest.mark.parametrize("style_id", ["orb", "waveform", "island"])
class TestLevelDrivesTheDrawing:
    """The old waveform animated identically whether you shouted or said
    nothing, which made the app look like it was listening when it might not
    be. For every style, loud must not look like silent."""

    def test_loud_and_silent_render_differently(self, qapp, style_id):
        from src.ui_pyqt6.recording_styles import build_display
        display = build_display(style_id)
        display.set_state("recording")

        display.set_level(0.0)
        silent = _pixels(_render(display))

        display.set_level(1.0)
        loud = _pixels(_render(display))

        assert silent != loud, f"{style_id} looks the same shouting as silent"

    def test_the_display_has_a_sensible_size(self, qapp, style_id):
        from src.ui_pyqt6.recording_styles import build_display
        size = build_display(style_id).preferred_size()
        assert 80 <= size.width() <= 640
        assert 48 <= size.height() <= 400

    def test_elapsed_and_mic_text_are_accepted(self, qapp, style_id):
        from src.ui_pyqt6.recording_styles import build_display
        display = build_display(style_id)
        display.set_elapsed("1:23")
        display.set_mic_text("Blue Yeti")
        assert display.elapsed_text == "1:23"
        assert "Blue Yeti" in display.mic_text


class TestOrbGlyphIsSteady:
    """Spec: only the glow responds to voice level. A mic glyph that wobbles
    with volume reads as nervous rather than responsive."""

    @staticmethod
    def _glyph_box(img):
        """Bounding box of the near-white mic glyph."""
        xs, ys = [], []
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.red() > 215 and c.green() > 215 and c.blue() > 215:
                    xs.append(x)
                    ys.append(y)
        assert xs, "no mic glyph was drawn at all"
        return min(xs), min(ys), max(xs), max(ys)

    def test_the_disc_and_mic_do_not_move_with_level(self, qapp):
        """The glow is allowed to bleed through the frosted disc — the spec
        asks for that — so this checks the geometry, not the colour: the mic
        glyph must occupy exactly the same pixels whatever the volume."""
        from src.ui_pyqt6.recording_styles import build_display
        orb = build_display("orb")
        orb.set_state("recording")

        orb.set_level(0.0)
        quiet = self._glyph_box(_render(orb))
        orb.set_level(1.0)
        loud = self._glyph_box(_render(orb))

        assert quiet == loud, f"the mic glyph moved: {quiet} -> {loud}"

    def test_the_glow_does_respond(self, qapp):
        from src.ui_pyqt6.recording_styles import build_display
        orb = build_display("orb")
        orb.set_state("recording")
        orb.set_level(0.0)
        quiet = _render(orb)
        orb.set_level(1.0)
        loud = _render(orb)

        cx = quiet.width() // 2
        edge_y = orb.orb_centre_y() - orb.DISC_RADIUS - 8
        assert quiet.pixelColor(cx, edge_y) != loud.pixelColor(cx, edge_y), (
            "the glow is the one thing that must follow the voice"
        )


class TestIslandDotStaysRed:
    """The Dynamic Island's recording dot is the one deliberate exception to
    the indigo rule."""

    def test_the_recording_dot_is_red(self, qapp):
        from src.ui_pyqt6.recording_styles import ISLAND_DOT_RED, build_display
        island = build_display("island")
        island.set_state("recording")
        island.set_level(0.5)
        img = _render(island)
        found = {
            img.pixelColor(x, y).name().lower()
            for y in range(img.height())
            for x in range(img.width())
        }
        assert ISLAND_DOT_RED.lower() in found


class TestTheDrawnLevelIsSmoothed:
    """Voice peaks arrive in single frames. Drawn raw, the badge jitters."""

    def test_one_jump_does_not_reach_the_target_immediately(self, qapp):
        from src.ui_pyqt6.recording_styles import build_display
        d = build_display("island")
        d.set_level(0.0)
        d.set_level(1.0)
        assert d.level == 1.0, "the measured level is reported as measured"
        assert 0.0 < d.drawn_level < 1.0, (
            f"the drawn level jumped straight to {d.drawn_level}"
        )

    def test_it_does_catch_up_over_several_frames(self, qapp):
        from src.ui_pyqt6.recording_styles import build_display
        d = build_display("island")
        for _ in range(40):
            d.set_level(1.0)
        assert d.drawn_level > 0.95

    def test_falling_is_gentler_than_rising(self, qapp):
        """A gate slamming shut looks worse than one easing shut."""
        from src.ui_pyqt6.recording_styles import build_display
        rising = build_display("island")
        rising.set_level(0.0)
        rising.set_level(1.0)
        falling = build_display("island")
        for _ in range(40):
            falling.set_level(1.0)
        before = falling.drawn_level
        falling.set_level(0.0)
        assert (before - falling.drawn_level) < rising.drawn_level


class TestTheIslandHoldsItsShape:
    """The pill was sized from the level, so every syllable resized the whole
    badge. The level belongs in the wave, not in the outline."""

    def _island(self):
        from src.ui_pyqt6.recording_styles import build_display
        return build_display("island")

    def test_the_pill_is_the_same_width_loud_or_quiet(self, qapp):
        island = self._island()
        quiet = island._pill_rect()
        for _ in range(40):
            island.set_level(1.0)
        loud = island._pill_rect()
        assert quiet.width() == loud.width()

    def test_the_wave_is_a_history_not_a_single_value(self, qapp):
        island = self._island()
        island.set_level(1.0)
        island.set_level(0.0)
        assert len(island._history) == island.NUM_BARS
        assert island._history[-1] != island._history[-2]

    def test_the_wave_changes_what_is_drawn(self, qapp):
        from PyQt6.QtGui import QPixmap
        island = self._island()
        island.resize(island.preferred_size())
        quiet = QPixmap(island.size())
        island.render(quiet)
        for _ in range(40):
            island.set_level(1.0)
        loud = QPixmap(island.size())
        island.render(loud)
        assert quiet.toImage() != loud.toImage(), "the wave does not react"


class TestTheWaveMovesAtAReadableSpeed:
    """The badge ran its animation at 60fps and pushed a new bar on every
    frame, so the island's fourteen bars scrolled past in under a quarter of
    a second. It read as a jittery, aggressive flicker rather than as
    something listening to you."""

    @staticmethod
    def _frame_ms() -> int:
        from src.ui_pyqt6.recording_overlay import _ANIMATION_INTERVAL_MS

        return _ANIMATION_INTERVAL_MS

    def test_a_quarter_second_of_speech_does_not_fill_the_whole_wave(self, qapp):
        from src.ui_pyqt6.recording_styles import build_display

        for style in ("island", "waveform"):
            d = build_display(style)
            frames = int(250 / self._frame_ms())
            for _ in range(frames):
                d.set_level(1.0)
                d.advance()
            raised = [v for v in d._history if v > 0.05]
            assert len(raised) <= d.NUM_BARS / 2, (
                "%s filled %d of its %d bars in a quarter second, so the wave "
                "crosses the badge in well under a second"
                % (style, len(raised), d.NUM_BARS)
            )

    def test_one_frame_of_sound_does_not_throw_the_bar_most_of_the_way_up(self, qapp):
        from src.ui_pyqt6.recording_styles import build_display

        d = build_display("island")
        d.set_level(1.0)
        assert d.drawn_level <= 0.2, (
            "a single frame moved the drawn level to %.2f, which is what makes "
            "every syllable snap" % d.drawn_level
        )

    def test_the_idle_drift_takes_seconds_to_come_round(self, qapp):
        import math

        from src.ui_pyqt6.recording_styles import build_display

        d = build_display("orb")
        start = d._phase
        frames = 0
        while d._phase - start < 2 * math.pi and frames < 10_000:
            d.advance()
            frames += 1
        seconds = frames * self._frame_ms() / 1000
        assert seconds >= 3.0, (
            "the idle drift comes round every %.1fs, which reads as a pulse "
            "rather than as breathing" % seconds
        )
