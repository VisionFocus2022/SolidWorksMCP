"""N4 补充探针（第 9 轮）：e2e 剖视图失败复现与变体定位（2026-08-30）。

e2e 现象：CreateSectionViewAt4 返回 None（sketch '草图1'，placement (0.27, 0.1)）。
第 8 轮探针成功场景与 e2e 的差异：剖切线长度/落点（第 8 轮线画在 sheet 视图
Position=(0,0) 的空白处，e2e 画在模型视图 Position 边上）、草图编号。
本轮：A 复现 → B 视图几何情报（IView Position 语义/尺寸成员）→ C 长线穿几何
变体 → D 先选草图再创建 → E 换 placement。
结论（探针后回填，第 9-12 轮）：
  1. 剖切线必须落在 **sheet 级空白区**：画在模型视图区域上的线会被归入该视图
     的草图，CreateSectionViewAt4 随后返回 None（第 9-11 轮：长线穿几何/
     seg.Select4 先选/EXTSKETCHSEGMENT/SKETCH 选择/MakeSectionLine 全部失败）。
  2. IView.Position 是视图锚点（左下角），不是中心；Width/Height/GetCenter
     成员均不存在。剖切线画在视图外紧邻空白区（竖直→下方，水平→左侧）即可。
  3. 成功契约（第 12 轮双线验证）：空白区 CreateLine → GetActiveSketch2().Name
     → CreateSectionViewAt4(x, y, 0, 草图名, 0, 0) 返回真剖视图（视图链 2→4，
     名如“剖面视图 草图1-草图1”）；连续两笔各建成功（草图1/草图3）。
  4. CreateSectionViewAt5 全参数形态拒（PARAMNOTFOUND）；
     ICreateSectionViewAt4 参数数拒；SectionName 参数传剖视图名（任意字符串）。
  5. 附带发现：SW 长会话后 InsertModelAnnotations2 可能一个尺寸都不入
     （SW_NO_EFFECT），重启 SW 恢复——与 MarkedForDrawing 失联同源的环境漂移。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import gencache

from solidworks_mcp.solidworks_api import drawing as drawing_api, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.utils.com import call_or_value

OUT = Path(__file__).resolve().parents[2] / "output" / "e2e-work"


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SW not running")
        return 2
    app = sw.app
    app.CloseAllDocuments(True)
    OUT.mkdir(parents=True, exist_ok=True)
    box = str(OUT / "probe_n9_box.SLDPRT")
    part.create_box(sw, 60.0, 40.0, 8.0, box, True)
    file_io.close_document(sw, False)

    r = drawing_api.create_drawing_from_part(sw, box)
    print("create:", r.get("success"))
    drawing_api.insert_model_dimensions(sw)
    drawing_api.organize_dimensions(sw)

    # A. 复现 e2e 失败（当前实现：线 x=左下角 x，y 跨 ±0.02）
    r = drawing_api.insert_section_view(sw, "工程图视图1", 0.0, "vertical")
    print("A current impl:", r.get("success"), r.get("message", "")[:140])

    model = sw.get_active_document()

    # B. 视图几何情报：IView.Position 语义 + 尺寸成员
    view = None
    v = call_or_value(model, "GetFirstView")
    for _ in range(20):
        if v is None:
            break
        if call_or_value(v, "Name") == "工程图视图1":
            view = v
            break
        v = call_or_value(v, "GetNextView")
    pos = call_or_value(view, "Position")
    print("view Position:", pos)
    for m in ("Width", "Height", "GetCenter", "Size"):
        try:
            print(f"view {m}:", call_or_value(view, m))
        except Exception as e:
            print(f"view {m}: <{type(e).__name__}>")
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    if mods is not None:
        names = [n for n in dir(mods.IView) if any(
            k in n.lower() for k in ("width", "height", "center", "bound"))]
        print("IView size members:", names)

    x0, y0 = float(pos[0]), float(pos[1])
    sm = call_or_value(model, "SketchManager")

    # B：CreateSectionViewAt5（历轮从未实测：At4 成功即 return）+ 已选线
    mods0 = gencache.GetModuleForProgID("SldWorks.Application")
    doc_cls = mods0.IDrawingDoc
    print("B At5 doc:", getattr(doc_cls, "CreateSectionViewAt5").__doc__)
    seg = sm.CreateLine(x0 + 0.05, y0 - 0.06, 0.0, x0 + 0.05, y0 + 0.06, 0.0)
    print("B seg.Select4:", seg.Select4(False, pythoncom.Nothing))
    ret = None
    for args in (
        (x0 + 0.15, y0, 0.0, "A", 0, 0),
        (x0 + 0.15, y0, 0.0, "A", 0),
        (x0 + 0.15, y0, 0.0, "A"),
    ):
        try:
            ret = model.CreateSectionViewAt5(*args)
            print(f"B At5 {len(args)}p -> {ret}")
            if ret is not None:
                break
        except Exception as e:
            print(f"B At5 {len(args)}p EXC: {e!r:.140}")

    if ret is None:
        # C：I 前缀低级版（参数 VARIANT 兼容性不同）
        try:
            ret = model.ICreateSectionViewAt4(x0 + 0.15, y0, 0.0, "A", 0, 0)
            print("C ICreateSectionViewAt4 ->", ret)
        except Exception as e:
            print(f"C ICreateSectionViewAt4 EXC: {e!r:.140}")

    if ret is not None:
        print("section view name:", call_or_value(ret, "Name"))

    # D：剖切语义验证——两条不同 x 的空白区竖直线各建剖视图 + PNG 目检
    from solidworks_mcp.solidworks_api.constants import swSaveAsOptions_Silent

    def count_views(doc) -> int:
        n, v = 0, call_or_value(doc, "GetFirstView")
        for _ in range(20):
            if v is None:
                break
            n += 1
            v = call_or_value(v, "GetNextView")
        return n

    app.CloseAllDocuments(True)
    tmpl = app.GetUserPreferenceStringValue(10)
    print("D template:", tmpl)
    d2 = app.NewDocument(tmpl, 0, 0.0, 0.0)
    d2.CreateDrawViewFromModelView3(os.path.abspath(box), "", 0.15, 0.10, 0.0)
    sm2 = call_or_value(d2, "SketchManager")
    # 线1：x=0.00，y 跨 ±0.02（sheet 原点，远离视图）
    sm2.CreateLine(0.00, 0.02, 0.0, 0.00, -0.02, 0.0)
    name_a = call_or_value(call_or_value(d2, "GetActiveSketch2"), "Name")
    v1 = d2.CreateSectionViewAt4(0.08, 0.02, 0.0, name_a, 0, 0)
    print(f"D line1 x=0.00 sketch={name_a!r} -> ",
          v1 is not None and call_or_value(v1, "Name"))
    # 线2：x=0.05（视图左缘 x 向），画在视图下方空白区 y∈[-0.08,-0.04]
    sm2.CreateLine(0.05, -0.04, 0.0, 0.05, -0.08, 0.0)
    name_b = call_or_value(call_or_value(d2, "GetActiveSketch2"), "Name")
    v2 = d2.CreateSectionViewAt4(0.25, -0.05, 0.0, name_b, 0, 0)
    print(f"D line2 x=0.05 below sketch={name_b!r} -> ",
          v2 is not None and call_or_value(v2, "Name"))
    print(f"D views = {count_views(d2)}")
    call_or_value(d2, "ViewZoomtofit2")
    png = str(OUT / "probe_n12_section.png")
    r3 = d2.SaveAs3(png, 0, swSaveAsOptions_Silent)
    print(f"D png save -> {r3}; {png}")

    app.CloseAllDocuments(True)
    os.remove(box) if os.path.exists(box) else None
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
