"""实机探针：T21-1 真实螺纹（helix+扫描切除）与 T21-3 钣金（Base-Flange）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_part\\probe_sheet_metal_thread.py
前置：SolidWorks 已启动。
取证目标：
  A. 钣金：顶面矩形草图 → FeatureManager.InsertSheetMetalBaseFlange
     (厚度米, ThickenDir, 半径米, 拉伸距离米, ...) → 特征树/体积判定
     （60×40 矩形板 t=2 → 体积≈4800mm³）
  B. 螺纹：圆柱 ⌀20×50 → 顶面 ⌀20 圆草图 → ModelDoc2.InsertHelix
     (11 参, Helixdef 定义方式) → 轴截面三角草图 → InsertCutSwept5?
     逐段判定；helix 特征选中机制是最大风险点
"""
from __future__ import annotations

import os
import sys

import pythoncom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solidworks_mcp.solidworks_api import file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.geometry import mm_to_m, walk_feature_names
from solidworks_mcp.solidworks_api.measure import get_bounding_box
from solidworks_mcp.utils.com import call_or_value

OUT_DIR = Path(__file__).resolve().parents[2] / "output" / "e2e-work"


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    app = sw.app
    app.CloseAllDocuments(True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- A. 钣金 Base-Flange ---
    blank = str(OUT_DIR / "probe_sm_blank.SLDPRT")
    from solidworks_mcp.solidworks_api import design
    made = design.create_new_part(sw, blank, True)
    print("new part:", made.get("success"))
    model = sw.get_active_document()
    # 顶面矩形草图（60×40 中心化）
    from solidworks_mcp.solidworks_api.geometry import select_plane
    ok = select_plane(model, ["Top Plane", "上视基准面"], use_extension_fallback=False)
    print("select top plane:", ok)
    sm = model.SketchManager
    sm.InsertSketch(True)
    sm.CreateCornerRectangle(
        mm_to_m(-30.0), mm_to_m(-20.0), 0.0,
        mm_to_m(30.0), mm_to_m(20.0), 0.0,
    )
    sm.InsertSketch(True)
    fm = call_or_value(model, "FeatureManager")
    print("FeatureManager:", fm is not None)
    try:
        feat = fm.InsertSheetMetalBaseFlange(
            mm_to_m(2.0),      # Thickness
            False,             # ThickenDir
            mm_to_m(0.0),      # Radius（平板无折弯）
            mm_to_m(0.0),      # ExtrudeDist1（轮廓自身封闭则 0）
            0.0,               # ExtrudeDist2
            False,             # FlipExtruDir
            0, 8,              # EndCondition1=给定? EndCondition2
            0,                 # DirToUse
            pythoncom.Nothing, # PCBA（dispatch 型，整型 0 报类型不匹配）
            True, 0, 0.0, 0.0, 0.0, True,  # relief 选项（默认）
        )
        name = call_or_value(feat, "Name") if feat is not None else None
        print("BaseFlange ->", feat is not None, "name:", name)
    except Exception as exc:
        print("BaseFlange EXC:", repr(exc)[:200])
    print("tree:", walk_feature_names(model)[-6:])
    mass = part.get_mass_properties(sw)
    print("mass:", mass.get("success"), (mass.get("data") or {}).get("volume_mm3"))
    bb = get_bounding_box(sw)
    print("bbox:", (bb.get("data") or {}).get("size_mm"))
    app.CloseAllDocuments(True)

    # --- B. 螺纹 helix + 扫描 ---
    rod = str(OUT_DIR / "probe_thread_rod.SLDPRT")
    print("\ncylinder:", part.create_cylinder(sw, 20.0, 50.0, rod, True).get("success"))
    model = sw.get_active_document()
    # 顶面 ⌀20 圆 → InsertHelix
    faces = part  # noqa
    top = part._select_top_face(model)
    print("top face selected:", top is not None)
    if top is not None:
        sm = model.SketchManager
        sm.InsertSketch(True)
        sm.CreateCircleByRadius(0, 0, 0, mm_to_m(10.0))
        sm.InsertSketch(True)
        # InsertHelix 真实 10 参（typelib）：
        # (Reversed, Clockwised, Tapered, Outward, Helixdef, Height,
        #  Pitch, Revolution, TaperAngle, Startangle)
        for helixdef in (0, 1, 2, 3):
            try:
                helix_ok = model.InsertHelix(
                    False, False, False, False,
                    helixdef,
                    0.0,                # Height（def=0/1 用）
                    mm_to_m(2.0),       # Pitch
                    20.0,               # Revolution
                    0.0, 0.0,           # TaperAngle, Startangle
                )
                print(f"InsertHelix def={helixdef} -> {helix_ok!r}")
            except Exception as exc:
                print(f"InsertHelix def={helixdef} EXC:", repr(exc)[:160])
        print("tree:", walk_feature_names(model)[-5:])
        # 三角截面（前视基准面）+ 螺旋线选中 + 扫描切除
        from solidworks_mcp.solidworks_api.geometry import select_plane as sp
        if sp(model, ["Front Plane", "前视基准面"], use_extension_fallback=False):
            sm.InsertSketch(True)
            # 齿形三角：x 从 9.5 到 10.2（跨外径 10），y 高 1.0（螺距 2 的一半）
            sm.CreateLine(
                mm_to_m(9.4), mm_to_m(-0.4), 0.0,
                mm_to_m(10.3), mm_to_m(0.4), 0.0,
            )
            sm.CreateLine(
                mm_to_m(10.3), mm_to_m(0.4), 0.0,
                mm_to_m(9.4), mm_to_m(1.2), 0.0,
            )
            sm.CreateLine(
                mm_to_m(9.4), mm_to_m(1.2), 0.0,
                mm_to_m(9.4), mm_to_m(-0.4), 0.0,
            )
            sm.InsertSketch(True)
            print("profile sketch tree:", walk_feature_names(model)[-3:])
        for curve_type in ("REFERENCECURVES", "Helix", "COMPOSITECURVE"):
            ok = model.Extension.SelectByID2(
                "螺旋线1", curve_type, 0, 0, 0, False, 1,
                pythoncom.Nothing, 0,
            ) or model.Extension.SelectByID2(
                "螺旋线/涡状线1", curve_type, 0, 0, 0, False, 1,
                pythoncom.Nothing, 0,
            )
            if ok:
                print("helix selected as", curve_type)
                break
        else:
            print("helix SELECT FAIL（各类型均不中）")
        fm2 = call_or_value(model, "FeatureManager")
        if ok and fm2 is not None:
            sketch_name = walk_feature_names(model)[-1]
            ok2 = model.Extension.SelectByID2(
                sketch_name, "SKETCH", 0, 0, 0, True, 1,
                pythoncom.Nothing, 0,
            )
            print("profile sketch selected:", ok2)
            try:
                feat = fm2.InsertCutSwept4(
                    False,   # Propagate
                    False,   # Alignment (none)
                    0,       # TwistCtrlOption (none)
                    False, False,  # KeepTangency, AdvancedSmoothing
                    0, 0,    # Start/EndMatchingType
                    False, 0.0, 0.0, 0,  # ThinBody trio
                    0,       # PathAlign
                    True, True,  # UseFeatScope, UseAutoSelect
                    0.0, True, False, False, False,
                )
                print("InsertCutSwept4 ->", feat)
                print("tree after sweep:", walk_feature_names(model)[-4:])
                mass2 = part.get_mass_properties(sw)
                print("mass after:", (mass2.get("data") or {}).get("volume_mm3"))
            except Exception as exc:
                print("InsertCutSwept4 EXC:", repr(exc)[:200])
    app.CloseAllDocuments(True)
    print("\ndone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
