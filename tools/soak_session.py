"""T22-1: 主包长会话 soak——「create_box → export_step → close」及其扩展负载。

用法：venv\\Scripts\\python.exe -X utf8 tools\\soak_session.py [--tool-filter F] [--rounds N]
  --tool-filter box-only   基线：box → export_step → close（T22 原链）
  --tool-filter +faces     加 topology.list_faces/list_bodies 面遍历
  --tool-filter +drawing   加 drawing 建图 → PDF 导出 → 全量关闭
  --tool-filter +assembly  加装配 new → add_component×2（预开嫌疑点）→ 全量关闭
前置：SolidWorks 已启动。产物：output/soak-report-<时间戳>.json。
判定：SW 进程工作集全程增幅 < 100MB 视为平稳（CloseDoc 无句柄泄漏的
必要证据；超过则记录证据并把 F4 升级为缺陷任务，不在本脚本内修）。
N10 二分定位：四组各 50 轮同会话顺序跑，组内增量即该负载贡献。
"""

from __future__ import annotations

import argparse
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


def _close_all(sw) -> dict:
    try:
        sw.app.CloseAllDocuments(True)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "message": repr(exc)[:120]}


def _round_box(sw) -> list:
    box = part.create_box(
        sw, 60.0, 40.0, 20.0, str(WORK_DIR / "soak_box.SLDPRT"), True
    )
    exported = file_io.export_step(sw, str(WORK_DIR / "soak_box.step"), True)
    closed = file_io.close_document(sw, False)
    return [box, exported, closed]


def _round_faces(sw) -> list:
    from solidworks_mcp.solidworks_api import topology

    box = part.create_box(
        sw, 60.0, 40.0, 20.0, str(WORK_DIR / "soak_box.SLDPRT"), True
    )
    faces = topology.list_faces(sw)
    bodies = topology.list_bodies(sw)
    closed = file_io.close_document(sw, False)
    return [box, faces, bodies, closed]


def _round_drawing(sw) -> list:
    from solidworks_mcp.solidworks_api import drawing as drawing_api

    box = part.create_box(
        sw, 60.0, 40.0, 20.0, str(WORK_DIR / "soak_box.SLDPRT"), True
    )
    # 盒子已保存：建图会隐式重开引用零件，收尾必须全量关闭
    closed_part = file_io.close_document(sw, False)
    drawn = drawing_api.create_drawing_from_part(
        sw, str(WORK_DIR / "soak_box.SLDPRT")
    )
    pdf = drawing_api.export_drawing_pdf(
        sw, str(WORK_DIR / "soak_box_drawing.pdf"), True
    )
    closed = _close_all(sw)
    return [box, closed_part, drawn, pdf, closed]


def _round_assembly(sw) -> list:
    from solidworks_mcp.solidworks_api import assembly as asm_api

    box = part.create_box(
        sw, 60.0, 40.0, 20.0, str(WORK_DIR / "soak_box.SLDPRT"), True
    )
    closed_part = file_io.close_document(sw, False)
    created = asm_api.new_assembly(
        sw, str(WORK_DIR / "soak_asm.SLDASM"), True
    )
    # add_component 内部预开零件文档（N10 嫌疑点）：每轮两组件叠加
    added1 = asm_api.add_component(sw, str(WORK_DIR / "soak_box.SLDPRT"), 0, 0, 0)
    added2 = asm_api.add_component(sw, str(WORK_DIR / "soak_box.SLDPRT"), 100, 0, 0)
    closed = _close_all(sw)
    return [box, closed_part, created, added1, added2, closed]


LOADOUTS = {
    "box-only": _round_box,
    "+faces": _round_faces,
    "+drawing": _round_drawing,
    "+assembly": _round_assembly,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tool-filter", choices=sorted(LOADOUTS), default="box-only",
        help="负载分组（N10 二分定位；默认 box-only=T22 原链）",
    )
    parser.add_argument(
        "--rounds", type=int, default=ROUNDS,
        help=f"轮数（默认 {ROUNDS}；分组定位用 50）",
    )
    args = parser.parse_args()
    tool_filter = args.tool_filter
    rounds = max(1, args.rounds)
    loadout = LOADOUTS[tool_filter]

    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    pid = _find_sldworks_pid()
    print(f"SLDWORKS pid = {pid}  filter={tool_filter} rounds={rounds}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    samples = []
    t_start = time.perf_counter()
    failures = 0
    for round_no in range(1, rounds + 1):
        t0 = time.perf_counter()
        results = loadout(sw)
        ok = all(r.get("success") for r in results)
        if not ok:
            failures += 1
            print(f"[{round_no:3}] FAIL " + " ".join(
                repr(r.get("message"))[:60] for r in results if not r.get("success")
            ))
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
        "tool_filter": tool_filter,
        "rounds": rounds, "failures": failures, "total_s": total_s,
        "sw_pid": pid, "samples": samples,
        "sw_rss_growth_mb": growth,
        "sw_rss_first_mb": first and first["sw_rss_mb"],
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
