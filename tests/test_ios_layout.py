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


def _chevron_pixels(row) -> set:
    """Distinct colours in the right-hand chevron strip of a rendered row."""
    from PyQt6.QtGui import QPixmap, QColor
    from src.ui_pyqt6.ios_layout import CHEVRON_WIDTH
    row.resize(240, 44)
    pm = QPixmap(row.size())
    pm.fill(QColor(0, 255, 0))
    row.render(pm)
    img = pm.toImage()
    seen = set()
    for x in range(row.width() - CHEVRON_WIDTH - 6, row.width()):
        for y in range(row.height()):
            seen.add(img.pixelColor(x, y).name())
    return seen


class TestDisclosureRow:
    def test_clicking_it_emits_clicked(self, qapp):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from src.ui_pyqt6.ios_layout import DisclosureRow
        row = DisclosureRow("History")
        seen = []
        row.clicked.connect(lambda: seen.append(True))
        QTest.mouseClick(row, Qt.MouseButton.LeftButton)
        assert seen == [True]

    def test_the_value_is_shown_on_the_right(self, qapp):
        from src.ui_pyqt6.ios_layout import DisclosureRow
        row = DisclosureRow("Language", value="English")
        assert row.value_label.text() == "English"

    def test_set_value_updates_it(self, qapp):
        from src.ui_pyqt6.ios_layout import DisclosureRow
        row = DisclosureRow("Language", value="English")
        row.set_value("Spanish")
        assert row.value_label.text() == "Spanish"

    def test_a_long_value_is_elided_rather_than_widening_the_row(self, qapp):
        from src.ui_pyqt6.ios_layout import DisclosureRow
        row = DisclosureRow("Microphone")
        row.setFixedWidth(320)
        row.set_value("Microphone Array (Realtek(R) Audio) - not connected")
        row.show()
        assert row.value_label.text().endswith("…")
        assert row.value_label.x() + row.value_label.width() <= 320

    def test_the_chevron_is_drawn_from_the_palette_at_paint_time(self, qapp, monkeypatch):
        """A row built before a theme change must still repaint in the new
        colours, so the chevron reads the palette when it paints rather than
        capturing one at construction.

        Both palettes share the same secondary grey, so a real theme switch
        cannot tell the two apart; a sentinel colour can.
        """
        from src.ui_pyqt6 import ios_layout
        from src.ui_pyqt6.theme import LIGHT
        row = ios_layout.DisclosureRow("History")
        sentinel = dict(LIGHT, secondary="#ff00ff")
        monkeypatch.setattr("src.ui_pyqt6.theme.current_palette", lambda: sentinel)
        assert any(c.startswith("#f") and "0" in c for c in _chevron_pixels(row)), (
            "the chevron ignored the palette in force when it painted"
        )
        assert "#ff00ff" in _chevron_pixels(row)
