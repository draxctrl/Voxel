"""The About pane: what this is, and where to go next."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui_pyqt6.panes.about import AboutPane


class TestWhatAboutTells:
    def test_it_shows_a_version(self, qapp, ctx):
        pane = AboutPane(ctx)
        pane.refresh()
        assert pane.version_text().strip() != ""

    def test_it_names_the_licence(self, qapp, ctx):
        text = AboutPane(ctx).licence_text()
        assert "GPL" in text or "General Public" in text

    def test_it_does_not_still_claim_mit(self, qapp, ctx):
        """Voxel was MIT. Telling a user it still is would be telling them
        they may close the source, which this licence does not allow."""
        assert "MIT" not in AboutPane(ctx).licence_text()

    def test_it_says_what_the_licence_means_in_plain_words(self, qapp, ctx):
        text = AboutPane(ctx).licence_text().lower()
        assert "share" in text or "changes" in text

    def test_it_links_to_the_project_and_to_support(self, qapp, ctx):
        links = AboutPane(ctx).links()
        assert any("github.com" in url for url in links.values())
        assert len(links) >= 2

    def test_every_link_is_https(self, qapp, ctx):
        for url in AboutPane(ctx).links().values():
            assert url.startswith("https://"), url


class TestAboutChangesNothing:
    def test_it_owns_no_settings(self):
        assert AboutPane.OWNS == frozenset()

    def test_opening_it_applies_nothing(self, qapp, ctx):
        AboutPane(ctx).refresh()
        assert ctx.applied == []


class TestLinksAreTheAccentColourNotQtDefaultBlue:
    """A QLabel anchor ignores the widget's `color` rule and renders in Qt's
    default blue with an underline, which is the one piece of chrome that
    makes the window look unfinished."""

    def test_every_link_carries_its_own_colour(self, qapp, ctx):
        from src.ui_pyqt6.theme import palette_for

        p = palette_for("dark")
        pane = AboutPane(ctx)
        pane.restyle(p)
        for label in pane._links:
            assert p["accent"] in label.text(), (
                f"link renders in Qt default blue: {label.text()}"
            )
