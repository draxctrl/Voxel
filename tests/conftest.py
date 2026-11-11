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


@pytest.fixture
def ctx(qapp, tmp_path):
    """A PaneContext over throwaway storage.

    `apply` records rather than acting, so a pane test can assert what the
    pane asked the app to change without starting the app.
    """
    from src.config import Config
    from src.history import HistoryStore
    from src.profiles import ProfileManager
    from src.ui_pyqt6.panes import PaneContext
    from src.ui_pyqt6.theme import current_palette

    config = Config(config_path=str(tmp_path / "config.json"))
    config.load()
    applied: list[tuple[str, object]] = []

    def apply(key, value):
        applied.append((key, value))
        config.set(key, value)

    context = PaneContext(
        config=config,
        profiles=ProfileManager(config),
        history=HistoryStore(db_path=str(tmp_path / "history.db")),
        apply=apply,
        palette=current_palette,
    )
    context.applied = applied
    return context
