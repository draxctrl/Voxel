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
    apply_theme,
    current_palette,
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


class TestNoDuplicateTheme:
    """The spec's anti-goal: two stylesheet copies that drift apart."""

    def test_settings_ui_has_no_private_theme_copy(self):
        import src.ui_pyqt6.settings_ui as s
        for name in ("_QSS", "_BG", "_CARD", "_ArrowComboBox", "_TickCheckBox"):
            assert not hasattr(s, name), f"{name} duplicates theme.py"

    def test_no_window_defines_its_own_scrollbar_rules(self):
        import inspect
        import src.ui_pyqt6.history_window as h
        import src.ui_pyqt6.stats_window as st
        import src.ui_pyqt6.settings_ui as se
        for mod in (h, st, se):
            assert "QScrollBar" not in inspect.getsource(mod), (
                f"{mod.__name__} styles scrollbars itself; theme.py owns that"
            )


class TestApplyTheme:
    def test_sets_the_application_stylesheet(self, qapp):
        name = apply_theme(qapp, "light")
        assert name == "light"
        assert LIGHT["card"] in qapp.styleSheet()

    def test_current_palette_follows_the_applied_theme(self, qapp):
        apply_theme(qapp, "light")
        assert current_palette() is LIGHT
        apply_theme(qapp, "dark")
        assert current_palette() is DARK

    def test_theme_change_replaces_the_old_palette_entirely(self, qapp):
        """A half-light, half-dark window is worse than either."""
        apply_theme(qapp, "dark")
        apply_theme(qapp, "light")
        sheet = qapp.styleSheet()
        assert LIGHT["card"] in sheet
        assert DARK["card"] not in sheet

    def test_defaults_to_the_system_theme_when_none_given(self, qapp, monkeypatch):
        monkeypatch.setattr("src.ui_pyqt6.theme.detect_system_theme", lambda: "light")
        assert apply_theme(qapp) == "light"


#: Colours that only ever belong to a dark UI. If one of these survives in a
#: widget's own stylesheet after switching to light, that widget is stranded.
_DARK_ONLY = (
    "#1C1C1E", "#2E2E31", "#39393D", "#48484A",   # dark palette
    "#1a1a1a", "#2a2a2a", "#0f0f0f", "#111111",   # legacy flat-dark palette
    "#e8e8e8", "#777777", "#333", "#1e1e3e",      # legacy literals
)


def _stranded_dark_styles(widget):
    """Child stylesheets still carrying dark-only colours."""
    found = []
    for child in widget.findChildren(object):
        sheet = getattr(child, "styleSheet", None)
        if sheet is None:
            continue
        try:
            text = sheet()
        except TypeError:
            continue
        for token in _DARK_ONLY:
            if token.lower() in text.lower():
                found.append((type(child).__name__, token, text[:60]))
                break
    return found


class TestNoHalfThemedWindows:
    """Review Focus 4: a theme change must restyle a window completely.

    Asserting on qapp.styleSheet() alone cannot fail for widgets carrying their
    own inline styles — which is the entire failure mode.
    """

    def _settings(self, tmp_path):
        from src.config import Config
        from src.ui_pyqt6.settings_ui import SettingsWindow
        cfg = Config(config_path=str(tmp_path / "c.json"))
        cfg.load()
        return SettingsWindow(config=cfg, on_save=lambda: None,
                              on_validate_key=lambda k: True, on_quit=lambda: None)

    def _history_and_stats(self, tmp_path):
        from src.history import HistoryStore
        from src.ui_pyqt6.history_window import HistoryWindow
        from src.ui_pyqt6.stats_window import StatsWindow
        store = HistoryStore(db_path=str(tmp_path / "h.db"))
        return HistoryWindow(store), StatsWindow(store)

    def test_settings_has_no_stranded_dark_styles_in_light(self, qapp, tmp_path):
        apply_theme(qapp, "light")
        stranded = _stranded_dark_styles(self._settings(tmp_path))
        assert stranded == [], f"stranded dark styles: {stranded}"

    def test_history_and_stats_have_no_stranded_dark_styles_in_light(self, qapp, tmp_path):
        apply_theme(qapp, "light")
        history, stats = self._history_and_stats(tmp_path)
        assert _stranded_dark_styles(history) == []
        assert _stranded_dark_styles(stats) == []

    def test_switching_theme_restyles_an_already_built_window(self, qapp, tmp_path):
        """The real scenario: Voxel is running when Windows flips to light."""
        apply_theme(qapp, "dark")
        window = self._settings(tmp_path)
        apply_theme(qapp, "light")
        stranded = _stranded_dark_styles(window)
        assert stranded == [], f"stranded after switch: {stranded}"


class TestLegacyConstantsRemoved:
    def test_theme_no_longer_exports_the_flat_dark_palette(self):
        import src.ui_pyqt6.theme as t
        for name in ("BG", "CARD", "BORDER", "INPUT_BG", "TEXT", "SUBTLE", "QSS"):
            assert not hasattr(t, name), f"{name} is a leftover flat-dark constant"


