"""The bundled Phosphor icon set and its tinting loader."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui_pyqt6.icons import ICON_NAMES, icon, _svg_path


class TestTheIconSetIsComplete:
    def test_every_named_icon_has_a_file(self):
        for name in ICON_NAMES:
            assert _svg_path(name) is not None, name

    def test_an_icon_is_tinted_to_the_colour_asked_for(self, qapp):
        image = icon("microphone", "#6366f1", 32).pixmap(32, 32).toImage()
        colours = {
            image.pixelColor(x, y).name()
            for x in range(32)
            for y in range(32)
            if image.pixelColor(x, y).alpha() > 200
        }
        assert "#6366f1" in colours


class TestAMissingIconDoesNotTakeTheWindowDown:
    def test_an_unknown_name_returns_a_usable_blank_icon(self, qapp):
        result = icon("no-such-icon", "#ffffff")
        assert result.isNull() is False
        assert result.pixmap(18, 18).isNull() is False
