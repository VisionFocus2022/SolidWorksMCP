"""Run one unittest module in order with per-test memory tracing.

A watchdog thread hard-exits the process if commit memory exceeds the
ceiling, so an infinite Mock-walk (the 34.86 GB runaway class of bug)
can never starve the host again. The last printed START line names the
test that was running when memory blew up.

Usage:
    python tools/run_suite_traced.py tests.test_design_extended [ceiling_mb]
"""

from __future__ import annotations

import ctypes
import importlib
import os
import sys
import threading
import time
import unittest
from ctypes import wintypes


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
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


_psapi = ctypes.WinDLL("psapi")
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi.GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
    wintypes.DWORD,
]


def commit_mb() -> float:
    info = PROCESS_MEMORY_COUNTERS()
    info.cb = ctypes.sizeof(info)
    handle = _kernel32.GetCurrentProcess()
    if not _psapi.GetProcessMemoryInfo(handle, ctypes.byref(info), info.cb):
        return -1.0
    return info.PagefileUsage / (1024.0 * 1024.0)


CEILING_MB = float(sys.argv[2]) if len(sys.argv) > 2 else 4096.0
_stop = threading.Event()


def _watchdog() -> None:
    while not _stop.wait(0.2):
        current = commit_mb()
        if current > CEILING_MB:
            print(
                f"WATCHDOG: commit {current:.0f} MB exceeded ceiling "
                f"{CEILING_MB:.0f} MB -- hard exit",
                flush=True,
            )
            os._exit(77)


class TracedResult(unittest.TextTestResult):
    def startTest(self, test):
        print(f"START {test.id()} mem={commit_mb():.0f}MB", flush=True)
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        print(f"END   {test.id()} mem={commit_mb():.0f}MB", flush=True)


def main() -> int:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    threading.Thread(target=_watchdog, daemon=True).start()
    module = importlib.import_module(sys.argv[1])
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(module)
    print(f"suite tests={suite.countTestCases()} ceiling={CEILING_MB:.0f}MB", flush=True)
    runner = unittest.TextTestRunner(verbosity=0, resultclass=TracedResult)
    result = runner.run(suite)
    _stop.set()
    print(f"FINAL mem={commit_mb():.0f}MB", flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
