"""实机探针定稿：工程图建图/三视图/自动尺寸/导出 PDF+PNG（T12，2026-08-29 实测契约）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_drawing.py
实机契约（供 drawing.py 实现）：
  - 模板发现：GetUserPreferenceStringValue(10)（swDefaultTemplateDrawing）→ GB 模板
    C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2026\\templates\\gb_a0..gb_a4p.drwdot；8/9=part/assembly
  - app.NewDocument(template, 0, 0.0, 0.0)（有模板时纸型参数被忽略）→ 动态 dispatch；
    GetType=3（swDocDRAWING，零参属性）；GetTitle='工程图1 - 图纸1'；GetSheetCount 零参属性
  - drawing.InsertModelAnnotations3(Option, Types, AllViews, DuplicateDims, HiddenFeatureDims,
    UsePlacementInSketch)——宿主是 **IDrawingDoc 本体**（typelib），不是 Extension！
    计划文档写 Extension 是错的；Extension 对象上 GetIDsOfNames 报 AttributeError。
  - 视图链：model.GetFirstView/GetNextView（零参属性）；视图计数判据=链长
  - 尺寸链：view.GetFirstDisplayDimension/GetNextDisplayDimension（零参属性）
  - PDF：drawing.SaveAs3(path, 0, swSaveAsOptions_Silent) → 0；A0 模板空图 44KB
  - PNG：SaveAs3 直出偏小（1KB），先 ViewZoomtofit2（零参属性）再导出验证
待二轮验证：Create1stAngleViews2 返回 False 的原因（ActivateDoc3？模板？）；
  手动三视图 CreateDrawViewFromModelView3 + SelectByID2("DRAWINGVIEW") + CreateUnfoldedViewAt3。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import VARIANT

from solidworks_mcp.solidworks_api import file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.constants import swSaveAsOptions_Silent
from solidworks_mcp.utils.com import call_or_value

OUT_DIR = Path(__file__).resolve().parents[2] / "output" / "e2e-work"

MAX_VIEWS = 50
MAX_DIMS_PER_VIEW = 200


def _find_templates(app) -> list[str]:
    found: list[str] = []
    pref_drawing = app.GetUserPreferenceStringValue(10)
    print(f"GetUserPreferenceStringValue(10) = {pref_drawing!r}")
    if isinstance(pref_drawing, str) and pref_drawing.lower().endswith(".drwdot"):
        found.append(pref_drawing)
    common_dir = Path(r"C:/ProgramData/SolidWorks") / "SOLIDWORKS 2026" / "templates"
    if common_dir.is_dir():
        for path in sorted(common_dir.glob("gb_a*.drwdot")):
            text = str(path)
            if text not in found:
                found.append(text)
    return found


def _walk_views(model) -> list:
    views = []
    view = call_or_value(model, "GetFirstView")
    for _ in range(MAX_VIEWS):
        if view is None:
            break
        name = call_or_value(view, "Name")
        if not isinstance(name, str):  # 退化代理哨兵（遍历铁律）
            break
        # 判据走 typelib 背书的零参属性：尺寸计数 + 注记计数
        try:
            n = call_or_value(view, "GetDisplayDimensionCount")
        except Exception:
            n = None
        try:
            ann = call_or_value(view, "GetAnnotationCount")  # IView 成员，注记计数
        except Exception:
            ann = None
        views.append((name, n, ann))
        view = call_or_value(view, "GetNextView")
    return views


def _report(drawing, tag: str) -> int:
    views = _walk_views(drawing)
    dims = sum(v[1] for v in views)
    anns = sum(a for _, _, a in views if isinstance(a, int))
    print(f"[{tag}] dims={dims} anns={anns} {views}")
    return dims


def _activate(app, title: str) -> None:
    """ActivateDoc3(title, True, 0, errors-byref)；typed 包装器拒 VARIANT 时用纯 int 重试。"""
    errs = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    try:
        app.ActivateDoc3(title, True, 0, errs)
        print(f"ActivateDoc3({title!r}) -> errs={errs.value}")
    except TypeError as exc:
        print(f"ActivateDoc3 byref rejected ({exc!r:.80}), retry plain int")
        app.ActivateDoc3(title, True, 0, 0)


def _png_size(path: Path):
    """读 IHDR（字节 16-24 大端 u32 宽高），无 Pillow 依赖。"""
    if not path.exists():
        return None
    head = path.read_bytes()[:24]
    if len(head) < 24 or head[12:16] != b"IHDR":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _mark_all_dimensions_for_drawing(app, box_path: str) -> int:
    """打开零件，把所有 DisplayDimension 对应 Dimension.MarkedForDrawing 置 True。

    走查模式照抄 features._feature_dimensions（已实机验证）：
    feat.GetFirstDisplayDimension（零参）→ disp.GetDimension2(0) →
    FullName(str) 哨兵 → feat.GetNextDisplayDimension(disp) 带参步进。
    """
    from solidworks_mcp.solidworks_api import features as feats

    model, err, _ = file_io._open_doc6(app, box_path, 1)  # 1 = swDocPART
    if model is None:
        print(f"reopen part failed err={err}")
        return -1
    marked = 0
    names = []
    for feat in feats.walk_features(model):
        try:
            disp = call_or_value(feat, "GetFirstDisplayDimension")
        except Exception:
            continue
        steps = 0
        while disp is not None and steps < 100:
            steps += 1
            try:
                dim = disp.GetDimension2(0)
                if not isinstance(getattr(dim, "FullName", None), str):
                    break
                names.append(dim.FullName)
            except Exception as exc:
                print(f"walk dim exc: {exc!r:.140}")
                break
            try:
                disp = feat.GetNextDisplayDimension(disp)
            except Exception:
                break
    # GetDimension2 返回对象不解析 MarkedForDrawing（<unknown>）——走 model.Parameter
    for full_name in names:
        try:
            dim = model.Parameter(full_name)
            before = call_or_value(dim, "MarkedForDrawing")
            dim.MarkedForDrawing = True
            if marked < 6:
                print(f"  {full_name!r} marked {before!r} -> True")
            marked += 1
        except Exception as exc:
            print(f"  mark {full_name!r} exc: {exc!r:.140}")
    call_or_value(model, "EditRebuild3")
    try:
        saved = model.Save3(swSaveAsOptions_Silent, 0, 0)  # typed 包装器 byref 拒 VARIANT（quirk #2）
    except TypeError:
        saved = model.Save3(swSaveAsOptions_Silent, *file_io._make_error_variants())[:1]
    print(f"marked {marked} dimensions; Save3 -> {saved!r}")
    app.CloseDoc(call_or_value(model, "GetTitle"))
    return marked


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    app = sw.app
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app.CloseAllDocuments(True)  # 防御：清掉上轮崩溃遗留（工程图引用零件会锁文件）

    templates = _find_templates(app)
    print(f"templates = {templates}")
    if not templates:
        return 3
    # 优先 A3（gb_a3），否则用户默认（pref 10 通常=A0），再否则第一个
    template = next(
        (t for t in templates if t.lower().endswith("gb_a3.drwdot")), templates[0]
    )
    print(f"chosen template = {template}")

    box_path = str(OUT_DIR / "probe_dw_box.SLDPRT")
    made = part.create_box(sw, 60.0, 40.0, 20.0, box_path, True)
    print(f"create_box: success={made.get('success')}")
    if not made.get("success"):
        return 4
    file_io.close_document(sw, False)

    drawing = app.NewDocument(template, 0, 0.0, 0.0)
    print(f"NewDocument -> {drawing!r:.80}")
    if drawing is None:
        return 5
    title = call_or_value(drawing, "GetTitle")
    print(f"GetTitle = {title!r}; GetType = {call_or_value(drawing, 'GetType')!r}")
    _activate(app, title)
    active_title = call_or_value(app, "ActiveDoc")
    print(f"ActiveDoc is drawing: {active_title is not None and call_or_value(active_title, 'GetTitle') == title}")

    abs_part = os.path.abspath(box_path)
    try:
        ok = drawing.Create1stAngleViews2(abs_part)
    except Exception as exc:
        ok = None
        print(f"Create1stAngleViews2 EXC: {exc!r:.200}")
    views = _walk_views(drawing)
    print(f"Create1stAngleViews2 -> {ok!r}; views = {views}")

    if not ok or len(views) < 2:
        # 手动三视图兜底：主视图 → 选它 → 投影视图（CreateUnfoldedViewAt3）
        print(">> 手动三视图路径")
        front = drawing.CreateDrawViewFromModelView3(abs_part, "", 0.15, 0.10, 0.0)
        print(f"CreateDrawViewFromModelView3 -> {front!r:.80}")
        front_name = call_or_value(front, "Name") if front is not None else None
        print(f"front view Name = {front_name!r}")
        if front_name:
            # NewDocument 返回的 dispatch 只解析 IModelDoc+IDrawingDoc 成员面
            # （SelectByID2 属 ModelDoc2，直接调 AttributeError）——选中走 Extension 9 参版
            ext = call_or_value(drawing, "Extension")
            sel = ext.SelectByID2(front_name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0,
                                  pythoncom.Nothing, 0)
            print(f"Extension.SelectByID2(DRAWINGVIEW) -> {sel!r}")
            top = drawing.CreateUnfoldedViewAt3(0.15, 0.19, 0.0, False)
            print(f"CreateUnfoldedViewAt3(top) -> {top!r:.80}")
            sel = ext.SelectByID2(front_name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0,
                                  pythoncom.Nothing, 0)
            side = drawing.CreateUnfoldedViewAt3(0.27, 0.10, 0.0, False)
            print(f"CreateUnfoldedViewAt3(side) -> {side!r:.80}")
        views = _walk_views(drawing)
        print(f"views after manual route = {views}")

    # 尺寸插入：宿主是 DrawingDoc 本体（typelib 18258-18282，非 Extension）。
    # v2 旧版带 AllTypes 布尔，未标记阶段已实证可入 1 尺寸；先标记全部尺寸再插，验证全量入图。
    def try_insert(tag, call):
        try:
            ret = call()
        except Exception as exc:
            print(f"[{tag}] EXC: {exc!r:.200}")
            return 0
        call_or_value(drawing, "EditRebuild3")
        return _report(drawing, tag)

    _mark_all_dimensions_for_drawing(app, os.path.abspath(box_path))
    _activate(app, title)
    winner = None
    attempts = [
        ("v2 all-types", lambda: drawing.InsertModelAnnotations2(0, True, 0, True, True, False)),
        ("v1 all-types", lambda: drawing.InsertModelAnnotations(0, True, 0, True)),
        ("v3 t=1023", lambda: drawing.InsertModelAnnotations3(0, 1023, True, True, False, True)),
        ("v4 all", lambda: drawing.InsertModelAnnotations4(0, 1023, True, True, False, True, True, True)),
    ]
    for tag, call in attempts:
        if try_insert(tag, call) > 0:
            winner = tag
            break
    print(f">> 标记后胜者: {winner!r}")

    # 缩放到整页再导出（PNG 直出偏小的假设）
    try:
        call_or_value(drawing, "ViewZoomtofit2")
        print("ViewZoomtofit2 ok")
    except Exception as exc:
        print(f"ViewZoomtofit2 exc: {exc!r:.120}")

    for out_name in ("probe_dw_box.pdf", "probe_dw_box.png"):
        out_path = str(OUT_DIR / out_name)
        if os.path.exists(out_path):
            os.remove(out_path)
        try:
            ret = drawing.SaveAs3(out_path, 0, swSaveAsOptions_Silent)
        except Exception as exc:
            ret = f"<exc {exc!r:.160}>"
        size = os.path.getsize(out_path) if os.path.exists(out_path) else -1
        print(f"SaveAs3 {out_name}: ret={ret!r} size={size}")
        if out_name.endswith(".png"):
            print(f"png IHDR: {_png_size(OUT_DIR / 'probe_dw_box.png')}")

    # 清理：工程图引用零件，CloseAllDocuments(True) 连引用件一起释放（文件锁教训）
    app.CloseAllDocuments(True)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
