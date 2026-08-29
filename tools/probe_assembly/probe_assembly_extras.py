"""实机探针：装配增强 T11——新建装配/干涉检查/BOM/mate 三新类型。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_assembly_extras.py
前置：SolidWorks 已启动。
取证目标：
  1. 装配模板（get_assembly_template / GetUserPreferenceStringValue(9)=gb_assembly.asmdot）
     → NewDocument(tpl,0,0,0) → GetType==2
  2. InterferenceDetectionManager（IAssemblyDoc 零参属性）→
     TreatCoincidenceAsInterference/TreatSubBodiesAsInterference 属性可写？→
     GetInterferences（零参）在重叠时非空（读 Volume/组件名）、分离时空
  3. 组件 GetPathName（零参属性）/ReferencedConfiguration（属性）→ BOM 聚合素材
  4. AddMate5 常量实证：tangent(4?)、angle(6?)、width(17?)——angle 的 Distance 槽传弧度
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import VARIANT

from solidworks_mcp.solidworks_api import file_io, part, topology
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.templates import get_assembly_template

OUT_DIR = Path(__file__).resolve().parents[2] / "output" / "e2e-work"

# swMateType_e 候选（swconst，typelib 无此枚举）
CAND_TANGENT, CAND_ANGLE, CAND_WIDTH = 4, 6, 17


def _select(model, name: str, entity_type: str, append: bool, asm_title: str) -> bool:
    names = [name]
    if name.count("@") == 1:
        names.append(f"{name}@{asm_title}")
    for candidate in names:
        if model.Extension.SelectByID2(
            candidate, entity_type, 0, 0, 0, append, 1, pythoncom.Nothing, 0
        ):
            return True
    return False


def _add_mate_raw(model, mate_type_val: int, dist_m: float):
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    mate = model.AddMate5(
        mate_type_val, 0, False, dist_m, dist_m, dist_m, 0, 0, 0, 0, 0,
        False, False, 0, err,
    )
    return mate, err.value


def _report_interference(model, tag: str) -> None:
    mgr = call_or_value(model, "InterferenceDetectionManager")
    print(f"[{tag}] mgr = {mgr!r:.60}")
    for prop in ("TreatCoincidenceAsInterference", "TreatSubBodiesAsInterference"):
        try:
            setattr(mgr, prop, False)
            print(f"  set {prop}=False ok")
        except Exception as exc:
            print(f"  set {prop} EXC: {exc!r:.100}")
    try:
        count = call_or_value(mgr, "GetInterferenceCount")
    except Exception as exc:
        count = f"<exc {exc!r:.100}>"
    print(f"  GetInterferenceCount = {count!r}")
    try:
        inters = call_or_value(mgr, "GetInterferences")
    except Exception as exc:
        inters = None
        print(f"  GetInterferences EXC: {exc!r:.100}")
    if inters:
        for i, inter in enumerate(inters[:5]):
            volume = call_or_value(inter, "Volume")
            comps = call_or_value(inter, "Components")
            names = [call_or_value(c, "Name2") for c in comps] if comps else []
            print(f"  interference[{i}] volume_m3={volume!r} comps={names}")


def _report_bom(model, tag: str) -> None:
    comps = model.GetComponents(False)
    rows = []
    for comp in comps or []:
        name = call_or_value(comp, "Name2")
        path = call_or_value(comp, "GetPathName")
        cfg = call_or_value(comp, "ReferencedConfiguration")
        rows.append((name, path, cfg))
    print(f"[{tag}] components={len(rows)}")
    for row in rows:
        print(f"  {row[0]!r} cfg={row[2]!r} path={row[1]}")


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    app = sw.app
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app.CloseAllDocuments(True)

    template = get_assembly_template()
    print(f"get_assembly_template -> {template!r}")
    if not template:
        template = app.GetUserPreferenceStringValue(9)
        print(f"pref(9) fallback -> {template!r}")
    if not template or not os.path.isfile(template):
        print("!! 无装配模板")
        return 3

    # 基准零件（面命名持久化，供实体选择）
    box_path = str(OUT_DIR / "probe_asm_box.SLDPRT")
    cyl_path = str(OUT_DIR / "probe_asm_cyl.SLDPRT")
    part.create_box(sw, 60.0, 40.0, 20.0, box_path, True)
    faces = topology.list_faces(sw)
    print("box faces:", [(f["name"], f["area_mm2"]) for f in faces["data"]["faces"]])
    file_io.close_document(sw, False)
    part.create_cylinder(sw, 20.0, 50.0, cyl_path, True)
    faces = topology.list_faces(sw)
    print("cyl faces:", [(f["name"], f["area_mm2"]) for f in faces["data"]["faces"]])
    file_io.close_document(sw, False)

    # --- 装配 A：两盒重叠 → 干涉非空 ---
    # 实机铁律：AddComponent4 要求零件文档已在会话中打开，否则静默 None
    for path in (box_path, cyl_path):
        file_io._open_doc6(app, path, 1)
    asm = app.NewDocument(template, 0, 0, 0)
    print(f"\nNewDocument -> {asm!r:.60}; GetType={call_or_value(asm, 'GetType')!r}")
    if asm is None:
        return 4
    title = os.path.splitext(call_or_value(asm, "GetTitle"))[0]
    c1 = asm.AddComponent4(box_path, "", 0.0, 0.0, 0.0)
    c2 = asm.AddComponent4(box_path, "", 0.01, 0.0, 0.0)  # 10mm 偏移重叠
    print(f"components: {[call_or_value(c, 'Name2') for c in (c1, c2) if c is not None]}")
    _report_bom(asm, "BOM 重叠装配")
    _report_interference(asm, "干涉-重叠")

    # mate 实证（在重叠装配上，失败不影响干涉结论）
    top_face = "Face2@probe_asm_box-1"
    cyl_face = "Face1@probe_asm_cyl-1"
    print("\n-- mate 常量实证 --")
    for tag, val, sel_plan in [
        ("tangent", CAND_TANGENT, [(top_face, "FACE"), (cyl_face, "FACE")]),
        ("angle", CAND_ANGLE, [("前视基准面@probe_asm_box-1", "PLANE"),
                               ("前视基准面@probe_asm_box-2", "PLANE")]),
        ("width", CAND_WIDTH, [("上视基准面@probe_asm_box-1", "PLANE"),
                               ("上视基准面@probe_asm_box-2", "PLANE")]),
    ]:
        asm.ClearSelection2(True)
        ok = True
        for i, (name, etype) in enumerate(sel_plan):
            if not _select(asm, name, etype, i > 0, title):
                print(f"[{tag}] select FAIL {name} {etype}")
                ok = False
                break
        if not ok:
            continue
        dist = math.radians(30.0) if tag == "angle" else 0.0
        try:
            mate, err = _add_mate_raw(asm, val, dist)
            mate_name = call_or_value(mate, "Name") if mate is not None else None
            print(f"[{tag}] val={val} -> mate={mate_name!r} err={err}")
        except Exception as exc:
            print(f"[{tag}] val={val} EXC: {exc!r:.160}")
        asm.ClearSelection2(True)

    # --- 装配 B：分离 → 干涉空 ---
    app.CloseAllDocuments(True)
    asm2 = app.NewDocument(template, 0, 0, 0)
    asm2.AddComponent4(box_path, "", 0.0, 0.0, 0.0)
    asm2.AddComponent4(cyl_path, "", 0.2, 0.0, 0.0)  # 200mm 分离
    _report_bom(asm2, "BOM 分离装配")
    _report_interference(asm2, "干涉-分离")

    app.CloseAllDocuments(True)
    print("\ndone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
