"""What Voxel is costing the machine, in figures a person can read.

Offline transcription runs a Whisper model on the user's own CPU, and the
only honest way to say what that costs is to show it. This reads the two
numbers that matter - memory held and share of the processor used - from
the operating system directly, so that nothing has to be bundled for it.

Everything here answers ``None`` rather than raising: a status line is
never worth taking a dictation down for.
"""
from __future__ import annotations

import ctypes
import logging
import os
import time
from ctypes import wintypes

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt"


def _current_process():
    """The pseudo-handle for this process.

    Declared rather than called bare: without an explicit return type
    ctypes hands back a C int, and on 64-bit Windows the handle is then
    truncated and every call made with it fails.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    return kernel32.GetCurrentProcess()


def _psapi():
    lib = ctypes.WinDLL("psapi", use_last_error=True)
    lib.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    lib.GetProcessMemoryInfo.restype = wintypes.BOOL
    return lib


def _kernel32_times():
    lib = ctypes.WinDLL("kernel32", use_last_error=True)
    lib.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    lib.GetProcessTimes.restype = wintypes.BOOL
    return lib


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _memory_bytes() -> int:
    """Memory this process is holding, from the OS."""
    if not _IS_WINDOWS:
        # Linux and macOS: the second field of statm is resident pages.
        with open("/proc/self/statm", encoding="ascii") as handle:
            pages = int(handle.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")

    counters = _PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
    ok = _psapi().GetProcessMemoryInfo(
        _current_process(), ctypes.byref(counters), counters.cb
    )
    if not ok:
        raise OSError(
            "GetProcessMemoryInfo failed (%d)" % ctypes.get_last_error()
        )
    return int(counters.WorkingSetSize)


def memory_mb() -> float | None:
    """Megabytes Voxel is holding, or None when it cannot be read."""
    try:
        return _memory_bytes() / (1024 * 1024)
    except Exception as e:  # pragma: no cover - platform specific
        logger.debug("Could not read memory use: %s", e)
        return None


def _cpu_seconds() -> float:
    """Processor time this process has used, across all its threads."""
    if not _IS_WINDOWS:
        times = os.times()
        return times.user + times.system

    creation = wintypes.FILETIME()
    exited = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    ok = _kernel32_times().GetProcessTimes(
        _current_process(),
        ctypes.byref(creation),
        ctypes.byref(exited),
        ctypes.byref(kernel),
        ctypes.byref(user),
    )
    if not ok:
        raise OSError("GetProcessTimes failed (%d)"
                      % ctypes.get_last_error())

    def _seconds(value: wintypes.FILETIME) -> float:
        # FILETIME counts 100-nanosecond intervals in two halves.
        ticks = (value.dwHighDateTime << 32) | value.dwLowDateTime
        return ticks / 10_000_000.0

    return _seconds(kernel) + _seconds(user)


class CpuMeter:
    """Share of the processor Voxel has used since the last reading.

    A percentage is a rate, so a single reading cannot produce one. The
    first call establishes the baseline and answers None; every call after
    that reports the span since the one before it.
    """

    def __init__(self) -> None:
        self._last_cpu: float | None = None
        self._last_wall: float | None = None

    def percent(self) -> float | None:
        try:
            cpu = _cpu_seconds()
        except Exception as e:  # pragma: no cover - platform specific
            logger.debug("Could not read processor time: %s", e)
            return None
        wall = time.monotonic()

        previous_cpu, previous_wall = self._last_cpu, self._last_wall
        self._last_cpu, self._last_wall = cpu, wall
        if previous_cpu is None or previous_wall is None:
            return None

        elapsed = wall - previous_wall
        if elapsed <= 0:
            return None
        cores = os.cpu_count() or 1
        share = (cpu - previous_cpu) / elapsed / cores * 100.0
        return max(0.0, min(100.0, share))


def summary(meter: CpuMeter) -> str:
    """One line naming what Voxel is using, for the settings window."""
    parts = []
    mb = memory_mb()
    if mb is not None:
        parts.append("%s MB of memory" % _round_mb(mb))
    share = meter.percent()
    if share is not None:
        parts.append("%.0f%% of the processor" % share)
    if not parts:
        return "Usage is not available on this computer."
    return "Voxel is using " + " and ".join(parts) + "."


def _round_mb(mb: float) -> str:
    """Whole megabytes: a figure that flickers in its decimals reads as
    noise rather than as information."""
    return "%d" % round(mb)
