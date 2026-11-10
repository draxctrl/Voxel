"""iOS-styled controls. Runs headless via Qt's offscreen platform."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.theme import LIGHT, DARK, IOSSwitch


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestIOSSwitch:
    def test_is_a_checkbox_so_existing_call_sites_still_work(self, qapp):
        """Settings calls setChecked/isChecked/stateChanged on these."""
        from PyQt6.QtWidgets import QCheckBox
        s = IOSSwitch("Mute sounds")
        assert isinstance(s, QCheckBox)
        s.setChecked(True)
        assert s.isChecked() is True
        s.setChecked(False)
        assert s.isChecked() is False

    def test_emits_state_changes(self, qapp):
        # _sync_offline_state depends on this signal.
        s = IOSSwitch("Offline mode")
        seen = []
        s.stateChanged.connect(lambda v: seen.append(v))
        s.setChecked(True)
        assert len(seen) == 1

    def test_on_colour_is_voxel_indigo_not_apple_green(self, qapp):
        s = IOSSwitch("x")
        s.set_palette(DARK)
        assert s._on_colour().name().lower() == "#6366f1"

    def test_off_colour_follows_the_palette(self, qapp):
        s = IOSSwitch("x")
        s.set_palette(DARK)
        assert s._off_colour().name().lower() == DARK["switch_off"].lower()
        s.set_palette(LIGHT)
        assert s._off_colour().name().lower() == LIGHT["switch_off"].lower()

    def test_reports_a_size_that_fits_the_pill_and_label(self, qapp):
        s = IOSSwitch("Mute sounds")
        hint = s.sizeHint()
        assert hint.width() > 0
        assert hint.height() >= 28

    def test_paints_without_error_in_both_states(self, qapp):
        from PyQt6.QtGui import QPixmap
        s = IOSSwitch("Run at login")
        s.resize(200, 32)
        for checked in (False, True):
            s.setChecked(checked)
            pixmap = QPixmap(s.size())
            s.render(pixmap)   # raises if paintEvent is broken
