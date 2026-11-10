"""
theme.py - Shared UI theme constants, stylesheet, and reusable widgets for Voxel.
"""
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import QComboBox, QCheckBox, QWidget

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# iOS palettes
#
# Two token sets with identical keys, so anything built from a palette works in
# either theme. Values are fixed by the design spec; the accent is Voxel indigo
# rather than iOS blue, and switches use indigo rather than Apple's green.
# ---------------------------------------------------------------------------

#: Voxel brand indigo, shared by both palettes.
ACCENT_INDIGO = "#6366f1"
ACCENT_INDIGO_HOVER = "#818cf8"
ACCENT_INDIGO_PRESSED = "#4f46e5"

LIGHT: dict[str, str] = {
    "bg": "#F2F2F7",
    "card": "#FFFFFF",
    "card_alt": "#FAFAFC",
    "separator": "#D6D6DA",
    "text": "#000000",
    "secondary": "#8E8E93",
    "accent": ACCENT_INDIGO,
    "accent_hover": ACCENT_INDIGO_HOVER,
    "accent_pressed": ACCENT_INDIGO_PRESSED,
    "switch_off": "#E9E9EB",
    "input_bg": "#FFFFFF",
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#f59e0b",
    "scrollbar": "#C7C7CC",
    "scrollbar_hover": "#A1A1A6",
}

DARK: dict[str, str] = {
    "bg": "#000000",
    "card": "#1C1C1E",
    "card_alt": "#2C2C2E",
    "separator": "#2E2E31",
    "text": "#FFFFFF",
    "secondary": "#8E8E93",
    "accent": ACCENT_INDIGO,
    "accent_hover": ACCENT_INDIGO_HOVER,
    "accent_pressed": ACCENT_INDIGO_PRESSED,
    "switch_off": "#39393D",
    "input_bg": "#1C1C1E",
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#f59e0b",
    "scrollbar": "#48484A",
    "scrollbar_hover": "#636366",
}

_THEMES = {"light": LIGHT, "dark": DARK}


def _read_apps_use_light_theme():
    """Raw AppsUseLightTheme value from the registry (Windows only).

    Split out so theme detection can be tested without touching the registry.
    """
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
    )
    try:
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value
    finally:
        key.Close()


def detect_system_theme() -> str:
    """"light" or "dark", following the Windows app theme setting.

    Defaults to dark on anything unexpected — a missing key on older or
    locked-down Windows, a non-Windows host, or a value we don't recognise.
    A theme is never worth crashing the app over.
    """
    try:
        value = _read_apps_use_light_theme()
    except Exception:
        return "dark"

    if value == 1:
        return "light"
    if value == 0:
        return "dark"
    return "dark"


def palette_for(name: str) -> dict[str, str]:
    """Palette for a theme name; unknown names fall back to dark."""
    return _THEMES.get(name, DARK)


# ---------------------------------------------------------------------------
# The stylesheet
#
# Built on demand from a palette rather than fixed at import time, so changing
# theme restyles live windows and dialogs created later use the current colours.
# This is the ONLY place chrome is defined: a second copy is what let the
# scrollbars and dropdowns drift apart in the first place.
# ---------------------------------------------------------------------------

#: Gap between a scrollbar and the content it scrolls, so the bar never sits on
#: top of the cards.
SCROLLBAR_GUTTER = 4
SCROLLBAR_THICKNESS = 8

FONT_STACK = '"Inter", "Segoe UI", system-ui, sans-serif'

#: Loaded font family names, so repeated calls don't re-register the same file.
_loaded_fonts: set[str] = set()


def load_fonts(assets_dir: str) -> bool:
    """Register the bundled Inter faces with Qt. True if at least one loaded.

    Inter stands in for SF Pro, which cannot legally be bundled. It ships with
    the app rather than being fetched at runtime, and the stylesheet falls back
    to Segoe UI, so a missing or unreadable font file costs typography and
    nothing else.
    """
    import os
    from PyQt6.QtGui import QFontDatabase

    font_dir = os.path.join(assets_dir, "fonts")
    if not os.path.isdir(font_dir):
        logger.warning("Font directory not found: %s — falling back to Segoe UI", font_dir)
        return False

    loaded_any = False
    for filename in sorted(os.listdir(font_dir)):
        if not filename.lower().endswith((".ttf", ".otf")):
            continue
        path = os.path.join(font_dir, filename)
        if path in _loaded_fonts:
            loaded_any = True
            continue
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id >= 0:
            _loaded_fonts.add(path)
            loaded_any = True
        else:
            logger.warning("Qt refused to load font %s", path)

    return loaded_any


