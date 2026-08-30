"""N8 步骤 6 复验：tangent mate 实机验证（IEntity 面选择路径）+ delete_mate 闭环。

ADR-0009 遗留：tangent(4)/width(17) 在 T11 仅确认常量值，mate 本身未验证
（SelectByID2 按名 FACE 不可靠）。本轮用 N8 已证路径复验 tangent：
  comp.GetBody() → 面遍历（GetFirstFace/GetNextFace）→ 面积最大面启发
  （box 顶/底面 2400 最大；圆柱侧面 2513 最大）→ mods.IEntity.Select2
  → AddMate5(tangent=4) → mate 名；再走生产 delete_mate 删除复检。
width 需 4 面选择的专用槽/薄片 fixture，超出 N8 范围 → 联动 N15。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import VARIANT, gencache

from solidworks_mcp.solidworks_api import assembly as asm_api, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.utils.com import call_or_value

OUT_DIR = Path(__file__).resolve().parents[2] / "output" / "e2e-work"


def _largest_face(mods, comp):
    typed_comp = mods.IComponent2(comp._oleobj_)
    body = typed_comp.GetBody()
    typed_body = mods.IBody2(body._oleobj_)
    best, best_area = None, -1.0
    face = typed_body.GetFirstFace()
    while face is not None:
        typed_face = mods.IFace2(face._oleobj_)  # GetNextFace 仅 typed 可达
        try:
            area = float(typed_face.GetArea())
        except Exception:
            area = 0.0
        if area > best_area:
            best, best_area = typed_face, area
        face = typed_face.GetNextFace()
    print(f"    largest face area = {best_area:.4f} m^2")
    return mods.IEntity(best._oleobj_)


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    app = sw.app
    mods = gencache.GetModuleForProgID("SldWorks.Application")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app.CloseAllDocuments(True)
    box_path = str(OUT_DIR / "probe_tw_box.SLDPRT")
    cyl_path = str(OUT_DIR / "probe_tw_cyl.SLDPRT")
    part.create_box(sw, 60.0, 40.0, 20.0, box_path, True)
    file_io.close_document(sw, False)
    part.create_cylinder(sw, 20.0, 40.0, cyl_path, True)
    file_io.close_document(sw, False)

    from solidworks_mcp.utils.templates import get_assembly_template
    file_io._open_doc6(app, box_path, 1)
    file_io._open_doc6(app, cyl_path, 1)
    asm = app.NewDocument(get_assembly_template(), 0, 0, 0)
    if asm is None:
        print("!! NewDocument failed")
        return 4
    asm.AddComponent4(box_path, "", 0.0, 0.0, 0.0)
    asm.AddComponent4(cyl_path, "", 0.05, 0.0, 0.0)
    comps = asm.GetComponents(False)
    cyl_comp = None
    for c in comps:
        if "cyl" in str(call_or_value(c, "Name2")).lower():
            cyl_comp = c
    box_comp = comps[0]
    print("components:", [str(call_or_value(c, "Name2")) for c in comps])

    print("== tangent mate（IEntity 面选择 + AddMate5 type=4）==")
    ent_box = _largest_face(mods, box_comp)
    ent_cyl = _largest_face(mods, cyl_comp)
    asm.ClearSelection2(True)
    if not (ent_box.Select2(False, 0) and ent_cyl.Select2(True, 0)):
        print("!! entity select failed")
        return 5
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    mate = asm.AddMate5(4, 0, False, 0, 0, 0, 0, 0, 0, 0, 0,
                        False, False, 0, err)
    mate_name = str(call_or_value(mate, "Name")) if mate is not None else None
    print(f"  AddMate5(tangent=4) -> {mate_name!r} err={err.value}")
    asm.ClearSelection2(True)

    ok = mate_name is not None
    if ok:
        print("== delete_mate（生产函数实机验证）==")
        result = asm_api.delete_mate(sw, mate_name)
        print("  delete_mate:", result["success"], result.get("message"))
        ok = bool(result["success"])

    app.CloseAllDocuments(True)
    print("SUMMARY:", "tangent_verified+delete_ok" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
