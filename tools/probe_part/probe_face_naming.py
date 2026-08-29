"""实机探针：面命名与选中机制（T5 步骤 7，2026-08-29 实测结论）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_face_naming.py
自足：新建零件 + 60x40x20 盒，list_faces 命名，验证两件事后关闭文档：
  1. 名称持久：SetEntityName → 保存 → 重开 → GetEntityName 回读一致；
  2. 有效选中机制：SelectByID2 按名（裸名/@标题/@标题.SLDPRT 三形态）在 SW 2026
     **均失败**（SKETCH/BODYFEATURE 类型可按名选中，FACE 不行）；改用
     「遍历面 → GetEntityName 匹配 → face.Select2(False, 0)」直接对象选中，实测 True。
后续 T7（圆角）/T11（mate）的选择型特征一律走 walk+Select2，勿依赖按名 SelectByID2 选面。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.topology import list_bodies, list_faces
from solidworks_mcp.utils.com import call_or_value

WORK = Path(__file__).resolve().parents[2] / "output" / "e2e-work" / "probe_named.SLDPRT"


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2

    if not design.create_new_part(sw)["success"]:
        return 3
    if not part.create_box(sw, 60, 40, 20)["success"]:
        return 3

    bodies = list_bodies(sw)
    print("list_bodies:", bodies["success"], bodies.get("message"))

    result = list_faces(sw)
    print("list_faces:", result["success"], result.get("message"))
    target = result["data"]["faces"][0]["name"]
    for f in result["data"]["faces"][:6]:
        print("OK=", f["name"], f["surface_type"], round(f["area_mm2"], 3), "mm2")

    model = sw.get_active_document()
    model.SaveAs3(str(WORK), 0, 1)
    title = file_io._model_title(model)

    by_name = False
    for cand in (target, f"{target}@{title}", f"{target}@{title}.SLDPRT"):
        model.ClearSelection2(True)
        by_name = bool(
            model.Extension.SelectByID2(
                cand, "FACE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
            )
        )
        print(f"SelectByID2 {cand!r} -> {by_name}")
        if by_name:
            break

    file_io.close_document(sw, save_changes=False)
    reopened = file_io.open_document(sw, str(WORK))
    print("reopen:", reopened["success"])

    model = sw.get_active_document()
    body = model.GetBodies2(0, False)[0]
    face = call_or_value(body, "GetFirstFace")
    name_after = model.GetEntityName(face)
    print(f"name persists across save/reopen: {name_after == target} ({name_after})")

    selected = False
    if name_after == target:
        walked, match = call_or_value(body, "GetFirstFace"), None
        while walked is not None:
            if model.GetEntityName(walked) == target:
                match = walked
                break
            walked = call_or_value(walked, "GetNextFace")
        if match is not None:
            model.ClearSelection2(True)
            selected = bool(match.Select2(False, 0))
            print(f"walk+Select2 on {target!r} -> {selected}")

    file_io.close_document(sw, save_changes=False)
    print(f"SUMMARY: by_name={by_name}; walk_select2={selected}; name_persists={name_after == target}")
    return 0 if (selected and name_after == target) else 1


if __name__ == "__main__":
    sys.exit(main())
