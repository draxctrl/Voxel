"""The three recording displays.

All three are driven by the real microphone level rather than a decorative
animation: the old waveform summed three sine waves and looked identical
whether the user shouted or said nothing, which made the app appear to be
listening when it might not have been.

They float above other applications rather than sitting inside a window, so
they keep their dark treatment in both the light and the dark theme — a light
badge would disappear against a light document.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

# ---------------------------------------------------------------------------
# Shared colours. Indigo everywhere, with one deliberate exception.
# ---------------------------------------------------------------------------
INDIGO = "#6366f1"
INDIGO_LIGHT = "#818cf8"
INDIGO_DARK = "#4f46e5"
#: The Dynamic Island's recording dot. Red is the one exception to indigo,
#: because that is what the thing it imitates does.
ISLAND_DOT_RED = "#ff453a"

_CARD_BG = QColor(0x13, 0x13, 0x1F, int(255 * 0.92))
_ISLAND_BG = QColor(0x0A, 0x0A, 0x0C, 245)
_TEXT = QColor(0xFF, 0xFF, 0xFF)
_DIM_TEXT = QColor(0xC8, 0xC8, 0xD4)
_MIC_TEXT = QColor(0xB4, 0xA8, 0xE6, 170)

#: id -> the words shown to the user in Settings.
RECORDING_STYLES: dict[str, str] = {
    "orb": "Orb",
    "waveform": "Waveform",
    "island": "Dynamic Island",
}

DEFAULT_STYLE = "orb"


def _mic_glyph_path(cx: float, cy: float, height: float) -> QPainterPath:
    """A microphone outline centred on (cx, cy), *height* tall overall."""
    unit = height / 24.0
    body_w = 7.5 * unit
    body_h = 12.0 * unit
    path = QPainterPath()
    # Capsule body
    body = QRectF(cx - body_w / 2, cy - height / 2, body_w, body_h)
    path.addRoundedRect(body, body_w / 2, body_w / 2)
    # Stand: an arc under the body plus a short stem
    arc_r = 6.0 * unit
    arc = QRectF(cx - arc_r, cy - height / 2 + body_h - arc_r, arc_r * 2, arc_r * 2)
    stand = QPainterPath()
    stand.arcMoveTo(arc, 200)
    stand.arcTo(arc, 200, 160)
    stroke_w = 1.8 * unit
    stroke = QPainterPath()
    stroke.addPath(stand)
    from PyQt6.QtGui import QPainterPathStroker

    stroker = QPainterPathStroker()
    stroker.setWidth(stroke_w)
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    path.addPath(stroker.createStroke(stand))
    # Stem
    stem = QRectF(cx - stroke_w / 2, cy - height / 2 + body_h + arc_r * 0.55,
                  stroke_w, 3.0 * unit)
    path.addRoundedRect(stem, stroke_w / 2, stroke_w / 2)
    return path.simplified()


class RecordingDisplay(QWidget):
    """One way of showing that Voxel is listening.

    Subclasses paint themselves; everything above them — the overlay window,
    the level provider, the timers — is shared.
    """

    style_id = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._level = 0.0
        #: What the paint code uses. The measured level arrives in single-frame
        #: spikes; drawn straight, every syllable makes the badge jump.
        self._drawn = 0.0
        self._phase = 0.0
        self._frames_since_bar = 0
        self._state = "recording"
        self.elapsed_text = ""
        self.mic_text = ""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # The application stylesheet styles bare QWidget and Qt type selectors
        # match subclasses, which would paint an opaque slab over the badge.
        self.setStyleSheet("QWidget { background: transparent; }")

    # -- inputs ---------------------------------------------------------
    #: How fast the drawn level chases the measured one, per frame. Rising
    #: stays the quicker of the two, or the badge feels laggy; falling is
    #: slower, because a gate slamming shut reads worse than one easing shut.
    #: Both are gentle: at 60fps even the rise takes about a fifth of a
    #: second, which is what makes the movement read as smooth rather than
    #: as a reaction to every syllable.
    ATTACK = 0.16
    RELEASE = 0.055

    #: How many animation frames one bar of a scrolling wave lasts. At 60fps
    #: a bar every four frames is about fifteen a second, so a fourteen-bar
    #: wave takes just under a second to cross. Pushing one per frame made
    #: the whole wave scroll past four times a second, which is the single
    #: thing that made the badge look frantic.
    FRAMES_PER_BAR = 4

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, float(level)))
        rate = self.ATTACK if self._level > self._drawn else self.RELEASE
        self._drawn += (self._level - self._drawn) * rate
        self.update()

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def set_elapsed(self, text: str) -> None:
        self.elapsed_text = text
        self.update()

    def set_mic_text(self, text: str) -> None:
        self.mic_text = text
        self.update()

    def advance(self, delta: float = 0.024) -> None:
        """Move the idle animation on one frame.

        Slow on purpose: the drift is meant to read as breathing, and at
        60fps anything faster than a few seconds a cycle reads as a pulse.
        """
        self._phase += delta
        self.update()

    def _scroll_wave(self) -> None:
        """Move the scrolling wave on, at most one bar every few frames.

        Between pushes the newest bar holds the loudest level it has seen,
        so slowing the scroll does not lose a syllable that happened to
        fall between two bars.
        """
        self._frames_since_bar += 1
        if self._frames_since_bar < self.FRAMES_PER_BAR:
            self._history[-1] = max(self._history[-1], self._drawn)
            return
        self._frames_since_bar = 0
        self._history.append(self._drawn)
        del self._history[: -self.NUM_BARS]

    # -- geometry -------------------------------------------------------
    def preferred_size(self) -> QSize:
        raise NotImplementedError

    # -- helpers --------------------------------------------------------
    @property
    def level(self) -> float:
        """The last measured level, as measured."""
        return self._level

    @property
    def drawn_level(self) -> float:
        """The smoothed level the paint code uses."""
        return self._drawn

    def _status_text(self) -> str:
        return {
            "recording": "Listening",
            "processing": "Processing",
            "clipboard": "Copied to clipboard",
        }.get(self._state, "Listening")

    def _font(self, size: int, bold: bool = False) -> QFont:
        font = QFont(self.font())
        font.setPointSize(size)
        font.setBold(bold)
        return font


class OrbDisplay(RecordingDisplay):
    """An indigo glow that swells with the voice, around a fixed frosted disc.

    Only the glow responds to level. The disc and its mic glyph stay put: a
    glyph that wobbles with volume reads as nervous rather than responsive.
    """

    style_id = "orb"

    WIDTH = 240
    HEIGHT = 230
    DISC_RADIUS = 34
    MAX_GLOW_RADIUS = 92
    ORB_CENTRE_Y = 96

    def preferred_size(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def orb_centre_y(self) -> int:
        return self.ORB_CENTRE_Y

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() / 2
        cy = float(self.ORB_CENTRE_Y)

        # -- the glow: the one thing that follows the voice ---------------
        drift = 0.5 + 0.5 * math.sin(self._phase)
        swell = 0.42 + 0.5 * self._drawn + 0.08 * drift
        radius = self.DISC_RADIUS + (self.MAX_GLOW_RADIUS - self.DISC_RADIUS) * swell

        glow = QRadialGradient(QPointF(cx, cy), radius)
        core = QColor(INDIGO_LIGHT)
        core.setAlphaF(0.55 + 0.4 * self._drawn)
        mid = QColor(INDIGO)
        mid.setAlphaF(0.30 + 0.30 * self._drawn)
        edge = QColor(INDIGO_DARK)
        edge.setAlphaF(0.0)
        glow.setColorAt(0.0, core)
        glow.setColorAt(0.45, mid)
        glow.setColorAt(1.0, edge)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # -- the frosted disc: fixed ---------------------------------------
        disc = QRadialGradient(QPointF(cx, cy - self.DISC_RADIUS * 0.4), self.DISC_RADIUS * 1.6)
        disc.setColorAt(0.0, QColor(255, 255, 255, 86))
        disc.setColorAt(1.0, QColor(255, 255, 255, 38))
        painter.setBrush(disc)
        painter.drawEllipse(QPointF(cx, cy), float(self.DISC_RADIUS), float(self.DISC_RADIUS))
        painter.setPen(QColor(255, 255, 255, 58))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), float(self.DISC_RADIUS), float(self.DISC_RADIUS))

        # -- the mic glyph: fixed, white to grey ---------------------------
        glyph = _mic_glyph_path(cx, cy, self.DISC_RADIUS * 1.15)
        shadow = QColor(0, 0, 0, 70)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.translate(0, 1.5)
        painter.drawPath(glyph)
        painter.translate(0, -1.5)

        gradient = QLinearGradient(
            QPointF(cx, cy - self.DISC_RADIUS * 0.6),
            QPointF(cx, cy + self.DISC_RADIUS * 0.6),
        )
        gradient.setColorAt(0.0, QColor("#ffffff"))
        gradient.setColorAt(0.45, QColor("#f4f4f7"))
        gradient.setColorAt(1.0, QColor("#b9b9c4"))
        painter.setBrush(gradient)
        painter.drawPath(glyph)

        # -- status, timer, device ----------------------------------------
        painter.setPen(_TEXT)
        painter.setFont(self._font(12, bold=True))
        painter.drawText(
            QRectF(0, cy + self.MAX_GLOW_RADIUS * 0.52, self.width(), 22),
            int(Qt.AlignmentFlag.AlignCenter),
            self._status_text(),
        )
        painter.setPen(_DIM_TEXT)
        painter.setFont(self._font(10))
        painter.drawText(
            QRectF(0, cy + self.MAX_GLOW_RADIUS * 0.52 + 20, self.width(), 18),
            int(Qt.AlignmentFlag.AlignCenter),
            self.elapsed_text,
        )
        painter.setPen(_MIC_TEXT)
        painter.setFont(self._font(8))
        painter.drawText(
            QRectF(0, cy + self.MAX_GLOW_RADIUS * 0.52 + 38, self.width(), 16),
            int(Qt.AlignmentFlag.AlignCenter),
            self.mic_text,
        )
        painter.end()


class WaveformDisplay(RecordingDisplay):
    """A frosted pill of live indigo bars, newest on the right."""

    style_id = "waveform"

    WIDTH = 320
    HEIGHT = 112
    NUM_BARS = 24
    BAR_W = 5
    BAR_GAP = 3
    BAR_MIN = 4
    BAR_MAX = 38
    RADIUS = 26

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Bars are a history of levels, so the shape of what was said scrolls
        # across the pill instead of wobbling in place.
        self._history = [0.0] * self.NUM_BARS

    def set_level(self, level: float) -> None:
        super().set_level(level)
        self._scroll_wave()

    def preferred_size(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()), self.RADIUS, self.RADIUS
        )
        painter.fillPath(path, _CARD_BG)
        painter.setPen(QColor(0x3D, 0x3D, 0x8B))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(_TEXT)
        painter.setFont(self._font(11, bold=True))
        painter.drawText(QRectF(18, 10, self.width() - 36, 18),
                         int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                         self._status_text())
        painter.setPen(_DIM_TEXT)
        painter.setFont(self._font(9))
        painter.drawText(QRectF(18, 10, self.width() - 36, 18),
                         int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                         self.elapsed_text)

        total_w = self.NUM_BARS * (self.BAR_W + self.BAR_GAP) - self.BAR_GAP
        x = (self.width() - total_w) / 2
        mid_y = self.height() / 2 + 8
        painter.setPen(Qt.PenStyle.NoPen)
        for i, value in enumerate(self._history[-self.NUM_BARS:]):
            height = self.BAR_MIN + value * (self.BAR_MAX - self.BAR_MIN)
            intensity = value
            colour = QColor(
                int(40 + intensity * (99 - 40)),
                int(40 + intensity * (102 - 40)),
                int(110 + intensity * (241 - 110)),
                225,
            )
            bar = QRectF(x + i * (self.BAR_W + self.BAR_GAP), mid_y - height / 2,
                         self.BAR_W, height)
            bar_path = QPainterPath()
            radius = min(self.BAR_W / 2, height / 2)
            bar_path.addRoundedRect(bar, radius, radius)
            painter.fillPath(bar_path, colour)

        painter.setPen(_MIC_TEXT)
        painter.setFont(self._font(8))
        painter.drawText(QRectF(0, self.height() - 24, self.width(), 16),
                         int(Qt.AlignmentFlag.AlignCenter), self.mic_text)
        painter.end()


class IslandDisplay(RecordingDisplay):
    """A compact near-black pill with a live wave where the gap used to be.

    The pill holds its shape. Sizing it from the level meant every syllable
    resized the whole badge, which read as flicker rather than as listening —
    the voice belongs in the wave, not in the outline.
    """

    style_id = "island"

    WIDTH = 260
    HEIGHT = 66
    PILL_W = 252
    PILL_H = 42
    DOT = 10
    #: The wave sits between the status text and the timer.
    NUM_BARS = 14
    BAR_W = 3
    BAR_GAP = 2
    BAR_MIN = 3
    BAR_MAX = 20

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # A history, so the shape of what was said scrolls through the wave
        # instead of all the bars wobbling together in place.
        self._history = [0.0] * self.NUM_BARS

    def set_level(self, level: float) -> None:
        super().set_level(level)
        self._scroll_wave()

    def preferred_size(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def _pill_rect(self) -> QRectF:
        """The pill's outline. Breathes by a pixel; never by the level."""
        breathe = 0.5 + 0.5 * math.sin(self._phase * 0.8)
        height = self.PILL_H + 1.5 * breathe
        return QRectF(
            (self.WIDTH - self.PILL_W) / 2,
            (self.HEIGHT - height) / 2,
            float(self.PILL_W),
            height,
        )

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._pill_rect()
        path = QPainterPath()
        path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.fillPath(path, _ISLAND_BG)

        # The recording dot is red: the one deliberate exception to indigo.
        dot_colour = QColor(ISLAND_DOT_RED if self._state == "recording" else INDIGO_LIGHT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_colour)
        dot_x = rect.left() + 14
        painter.drawEllipse(
            QRectF(dot_x, rect.center().y() - self.DOT / 2, self.DOT, self.DOT)
        )

        text_left = dot_x + self.DOT + 7
        painter.setPen(_TEXT)
        painter.setFont(self._font(10, bold=True))
        painter.drawText(
            QRectF(text_left, rect.top(), 78, rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._status_text(),
        )

        painter.setPen(_DIM_TEXT)
        painter.setFont(self._font(9))
        timer_rect = QRectF(rect.right() - 54, rect.top(), 40, rect.height())
        painter.drawText(
            timer_rect,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            self.elapsed_text,
        )

        self._paint_wave(painter, text_left + 80, timer_rect.left() - 8, rect.center().y())
        painter.end()

    def _paint_wave(self, painter, left: float, right: float, mid_y: float) -> None:
        """Live bars in the space between the status text and the timer."""
        span = right - left
        if span <= 0:
            return
        total = self.NUM_BARS * (self.BAR_W + self.BAR_GAP) - self.BAR_GAP
        x = left + max(0.0, (span - total) / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        for value in self._history[-self.NUM_BARS:]:
            height = self.BAR_MIN + value * (self.BAR_MAX - self.BAR_MIN)
            colour = QColor(INDIGO_LIGHT)
            colour.setAlphaF(0.45 + 0.55 * value)
            painter.setBrush(colour)
            painter.drawRoundedRect(
                QRectF(x, mid_y - height / 2, float(self.BAR_W), height),
                self.BAR_W / 2,
                self.BAR_W / 2,
            )
            x += self.BAR_W + self.BAR_GAP


_BUILDERS: dict[str, type[RecordingDisplay]] = {
    OrbDisplay.style_id: OrbDisplay,
    WaveformDisplay.style_id: WaveformDisplay,
    IslandDisplay.style_id: IslandDisplay,
}


def build_display(style_id: str | None, parent: QWidget | None = None) -> RecordingDisplay:
    """The display for *style_id*; anything unrecognised gets the default.

    A style name that no longer exists — hand-edited, or left behind by a
    downgrade — must cost the user their choice of animation, never every
    dictation from then on.
    """
    builder = _BUILDERS.get(style_id or "", _BUILDERS[DEFAULT_STYLE])
    return builder(parent)