class TestGroupedCardStyling:
    """The grouped cards are styled from the palette like everything else."""

    def test_card_rule_uses_the_palette_card_colour(self):
        from src.ui_pyqt6.theme import build_qss, palette_for
        for name in ("light", "dark"):
            p = palette_for(name)
            qss = build_qss(p)
            assert f"QFrame#group_card" in qss
            assert f"background-color: {p['card']}" in qss

    def test_hairline_uses_the_separator_colour(self):
        from src.ui_pyqt6.theme import build_qss, palette_for
        for name in ("light", "dark"):
            p = palette_for(name)
            assert f"background-color: {p['separator']}" in build_qss(p)

    def test_rows_opt_out_of_the_window_background(self):
        """A row is a bare QWidget: without this it paints over its own card."""
        from src.ui_pyqt6.theme import build_qss, LIGHT
        assert "QWidget#settings_row {\n    background: transparent;" in build_qss(LIGHT)


class TestSwitchesDoNotPaintTheirOwnBackground:
    """A switch is a QCheckBox, so the QWidget background rule reaches it and
    paints a window-coloured box around the pill when it sits on a card."""

    def test_checkbox_opts_out_of_the_window_background(self):
        from src.ui_pyqt6.theme import build_qss, LIGHT
        assert "QCheckBox {\n    background: transparent;" in build_qss(LIGHT)

    def test_a_switch_on_a_card_leaves_the_card_showing(self, qapp):
        """Rendered proof: the pixels around the pill must be card colour."""
        from PyQt6.QtGui import QPixmap, QColor
        from src.ui_pyqt6.theme import apply_theme, IOSSwitch, LIGHT
        from src.ui_pyqt6.ios_layout import GroupCard, SettingsRow
        apply_theme(qapp, "light")
        card = GroupCard()
        switch = IOSSwitch()
        switch.setFixedWidth(IOSSwitch.TRACK_W + 4)
        card.add_row(SettingsRow("Offline mode", control=switch))
        card.resize(360, 44)
        card.show()
        pm = QPixmap(card.size())
        card.render(pm)
        img = pm.toImage()
        # The switch widget is a few pixels wider than the pill it draws. That
        # sliver is where a window-coloured background shows up as a box.
        sliver_x = switch.x() + switch.width() - 2
        found = img.pixelColor(sliver_x, 22).name().lower()
        assert found == LIGHT["card"].lower(), (
            f"the switch painted {found} over its card at x={sliver_x}"
        )


class TestTheSwitchHasNoNativeIndicator:
    """IOSSwitch draws its own pill. Qt also draws a QCheckBox indicator
    underneath it, and its border shows as an outlined box around the pill —
    which is what makes a row of 'off' switches look wrong."""

    def test_the_indicator_is_styled_away(self, qapp):
        from src.ui_pyqt6.theme import IOSSwitch
        qss = IOSSwitch().styleSheet()
        for rule in ("border: none", "background: transparent", "image: none"):
            assert rule in qss, f"the indicator is still drawn: {rule!r} missing"

    # There is deliberately no rendered test here. The native indicator is
    # drawn by the platform style, and pytest runs on the offscreen platform,
    # whose style does not draw it — a pixel test would pass while the bug was
    # live on Windows. The stylesheet assertion above is the honest check; the
    # visual proof is a real-platform render.


class TestTheDropdownOpensFromItsField:
    """Style A: the list is the field growing downward — same width, flush
    against its bottom edge, and it never spills outside the window."""

    def _combo(self):
        from src.ui_pyqt6.theme import ArrowComboBox
        combo = ArrowComboBox()
        combo.addItems([
            "Hold to talk",
            "VoiceWave Microphone (EaseUS Virtual Device) with a very long name",
        ])
        combo.setFixedWidth(200)
        return combo

    def test_the_popup_is_never_wider_than_the_field(self, qapp):
        combo = self._combo()
        combo.show()
        combo.showPopup()
        try:
            assert combo.view().maximumWidth() == combo.width()
            assert combo.view().window().width() <= combo.width() + 2, (
                "the popup is wider than the field, so it hangs outside the window"
            )
        finally:
            combo.hidePopup()

    def test_the_popup_window_is_transparent_so_its_corners_can_round(self, qapp):
        from PyQt6.QtCore import Qt
        combo = self._combo()
        assert combo.view().window().testAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        ), "the popup window is opaque, so a border-radius leaves black corners"

    def test_the_list_is_joined_to_the_bottom_of_the_field(self):
        from src.ui_pyqt6.theme import build_qss, DARK
        block = build_qss(DARK).split("QComboBox QAbstractItemView {")[1].split("}")[0]
        assert "border-top: none" in block
        assert "border-top-left-radius: 0px" in block
        assert "border-bottom-left-radius: 10px" in block
