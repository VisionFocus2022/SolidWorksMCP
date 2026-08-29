"""Run pytest inside a Windows Job Object with a hard memory ceiling.

Why this exists: a runaway test once ballooned an orphaned python process to
34.86 GB (the whole host's RAM), starving SolidWorks and every other test run
(WinError 1455 "pagefile too small"). Two kernel-enforced guards prevent a
repeat:

1. JOB_OBJECT_LIMIT_PROCESS_MEMORY -- the job (pytest and all its children)
   may never commit more than ``--max-mem-gb`` gigabytes. A runaway test gets
   MemoryError inside the run instead of consuming the host.
2. JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE -- if the spawning terminal dies (IDE
   timeout, sandbox teardown, user closes the window), the kernel kills the
   whole job. No more orphaned pytest processes left behind.

Usage:
    python tools/run_pytest_guarded.py tests -q
    python tools/run_pytest_guarded.py --max-mem-gb 6 tests --tb=short
"""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
from ctypes import wintypes

JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),  # ULONG_PTR
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def create_guarded_job(max_mem_bytes: int) -> wintypes.HANDLE:
    """Create a job object enforcing the memory ceiling; returns its handle."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise OSError("CreateJobObjectW failed")

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    info.ProcessMemoryLimit = max_mem_bytes

    ok = kernel32.SetInformationJobObject(
        handle,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        raise ctypes.WinError()
    return handle


def peak_job_memory_gb(handle: wintypes.HANDLE) -> float:
    kernel32 = ctypes.windll.kernel32
    kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    ok = kernel32.QueryInformationJobObject(
        handle,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
        None,
    )
    if not ok:
        return 0.0
    return info.PeakJobMemoryUsed / (1024**3)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--max-mem-gb", type=float, default=4.0)
    known, passthrough = parser.parse_known_args()
    if not passthrough:
        passthrough = ["tests"]

    max_bytes = int(known.max_mem_gb * 1024**3)
    handle = create_guarded_job(max_bytes)

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
    ]
    if not kernel32.AssignProcessToJobObject(
        handle, kernel32.GetCurrentProcess()
    ):
        raise ctypes.WinError()

    print(
        f"[guarded] pytest job: memory ceiling {known.max_mem_gb:g} GB, "
        "kill-on-close enabled",
        file=sys.stderr,
    )
    try:
        return subprocess.call([sys.executable, "-m", "pytest", *passthrough])
    finally:
        print(
            f"[guarded] peak job memory: {peak_job_memory_gb(handle):.2f} GB",
            file=sys.stderr,
        )
        kernel32.CloseHandle(handle)


if __name__ == "__main__":
    raise SystemExit(main())
