"""Recording overlay behaviour. Runs headless via Qt's offscreen platform."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def overlay(qapp):
    from src.ui_pyqt6.recording_overlay import RecordingOverlay
    o = RecordingOverlay()
    yield o
    o.deleteLater()


class TestMicText:
    def test_set_mic_text_updates_the_label(self, overlay):
        overlay.set_mic_text("Blue Yeti")
        assert overlay._display.mic_text == "Blue Yeti"

    def test_mic_text_survives_hide(self, overlay):
        """The warning must persist across dictations, not show once.

        _on_hide() restores the label from _mic_name, so set_mic_text must
        update that too or the warning is wiped after the first recording.
        """
        overlay.set_mic_text("⚠ Blue Yeti not found — using Realtek Mic")
        overlay._on_hide()
        assert "not found" in overlay._display.mic_text

    def test_long_mic_text_is_truncated(self, overlay):
        """Warning strings are far longer than device names and would overflow."""
        long_text = "⚠ Microphone (Blue Yeti Stereo) not found — using Microphone Array (Realtek Audio)"
        overlay.set_mic_text(long_text)
        assert len(overlay._display.mic_text) <= 28
        assert overlay._display.mic_text.endswith("…")


class TestOverlayStaysTranslucent:
    """The overlay is a floating hand-painted pill on a translucent window.

    Styling bare QWidget on the QApplication reaches it (Qt type selectors match
    subclasses) and paints an opaque rectangle over the pill — turning the
    badge into a hard-edged slab on every dictation.
    """

    def _corner_and_centre(self, qapp, overlay):
        from PyQt6.QtGui import QPixmap, QColor
        overlay.show_recording()
        qapp.processEvents()
        overlay.resize(320, 110)
        pm = QPixmap(overlay.size())
        pm.fill(QColor(0, 255, 0))        # sentinel: survives only if transparent
        overlay.render(pm)
        img = pm.toImage()
        return img.pixelColor(2, 2).name(), img.pixelColor(160, 55).name()

    def test_corner_stays_transparent_under_an_applied_theme(self, qapp, overlay):
        from src.ui_pyqt6.theme import apply_theme
        for theme in ("dark", "light"):
            apply_theme(qapp, theme)
            corner, _ = self._corner_and_centre(qapp, overlay)
            assert corner == "#00ff00", (
                f"{theme}: overlay corner is {corner} - the window is opaque"
            )

    def test_card_is_still_painted_under_an_applied_theme(self, qapp, overlay):
        from src.ui_pyqt6.theme import apply_theme
        apply_theme(qapp, "light")
        _, centre = self._corner_and_centre(qapp, overlay)
        assert centre != LIGHT_BG, "overlay centre was flooded by the app background"


LIGHT_BG = "#f2f2f7"


class TestOverlayHostsAStyle:
    """The overlay became a host: it builds the chosen display, feeds it the
    real microphone level, and positions itself."""

    def test_it_builds_the_configured_style(self, qapp):
        from src.ui_pyqt6.recording_overlay import RecordingOverlay
        for style_id in ("orb", "waveform", "island"):
            o = RecordingOverlay(style=style_id)
            assert o.style == style_id
            assert o._display.style_id == style_id
            o.deleteLater()

    def test_an_unknown_configured_style_still_shows_something(self, qapp):
        """A hand-edited or downgraded config must not break every dictation."""
        from src.ui_pyqt6.recording_overlay import RecordingOverlay
        from src.ui_pyqt6.recording_styles import DEFAULT_STYLE
        o = RecordingOverlay(style="spinning-pizza")
        assert o._display.style_id == DEFAULT_STYLE
        o.deleteLater()

    def test_the_level_provider_feeds_the_display(self, qapp):
        from src.ui_pyqt6.recording_overlay import RecordingOverlay
        o = RecordingOverlay(level_provider=lambda: 0.75)
        o._tick_animation()
        assert o._display.level == pytest.approx(0.75)
        o.deleteLater()

    def test_a_failing_level_provider_does_not_stop_the_animation(self, qapp):
        """A provider that raises must cost a frame, never the recording."""
        from src.ui_pyqt6.recording_overlay import RecordingOverlay

        def boom():
            raise RuntimeError("audio subsystem went away")

        o = RecordingOverlay(level_provider=boom)
        o.show_recording()
        qapp.processEvents()
        o._tick_animation()
        o._tick_animation()
        assert o._wave_timer.isActive()
        o.deleteLater()

    def test_no_level_provider_is_fine(self, qapp):
        from src.ui_pyqt6.recording_overlay import RecordingOverlay
        o = RecordingOverlay()
        o._tick_animation()
        assert o._display.level == 0.0
        o.deleteLater()

    def test_every_style_keeps_a_translucent_window(self, qapp):
        """The application stylesheet reaches this window; if it wins, the
        badge becomes an opaque slab on every dictation."""
        from PyQt6.QtGui import QPixmap, QColor
        from src.ui_pyqt6.recording_overlay import RecordingOverlay
        from src.ui_pyqt6.theme import apply_theme
        for theme in ("light", "dark"):
            apply_theme(qapp, theme)
            for style_id in ("orb", "waveform", "island"):
                o = RecordingOverlay(style=style_id)
                o.show_recording()
                qapp.processEvents()
                pm = QPixmap(o.size())
                pm.fill(QColor(0, 255, 0))
                o.render(pm)
                corner = pm.toImage().pixelColor(1, 1).name()
                assert corner == "#00ff00", (
                    f"{style_id}/{theme}: corner is {corner} - the window is opaque"
                )
                o.deleteLater()

    def test_set_style_swaps_the_display(self, qapp):
        from src.ui_pyqt6.recording_overlay import RecordingOverlay
        o = RecordingOverlay(style="orb")
        o.set_style("island")
        assert o.style == "island"
        assert o._display.style_id == "island"
        o.deleteLater()


class TestOverlayResetsBetweenDictations:
    """The overlay object is reused for every dictation, so anything left
    behind by the last one shows up at the start of the next."""

    def test_elapsed_restarts_at_zero(self, qapp, overlay):
        overlay.show_recording()
        for _ in range(5):
            overlay._tick_elapsed()
        assert overlay._display.elapsed_text == "0:05"
        overlay._on_hide()
        overlay.show_recording()
        assert overlay._display.elapsed_text == "0:00"

    def test_the_level_is_cleared_so_the_badge_does_not_open_mid_shout(self, qapp, overlay):
        overlay.show_recording()
        overlay._display.set_level(0.95)
        overlay._on_hide()
        overlay.show_recording()
        assert overlay._display.level == 0.0

    def test_the_mic_warning_survives_but_the_clipboard_notice_does_not(self, qapp, overlay):
        """set_mic_text is a standing warning; "Paste with Ctrl+V" is a notice
        for one dictation only."""
        overlay._on_set_mic_text("⚠ Blue Yeti not found")
        overlay._on_show_clipboard()
        assert "Paste" in overlay._display.mic_text
        overlay._on_hide()
        overlay.show_recording()
        assert "not found" in overlay._display.mic_text

    def test_timers_stop_when_hidden(self, qapp, overlay):
        """A hidden badge animating at 60fps burns a core for nothing."""
        overlay.show_recording()
        assert overlay._wave_timer.isActive()
        assert overlay._elapsed_timer.isActive()
        overlay._on_hide()
        assert not overlay._wave_timer.isActive()
        assert not overlay._elapsed_timer.isActive()

    def test_the_state_goes_back_to_recording_after_processing(self, qapp, overlay):
        overlay.show_recording()
        overlay._on_show_processing()
        overlay._on_hide()
        overlay.show_recording()
        assert overlay._display._status_text() == "Listening"
