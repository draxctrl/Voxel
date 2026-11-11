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


def _luminance(hex_colour: str) -> float:
    """WCAG relative luminance of a #rrggbb string."""
    h = hex_colour.lstrip("#")
    parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in parts]
    r, g, b = linear
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: str, bg: str) -> float:
    a, b = _luminance(fg), _luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


class TestTheDarkSurfacesAreTheOnesTheDesignFixes:
    def test_the_rail_is_darker_than_the_pane(self):
        assert DARK["rail"] == "#16171a"
        assert DARK["pane"] == "#1e1f23"
        assert DARK["row"] == "#2a2c32"
        assert DARK["row_border"] == "#32343b"

    def test_the_text_colours_are_the_ones_the_design_fixes(self):
        assert DARK["muted"] == "#9b9ca5"
        assert DARK["faint"] == "#6d6f78"


class TestBothPalettesDefineEveryKey:
    def test_light_and_dark_have_the_same_keys(self):
        assert set(LIGHT) == set(DARK)

    def test_every_sidebar_key_exists(self):
        for key in ("rail", "rail_text", "rail_text_active", "rail_active_bg",
                    "pane", "row", "row_border", "muted", "faint"):
            assert key in DARK and key in LIGHT, key


class TestTextStaysReadableOnEverySurface:
    @pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
    @pytest.mark.parametrize("fg,bg", [("text", "pane"), ("text", "row"),
                                       ("muted", "row"), ("rail_text", "rail"),
                                       ("rail_text_active", "rail_active_bg")])
    def test_contrast_is_at_least_4_5_to_1(self, palette, fg, bg):
        ratio = _contrast(palette[fg], palette[bg])
        assert ratio >= 4.5, f"{fg} on {bg} is only {ratio:.2f}:1"


class TestTheLegacySurfacesFollowTheNewDesign:
    """ArrowComboBox and IOSSwitch read `card`, `input_bg` and `separator`.
    If those still hold the old iOS values, every control the new panes
    reuse sits in a differently-coloured hole."""

    def test_the_card_colour_is_the_new_row_colour(self):
        for p in (LIGHT, DARK):
            assert p["card"] == p["row"]
            assert p["input_bg"] == p["row"]
            assert p["separator"] == p["row_border"]
            assert p["bg"] == p["pane"]
            assert p["secondary"] == p["muted"]


