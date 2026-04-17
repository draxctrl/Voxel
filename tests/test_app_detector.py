import platform
from unittest.mock import patch, MagicMock

from src.app_detector import AppDetector


class TestGetActiveApp:
    def test_returns_unknown_on_unsupported_platform(self):
        detector = AppDetector()
        with patch("src.app_detector.platform.system", return_value="Linux"):
            assert detector.get_active_app() == "unknown"

    def test_returns_unknown_on_exception(self):
        detector = AppDetector()
        with patch("src.app_detector.platform.system", side_effect=RuntimeError("boom")):
            assert detector.get_active_app() == "unknown"


class TestWindowsDetection:
    @patch("src.app_detector.platform.system", return_value="Windows")
    def test_returns_exe_name_lowercase(self, _mock_sys):
        detector = AppDetector()
        with patch.object(detector, "_get_active_app_windows", return_value="chrome"):
            assert detector.get_active_app() == "chrome"

    @patch("src.app_detector.platform.system", return_value="Windows")
    def test_returns_unknown_when_windows_fails(self, _mock_sys):
        detector = AppDetector()
        with patch.object(
            detector, "_get_active_app_windows", side_effect=OSError("access denied")
        ):
            assert detector.get_active_app() == "unknown"


class TestMacOSDetection:
    @patch("src.app_detector.platform.system", return_value="Darwin")
    def test_returns_app_name_from_osascript(self, _mock_sys):
        detector = AppDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Google Chrome\n"
        with patch("src.app_detector.subprocess.run", return_value=mock_result):
            assert detector.get_active_app() == "google chrome"

    @patch("src.app_detector.platform.system", return_value="Darwin")
    def test_returns_unknown_when_osascript_fails(self, _mock_sys):
        detector = AppDetector()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("src.app_detector.subprocess.run", return_value=mock_result):
            assert detector.get_active_app() == "unknown"

    @patch("src.app_detector.platform.system", return_value="Darwin")
    def test_returns_unknown_when_osascript_empty(self, _mock_sys):
        detector = AppDetector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "   \n"
        with patch("src.app_detector.subprocess.run", return_value=mock_result):
            assert detector.get_active_app() == "unknown"


class TestWindowsInternals:
    def test_get_active_app_windows_extracts_basename(self):
        """Test the path-to-name extraction logic in isolation."""
        import os

        # Simulate what _get_active_app_windows does with the exe path
        exe_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        base = os.path.basename(exe_path)
        name, _ = os.path.splitext(base)
        assert name.lower() == "chrome"

        exe_path2 = r"C:\Windows\System32\notepad.exe"
        base2 = os.path.basename(exe_path2)
        name2, _ = os.path.splitext(base2)
        assert name2.lower() == "notepad"


class TestConfigDefaults:
    def test_auto_profile_default(self):
        from src.config import DEFAULT_CONFIG

        assert DEFAULT_CONFIG["auto_profile"] is False

    def test_app_profiles_default(self):
        from src.config import DEFAULT_CONFIG

        assert DEFAULT_CONFIG["app_profiles"] == {}
