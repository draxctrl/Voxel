"""Country flags beside each language.

Windows renders flag emoji as letter pairs, so these must be image assets.
"""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.main import _get_assets_dir as assets_dir
from src.ui_pyqt6.flags import LANGUAGE_FLAGS, flag_icon


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestLanguageMapping:
    def test_follows_speaker_numbers_not_country_of_origin(self):
        assert LANGUAGE_FLAGS["en"] == "us"
        assert LANGUAGE_FLAGS["pt"] == "br"
        assert LANGUAGE_FLAGS["zh"] == "cn"
        assert LANGUAGE_FLAGS["es"] == "es"

    def test_covers_every_remaining_language(self):
        for code, country in (("fr", "fr"), ("de", "de"), ("it", "it"),
                              ("ja", "jp"), ("ko", "kr")):
            assert LANGUAGE_FLAGS[code] == country

    def test_auto_detect_has_no_flag(self):
        assert "auto" not in LANGUAGE_FLAGS

    def test_every_mapped_language_has_an_asset_file(self):
        for country in LANGUAGE_FLAGS.values():
            path = Path(assets_dir()) / "flags" / f"{country}.svg"
            assert path.exists(), f"missing flag asset: {path}"


class TestFlagIcon:
    def test_returns_an_icon_for_a_known_language(self, qapp):
        icon = flag_icon("en", assets_dir())
        assert icon is not None
        assert not icon.isNull()

    def test_returns_none_for_a_language_with_no_flag(self, qapp):
        assert flag_icon("auto", assets_dir()) is None

    def test_returns_none_for_an_unknown_language(self, qapp):
        assert flag_icon("xx", assets_dir()) is None

    def test_returns_none_when_the_asset_is_missing(self, qapp):
        """A frozen build without the flags must still list languages."""
        assert flag_icon("en", "C:/no/such/dir") is None
