"""iOS grouped-card layout widgets. Runs headless via Qt's offscreen platform."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QComboBox, QFrame


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _separators(card) -> int:
    return len([c for c in card.findChildren(QFrame) if c.objectName() == "row_separator"])


class TestSectionHeader:
    def test_text_is_upper_cased(self, qapp):
        from src.ui_pyqt6.ios_layout import section_header
        assert section_header("Recording").text() == "RECORDING"

    def test_object_name_lets_the_stylesheet_reach_it(self, qapp):
        from src.ui_pyqt6.ios_layout import section_header
        assert section_header("Recording").objectName() == "group_header"


class TestGroupCard:
    def test_first_row_gets_no_separator_above_it(self, qapp):
        from src.ui_pyqt6.ios_layout import GroupCard, SettingsRow
        card = GroupCard()
        card.add_row(SettingsRow("One"))
        assert _separators(card) == 0

    def test_each_later_row_is_separated_from_the_one_before(self, qapp):
        from src.ui_pyqt6.ios_layout import GroupCard, SettingsRow
        card = GroupCard()
        for n in ("One", "Two", "Three"):
            card.add_row(SettingsRow(n))
        assert _separators(card) == 2

    def test_separators_are_inset_so_they_do_not_touch_the_left_edge(self, qapp):
        from src.ui_pyqt6.ios_layout import GroupCard, SettingsRow, SEPARATOR_INSET
        card = GroupCard()
        card.add_row(SettingsRow("One"))
        card.add_row(SettingsRow("Two"))
        sep = [c for c in card.findChildren(QFrame) if c.objectName() == "row_separator"][0]
        assert sep.layout().contentsMargins().left() == SEPARATOR_INSET


class TestSettingsRow:
    def test_title_is_shown(self, qapp):
        from src.ui_pyqt6.ios_layout import SettingsRow
        assert SettingsRow("Microphone").title_label.text() == "Microphone"

    def test_no_subtitle_means_no_subtitle_label(self, qapp):
        from src.ui_pyqt6.ios_layout import SettingsRow
        assert SettingsRow("Microphone").subtitle_label is None

    def test_subtitle_is_secondary_styled(self, qapp):
        from src.ui_pyqt6.ios_layout import SettingsRow
        row = SettingsRow("Mode", subtitle="How your words are cleaned up")
        assert row.subtitle_label.objectName() == "row_sub"

    def test_the_control_is_reparented_into_the_row(self, qapp):
        from src.ui_pyqt6.ios_layout import SettingsRow
        combo = QComboBox()
        row = SettingsRow("Language", control=combo)
        assert combo.parent() is row
