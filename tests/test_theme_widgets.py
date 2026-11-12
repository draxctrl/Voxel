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
    """Style A: the list opens from the field. It is exactly as wide as the
    field, so it can never hang outside the window, and long names are elided
    with the full text on hover rather than widening the popup."""

    def test_popup_matches_the_field_width_exactly(self, qapp):
        c = ArrowComboBox()
        c.addItems(["a", "b"])
        c.resize(300, 36)
        c.show()
        c.showPopup()
        try:
            assert c.view().maximumWidth() == 300
            assert c.view().minimumWidth() == 300
        finally:
            c.hidePopup()

    def test_a_long_item_does_not_widen_the_popup(self, qapp):
        from PyQt6.QtCore import Qt
        c = ArrowComboBox()
        c.addItem("VoiceWave Microphone (EaseUS Virtual Device)" * 3)
        c.resize(120, 36)
        c.show()
        c.showPopup()
        try:
            # The combo has its own minimum width, so compare with what it
            # actually ended up being, not with the requested 120.
            assert c.view().maximumWidth() == c.width()
            assert c.itemData(0, Qt.ItemDataRole.ToolTipRole) == c.itemText(0), (
                "an elided name must still be readable on hover"
            )
        finally:
            c.hidePopup()

    def test_an_existing_tooltip_is_left_alone(self, qapp):
        from PyQt6.QtCore import Qt
        c = ArrowComboBox()
        c.addItem("Built-in microphone")
        c.setItemData(0, "The one in the lid", Qt.ItemDataRole.ToolTipRole)
        c.resize(200, 36)
        c.show()
        c.showPopup()
        try:
            assert c.itemData(0, Qt.ItemDataRole.ToolTipRole) == "The one in the lid"
        finally:
            c.hidePopup()

    def test_an_empty_combo_still_opens(self, qapp):
        c = ArrowComboBox()
        c.resize(240, 36)
        c.show()
        c.showPopup()
        try:
            assert c.view().maximumWidth() == 240
        finally:
            c.hidePopup()


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