class TestTheAccentIsVoxelIndigo:
    def test_accent_is_voxel_indigo_in_both_palettes(self):
        """Never iOS blue, and switches are never Apple green."""
        for p in (LIGHT, DARK):
            assert p["accent"] == "#6366f1"
            assert p["accent_hover"] == "#818cf8"
            assert p["accent_pressed"] == "#4f46e5"
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

    def test_the_popup_is_not_styled_here_as_well(self):
        """ArrowComboBox owns the dropdown panel and its rows. A second
        definition in the shared sheet is one that drifts."""
        assert "QComboBox QAbstractItemView" not in build_qss(DARK)

    def test_font_stack_falls_back_to_the_bundled_face(self):
        """If Windows' own UI font is missing, text must still render in
        the face Voxel ships."""
        assert '"Inter"' in build_qss(DARK)
        assert 'sans-serif' in build_qss(DARK)

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

    def _ui_modules(self):
        import importlib
        import pkgutil

        import src.ui_pyqt6.panes as panes_pkg

        modules = [
            importlib.import_module("src.ui_pyqt6.settings_window"),
            importlib.import_module("src.ui_pyqt6.nav_rail"),
        ]
        for info in pkgutil.iter_modules(panes_pkg.__path__):
            modules.append(
                importlib.import_module("src.ui_pyqt6.panes." + info.name)
            )
        return modules

    def test_no_window_or_pane_defines_its_own_scrollbar_rules(self):
        import inspect

        for module in self._ui_modules():
            assert "QScrollBar" not in inspect.getsource(module), (
                f"{module.__name__} styles scrollbars itself; theme.py owns that"
            )

    def test_no_pane_hard_codes_a_palette_colour(self):
        """A hex literal in a pane is a colour that will not follow the
        theme. The accent placeholder in link markup is replaced on
        restyle, and white on the accent button is white in both themes."""
        import inspect
        import re

        allowed = {"#6366f1", "#ffffff", "#43b581", "#ff453a", "#ef4444"}
        for module in self._ui_modules():
            for found in re.findall(r"#[0-9a-fA-F]{6}", inspect.getsource(module)):
                assert found.lower() in allowed, (
                    f"{module.__name__} hard-codes {found}"
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
    # Not "#16171a": that is also the LIGHT palette's rail_text_active, so
    # it appears legitimately in a light stylesheet.
    "#1e1f23", "#2a2c32", "#32343b",              # dark palette
    "#1C1C1E", "#2E2E31", "#39393D", "#48484A",   # previous dark palette
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
    """Review Focus 3: a theme change must restyle a window completely.

    Asserting on qapp.styleSheet() alone cannot fail for widgets carrying
    their own inline styles - which is the entire failure mode.
    """

    def _window(self, tmp_path):
        from src.config import Config
        from src.history import HistoryStore
        from src.profiles import ProfileManager
        from src.ui_pyqt6.panes import PaneContext
        from src.ui_pyqt6.settings_window import SettingsWindow

        cfg = Config(config_path=str(tmp_path / "c.json"))
        cfg.load()
        ctx = PaneContext(
            config=cfg,
            profiles=ProfileManager(cfg),
            history=HistoryStore(db_path=str(tmp_path / "h.db")),
            apply=lambda key, value: cfg.set(key, value),
            palette=current_palette,
        )
        return SettingsWindow(ctx)

    def test_the_window_has_no_stranded_dark_styles_in_light(self, qapp, tmp_path):
        apply_theme(qapp, "light")
        window = self._window(tmp_path)
        window.restyle(LIGHT)
        stranded = _stranded_dark_styles(window)
        assert stranded == [], f"stranded dark styles: {stranded}"

    def test_switching_theme_restyles_an_already_built_window(self, qapp, tmp_path):
        """The real scenario: Voxel is running when Windows flips to light."""
        apply_theme(qapp, "dark")
        window = self._window(tmp_path)
        window.restyle(DARK)
        apply_theme(qapp, "light")
        window.restyle(LIGHT)
        stranded = _stranded_dark_styles(window)
        assert stranded == [], f"stranded after switch: {stranded}"

    def test_every_pane_is_restyled_not_only_the_visible_one(self, qapp, tmp_path):
        apply_theme(qapp, "dark")
        window = self._window(tmp_path)
        window.restyle(LIGHT)
        for pane in window.panes():
            stranded = _stranded_dark_styles(pane)
            assert stranded == [], f"{pane.PANE_ID} kept dark styles: {stranded}"


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

    def test_a_switch_on_a_row_leaves_the_row_showing(self, qapp):
        """Rendered proof: the pixels around the pill must be row colour."""
        from PyQt6.QtGui import QPixmap
        from src.ui_pyqt6.panes.widgets import SwitchRow
        from src.ui_pyqt6.theme import apply_theme, LIGHT

        apply_theme(qapp, "light")
        row = SwitchRow("Work offline", "Slower, but nothing leaves this computer")
        row.restyle(LIGHT)
        row.resize(360, 52)
        row.show()
        qapp.processEvents()
        pm = QPixmap(row.size())
        row.render(pm)
        img = pm.toImage()
        switch = row.switch()
        # The switch widget is a few pixels wider than the pill it draws.
        # That sliver is where a window-coloured background shows up as a box.
        centre = switch.mapTo(row, switch.rect().center())
        sliver_x = switch.mapTo(row, switch.rect().topRight()).x() - 2
        found = img.pixelColor(sliver_x, centre.y()).name().lower()
        assert found == LIGHT["row"].lower(), (
            f"the switch painted {found} over its row at x={sliver_x}"
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


def Qt_transparent():
    from PyQt6.QtCore import Qt
    return Qt.GlobalColor.transparent


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

    def test_the_panel_is_painted_by_hand_not_by_the_stylesheet(self, qapp):
        """Qt's stylesheet renderer gives a popup one clean corner and one
        five-pixel stair, so the panel is drawn with an antialiased path."""
        from PyQt6.QtGui import QPixmap
        combo = self._combo()
        popup = combo.view().window()
        popup.resize(200, 80)
        pm = QPixmap(popup.size())
        pm.fill(Qt_transparent())
        combo.paint_panel(pm)
        img = pm.toImage()
        # Opposite bottom corners must be the same shape: count how far in
        # the fill starts on the last row of the curve.
        def inset_from(edge_x_range, y):
            for n, x in enumerate(edge_x_range):
                if img.pixelColor(x, y).alpha() > 128:
                    return n
            return -1
        y = popup.height() - 2
        left = inset_from(range(0, 40), y)
        right = inset_from(range(popup.width() - 1, popup.width() - 41, -1), y)
        assert left == right, (
            f"the bottom corners differ: {left}px of curve on the left, "
            f"{right}px on the right"
        )
        assert left > 2, "the corners are not rounded at all"

    def test_the_list_itself_paints_nothing(self, qapp):
        """Anything the list paints sits on top of the panel as a hard-edged
        rectangle and squares off the corners."""
        combo = self._combo()
        qss = combo.popup_qss()
        assert "background: transparent" in qss
        assert "QAbstractItemView::viewport { background: transparent; }" in qss


class TestTextIsDrawnOnWholePixels:
    """Windows cannot draw half a pixel. A font-size like 13.5px is
    rasterised between two pixel grids and every letter comes out soft,
    which reads as a blurry, unfinished window."""

    def _ui_sources(self):
        import importlib
        import inspect
        import pkgutil

        import src.ui_pyqt6.panes as panes_pkg

        names = ["src.ui_pyqt6.settings_window", "src.ui_pyqt6.nav_rail",
                 "src.ui_pyqt6.theme"]
        for info in pkgutil.iter_modules(panes_pkg.__path__):
            names.append("src.ui_pyqt6.panes." + info.name)
        return [(n, inspect.getsource(importlib.import_module(n))) for n in names]

    def test_no_stylesheet_asks_for_a_fractional_font_size(self):
        import re

        offenders = []
        for name, source in self._ui_sources():
            for found in re.findall(r"font-size:\s*([0-9]*\.[0-9]+)px", source):
                offenders.append(f"{name}: {found}px")
        assert offenders == [], f"fractional font sizes: {offenders}"

    def test_the_shared_stylesheet_has_none_either(self):
        import re

        from src.ui_pyqt6.theme import build_qss, DARK

        assert re.search(r"font-size:\s*[0-9]*\.[0-9]+px", build_qss(DARK)) is None


class TestSmallTextIsSnappedToThePixelGrid:
    """Qt's default hinting leaves 11-13px text soft on Windows: the stems
    of the letters fall between pixels. Full hinting snaps them, which is
    the difference between crisp and smudged at these sizes."""

    def test_the_application_font_asks_for_full_hinting(self, qapp):
        from PyQt6.QtGui import QFont

        apply_theme(qapp, "dark")
        assert (
            qapp.font().hintingPreference()
            == QFont.HintingPreference.PreferFullHinting
        )

    def test_the_application_font_is_the_bundled_one(self, qapp):
        apply_theme(qapp, "dark")
        assert qapp.font().family() == "Inter"


class TestTheUiFontIsTheOneWindowsDrawsBest:
    """Inter is a web font with minimal hinting; at 11-13px on Windows its
    stems land between pixels and the text reads as soft. Segoe UI Variable
    is hinted for exactly these sizes and is what every native window uses,
    so it is first in the stack with Inter behind it."""

    def test_segoe_ui_variable_comes_first(self):
        from src.ui_pyqt6.theme import FONT_STACK

        assert FONT_STACK.startswith('"Segoe UI Variable Text"')
        assert "Inter" in FONT_STACK

    def test_the_stylesheet_uses_that_stack(self):
        assert '"Segoe UI Variable Text"' in build_qss(DARK)

    def test_the_application_font_does_not_force_grey_antialiasing(self, qapp):
        """PreferAntialias turns off ClearType's subpixel rendering, which
        is the thing making the text crisp in the first place."""
        from PyQt6.QtGui import QFont

        apply_theme(qapp, "dark")
        assert qapp.font().styleStrategy() != QFont.StyleStrategy.PreferAntialias
