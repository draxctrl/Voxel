"""The shared pane furniture: rows that are actually drawn as rows."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.panes.widgets import ChoiceRow, SwitchRow
from src.ui_pyqt6.theme import palette_for


@pytest.mark.parametrize("theme", ["dark", "light"])
class TestARowIsDrawnAsACard:
    """A stylesheet built with the wrong formatter leaves literal braces in
    the rule, Qt discards it silently, and the row renders as bare text on
    the pane background - which looked fine to the tests and wrong on screen."""

    def test_a_choice_row_has_a_usable_stylesheet(self, qapp, theme):
        p = palette_for(theme)
        row = ChoiceRow("x", "Title", "Subtitle")
        row.restyle(p)
        sheet = row.styleSheet()
        assert "{{" not in sheet and "}}" not in sheet, f"unformatted braces: {sheet}"
        assert "background-color: " + p["row"] in sheet
        assert p["row_border"] in sheet

    def test_a_selected_choice_row_takes_the_accent_border(self, qapp, theme):
        p = palette_for(theme)
        row = ChoiceRow("x", "Title")
        row.restyle(p)
        row.set_selected(True)
        assert p["accent"] in row.styleSheet()

    def test_a_switch_row_has_a_usable_stylesheet(self, qapp, theme):
        p = palette_for(theme)
        row = SwitchRow("Label", "Description")
        row.restyle(p)
        sheet = row.styleSheet()
        assert "{{" not in sheet and "}}" not in sheet, f"unformatted braces: {sheet}"
        assert "background-color: " + p["row"] in sheet


class TestAPaneDoesNotStretchItsRowsAcrossAWideWindow:
    """A settings row 900px wide puts its label and its control a screen
    apart. Content is capped and the rest is margin."""

    def test_the_body_caps_its_content_width(self, qapp, ctx):
        from src.ui_pyqt6.panes.widgets import CONTENT_MAX_WIDTH
        from src.ui_pyqt6.panes.writing_style import WritingStylePane

        pane = WritingStylePane(ctx)
        pane.restyle(ctx.palette())
        pane.resize(1400, 620)
        pane.show()
        qapp.processEvents()
        row = pane._offline
        assert row.width() <= CONTENT_MAX_WIDTH, (
            f"a row is {row.width()}px wide on a 1400px pane"
        )

    def test_the_cap_is_wide_enough_for_the_designed_window(self, qapp):
        from src.ui_pyqt6.panes.widgets import CONTENT_MAX_WIDTH

        # 980 window - 198 rail - 2x28 margins = 726 of usable pane.
        assert 600 <= CONTENT_MAX_WIDTH <= 726


class TestEveryRowActuallyPaintsItsBackground:
    """A plain QWidget ignores a stylesheet background unless it is a QFrame
    or sets WA_StyledBackground, so a row can carry a perfectly correct
    stylesheet and still render as bare text on the pane. Only pixels tell."""

    def _rendered_corner(self, qapp, widget, palette):
        """Render the row inside a parent, as it really lives.

        A top-level widget paints its stylesheet background whatever class
        it is; a child one only does so if it is a QFrame or sets
        WA_StyledBackground. Rendering it unparented would pass on a row
        that is invisible in the window.
        """
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QVBoxLayout, QWidget

        host = QWidget()
        host.setObjectName("host")
        host.setStyleSheet("QWidget#host { background-color: %s; }" % palette["pane"])
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        widget.restyle(palette)
        host.resize(600, 56)
        host.show()
        qapp.processEvents()
        pixmap = QPixmap(host.size())
        host.render(pixmap)
        centre = widget.mapTo(host, widget.rect().center())
        return pixmap.toImage().pixelColor(centre.x(), centre.y()).name().lower()

    def test_a_switch_row_paints_the_row_colour(self, qapp):
        from src.ui_pyqt6.panes.widgets import SwitchRow

        p = palette_for("dark")
        found = self._rendered_corner(qapp, SwitchRow("Label", "Description"), p)
        assert found == p["row"].lower(), f"the row painted {found}, not {p['row']}"

    def test_a_shortcut_row_paints_the_row_colour(self, qapp):
        from src.ui_pyqt6.panes.shortcuts import _ShortcutRow

        p = palette_for("dark")
        found = self._rendered_corner(qapp, _ShortcutRow("Label", "Description"), p)
        assert found == p["row"].lower(), f"the row painted {found}, not {p['row']}"

    def test_a_choice_row_paints_the_row_colour(self, qapp):
        p = palette_for("dark")
        found = self._rendered_corner(qapp, ChoiceRow("x", "Title", "Subtitle"), p)
        assert found == p["row"].lower(), f"the row painted {found}, not {p['row']}"
