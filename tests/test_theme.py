"""Theme tokens, system theme detection, and the single shared stylesheet."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.theme import (
    LIGHT,
    DARK,
    detect_system_theme,
    palette_for,
    build_qss,
    load_fonts,
)
from src.main import _get_assets_dir as _assets_dir


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestPaletteTokens:
    def test_both_palettes_define_the_same_tokens(self):
        assert set(LIGHT) == set(DARK)

    def test_light_palette_matches_the_spec(self):
        assert LIGHT["bg"] == "#F2F2F7"
        assert LIGHT["card"] == "#FFFFFF"
        assert LIGHT["separator"] == "#D6D6DA"
        assert LIGHT["text"] == "#000000"
        assert LIGHT["secondary"] == "#8E8E93"
        assert LIGHT["switch_off"] == "#E9E9EB"

    def test_dark_palette_matches_the_spec(self):
        assert DARK["bg"] == "#000000"
        assert DARK["card"] == "#1C1C1E"
        assert DARK["separator"] == "#2E2E31"
        assert DARK["text"] == "#FFFFFF"
        assert DARK["secondary"] == "#8E8E93"
        assert DARK["switch_off"] == "#39393D"

    def test_accent_is_voxel_indigo_in_both_palettes(self):
        """Never iOS blue, and switches are never Apple green."""
        for p in (LIGHT, DARK):
            assert p["accent"] == "#6366f1"
            assert p["accent"] != "#007AFF"
            assert p["switch_off"] != "#34C759"


class TestSystemThemeDetection:
    def test_reads_light_from_the_registry(self, monkeypatch):
        monkeypatch.setattr("src.ui_pyqt6.theme._read_apps_use_light_theme", lambda: 1)
        assert detect_system_theme() == "light"

    def test_reads_dark_from_the_registry(self, monkeypatch):
        monkeypatch.setattr("src.ui_pyqt6.theme._read_apps_use_light_theme", lambda: 0)
        assert detect_system_theme() == "dark"

    def test_falls_back_to_dark_when_the_key_is_missing(self, monkeypatch):
        """Older Windows, or locked-down policy: default, never crash."""
        def boom():
            raise FileNotFoundError("no such registry key")
        monkeypatch.setattr("src.ui_pyqt6.theme._read_apps_use_light_theme", boom)
        assert detect_system_theme() == "dark"

    def test_falls_back_to_dark_when_the_value_is_unexpected(self, monkeypatch):
        monkeypatch.setattr("src.ui_pyqt6.theme._read_apps_use_light_theme", lambda: None)
        assert detect_system_theme() == "dark"


class TestPaletteFor:
    def test_known_names(self):
        assert palette_for("light") is LIGHT
        assert palette_for("dark") is DARK

    def test_unknown_name_returns_dark(self):
        assert palette_for("solarized") is DARK


class TestBuildQss:
    def test_uses_the_palette_colours(self):
        assert DARK["card"] in build_qss(DARK)
        assert LIGHT["card"] in build_qss(LIGHT)

    def test_leaves_no_unsubstituted_placeholders(self):
        qss = build_qss(DARK)
        assert "{bg}" not in qss and "{card}" not in qss and "{accent}" not in qss

    def test_scrollbar_reserves_clearance_from_content(self):
        """The bar must not sit on top of the cards it scrolls."""
        qss = build_qss(DARK)
        assert "QScrollBar:vertical" in qss
        vertical_block = qss.split("QScrollBar:vertical")[1].split("}")[0]
        assert "margin" in vertical_block

    def test_scrollbar_styles_every_subcontrol(self):
        """Any subcontrol left unstyled falls back to the native Windows scrollbar."""
        qss = build_qss(DARK)
        for part in ("add-line", "sub-line", "add-page", "sub-page"):
            assert part in qss, f"{part} unstyled - Qt will draw the native bar"

    def test_horizontal_scrollbar_is_styled_too(self):
        assert "QScrollBar:horizontal" in build_qss(DARK)

    def test_combo_popup_is_styled(self):
        assert "QComboBox QAbstractItemView" in build_qss(DARK)

    def test_font_stack_falls_back_to_segoe(self):
        """If Inter fails to load, text must still render in the system face."""
        assert '"Inter", "Segoe UI"' in build_qss(DARK)

    def test_scroll_area_border_is_removed_centrally(self):
        # Per-window "QScrollArea { border: none }" overrides are what sent
        # Stats and the FAQ back to native scrollbars.
        assert "QScrollArea" in build_qss(DARK)


class TestFontLoading:
    def test_returns_false_for_a_missing_directory(self, qapp):
        """A frozen build with the fonts left out must not crash on startup."""
        assert load_fonts("C:/definitely/not/here") is False

    def test_registers_inter_from_the_bundled_assets(self, qapp):
        from PyQt6.QtGui import QFontDatabase
        assert load_fonts(_assets_dir()) is True
        assert "Inter" in QFontDatabase.families()

    def test_is_safe_to_call_twice(self, qapp):
        assert load_fonts(_assets_dir()) is True
        assert load_fonts(_assets_dir()) is True
