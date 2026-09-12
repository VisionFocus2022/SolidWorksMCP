# -*- coding: utf-8 -*-
"""N57 批次 C：CSG 导出方向 SW 实机 roundtrip（N54 观察项闭环）。

链路：build123d 六角柱脚本（R20 h10，理论 2598.076 mm3）
   → aicad csg_plan_from_script（AST→polygon_prism op，离线互证 2.33e-16 已有）
   → 主仓 rebuild_csg_plan 在真实 SW 重建
   → SW 体积 vs 理论 ±1% 互证。
退出码 0 = 导出方向实机闭环 PASS。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

MAIN_ROOT = Path(__file__).resolve().parents[1]
AICAD_ROOT = MAIN_ROOT / "aicad"
sys.path.insert(0, str(MAIN_ROOT))
sys.path.insert(0, str(AICAD_ROOT))

SCRIPT = (
    "from build123d import *\n\n"
    "PARAMS = {}\n\n\n"
    "def build():\n"
    "    return extrude(RegularPolygon(20, 6), 10)\n"
)
THEORY = 10392.305  # 正六棱柱 R20 h10 = (3*sqrt(3)/2)*R^2*h（首版笔误 2598=R 取 10 的错值，实测双端一致 10392.305 已纠正）


def main() -> int:
    # 1. build123d 实际体积（沙箱真跑，非引用理论）
    from aicad.kernel.sandbox import Sandbox, SandboxLimits
    from aicad.settings import get_settings as aicad_settings

    with tempfile.TemporaryDirectory(prefix="csg-rt-") as d:
        box = Sandbox(SandboxLimits.from_settings(aicad_settings()))
        r = box.run(SCRIPT, {}, Path(d))
        box.close()
    assert r.ok, f"sandbox build failed: {r.message}"
    b123_volume = float(r.report["metrics"]["volume_mm3"])
    print(f"build123d volume: {b123_volume:.3f} (theory {THEORY})", flush=True)

    # 2. AST → CSG plan
    from aicad.interop.sw_features.csg_export import csg_plan_from_script

    plan = csg_plan_from_script(SCRIPT)
    ops = [op["op"] for op in plan["operations"]]
    print(f"csg plan ops: {ops}", flush=True)
    assert ops == ["polygon_prism"], ops

    # 3. SW 实机重建
    import pythoncom
    from solidworks_mcp.solidworks_api.app import SolidWorksApp
    from solidworks_mcp.solidworks_api.design import rebuild_csg_plan

    pythoncom.CoInitialize()
    sw = SolidWorksApp()
    conn = sw.connect(launch_if_needed=False)
    assert conn.get("success") is True, conn
    from solidworks_mcp.solidworks_api.part import get_mass_properties

    try:
        result = rebuild_csg_plan(sw, plan)
        print(f"rebuild: success={result.get('success')} features={(result.get('data') or {}).get('feature_count')}", flush=True)
        assert result.get("success") is True, result
        mass = get_mass_properties(sw)
        assert mass.get("success") is True, mass
        sw_volume = float((mass.get("data") or {}).get("volume")) * 1e9  # m^3 -> mm^3
        print(f"SW volume: {sw_volume:.3f}", flush=True)

        rel = abs(sw_volume - b123_volume) / b123_volume
        print(f"rel diff vs build123d: {rel:.3e} (window 1%)", flush=True)
        assert rel <= 0.01, f"roundtrip mismatch: {rel}"
        print("BATCH C PASS: build123d -> AST -> SW real-machine roundtrip", flush=True)
        return 0
    finally:
        try:
            sw.app.CloseAllDocuments(True)
            print("cleanup: CloseAllDocuments done", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"cleanup warn: {exc}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
