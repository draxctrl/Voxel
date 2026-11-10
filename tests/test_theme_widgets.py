"""iOS-styled controls. Runs headless via Qt's offscreen platform."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.theme import LIGHT, DARK, IOSSwitch, ArrowComboBox


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


class TestArrowComboBoxPopup:
    """The popup used to be resized to a text-derived width and repositioned,
    which is why the dropdowns read as detached from their field."""

    def test_popup_is_never_narrower_than_the_field(self, qapp):
        c = ArrowComboBox()
        c.addItems(["a", "b"])
        c.resize(300, 36)
        assert c._popup_width() >= 300

    def test_popup_grows_for_long_items(self, qapp):
        c = ArrowComboBox()
        c.addItem("a" * 120)
        c.resize(120, 36)
        assert c._popup_width() > 120

    def test_popup_width_is_capped_to_stay_usable(self, qapp):
        c = ArrowComboBox()
        c.addItem("x" * 4000)
        c.resize(120, 36)
        assert c._popup_width() <= 900

    def test_empty_combo_still_reports_the_field_width(self, qapp):
        c = ArrowComboBox()
        c.resize(240, 36)
        assert c._popup_width() >= 240


class TestSwitchFollowsLiveTheme:
    """A switch built after apply_theme must use the theme in force, not the
    palette it was constructed with — otherwise light mode shows dark pills."""

    def test_switch_created_after_apply_theme_uses_it(self, qapp):
        from src.ui_pyqt6.theme import apply_theme
        apply_theme(qapp, "light")
        s = IOSSwitch("Run at login")          # created AFTER the theme
        assert s._off_colour().name().lower() == LIGHT["switch_off"].lower()

    def test_switch_tracks_a_later_theme_change(self, qapp):
        from src.ui_pyqt6.theme import apply_theme
        s = IOSSwitch("Run at login")
        apply_theme(qapp, "dark")
        assert s._off_colour().name().lower() == DARK["switch_off"].lower()
        apply_theme(qapp, "light")
        assert s._off_colour().name().lower() == LIGHT["switch_off"].lower()

    def test_explicit_palette_still_wins(self, qapp):
        from src.ui_pyqt6.theme import apply_theme
        apply_theme(qapp, "light")
        s = IOSSwitch("x")
        s.set_palette(DARK)
        assert s._off_colour().name().lower() == DARK["switch_off"].lower()
