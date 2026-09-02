"""N32 探针：装配图 BOM 表 + 自动气泡全链（2026-09-01 SW 2026 v34.2.1）。

取证（类型库+反射）：
  - IView.InsertBomTable5(UseAnchorPoint, X, Y, AnchorType, BomType,
    Configuration, TableTemplate, Hidden, IndentedNumberingType,
    DetailedCutList, DissolvePartLevelRows) 11 参；
    swBomType_PartsOnly=1 / swBOMConfigurationAnchor_TopLeft=1
  - IDrawingDoc.AutoBalloon4(Layout, IgnoreMultiple, Style, Size,
    UpperTextContent, UpperText, LowerTextContent, LowerText, Layername,
    BalloonsToFaces) 10 参；swBS_SplitCirc=7
链路：两零件（box/cylinder 各存盘）→ 装配 2 组件 → 建图（drawing 域
先例）→ 选视图 → InsertBomTable5 → AutoBalloon4 → 判据=视图注解数增长
+ PDF 落盘（弱判据）。

结论（2026-09-01 实机）：
1. **BOM 表 OK**：`IView.InsertBomTable5(False, x_m, y_m, 1, 1/2, "", "",
   False, 0, False, False)`（PartsOnly=1/TopLevelOnly=2，锚点 1=左上）返回
   表对象、进 PDF（43-46KB）。→ 生产工具 `drawing_insert_bom_table`。
2. **AutoBalloon 家族 BLOCKED（证据完备 10+ 变体）**：AutoBalloon(1 参)/
   AutoBalloon2(2 参)/AutoBalloon4(10 参，Style Circular=1/SplitCirc=7、
   Size 0/3、Layout 0/1) × typed IDrawingDoc/dynamic 全部**静默返回 None**
   （无异常、注解数不动、PDF 无气泡）——T8-mirror/pattern/rib/combine 同
   族。swBalloonTextItemNumber=1（反射确认）。终极路径=宏录制器对照。
3. **assembly.add_component 生产 bug（已修）**：`_preopen_component_document`
   的 OpenDoc6 把活动文档切到零件后 `_get_or_create_assembly` 只认活动文档
   → 每次 add 新建装配、组件漂移丢失（两组件场景实测只剩 1 个）。修复=
   先取装配再 preopen + AddComponent4 落在记住的装配 + ActivateDoc3 切回。
4. 装配图建图：`create_drawing_from_part` 校验限 .sldprt——装配图走
   NewDocument(模板)+CreateDrawViewFromModelView3（本探针抄核心）。
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom

from solidworks_mcp.solidworks_api import assembly, design, drawing, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.geometry import latest_feature_name, mm_to_m
from solidworks_mcp.utils.com import call_or_value

OUT = Path(__file__).resolve().parents[2] / "output" / "n32_probe"


def _make_parts(sw):
    OUT.mkdir(exist_ok=True)
    paths = []
    for name, builder in (
        ("box20", lambda: part.create_box(sw, 40.0, 30.0, 10.0, save_path=str(OUT / "box20.sldprt"), overwrite_confirm=True)),
        ("cyl10", lambda: part.create_cylinder(sw, 16.0, 25.0, save_path=str(OUT / "cyl10.sldprt"), overwrite_confirm=True)),
    ):
        assert design.create_new_part(sw)["success"], name
        r = builder()
        assert r["success"], (name, r)
        paths.append(r["data"]["saved_to"])
        file_io.close_document(sw, save_changes=False)
    return paths


def _make_assembly(sw, paths):
    assert assembly.new_assembly(sw, save_path=str(OUT / "asm.sldasm"), overwrite_confirm=True)["success"]
    for p in paths:
        r = assembly.add_component(sw, p)
        assert r["success"], (p, r)
    saved = sw.get_active_document().SaveAs3(str(OUT / "asm.sldasm"), 0, 1)
    print(f"[asm] components={assembly.get_components(sw)['data']['components']}")
    return str(OUT / "asm.sldasm")


def _view_annotation_count(drawing_model, view) -> int:
    count = call_or_value(view, "GetAnnotationCount")
    return count if isinstance(count, int) else -1


def main() -> int:
    sw = get_solidworks_app()
    assert sw.connect(launch_if_needed=True)["success"]
    try:
        sw.app.CloseAllDocuments(True)
    except Exception:
        pass
    paths = _make_parts(sw)
    asm_path = _make_assembly(sw, paths)
    file_io.close_document(sw, save_changes=False)

    # 装配图：create_drawing_from_part 校验限 .sldprt——探针抄其核心
    # （模板 + NewDocument + 单前视图，投影对 BOM 非必需）
    from solidworks_mcp.solidworks_api.drawing import FRONT_XY, _resolve_template

    template = _resolve_template(sw.app)
    drawing_doc = sw.app.NewDocument(template, 12, 0.0, 0.0)  # 12 = A3
    print(f"[dwg] doc={drawing_doc is not None} template={template}")
    if drawing_doc is None:
        return 1
    front = drawing_doc.CreateDrawViewFromModelView3(
        os.path.abspath(asm_path), "", FRONT_XY[0], FRONT_XY[1], 0.0
    )
    print(f"[dwg] front view: {front!r}")
    if front is None:
        return 1
    model = sw.get_active_document()

    # 选中前视图（T12 先例：工程图视图N / DRAWINGVIEW）
    view_name = None
    for candidate in ("工程图视图1", "Drawing View1", "工程图视图2"):
        if model.Extension.SelectByID2(
            candidate, "DRAWINGVIEW", 0, 0, 0, False, 0, pythoncom.Nothing, 0
        ):
            view_name = candidate
            break
    print(f"[dwg] view selected: {view_name!r}")
    if view_name is None:
        return 1
    view = model.SelectionManager.GetSelectedObject6(1, -1)
    count0 = _view_annotation_count(model, view)

    # BOM 表：PartsOnly=1，锚点 TopLeft=1，不用模板锚点、放图面右上角
    table = view.InsertBomTable5(
        False, 0.24, 0.02, 1, 1, "", "", False, 0, False, False
    )
    print(f"[bom] table: {table!r}")
    # 诊断：BOM 表行数（0 行=组件未被收录，气泡无从生成）
    try:
        anns = table.GetTableAnnotations()
        first = anns[0] if anns else None
        rows = call_or_value(first, "GetRowCount") if first else None
        cols = call_or_value(first, "GetColumnCount") if first else None
        print(f"[bom] table annotations={len(anns) if anns else 0} rows={rows} cols={cols}")
    except Exception as exc:  # noqa: BLE001
        print(f"[bom] diag EXC {exc!r}")
    count1 = _view_annotation_count(model, view)

    # 自动气泡（SplitCirc=7；UpperTextContent=1=swBalloonTextItemNumber）
    # dynamic 调用静默零产出（Blend2 同族）——typed IDrawingDoc 直调
    from win32com.client import gencache

    mods = gencache.GetModuleForProgID("SldWorks.Application")
    typed_dwg = mods.IDrawingDoc(model._oleobj_)
    balloons = None
    variants = [
        ("ab1", lambda: typed_dwg.AutoBalloon(0)),
        ("ab2", lambda: typed_dwg.AutoBalloon2(0, True)),
        ("ab4_circ", lambda: typed_dwg.AutoBalloon4(
            0, True, 1, 3, 1, "", 0, "", "", False)),
        ("ab4_dyn", lambda: model.AutoBalloon2(0, True)),
    ]
    for tag, fn in variants:
        model.ClearSelection2(True)
        if not model.Extension.SelectByID2(
            view_name, "DRAWINGVIEW", 0, 0, 0, False, 0, pythoncom.Nothing, 0
        ):
            continue
        try:
            balloons = fn()
            print(f"[balloon:{tag}] ret={balloons!r}")
            if balloons not in (None, 0, False):
                break
        except Exception as exc:  # noqa: BLE001
            print(f"[balloon:{tag}] EXC {exc!r}")
    count2 = _view_annotation_count(model, view)

    pdf = OUT / "asm_bom.pdf"
    code = model.SaveAs3(str(pdf), 0, 1)
    size = pdf.stat().st_size if pdf.exists() else 0
    ok = count2 > count1 >= count0 and size > 10_000
    print(
        f"[pdf] code={code} size={size}B; annotations {count0}->{count1}->{count2} "
        f"=> {'OK' if ok else 'MISS'}"
    )
    file_io.close_document(sw, save_changes=False)
    print("SUMMARY:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
