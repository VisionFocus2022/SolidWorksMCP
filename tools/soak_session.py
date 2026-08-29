"""T22-1: 主包长会话 soak——100 轮「create_box → export_step → close」。

用法：venv\\Scripts\\python.exe -X utf8 tools\\soak_session.py
前置：SolidWorks 已启动。产物：output/soak-report-<时间戳>.json。
判定：SW 进程工作集全程增幅 < 100MB 视为平稳（CloseDoc 无句柄泄漏的
必要证据；超过则记录证据并把 F4 升级为缺陷任务，不在本脚本内修）。
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solidworks_mcp.solidworks_api import file_io, part  # noqa: E402
from solidworks_mcp.solidworks_api.app import get_solidworks_app  # noqa: E402

OUT_DIR = ROOT / "output"
WORK_DIR = OUT_DIR / "soak-work"
ROUNDS = 100
SAMPLE_EVERY = 10
RSS_GROWTH_BUDGET_MB = 100.0


def _find_sldworks_pid() -> int | None:
    raw = subprocess.run(
        ["tasklist", "/fo", "csv", "/fi", "IMAGENAME eq SLDWORKS.EXE"],
        capture_output=True,
    ).stdout
    out = raw.decode("gbk", errors="replace")  # 中文系统控制台是 GBK
    for line in out.splitlines()[1:]:
        fields = [f.strip('"') for f in line.split('","')]
        if len(fields) > 1 and fields[0].upper() == "SLDWORKS.EXE":
            return int(fields[1])
    return None


class _PMC(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _rss_mb(pid: int) -> float | None:
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_PMC), ctypes.c_ulong,
    ]
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x0410, False, pid)  # QUERY|READ
    if not handle:
        return None
    try:
        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return None
        return pmc.WorkingSetSize / 1e6
    finally:
        kernel32.CloseHandle(handle)


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    pid = _find_sldworks_pid()
    print(f"SLDWORKS pid = {pid}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    samples = []
    t_start = time.perf_counter()
    failures = 0
    for round_no in range(1, ROUNDS + 1):
        t0 = time.perf_counter()
        box = part.create_box(
            sw, 60.0, 40.0, 20.0, str(WORK_DIR / "soak_box.SLDPRT"), True
        )
        exported = file_io.export_step(
            sw, str(WORK_DIR / "soak_box.step"), True
        )
        closed = file_io.close_document(sw, False)
        ok = box.get("success") and exported.get("success") and closed.get("success")
        if not ok:
            failures += 1
            print(f"[{round_no:3}] FAIL box={box.get('message')!r:.80} "
                  f"export={exported.get('message')!r:.80} "
                  f"close={closed.get('message')!r:.80}")
        if round_no % SAMPLE_EVERY == 0 or round_no == 1:
            rss = _rss_mb(pid) if pid else None
            elapsed = round(time.perf_counter() - t_start, 1)
            samples.append(
                {"round": round_no, "elapsed_s": elapsed,
                 "sw_rss_mb": round(rss, 1) if rss else None}
            )
            print(f"[{round_no:3}] t={elapsed:7.1f}s rss={rss and round(rss,1)}MB "
                  f"round_cost={round(time.perf_counter() - t0, 2)}s")

    total_s = round(time.perf_counter() - t_start, 1)
    first = next((s for s in samples if s["sw_rss_mb"]), None)
    last = next((s for s in reversed(samples) if s["sw_rss_mb"]), None)
    growth = (last["sw_rss_mb"] - first["sw_rss_mb"]) if first and last else None
    stable = growth is not None and growth < RSS_GROWTH_BUDGET_MB

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rounds": ROUNDS, "failures": failures, "total_s": total_s,
        "sw_pid": pid, "samples": samples,
        "sw_rss_growth_mb": growth,
        "stable": stable,
        "verdict": (
            "stable" if stable else
            "leak-suspected" if growth is not None else "unmeasured"
        ),
        "note": (
            "工作集增幅 < 100MB：CloseDoc 长会话无泄漏证据"
            if stable else
            "增幅超预算或未测到——F4 保留为缺陷观察项"
        ),
    }
    out = OUT_DIR / f"soak-report-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n报告：{out}")
    print(f"verdict={report['verdict']} growth={growth}MB "
          f"failures={failures} total={total_s}s")
    return 0 if (failures == 0 and stable) else (3 if failures else 4)


if __name__ == "__main__":
    sys.exit(main())
