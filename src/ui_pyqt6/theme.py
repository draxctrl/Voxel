"""
theme.py - Shared UI theme constants, stylesheet, and reusable widgets for Voxel.
"""
import logging

from PyQt6.QtCore import Qt, QPoint, QObject, QEvent, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
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

#: The sidebar design's surfaces. Four of them, from back to front:
#: the rail (darkest), the pane it sits beside, the rows on that pane, and
#: the hairline between rows. The legacy iOS keys below them are aliases
#: onto the same colours, so ArrowComboBox and IOSSwitch — the two widgets
#: that outlived the old settings page — sit on the new surfaces instead of
#: cutting differently-coloured holes in them.
LIGHT: dict[str, str] = {
    # sidebar design
    "rail": "#ececf0",
    "rail_text": "#4a4b53",
    "rail_text_active": "#16171a",
    "rail_active_bg": "#dcdce4",
    "pane": "#f7f7fa",
    "row": "#ffffff",
    "row_border": "#dddde3",
    "muted": "#6b6c75",
    "faint": "#83858f",
    # legacy names, pointed at the surfaces above
    "bg": "#f7f7fa",
    "card": "#ffffff",
    "card_alt": "#f2f2f6",
    "separator": "#dddde3",
    "text": "#101114",
    "secondary": "#6b6c75",
    "input_bg": "#ffffff",
    # the rest
    "accent": ACCENT_INDIGO,
    "accent_hover": ACCENT_INDIGO_HOVER,
    "accent_pressed": ACCENT_INDIGO_PRESSED,
    "switch_off": "#e3e3e9",
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#f59e0b",
    "scrollbar": "#c9c9d1",
    "scrollbar_hover": "#a9a9b4",
}

DARK: dict[str, str] = {
    # sidebar design
    "rail": "#16171a",
    "rail_text": "#b9bac2",
    "rail_text_active": "#ffffff",
    "rail_active_bg": "#2b2e36",
    "pane": "#1e1f23",
    "row": "#2a2c32",
    "row_border": "#32343b",
    "muted": "#9b9ca5",
    "faint": "#6d6f78",
    # legacy names, pointed at the surfaces above
    "bg": "#1e1f23",
    "card": "#2a2c32",
    "card_alt": "#32343b",
    "separator": "#32343b",
    "text": "#ffffff",
    "secondary": "#9b9ca5",
    "input_bg": "#2a2c32",
    # the rest
    "accent": ACCENT_INDIGO,
    "accent_hover": ACCENT_INDIGO_HOVER,
    "accent_pressed": ACCENT_INDIGO_PRESSED,
    "switch_off": "#3a3d45",
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#f59e0b",
    "scrollbar": "#3f424a",
    "scrollbar_hover": "#52555e",
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

#: Corner radius of a grouped settings card, shared with ios_layout.
CARD_RADIUS = 12

#: Windows' own UI typeface first. Inter is a web font with minimal
#: hinting: at 11-13px its stems land between pixels and the text reads as
#: soft, which is what makes a Qt window look unfinished beside a native
#: one. Segoe UI Variable is hinted for exactly these sizes. Inter stays
#: behind it as the fallback, and is still bundled for machines without it.
FONT_STACK = (
    '"Segoe UI Variable Text", "Segoe UI", "Inter", system-ui, sans-serif'
)

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

/* A switch is a QCheckBox, so the QWidget rule above would paint a
   window-coloured box around the pill wherever one sits on a card. */
QCheckBox {{
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

/* The dropdown panel and its rows are drawn by ArrowComboBox, which owns
   every combo in Voxel: the panel by hand (Qt's stylesheet renderer rounds
   a popup's corners unevenly) and the rows from ArrowComboBox.popup_qss().
   Nothing is styled here, so there is no second definition to drift. */

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

/* Qt adds the padding on top of min-height, so these two together are the
   button's height. Kept under a settings row: Save is one action, it does
   not need a bar across the bottom of the window. */
QPushButton#save_btn {{
    font-size: 13px;
    border-radius: 9px;
    min-height: 30px;
    padding: 5px 18px;
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

/* --- iOS grouped cards ---------------------------------------------------
   A row is a bare QWidget, and the QWidget rule above would paint the window
   background straight over the card it sits in, so rows opt out explicitly. */
QLabel#group_header {{
    color: {p['secondary']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
    background: transparent;
}}

QFrame#group_card {{
    background-color: {p['card']};
    border: none;
    border-radius: {CARD_RADIUS}px;
}}

