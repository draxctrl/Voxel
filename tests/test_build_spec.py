"""The packaged .exe must contain the modules the app loads by name.

The panes are looked up through importlib, so PyInstaller's analysis
walks straight past them: it reads import statements, and there are
none to read. The first build after the rebuild started and died with
"No module named 'src.ui_pyqt6.panes.writing_style'" in a Windows
error box. Nothing in the test suite could have caught it, because
running from source never needed the spec to be right.
"""
import io
import os
import re

from src.ui_pyqt6.panes import _REGISTRY

SPEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build.spec")


def _hidden_imports() -> list[str]:
    """The hiddenimports list from build.spec, as plain strings."""
    text = io.open(SPEC, encoding="utf-8").read()
    block = re.search(r"hiddenimports\s*=\s*\[(.*?)\]", text, re.S)
    assert block, "build.spec has no hiddenimports list"
    return re.findall(r"['\"]([^'\"]+)['\"]", block.group(1))


class TestEveryDynamicallyLoadedPaneIsBundled:
    def test_each_registry_module_is_named_in_the_spec(self):
        hidden = _hidden_imports()
        missing = []
        for target in _REGISTRY.values():
            if target is None:
                continue
            module = "src.ui_pyqt6.panes." + target.partition(":")[0]
            if module not in hidden:
                missing.append(module)
        assert not missing, (
            "these panes load by name and would be left out of the build: %s"
            % ", ".join(missing)
        )

    def test_the_registry_itself_is_not_empty(self):
        """A registry that silently emptied would make the check vacuous."""
        assert [t for t in _REGISTRY.values() if t], "no panes to check"


class TestOfflineTranscriptionIsInTheBuild:
    """The app offers Work offline, the README sells it against WisprFlow,
    and for three versions the packaged build excluded the components that
    make it work. Turning it on there broke every dictation."""

    #: What faster-whisper needs to run. torch is not among them: it is
    #: huge and faster-whisper does not use it.
    REQUIRED = ("faster_whisper", "ctranslate2", "onnxruntime", "tokenizers",
                "huggingface_hub", "av", "numpy")

    @staticmethod
    def _excludes() -> list[str]:
        text = io.open(SPEC, encoding="utf-8").read()
        block = re.search(r"excludes\s*=\s*\[(.*?)\]", text, re.S)
        assert block, "build.spec has no excludes list"
        return re.findall(r"['\"]([^'\"]+)['\"]", block.group(1))

    def test_nothing_offline_mode_needs_is_excluded(self):
        excluded = set(self._excludes())
        shut_out = [name for name in self.REQUIRED if name in excluded]
        assert not shut_out, (
            "offline transcription cannot work in the build without: %s"
            % ", ".join(shut_out)
        )

    def test_the_engine_loads_before_qt_in_the_build_too(self):
        """The preload is what stops the packaged app crashing as well."""
        text = io.open(SPEC, encoding="utf-8").read()
        assert "src/main.py" in text or "src\\main.py" in text
        import src.offline_preload  # noqa: F401  - must import cleanly
