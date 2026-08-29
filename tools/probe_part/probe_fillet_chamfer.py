"""实机探针：面圆角 FeatureFillet3 + 面倒角 FeatureChamfer（T7 步骤 1，2026-08-29）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_fillet_chamfer.py
选中机制走 T5 结论：遍历面 → GetEntityName 匹配 → face.Select2(append, mark)
（SelectByID2 按名选不中 FACE，见 tools/probe_face_naming.py）。
候选 API（本机 typelib 权威，计划的 FeatureFillet3-22参 / InsertFeatureChamfer4 不存在）：
  IModelDoc2.FeatureFillet3(R1, Propagate, Ftyp, VarRadTyp, OverflowType,
                            NRadii, Radii, UseHelpPoint, UseTangentHoldLine)
  IModelDoc2.FeatureChamfer(Width, Angle, Flip)   # Angle 弧度
几何：60x40x20 盒 → 全 6 面 R5 圆角（bbox 应保持 [60,40,20]，体积下降）
→ 单面 2mm 45° 倒角（体积进一步下降，重建无错）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.measure import get_bounding_box
from solidworks_mcp.solidworks_api.part import get_mass_properties
from solidworks_mcp.solidworks_api.topology import list_faces
from solidworks_mcp.utils.com import call_or_value


def _select_named_faces(model, wanted):
    """T5 结论机制：遍历面 → GetEntityName 匹配 → Select2(append, mark=1)。"""
    model.ClearSelection2(True)
    selected, missing = 0, list(wanted)
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            name = model.GetEntityName(face)
            if name in wanted:
                if face.Select2(True, 1):
                    selected += 1
                missing.remove(name)
            face = call_or_value(face, "GetNextFace")
    return selected, missing


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2

    if not design.create_new_part(sw)["success"]:
        return 3
    if not part.create_box(sw, 60, 40, 20)["success"]:
        return 3
    model = sw.get_active_document()

    listing = list_faces(sw)
    all_names = [f["name"] for f in listing["data"]["faces"]]
    print("named faces:", all_names)

    v0 = get_mass_properties(sw)["data"]["volume"] * 1e9
    print(f"volume before: {v0:.1f} mm3 (expect 48000)")

    # --- 圆角：全部 6 面 R5 ---
    from solidworks_mcp.solidworks_api.features import _find_feature
    from solidworks_mcp.solidworks_api.geometry import latest_feature_name

    selected, missing = _select_named_faces(model, all_names)
    print(f"fillet selection: {selected} faces, missing={missing}")
    before_fillet = latest_feature_name(model)
    code = model.FeatureFillet3(
        0.005,  # R1（米）
        False,  # Propagate
        0,      # Ftyp = swConstRad
        False,  # VarRadTyp
        0,      # OverflowType
        1,      # NRadii
        (0.005,),  # Radii
        False,  # UseHelpPoint
        False,  # UseTangentHoldLine
    )
    after_fillet = latest_feature_name(model)
    fillet_feat = _find_feature(model, after_fillet) if after_fillet != before_fillet else None
    print(f"FeatureFillet3 -> code={code!r} ({type(code).__name__}); "
          f"feature={after_fillet!r} type={call_or_value(fillet_feat, 'GetTypeName2') if fillet_feat else 'N/A'}")
    box = get_bounding_box(sw)
    mass1 = get_mass_properties(sw)
    v1 = mass1["data"]["volume"] * 1e9 if mass1["success"] else -1
    print(f"bbox after fillet: {box['data']['size_mm'] if box['success'] else box['message']}")
    print(f"volume after fillet: {v1:.1f} mm3 (bbox 应保持 [60,40,20], 体积下降)")

    # --- 倒角：单面 2mm 45° ---
    selected, missing = _select_named_faces(model, all_names[:1])
    print(f"chamfer selection: {selected} face")
    before_cham = latest_feature_name(model)
    ret = model.FeatureChamfer(0.002, math.pi / 4, False)
    after_cham = latest_feature_name(model)
    cham_feat = _find_feature(model, after_cham) if after_cham != before_cham else None
    print(f"FeatureChamfer -> ret={ret!r} ({type(ret).__name__}); "
          f"feature={after_cham!r} type={call_or_value(cham_feat, 'GetTypeName2') if cham_feat else 'N/A'}")
    mass = get_mass_properties(sw)
    v2 = mass["data"]["volume"] * 1e9 if mass["success"] else -1
    print(f"volume after chamfer: {v2:.1f} mm3 (应进一步下降, rebuild ok={mass['success']})")

    file_io.close_document(sw, save_changes=False)
    ok = fillet_feat is not None and cham_feat is not None and v0 > v1 > v2 >= 0
    print(f"SUMMARY: {'OK' if ok else 'FAILED'} (v0={v0:.0f} > v1={v1:.0f} > v2={v2:.0f})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
