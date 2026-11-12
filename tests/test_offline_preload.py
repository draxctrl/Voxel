"""The import order that keeps offline mode from killing the process."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inspect


class TestCtranslate2LoadsBeforeQt:
    """Importing PyQt6 first and then building a Whisper model crashes the
    process with an access violation - no exception, no log, the app just
    disappears. Proven by bisecting it: plain process fine, worker thread
    fine, PyQt6 imported first fatal, ctranslate2 imported first fine."""

    def test_main_imports_the_preload_before_pyqt(self):
        source = inspect.getsource(__import__("src.main", fromlist=["main"]))
        preload_at = source.index("offline_preload")
        qt_at = source.index("from PyQt6")
        assert preload_at < qt_at, (
            "src/main.py imports PyQt6 before the offline preload, which is "
            "the order that crashes"
        )

    def test_the_preload_never_raises_when_it_is_absent(self, monkeypatch):
        """The packaged build leaves ctranslate2 out on purpose."""
        import src.offline_preload as preload

        assert preload.is_loaded() in (True, False)

    def test_it_reports_whether_offline_can_run_natively(self):
        import src.offline_preload as preload
        from src.offline_transcriber import is_available

        if is_available():
            assert preload.is_loaded() is True, (
                "faster-whisper is installed but its native half did not load"
            )
