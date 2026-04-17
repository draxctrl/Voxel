"""Detect the currently focused application for automatic profile switching."""

import logging
import platform
import subprocess
import os

logger = logging.getLogger(__name__)


class AppDetector:
    """Detects the currently focused/active application on Windows and macOS."""

    def get_active_app(self) -> str:
        """Return the name/identifier of the currently focused application.

        Returns lowercase app name like 'chrome', 'code', 'outlook',
        'slack', 'discord', 'notepad', etc.
        Returns 'unknown' if detection fails.
        """
        try:
            system = platform.system()
            if system == "Windows":
                return self._get_active_app_windows()
            elif system == "Darwin":
                return self._get_active_app_macos()
            else:
                logger.debug("Unsupported platform for app detection: %s", system)
                return "unknown"
        except Exception as e:
            logger.debug("Failed to detect active app: %s", e)
            return "unknown"

    def _get_active_app_windows(self) -> str:
        """Get active app on Windows using ctypes Win32 API."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        # Get the foreground window handle
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown"

        # Get the process ID for that window
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return "unknown"

        # Open the process to query its module name
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        process_handle = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value
        )
        if not process_handle:
            return "unknown"

        try:
            # Get the executable file path
            exe_path = ctypes.create_unicode_buffer(512)
            psapi.GetModuleFileNameExW(process_handle, None, exe_path, 512)
            if not exe_path.value:
                return "unknown"

            # Extract base name without extension, lowercased
            base = os.path.basename(exe_path.value)
            name, _ = os.path.splitext(base)
            return name.lower()
        finally:
            kernel32.CloseHandle(process_handle)

    def _get_active_app_macos(self) -> str:
        """Get active app on macOS using AppleScript via osascript."""
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first '
                "application process whose frontmost is true",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "unknown"
        return result.stdout.strip().lower()