def build_qss(palette: dict[str, str]) -> str:
    """Render the application stylesheet for *palette*."""
    p = palette
    return f"""
QWidget {{
    background-color: {p['bg']};
    color: {p['text']};
    font-family: {FONT_STACK};
    font-size: 13px;
}}

QLabel {{
    background: transparent;
    color: {p['text']};
}}

QLabel#subtitle, QLabel#section_sub, QLabel#status_label {{
    color: {p['secondary']};
    font-size: 11px;
}}

QLabel#section_title {{
    color: {p['text']};
    font-size: 13px;
    font-weight: 600;
}}

QLabel#app_title {{
    color: {p['text']};
    font-size: 22px;
    font-weight: 700;
}}

QLineEdit {{
    background-color: {p['input_bg']};
    color: {p['text']};
    border: 1px solid {p['separator']};
    border-radius: 10px;
    padding: 6px 10px;
    font-family: {FONT_STACK};
    font-size: 13px;
    selection-background-color: {p['accent']};
}}

QLineEdit:focus {{
    border: 1px solid {p['accent']};
}}

QLineEdit[readOnly="true"] {{
    color: {p['secondary']};
}}

QTextEdit {{
    background-color: {p['input_bg']};
    color: {p['text']};
    border: 1px solid {p['separator']};
    border-radius: 10px;
    padding: 8px;
    font-family: {FONT_STACK};
    font-size: 13px;
    selection-background-color: {p['accent']};
}}

QTextEdit:focus {{
    border: 1px solid {p['accent']};
}}

QComboBox {{
    background-color: {p['input_bg']};
    color: {p['text']};
    border: 1px solid {p['separator']};
    border-radius: 10px;
    padding: 6px 10px;
    font-family: {FONT_STACK};
    font-size: 13px;
    min-width: 120px;
}}

QComboBox:focus {{
    border: 1px solid {p['accent']};
}}

QComboBox:disabled {{
    color: {p['secondary']};
    background-color: {p['bg']};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0px;
    height: 0px;
}}

/* Popup matches the field it belongs to: same radius, same border, same fill. */
QComboBox QAbstractItemView {{
    background-color: {p['card']};
    color: {p['text']};
    border: 1px solid {p['separator']};
    border-radius: 10px;
    selection-background-color: {p['accent']};
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    min-height: 24px;
    border-radius: 6px;
}}

QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {{
    background-color: {p['accent']};
    color: #FFFFFF;
}}

QPushButton {{
    background-color: {p['accent']};
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 6px 18px;
    font-family: {FONT_STACK};
    font-size: 12px;
    font-weight: 600;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {p['accent_hover']};
}}

QPushButton:pressed {{
    background-color: {p['accent_pressed']};
}}

QPushButton#save_btn {{
    font-size: 14px;
    border-radius: 12px;
    min-height: 42px;
    padding: 10px 18px;
}}

QPushButton#capture_btn_recording {{
    background-color: {p['error']};
}}

QFrame#divider {{
    background-color: {p['separator']};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

/* --- scrollbars: defined once, for every window --------------------------
   Every subcontrol is styled. Anything left out makes Qt fall back to the
   native Windows scrollbar for that part, which is what made Stats and the
   FAQ dialog look unlike the rest of the app. */
QScrollBar:vertical {{
    background: transparent;
    width: {SCROLLBAR_THICKNESS}px;
    margin: 0px 0px 0px {SCROLLBAR_GUTTER}px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {p['scrollbar']};
    border-radius: {SCROLLBAR_THICKNESS // 2}px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p['scrollbar_hover']};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: {SCROLLBAR_THICKNESS}px;
    margin: {SCROLLBAR_GUTTER}px 0px 0px 0px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {p['scrollbar']};
    border-radius: {SCROLLBAR_THICKNESS // 2}px;
    min-width: 28px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {p['scrollbar_hover']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QToolTip {{
    background-color: {p['card']};
    color: {p['text']};
    border: 1px solid {p['separator']};
    border-radius: 8px;
    padding: 6px 8px;
}}
"""


