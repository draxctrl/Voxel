"""Tell Windows that this is Voxel, not the program that launched it.

Windows decides a window's taskbar icon, its grouping and what a pin
points at from the process's Application User Model ID. Without one of
its own, a Python app inherits python.exe's - which is why Voxel run
from source shows the Python logo on the taskbar however carefully its
window icon is set.

Claimed before any window exists: afterwards Windows has already chosen
and the call changes nothing.
"""
from __future__ import annotations

import ctypes
import logging
import os

logger = logging.getLogger(__name__)

#: Company.Product.Component.Version, which is the shape Windows expects.
APP_ID = "Voxel.Dictation.App.1"


def _set_app_id() -> None:
    if os.name != "nt":
        return
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def claim() -> bool:
    """Claim the identity. False when Windows would not take it."""
    try:
        _set_app_id()
    except Exception as e:
        logger.debug("Could not claim the taskbar identity: %s", e)
        return False
    return True
