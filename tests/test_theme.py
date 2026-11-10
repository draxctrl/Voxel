"""Theme tokens, system theme detection, and the single shared stylesheet."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.theme import LIGHT, DARK, detect_system_theme, palette_for


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