#: Palette currently applied, so dialogs built later use the live colours
#: instead of whatever was captured when a module was first imported.
_current_palette: dict[str, str] = DARK


def current_palette() -> dict[str, str]:
    """The palette in force right now."""
    return _current_palette


def apply_theme(app, theme_name: str | None = None) -> str:
    """Style the whole application. Returns the theme name applied.

    The stylesheet goes on the QApplication rather than each window, so every
    window — and every dialog created afterwards — inherits it, and a theme
    change restyles all of them at once rather than leaving some half-converted.
    """
    global _current_palette

    name = theme_name or detect_system_theme()
    palette = palette_for(name)
    _current_palette = palette
    app.setStyleSheet(build_qss(palette))

    # Repaint hand-drawn controls, which read tokens rather than QSS.
    for widget in app.allWidgets():
        if isinstance(widget, IOSSwitch):
            widget.set_palette(palette)

    logger.info("Applied %s theme", name)
    return name


# ---------------------------------------------------------------------------
# Legacy flat-dark constants (removed once every window reads a palette)
# ---------------------------------------------------------------------------
BG = "#0f0f0f"
CARD = "#1a1a1a"
BORDER = "#2a2a2a"
INPUT_BG = "#111111"
TEXT = "#e8e8e8"
SUBTLE = "#777777"
ACCENT = "#6366f1"
ACCENT_HOVER = "#818cf8"
SUCCESS = "#22c55e"
ERROR = "#ef4444"
WARNING = "#f59e0b"

# ---------------------------------------------------------------------------
# QSS stylesheet
# ---------------------------------------------------------------------------
QSS = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI";
    font-size: 13px;
}}

QLabel {{
    background: transparent;
    color: {TEXT};
}}

QLabel#subtitle {{
    color: {SUBTLE};
    font-size: 11px;
}}

QLabel#section_title {{
    color: {TEXT};
    font-size: 13px;
    font-weight: bold;
}}

QLabel#section_sub {{
    color: {SUBTLE};
    font-size: 11px;
}}

QLabel#status_label {{
    color: {SUBTLE};
    font-size: 11px;
}}

QLabel#app_title {{
    color: {TEXT};
    font-size: 22px;
    font-weight: bold;
}}

QLineEdit {{
    background-color: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-family: "Segoe UI";
    font-size: 13px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

QLineEdit[readOnly="true"] {{
    color: {SUBTLE};
    font-family: "Consolas";
}}

QComboBox {{
    background-color: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-family: "Segoe UI";
    font-size: 13px;
    min-width: 120px;
}}

QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    background: {INPUT_BG};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0px;
    height: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: none;
    padding: 4px;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    min-height: 24px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {ACCENT};
    color: white;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

QComboBox QAbstractItemView::indicator {{
    width: 0px;
    height: 0px;
}}

QPushButton {{
    background-color: {ACCENT};
    color: {TEXT};
    border: none;
    border-radius: 8px;
    padding: 6px 18px;
    font-family: "Segoe UI";
    font-size: 12px;
    font-weight: bold;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton:pressed {{
    background-color: {ACCENT};
}}

QPushButton#save_btn {{
    font-size: 14px;
    border-radius: 10px;
    min-height: 42px;
    padding: 10px 18px;
}}

QPushButton#capture_btn_recording {{
    background-color: {ERROR};
}}

QPushButton#capture_btn_recording:hover {{
    background-color: #f87171;
}}

