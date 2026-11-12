"""Windows shows the host program's icon until the app claims its own."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import taskbar_identity


class TestClaimingTheTaskbarIdentity:
    def test_the_id_names_voxel_and_nothing_else(self):
        """Windows groups windows, pins and icons by this string, so it has
        to be ours rather than the Python that happens to be running it."""
        assert "Voxel" in taskbar_identity.APP_ID
        assert "python" not in taskbar_identity.APP_ID.lower()

    def test_claiming_it_reports_success(self):
        assert taskbar_identity.claim() is True

    def test_a_refusal_is_not_a_crash(self, monkeypatch):
        def boom():
            raise OSError("shell32 is not available")

        monkeypatch.setattr(taskbar_identity, "_set_app_id", boom)
        assert taskbar_identity.claim() is False

    def test_it_is_claimed_before_any_window_exists(self):
        """Set after a window is created, Windows has already decided which
        icon to show and the call does nothing."""
        import inspect

        import src.main as main

        source = inspect.getsource(main.VoxelApp.__init__)
        claim_at = source.index("taskbar_identity.claim()")
        app_at = source.index("QApplication(")
        assert claim_at < app_at, (
            "the identity is claimed after the application is built"
        )
