"""Load ctranslate2 before Qt does anything, or offline mode kills the app.

Importing PyQt6 first and then building a Whisper model crashes the whole
process with a Windows access violation, inside ctranslate2's native code.
No Python exception, no log line, no error box - Voxel simply vanishes the
moment a dictation runs offline. Importing ctranslate2 first stops it, so
the two libraries' native halves are loaded in an order they survive.

It costs about a quarter of a second, and only where offline transcription
is installed at all: the packaged build leaves it out, so the import fails
immediately and costs nothing.

This module must be imported before PyQt6. tests/test_offline_preload.py
holds main.py to that order.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Whether the native half of offline transcription is loaded and safe.
LOADED = False

try:
    import ctranslate2  # noqa: F401

    LOADED = True
except Exception as e:  # pragma: no cover - depends on what is installed
    logger.debug("Offline transcription is not installed here: %s", e)


def is_loaded() -> bool:
    return LOADED