QCheckBox {{
    color: {SUBTLE};
    font-size: 12px;
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {INPUT_BG};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked:hover {{
    background-color: {ACCENT_HOVER};
}}

QFrame#divider {{
    background-color: {BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

QTextEdit {{
    background-color: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    font-family: "Segoe UI";
    font-size: 13px;
    selection-background-color: {ACCENT};
}}

QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}

QScrollBar:vertical {{
    background: {BG};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {SUBTLE};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollArea {{
    border: none;
}}
"""


# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------
class ArrowComboBox(QComboBox):
    """QComboBox that draws a visible chevron arrow and has a wide popup."""

    #: Beyond this the popup stops being a dropdown and starts being a wall.
    MAX_POPUP_WIDTH = 900
    #: Room for the item padding, the checkmark column and any icon.
    ITEM_CHROME = 56

    def _popup_width(self) -> int:
        """How wide the popup should be: at least the field, never absurd.

        The old version sized the popup from item text alone and then moved and
        resized its top-level window, so it floated free of the control it
        belonged to. Qt already aligns the popup to the field — it just needs
        to be told a sensible width.
        """
        fm = self.fontMetrics()
        widest = 0
        for i in range(self.count()):
            widest = max(widest, fm.horizontalAdvance(self.itemText(i)))
        return min(max(self.width(), widest + self.ITEM_CHROME), self.MAX_POPUP_WIDTH)

    def showPopup(self):  # noqa: N802
        self.view().setMinimumWidth(self._popup_width())
        # Deliberately no resize/move of the popup window: that is what made
        # the dropdown look detached from its field.
        super().showPopup()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0x77, 0x77, 0x77), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        x = self.width() - 18
        y = self.height() // 2
        painter.drawLine(x - 4, y - 2, x, y + 2)
        painter.drawLine(x, y + 2, x + 4, y - 2)
        painter.end()


class IOSSwitch(QCheckBox):
    """An iOS pill switch that is still a QCheckBox underneath.

    Subclassing QCheckBox keeps every existing setChecked / isChecked /
    stateChanged call site working, so swapping it in is a one-line change at
    each site rather than a rewrite. The pill is drawn rather than styled
    because QSS can't express the knob's travel.

    The "on" colour is Voxel indigo, deliberately not Apple's green.
    """

    TRACK_W = 44
    TRACK_H = 26
    KNOB_INSET = 3

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._palette_tokens: dict[str, str] = DARK
        # The native indicator is hidden; we draw the pill ourselves.
        self.setStyleSheet(
            f"QCheckBox::indicator {{ width: {self.TRACK_W}px; height: {self.TRACK_H}px; }}"
        )

    def set_palette(self, palette: dict[str, str]) -> None:
        self._palette_tokens = palette
        self.update()

    def _on_colour(self) -> QColor:
        return QColor(self._palette_tokens["accent"])

    def _off_colour(self) -> QColor:
        return QColor(self._palette_tokens["switch_off"])

    def sizeHint(self):  # noqa: N802
        hint = super().sizeHint()
        hint.setHeight(max(hint.height(), self.TRACK_H + 4))
        return hint

    def paintEvent(self, event):  # noqa: N802
        # Let the base class draw the label, then paint the pill over the
        # (hidden) indicator area.
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        y = (self.height() - self.TRACK_H) // 2
        radius = self.TRACK_H / 2
        painter.setBrush(self._on_colour() if self.isChecked() else self._off_colour())
        painter.drawRoundedRect(0, y, self.TRACK_W, self.TRACK_H, radius, radius)

        knob_d = self.TRACK_H - (self.KNOB_INSET * 2)
        knob_x = (
            self.TRACK_W - knob_d - self.KNOB_INSET if self.isChecked() else self.KNOB_INSET
        )
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(knob_x, y + self.KNOB_INSET, knob_d, knob_d)
        painter.end()


class TickCheckBox(QCheckBox):
    """QCheckBox that draws a white checkmark when checked."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            indicator_x = 1
            indicator_y = (self.height() - 18) // 2
            pen = QPen(QColor(255, 255, 255), 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(indicator_x + 4, indicator_y + 9, indicator_x + 7, indicator_y + 13)
            painter.drawLine(indicator_x + 7, indicator_y + 13, indicator_x + 14, indicator_y + 5)
            painter.end()