QWidget#settings_row {{
    background: transparent;
}}

QFrame#row_separator {{
    background: transparent;
    border: none;
}}

QFrame#hairline {{
    background-color: {p['separator']};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

QLabel#row_title {{
    color: {p['text']};
    font-size: 13px;
    background: transparent;
}}

QLabel#row_sub {{
    color: {p['secondary']};
    font-size: 11px;
    background: transparent;
}}

QWidget#style_picker {{
    background: transparent;
}}

QFrame#style_tile {{
    background-color: {p['card_alt']};
    border: 2px solid transparent;
    border-radius: 10px;
}}

QFrame#style_tile[selected="true"] {{
    border: 2px solid {p['accent']};
}}

QLabel#tile_label {{
    color: {p['secondary']};
    font-size: 10px;
    background: transparent;
}}

QLabel#row_value {{
    color: {p['secondary']};
    font-size: 13px;
    background: transparent;
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


def _set_application_font(app) -> None:
    """Make small text crisp.

    Two things decide whether small text looks sharp: the typeface, and
    hinting. Windows' own UI face is hinted for 11-13px; full hinting
    snaps its stems to the pixel grid. Set on the application font so
    every widget inherits it - stylesheets override the size, not this.
    """
    from PyQt6.QtGui import QFont, QFontDatabase

    families = QFontDatabase.families()
    font = app.font()
    for candidate in ("Segoe UI Variable Text", "Segoe UI", "Inter"):
        if candidate in families:
            font.setFamily(candidate)
            break
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    # No style strategy: PreferAntialias asks for grey antialiasing and
    # turns ClearType's subpixel rendering off, which is the opposite of
    # what makes small text sharp here.
    app.setFont(font)


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
    _set_application_font(app)
    app.setStyleSheet(build_qss(palette))

    # Repaint hand-drawn controls, which read tokens rather than QSS.
    for widget in app.allWidgets():
        if isinstance(widget, IOSSwitch):
            widget.update()

    # Windows carrying their own inline styles re-apply them, so a theme change
    # can't leave one half light and half dark.
    for window in app.topLevelWidgets():
        restyle = getattr(window, "_restyle", None)
        if callable(restyle):
            try:
                restyle()
            except Exception as e:
                logger.warning("Could not restyle %s: %s", type(window).__name__, e)

    logger.info("Applied %s theme", name)
    return name




# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------
class _PanelPainter(QObject):
    """Draws the dropdown panel in place of the container's own painting.

    Qt's stylesheet renderer rounds a popup's corners unevenly — one corner
    comes out a clean arc and the opposite one a five-pixel stair. Taking the
    container's paint event and drawing the panel with an antialiased path is
    the only way to get four corners that match.
    """

    def __init__(self, combo: "ArrowComboBox") -> None:
        super().__init__(combo)
        self._combo = combo

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.Type.Paint:
            self._combo.paint_panel(obj)
            # Consuming the container's own paint event only skips its
            # background; the list inside paints in its own event.
            return True
        return False


