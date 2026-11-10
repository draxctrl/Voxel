"""
theme.py - Shared UI theme constants, stylesheet, and reusable widgets for Voxel.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import QComboBox, QCheckBox, QWidget

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

    def showPopup(self):
        fm = self.fontMetrics()
        max_w = self.width()
        for i in range(self.count()):
            text_w = fm.horizontalAdvance(self.itemText(i)) + 80
            if text_w > max_w:
                max_w = text_w
        self.view().setMinimumWidth(max_w)
        super().showPopup()
        popup_window = self.view().window()
        if popup_window:
            popup_window.resize(max_w, popup_window.height())

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
