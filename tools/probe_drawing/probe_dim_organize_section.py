"""N4 实机探针：尺寸去重/错开 + 剖视图 API 取证（2026-08-30，8 轮收敛）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_drawing\\probe_dim_organize_section.py
取证目标：
  A. 类型库枚举（makepy 后 gencache）：IDisplayDimension / IDrawingDoc Section* / IView
  B. 实机遍历每个 DisplayDimension：FullName、选择名、注记定位（米制）
  C. 实机试删一个重复尺寸；试剖视图签名
结论（探针后回填）：
  1. 遍历：IView.GetDisplayDimensions 是零参属性（动态 dispatch 下不加括号）→
     tuple[IDisplayDimension]；GetDisplayDimensionCount 同为零参属性（计数判据）。
  2. 去重键：dd.GetDimension2(0).FullName（如 'D1@凸台-拉伸1@probe_n4_plate.Part'）；
     dd.GetText(0/1/2) 返回空串不可用作键。
  3. 删除链路（第 8 轮打通）：
     selname = call_or_value(dd, "GetNameForSelection")  # 零参属性，工程图专用名
       → 'D1@凸台-拉伸1@probe_n4_plate-2@工程图视图1'（FullName 选择返回 False！）
     ext.SelectByID2(selname, "DIMENSION", 0,0,0, False, 0, Nothing, 0) -> True
     drawing.DeleteSelection(True) -> True  # 带参方法！无参报 DISP_E_PARAMNOTFOUND
     删除后计数 1→0；被删对象后续 COM 调用报“对象已断开”（预期）。
  4. 错开：ann = dd.GetAnnotation（零参属性）→ ann.GetPosition()/SetPosition(x,y,z)
     实测成功（米制图纸坐标），SetPosition 返回 True 且位置变化。
     ann.Select/Select2/SelectByMark 选择可用但 Select3 参数类型不匹配——
     选择一律走 SelectByID2(selname)，不依赖 ann.Select*。
  5. 剖视图（三轮稳定）：sm.CreateLine 画剖切线（探针 ±0.02m）→
     sketch = call_or_value(drawing, "GetActiveSketch2"); name = sketch.Name →
     drawing.CreateSectionViewAt4(x, y, 0.0, name, 0, 0) 返回剖视图对象。
     CreateSectionView/At/At2/At3 均拒（参数数/类型）；At5 不在动态 dispatch。
  6. 环境注记：Parameter.MarkedForDrawing 当前 SW 会话失联（T12 时曾可用），
     尺寸只入 1 个——工具面向“尺寸已存在”场景，不阻塞。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import VARIANT, gencache

from solidworks_mcp.solidworks_api import file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.utils.com import call_or_value

OUT_DIR = Path(__file__).resolve().parents[2] / "output" / "e2e-work"
MAX_DDS = 60


def _dir_filtered(obj, keywords) -> list[str]:
    try:
        names = dir(obj)
    except Exception as exc:
        return [f"<dir exc {exc!r:.80}>"]
    return [n for n in names if any(k.lower() in n.lower() for k in keywords)]


def _typelib_module():
    """Return the generated SldWorks typelib module, generating it once."""
    module = gencache.GetModuleForProgID("SldWorks.Application")
    if module is not None:
        return module
    # EnsureDispatch cannot automate makepy for SldWorks; generate via CLI.
    import subprocess
    subprocess.run(
        [sys.executable, "-m", "win32com.client.makepy",
         "SldWorks 2026 Type Library"],
        capture_output=True, timeout=120,
    )
    return gencache.GetModuleForProgID("SldWorks.Application")


def phase_a_typelib(app) -> None:
    print("=" * 20, "A. 类型库枚举", "=" * 20)
    mods = _typelib_module()
    if mods is None:
        print("typelib module unavailable even after makepy; skip phase A")
        return
    dd = mods.IDisplayDimension
    print("-- IDisplayDimension Text/Point/Position/Value/Orientation/Delete/Select:")
    for n in _dir_filtered(dd, ["text", "point", "position", "value", "orient", "delete", "select"]):
        print("   ", n)
    print("-- IDrawingDoc Section*:")
    doc = mods.IDrawingDoc
    for n in _dir_filtered(doc, ["section"]):
        print("   ", n)
    view = mods.IView
    print("-- IView DisplayDimension members:")
    for n in _dir_filtered(view, ["displaydimension"]):
        print("   ", n)
    # docstring 摘录关键签名
    print("-- key docstrings:")
    for name in ("GetText", "GetTextCount", "GetTextAt", "GetBasePoint",
                 "SetTextPosition", "GetTextPosition"):
        attr = getattr(dd, name, None)
        if attr is not None and getattr(attr, "__doc__", None):
            print(f"    {name}: {attr.__doc__[:160]}")
    for name in (n for n in dir(doc) if "section" in n.lower()):
        attr = getattr(doc, name, None)
        if attr is not None and getattr(attr, "__doc__", None):
            print(f"    {name}: {attr.__doc__[:200]}")


def _walk_views(model) -> list:
    views = []
    view = call_or_value(model, "GetFirstView")
    for _ in range(50):
        if view is None:
            break
        name = call_or_value(view, "Name")
        if not isinstance(name, str):
            break
        views.append((name, view))
        view = call_or_value(view, "GetNextView")
    return views


def _collect_dds(view, name: str) -> list:
    """GetDisplayDimensions is a zero-arg PROPERTY returning a tuple (verified)."""
    dds: list = []
    try:
        got = call_or_value(view, "GetDisplayDimensions")
        if got:
            dds = list(got)
            print(f"  view {name!r}: GetDisplayDimensions(prop) -> {len(dds)}")
            return dds
        print(f"  view {name!r}: GetDisplayDimensions(prop) -> empty")
    except Exception as exc:
        print(f"  GetDisplayDimensions exc: {exc!r:.100}")
    return dds


def phase_b_walk_dimensions(drawing) -> list:
    print("=" * 20, "B. 实机遍历 DisplayDimension", "=" * 20)
    mods = _typelib_module()
    if mods is not None:
        ann_cls = getattr(mods, "IAnnotation", None)
        if ann_cls is not None:
            print("-- IAnnotation key members:",
                  _dir_filtered(ann_cls, ["position", "delete", "select", "name"]))
            for nm in ("Select", "Select2", "Select3", "DeSelect"):
                attr = getattr(ann_cls, nm, None)
                if attr is not None and getattr(attr, "__doc__", None):
                    print(f"    IAnnotation.{nm}: {attr.__doc__[:200]}")
    found = []
    for name, view in _walk_views(drawing):
        try:
            count = call_or_value(view, "GetDisplayDimensionCount")
        except Exception:
            count = None
        if not count:
            continue
        print(f"view {name!r}: count={count}")
        for dd in _collect_dds(view, name):
            rec = {"view": name}
            try:
                dim = dd.GetDimension2(0)
                rec["full"] = call_or_value(dim, "FullName")
            except Exception as exc:
                rec["full"] = f"<{type(exc).__name__}>"
            try:
                # 与 GetDisplayDimensions 同理：零参成员在动态 dispatch 下是属性
                rec["selname"] = call_or_value(dd, "GetNameForSelection")
            except Exception as exc:
                rec["selname"] = f"<{type(exc).__name__}>"
            texts = {}
            for mid in range(0, 3):
                try:
                    texts[mid] = dd.GetText(mid)
                except Exception:
                    break
            rec["gettext"] = texts
            try:
                ann = dd.GetAnnotation
                rec["annpos"] = call_or_value(ann, "GetPosition")
            except Exception as exc:
                rec["annpos"] = f"<{type(exc).__name__}>"
            found.append((rec, dd))
            print("  ", rec)
    return found


def _delete_selection(drawing) -> bool:
    """DeleteSelection(AlsoDeleteUnusedFeaturesAndRefs) 是带参方法（无参即 PARAMNOTFOUND）。"""
    for arg in (True, False):
        try:
            ret = drawing.DeleteSelection(arg)
            print(f"drawing.DeleteSelection({arg}) -> {ret!r}")
            if ret:
                return True
        except Exception as exc:
            print(f"drawing.DeleteSelection({arg}) EXC: {exc!r:.140}")
    return False


def phase_c_mutations(drawing, app, dds: list) -> None:
    print("=" * 20, "C. 删除/剖视图试验", "=" * 20)
    # C1: 试 Delete 一个尺寸（挑文本重复的第二个；找不到就最后一个）
    victims = []
    seen_text: dict = {}
    for rec, dd in dds:
        key = str(rec.get("gettext", {}).get(1, "")) + str(rec.get("dim2"))
        if key in seen_text:
            victims.append(dd)
        else:
            seen_text[key] = True
    if not victims and dds:
        victims = [dds[-1][1]]
    if victims:
        victim = victims[0]
        try:
            ann = victim.GetAnnotation
            print("runtime ann dir:",
                  _dir_filtered(ann, ["delete", "position", "select"]))
        except Exception as exc:
            print(f"victim GetAnnotation exc: {exc!r:.100}")
            ann = None
        deleted = False
        # 路线0：Extension.SelectByID2(GetNameForSelection,"DIMENSION") + DeleteSelection
        # （FullName 选择返回 False——尺寸选择专用名走 GetNameForSelection）
        full_names = []
        for rec, dd_ in dds:
            if dd_ is not victim:
                continue
            nm = rec.get("selname")
            if isinstance(nm, str) and nm and not nm.startswith("<"):
                full_names.append(nm)
            elif isinstance(rec.get("full"), str):
                full_names.append(rec["full"])
        mods0 = gencache.GetModuleForProgID("SldWorks.Application")
        if mods0 is not None:
            print("dd Select members:",
                  _dir_filtered(mods0.IDisplayDimension, ["select"]))
        ext2 = call_or_value(drawing, "Extension")
        for nm in dict.fromkeys(full_names):
            try:
                sel = ext2.SelectByID2(nm, "DIMENSION", 0.0, 0.0, 0.0, False, 0,
                                       pythoncom.Nothing, 0)
                print(f"ext.SelectByID2({nm!r}, DIMENSION) -> {sel!r}")
                if sel:
                    ret = _delete_selection(drawing)
                    if ret:
                        deleted = True
                        break
            except Exception as exc:
                print(f"SelectByID2({nm!r}) EXC: {exc!r:.140}")
        if not deleted:
            # 路线0b：dd.Select3 参数形态对比 + DeleteSelection
            for args in ((False, 0), (False, 0, 0)):
                try:
                    sel = victim.Select3(*args)
                    print(f"dd.Select3{args!r} -> {sel!r}")
                    if sel:
                        ret = call_or_value(drawing, "DeleteSelection")
                        print(f"drawing.DeleteSelection -> {ret!r}")
                        if ret:
                            deleted = True
                            break
                except Exception as exc:
                    print(f"dd.Select3{args!r} EXC: {exc!r:.140}")
            if deleted:
                pass
        if not deleted and ann is not None:
            # 路线0c：ann.Select 家族 × 参数形态（裸 / VARIANT）+ DeleteSelection
            for meth in ("Select", "Select2", "Select3", "SelectByMark"):
                for args in (
                    (False,) if meth == "Select" else (False, 0),
                    (VARIANT(pythoncom.VT_BOOL, False),)
                    if meth == "Select"
                    else (VARIANT(pythoncom.VT_BOOL, False), VARIANT(pythoncom.VT_I4, 0)),
                ):
                    try:
                        sel = getattr(ann, meth)(*args)
                        print(f"ann.{meth}{args!r:.40} -> {sel!r}")
                        if sel:
                            ret = _delete_selection(drawing)
                            if ret:
                                deleted = True
                                break
                    except Exception as exc:
                        print(f"ann.{meth}{args!r:.40} EXC: {exc!r:.140}")
                if deleted:
                    break
        if ann is not None:
            # 路线1：ann.Select3 + drawing.DeleteSelection
            try:
                sel = ann.Select3(False, 0)
                print(f"ann.Select3(False,0) -> {sel!r}")
                if sel:
                    ret = _delete_selection(drawing)
                    if ret:
                        deleted = True
            except Exception as exc:
                print(f"ann.Select3/DeleteSelection EXC: {exc!r:.140}")
        if not deleted and ann is not None:
            for deleter in ("Delete", "Delete3", "Delete2"):
                try:
                    ret = getattr(ann, deleter)()
                    print(f"ann.{deleter}() -> {ret!r}")
                    if ret:
                        deleted = True
                        break
                except Exception as exc:
                    print(f"ann.{deleter} EXC: {exc!r:.120}")
        if not deleted:
            for deleter in ("Delete",):
                try:
                    ret = getattr(victim, deleter)()
                    print(f"dd.{deleter}() -> {ret!r}")
                    if ret:
                        deleted = True
                        break
                except Exception as exc:
                    print(f"dd.{deleter} EXC: {exc!r:.120}")
        call_or_value(drawing, "EditRebuild3")
        total = sum(
            call_or_value(v, "GetDisplayDimensionCount") or 0
            for _, v in _walk_views(drawing)
        )
        print(f"after delete(deleted={deleted}): total dims = {total}")
    else:
        print("no duplicate victim available for delete test")

    # C1b: SetPosition 错开试验（删除未必成功，任意尺寸都可当 mover 实测）
    movers = [dd for _, dd in dds]
    if movers and dds:
        try:
            ann = movers[0].GetAnnotation
            pos = call_or_value(ann, "GetPosition")
            print(f"mover ann.GetPosition() = {pos!r}")
            ret = ann.SetPosition(pos[0] + 0.005, pos[1] + 0.005, pos[2])
            print(f"ann.SetPosition(+5mm) -> {ret!r}; now {call_or_value(ann, 'GetPosition')!r}")
        except Exception as exc:
            print(f"SetPosition exc: {exc!r:.140}")

    # C2: 剖视图 API 签名尝试（仅枚举存在的成员）
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    if mods is None:
        mods = _typelib_module()
    doc_cls = mods.IDrawingDoc
    cands = [n for n in dir(doc_cls) if "section" in n.lower()]
    print(f"section candidates on IDrawingDoc: {cands}")
    # 在主视图上画一条竖直剖切线再调 CreateSectionViewAt5（若存在）
    views = _walk_views(drawing)
    main = next((v for n, v in views if n and "工程图" not in n), None)
    if main is None:
        print("no model view found; skip section test")
        return
    main_name = call_or_value(main, "Name")
    ext = call_or_value(drawing, "Extension")
    try:
        drawing.IActivateView(main_name)
    except Exception as exc:
        print(f"IActivateView exc: {exc!r:.100}")
    pos = call_or_value(main, "Position")
    cpos = call_or_value(main, "GetCenter") if hasattr(main, "GetCenter") else None
    print(f"main view {main_name!r} Position={pos!r} GetCenter={cpos!r}")
    x0 = float(pos[0])
    y0 = float(pos[1])
    sm = drawing.SketchManager
    seg = sm.CreateLine(x0, y0 + 0.02, 0.0, x0, y0 - 0.02, 0.0)
    print(f"SketchManager.CreateLine -> {seg!r:.60}")
    sketch_name = call_or_value(drawing, "GetActiveSketch2")
    print(f"GetActiveSketch2 -> {sketch_name!r}")
    try:
        sketch_name = sketch_name.Name
    except Exception:
        pass
    for cand in cands:
        if not cand.lower().startswith("createsectionview"):
            continue
        fn = getattr(drawing, cand, None)
        if fn is None:
            print(f"{cand}: not on runtime dispatch")
            continue
        print(f"{cand} doc: {getattr(doc_cls, cand).__doc__[:220]}")
        for args in (
            (x0 + 0.05, y0, 0.0, str(sketch_name), 0, 0),
            (x0 + 0.05, y0, 0.0, str(sketch_name), 0, ""),
        ):
            try:
                ret = fn(*args)
                print(f"{cand}{args!r:.80} -> {ret!r:.80}")
                if ret:
                    return
            except Exception as exc:
                print(f"{cand}{args!r:.60} EXC: {exc!r:.140}")


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    app = sw.app
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app.CloseAllDocuments(True)

    phase_a_typelib(app)

    box_path = str(OUT_DIR / "probe_n4_plate.SLDPRT")
    made = part.create_box(sw, 60.0, 40.0, 8.0, box_path, True)
    if not made.get("success"):
        print(f"create_box failed: {made}")
        return 4
    file_io.close_document(sw, False)

    templates = app.GetUserPreferenceStringValue(10)
    print(f"drawing template = {templates!r}")
    drawing = app.NewDocument(templates, 0, 0.0, 0.0)
    if drawing is None:
        return 5
    abs_part = os.path.abspath(box_path)
    front = drawing.CreateDrawViewFromModelView3(abs_part, "", 0.15, 0.10, 0.0)
    print(f"front view -> {front!r:.60}")
    ext = call_or_value(drawing, "Extension")
    front_name = call_or_value(front, "Name")
    ext.SelectByID2(front_name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0,
                    pythoncom.Nothing, 0)
    drawing.CreateUnfoldedViewAt3(0.15, 0.19, 0.0, False)
    ext.SelectByID2(front_name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0,
                    pythoncom.Nothing, 0)
    drawing.CreateUnfoldedViewAt3(0.27, 0.10, 0.0, False)
    # 尺寸插入：未标记时 v2 只入 1 个；v3/v4 全类型变体或许更高（探针验证）
    from tools.probe_drawing.probe_drawing import _mark_all_dimensions_for_drawing
    try:
        marked = _mark_all_dimensions_for_drawing(app, abs_part)
    except Exception as exc:
        marked = -1
        print(f"mark exc: {exc!r:.120}")
    print(f"marked for drawing: {marked}")
    best = 0
    for tag, call in (
        ("v2", lambda: drawing.InsertModelAnnotations2(0, True, 0, True, True, False)),
        ("v3-1023", lambda: drawing.InsertModelAnnotations3(0, 1023, True, True, False, True)),
        ("v4-1023", lambda: drawing.InsertModelAnnotations4(0, 1023, True, True, False, True, True, True)),
    ):
        try:
            call()
            call_or_value(drawing, "EditRebuild3")
            total = sum(
                call_or_value(v, "GetDisplayDimensionCount") or 0
                for _, v in _walk_views(drawing)
            )
            print(f"insert {tag}: total dims = {total}")
            best = max(best, total)
        except Exception as exc:
            print(f"insert {tag} EXC: {exc!r:.140}")
    print(f">> best total dims = {best}")

    dds = phase_b_walk_dimensions(drawing)
    phase_c_mutations(drawing, app, dds)

    app.CloseAllDocuments(True)
    os.remove(abs_part) if os.path.exists(abs_part) else None
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
