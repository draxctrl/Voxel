"""Phosphor icons, loaded from bundled SVG and tinted to a colour.

The SVGs ship in `src/assets/icons/phosphor/`. They are Phosphor Icons
(MIT) with `fill="currentColor"`, so tinting is a string replacement on
the markup before it reaches the renderer.

A missing or unreadable file must never take the window down: a
packaged build whose `datas` entry was forgotten should show blank
squares in the sidebar, not fail to launch.
"""
from __future__ import annotations

import logging
import os
import sys

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

logger = logging.getLogger(__name__)

#: Every icon this UI asks for. The test suite checks each has a file,
#: so adding a name here without the SVG fails the build, not the user.
ICON_NAMES = frozenset(
    {
        "pencil-simple",
        "globe-simple",
        "microphone",
        "microphone-fill",
        "keyboard",
        "waveform",
        "clock-counter-clockwise",
        "chart-bar",
        "sliders-horizontal",
        "info",
        "magnifying-glass",
        "copy",
        "trash",
        "chat-text",
        "arrow-right",
        "check-circle-fill",
    }
)

_ICON_DIR_PARTS = ("assets", "icons", "phosphor")

_cache: dict[tuple[str, str, int], QIcon] = {}


def _icon_dirs() -> list[str]:
    """Candidate directories holding the SVGs, best guess first.

    Mirrors `settings_ui._resolve_assets_root`: PyInstaller's unpack
    directory first, then the source tree.
    """
    candidates: list[str] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "src", *_ICON_DIR_PARTS))
        candidates.append(os.path.join(meipass, *_ICON_DIR_PARTS))

    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(os.path.join(here, "..", *_ICON_DIR_PARTS)))
    return candidates


def _svg_path(name: str) -> str | None:
    """Full path to `<name>.svg`, or None when it is not bundled."""
    for directory in _icon_dirs():
        candidate = os.path.join(directory, f"{name}.svg")
        if os.path.isfile(candidate):
            return candidate
    return None


def _tinted_markup(markup: str, colour: str) -> str:
    """The SVG text with its colour forced to `colour`."""
    for token in ('"currentColor"', '"#000"', '"#000000"', '"black"'):
        markup = markup.replace(token, f'"{colour}"')
    return markup


def _blank_icon(size: int) -> QIcon:
    """A transparent icon of the right size — a gap, not a crash."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    return QIcon(pixmap)


def icon(name: str, colour: str, size: int = 18) -> QIcon:
    """The named Phosphor icon, tinted to `colour`, at `size` pixels."""
    key = (name, colour, size)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    path = _svg_path(name)
    markup: str | None = None
    if path is None:
        logger.warning("Icon '%s' is not bundled; showing a blank", name)
    else:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                markup = handle.read()
        except OSError as e:
            logger.warning("Icon '%s' could not be read (%s); showing a blank", name, e)

    if markup is None:
        result = _blank_icon(size)
        _cache[key] = result
        return result

    renderer = QSvgRenderer(_tinted_markup(markup, colour).encode("utf-8"))
    if not renderer.isValid():
        logger.warning("Icon '%s' is not valid SVG; showing a blank", name)
        result = _blank_icon(size)
        _cache[key] = result
        return result

    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    result = QIcon(pixmap)
    _cache[key] = result
    return result