class ArrowComboBox(QComboBox):
    """A combo whose list belongs to its field.

    The list is exactly as wide as the field, so it can never hang outside the
    window, and names too long for it are right-elided with the full name on
    hover. How the panel sits relative to the field is one of three styles,
    set by :attr:`POPUP_STYLE`:

    ``joined``    flush under the field, square where they meet, rounded below
    ``floating``  a raised card a few pixels below, rounded all round
    ``overlay``   covers the field, iOS-picker style, rounded all round

    The panel is drawn by :meth:`paint_panel` onto the popup's container
    window, which is translucent. Everything Qt would otherwise paint there —
    the container's background and the list's — is turned off, so there is
    exactly one rounded shape on screen and nothing square behind it.
    """

    #: ``joined`` | ``floating`` | ``overlay``
    POPUP_STYLE = "floating"
    #: Corner radius of the panel, in pixels.
    POPUP_RADIUS = 12
    #: Space between the field and a floating panel.
    POPUP_GAP = 6

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # The container is a top-level window; it has to be transparent before
        # it is ever shown or the panel sits inside an opaque square.
        popup = self.view().window()
        popup.setWindowFlags(
            popup.windowFlags()
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup.setObjectName("combo_popup")
        self._panel_painter = _PanelPainter(self)
        popup.installEventFilter(self._panel_painter)
        # Right-elide, so a name is cut at its end rather than through its
        # middle; the full name is on the tooltip.
        self.view().setTextElideMode(Qt.TextElideMode.ElideRight)

    # -- the panel ------------------------------------------------------
    def _panel_colours(self) -> tuple[QColor, QColor]:
        p = current_palette()
        dark = p["card"] == DARK["card"]
        if self.POPUP_STYLE == "joined":
            fill = p["input_bg"]
        else:
            fill = "#2C2C2E" if dark else "#FFFFFF"
        return QColor(fill), QColor(p["separator"])

    def _panel_path(self, rect: QRectF) -> QPainterPath:
        r = float(self.POPUP_RADIUS)
        path = QPainterPath()
        if self.POPUP_STYLE != "joined":
            path.addRoundedRect(rect, r, r)
            return path
        # Joined: square where it meets the field, rounded below.
        path.moveTo(rect.left(), rect.top())
        path.lineTo(rect.right(), rect.top())
        path.lineTo(rect.right(), rect.bottom() - r)
        path.quadTo(rect.right(), rect.bottom(), rect.right() - r, rect.bottom())
        path.lineTo(rect.left() + r, rect.bottom())
        path.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - r)
        path.closeSubpath()
        return path

    def paint_panel(self, frame) -> None:
        """Paint the panel onto the popup's container window."""
        fill, border = self._panel_colours()
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Half-pixel inset so the 1px stroke lands inside the widget rather
        # than straddling its edge, where half of it would be clipped away.
        rect = QRectF(frame.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = self._panel_path(rect)
        painter.fillPath(path, fill)
        painter.strokePath(path, QPen(border, 1))
        painter.end()

    def popup_qss(self) -> str:
        """Styling for the list on top of the panel: rows only, no background.

        Read at open time rather than at construction, so a switch between
        light and dark reaches dropdowns that already exist.
        """
        p = current_palette()
        inset = 4 if self.POPUP_STYLE == "joined" else 6
        radius = 0 if self.POPUP_STYLE == "joined" else 8
        top_pad = 2 if self.POPUP_STYLE == "joined" else 5
        return f"""
        QAbstractItemView {{
            background: transparent;
            border: none;
            outline: none;
            padding: {top_pad}px 0px {max(top_pad, 5)}px 0px;
        }}
        QAbstractItemView::viewport {{ background: transparent; }}
        QAbstractItemView::item {{
            padding: 8px 10px;
            margin: 0px {inset}px;
            min-height: 24px;
            border: none;
            border-radius: {radius}px;
            color: {p['text']};
        }}
        QAbstractItemView::item:selected, QAbstractItemView::item:hover {{
            background-color: {p['accent']};
            color: #FFFFFF;
        }}
        """

    def _popup_offset(self) -> int:
        """Where the panel's top edge goes, relative to the field's top."""
        if self.POPUP_STYLE == "joined":
            return self.height()
        if self.POPUP_STYLE == "floating":
            return self.height() + self.POPUP_GAP
        return 0   # overlay: the panel covers the field

    def wheelEvent(self, event):  # noqa: N802
        """Scroll the page, never retune the setting under the pointer.

        Qt changes a combo's value on a wheel roll and accepts the event. The
        settings groups scroll, so without this, rolling the wheel on the way
        past Microphone silently picks a different microphone and the next Save
        writes it. Ignoring the event passes it to the scroll area.
        """
        if self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()

    def showPopup(self):  # noqa: N802
        view = self.view()
        view.setMinimumWidth(self.width())
        view.setMaximumWidth(self.width())
        # A name too long for the field is elided in the list, so give it back
        # on hover rather than widening the popup past the window edge.
        for i in range(self.count()):
            if not self.itemData(i, Qt.ItemDataRole.ToolTipRole):
                self.setItemData(i, self.itemText(i), Qt.ItemDataRole.ToolTipRole)

        popup = view.window()
        view.setStyleSheet(self.popup_qss())
        super().showPopup()
        # Clamping the list is not enough: Qt sizes the popup's own top-level
        # window from the widest item, so a long device name leaves an 800px
        # window hanging outside the app.
        popup.resize(self.width(), popup.height())
        popup.move(self.mapToGlobal(QPoint(0, self._popup_offset())))

    def paintEvent(self, event):
        # A fixed-width combo in a settings row is narrower than a long device
        # name. Qt's stylesheet style clips the label mid-word instead of
        # eliding it, so the text is painted here: the frame is drawn without
        # its label, then the label goes back elided. The item text itself is
        # untouched, so the popup still shows every name in full.
        from PyQt6.QtWidgets import QStyle, QStyleOptionComboBox

        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        full_text = opt.currentText
        opt.currentText = ""
        painter = QPainter(self)
        self.style().drawComplexControl(
            QStyle.ComplexControl.CC_ComboBox, opt, painter, self
        )
        text_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            opt,
            QStyle.SubControl.SC_ComboBoxEditField,
            self,
        )
        if not opt.currentIcon.isNull():
            icon_size = opt.iconSize
            opt.currentIcon.paint(
                painter,
                text_rect.x(),
                text_rect.y() + (text_rect.height() - icon_size.height()) // 2,
                icon_size.width(),
                icon_size.height(),
            )
            text_rect.setLeft(text_rect.left() + icon_size.width() + 8)
        # Leave the chevron its room.
        text_rect.setRight(max(text_rect.left(), self.width() - 26))
        painter.setPen(QColor(current_palette()["secondary" if not self.isEnabled() else "text"]))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.fontMetrics().elidedText(
                full_text, Qt.TextElideMode.ElideRight, text_rect.width()
            ),
        )
        painter.end()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(current_palette()['secondary']), 1.8)
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
        # None means "follow the applied theme". Holding a copy meant a switch
        # built after apply_theme kept the construction-time palette — light
        # mode rendered dark pills.
        self._palette_tokens: dict[str, str] | None = None
        # The native indicator is hidden; we draw the pill ourselves.
        # Qt draws its own indicator under our pill, and its border shows as
        # an outlined box around the pill. Keep the indicator's size (it
        # reserves the room the pill is painted into) but strip everything
        # that would be drawn.
        self.setStyleSheet(
            "QCheckBox::indicator {"
            f" width: {self.TRACK_W}px; height: {self.TRACK_H}px;"
            " border: none; background: transparent; image: none;"
            "}"
        )

    def set_palette(self, palette: dict[str, str]) -> None:
        """Pin this switch to a specific palette, overriding the applied theme."""
        self._palette_tokens = palette
        self.update()

    def _tokens(self) -> dict[str, str]:
        return self._palette_tokens if self._palette_tokens is not None else current_palette()

    def _on_colour(self) -> QColor:
        return QColor(self._tokens()["accent"])

    def _off_colour(self) -> QColor:
        return QColor(self._tokens()["switch_off"])

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

