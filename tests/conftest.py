"""Shared fixtures. Qt runs headless on the offscreen platform."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole test session.

    The repo has no pytest-qt; every Qt test shares this instead of
    `qtbot`. Qt forbids a second QApplication in a process, so this is
    session-scoped and never torn down.
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    # The real app loads Inter at startup. Without it, every label here is
    # measured in a different face than the one the user sees, and a layout
    # test can pass while the shipped window clips.
    from src.main import _get_assets_dir
    from src.ui_pyqt6.theme import apply_theme, load_fonts

    load_fonts(_get_assets_dir())
    # Likewise the stylesheet: it sets the base font size every widget
    # inherits, so without it every layout measurement here is taken in a
    # smaller face than the shipped window uses.
    apply_theme(app, "dark")
    yield app
