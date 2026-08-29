"""实机探针：FeatureRevolve2 回转体（T6 步骤 1，2026-08-29）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_revolve.py
验证「中心线 + 矩形轮廓」草图 → IFeatureManager.FeatureRevolve2(20 参，
参数顺序以本机 typelib 为准) → 特征树回转体。几何：外径40/内径20/高20 环。
期望：bbox=[40,40,20]mm；体积≈π(20²-5²)·20=23562mm³；GetTypeName2 样本。
若直接调用失败：回退「按名选中草图特征再调」。结束关闭文档。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom

from solidworks_mcp.solidworks_api import design, file_io
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.measure import get_bounding_box
from solidworks_mcp.solidworks_api.part import _select_plane
from solidworks_mcp.utils.com import call_or_value


def _try_revolve(model) -> object:
    return model.FeatureManager.FeatureRevolve2(
        True,   # SingleDir
        True,   # IsSolid
        False,  # IsThin
        False,  # IsCut
        False,  # ReverseDir
        False,  # BothDirectionUpToSameEntity
        0,      # Dir1Type = swEndCondBlind
        0,      # Dir2Type
        2 * math.pi,  # Dir1Angle（弧度，全周）
        0.0,    # Dir2Angle
        False,  # OffsetReverse1
        False,  # OffsetReverse2
        0.0,    # OffsetDistance1
        0.0,    # OffsetDistance2
        0,      # ThinType
        0.0,    # ThinThickness1
        0.0,    # ThinThickness2
        True,   # Merge
        True,   # UseFeatScope
        True,   # UseAutoSelect
    )


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2

    if not design.create_new_part(sw)["success"]:
        return 3
    model = sw.get_active_document()

    plane_name = _select_plane(model)
    print("plane:", plane_name)
    if plane_name is None:
        return 3

    # 草图：y 轴中心线（旋转轴）+ 右侧矩形轮廓（内径10/外径40/高20 → 米）
    model.SketchManager.InsertSketch(True)
    axis = model.SketchManager.CreateLine(0, -0.01, 0, 0, 0.01, 0)
    axis.ConstructionGeometry = True
    print("axis marked:", axis.ConstructionGeometry)
    model.SketchManager.CreateCornerRectangle(0.005, -0.01, 0, 0.02, 0.01, 0)
    model.SketchManager.InsertSketch(True)

    feature = _try_revolve(model)
    print("direct revolve ->", "None" if feature is None else type(feature).__name__)
    if feature is None:
        # 回退：按名选中最新草图特征（SKETCH 类型按名选中有效，design.py 实证）
        names = design._latest_feature_name(model)  # noqa: SLF001 探针允许私有
        sketch_name = None
        from solidworks_mcp.solidworks_api.features import get_features

        for name in get_features(sw)["data"]["features"]:
            if name.startswith("草图") or "Sketch" in name:
                sketch_name = name
        print("fallback select sketch:", sketch_name)
        if sketch_name:
            model.ClearSelection2(True)
            model.Extension.SelectByID2(
                sketch_name, "SKETCH", 0, 0, 0, False, 0, pythoncom.Nothing, 0
            )
            feature = _try_revolve(model)
            print("fallback revolve ->", "None" if feature is None else "OK")

    if feature is None:
        file_io.close_document(sw, save_changes=False)
        print("SUMMARY: FAILED")
        return 4

    print("feature name:", feature.Name, "| type:", call_or_value(feature, "GetTypeName2"))
    box = get_bounding_box(sw)
    print("bbox:", box["data"]["size_mm"] if box["success"] else box["message"])
    from solidworks_mcp.solidworks_api.part import get_mass_properties

    mass = get_mass_properties(sw)
    if mass["success"]:
        print("volume_mm3:", round(mass["data"]["volume"] * 1e9, 1), "(expect ≈23561.9)")

    file_io.close_document(sw, save_changes=False)
    print("SUMMARY: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
