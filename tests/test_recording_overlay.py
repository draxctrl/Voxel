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
        assert overlay._mic_label.text() == "Blue Yeti"

    def test_mic_text_survives_hide(self, overlay):
        """The warning must persist across dictations, not show once.

        _on_hide() restores the label from _mic_name, so set_mic_text must
        update that too or the warning is wiped after the first recording.
        """
        overlay.set_mic_text("⚠ Blue Yeti not found — using Realtek Mic")
        overlay._on_hide()
        assert "not found" in overlay._mic_label.text()

    def test_long_mic_text_is_truncated(self, overlay):
        """Warning strings are far longer than device names and would overflow."""
        long_text = "⚠ Microphone (Blue Yeti Stereo) not found — using Microphone Array (Realtek Audio)"
        overlay.set_mic_text(long_text)
        assert len(overlay._mic_label.text()) <= 28
        assert overlay._mic_label.text().endswith("…")


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
