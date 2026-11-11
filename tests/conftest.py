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
    yield app
