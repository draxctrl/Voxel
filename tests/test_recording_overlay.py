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
