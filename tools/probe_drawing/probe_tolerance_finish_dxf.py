"""N5 实机探针：公差/粗糙度/注释 + DXF 导出 API 取证（2026-08-30）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_drawing\\probe_tolerance_finish_dxf.py
取证目标：
  A. 类型库枚举：IDisplayDimension Tolerance* / IDrawingDoc SurfaceFinish*|Text*|Note*
     / swToleranceType_e 枚举值（swTolPlusMinus 定位）
  B. 实机公差：ToleranceType=swTolPlusMinus + ToleranceMax/Min 赋值读回（单位验证：米）
  C. 实机粗糙度符号与注释文本：InsertSurfaceFinishSymbol / CreateText2 签名试探
  D. DXF 导出（SaveAs3 silent）+ 文件头字节断言（ASCII vs Binary）
结论（探针后回填，5 轮收敛）：
  1. 公差在 IDimension 层（不在 IDisplayDimension——typelib 中后者 toler 成员为空）：
     dim = dd.GetDimension2(0)（动态 CDispatch）。动态形态下 GetToleranceType
     是零参属性、GetToleranceValues 返回 None、SetTolerance* 不可带参调用——
     必须静态包装：mods = gencache.GetModuleForProgID('SldWorks.Application');
     dim_s = mods.IDimension(dim._oleobj_)（EnsureDispatch 对子对象拒绝）。
     实测：dim_s.SetToleranceType(5) -> True；
     dim_s.SetToleranceValues(TolMin, TolMax)（米制，顺序先 min 后 max）-> True；
     读回 GetToleranceType()=5、GetToleranceValues()=(-5e-05, 0.0001) 精确。
     枚举佐证：0-8 全接受，唯 type=7 时 values 归零 → 序列与 swToleranceType_e
     文档一致（7=Fit 不吃 min/max），故 5=PlusMinus。
     注：DXF 导出不合公差文本（SW DXF 导出对公差显示支持有限），API 读回即验收判据。
  2. 粗糙度：InsertSurfaceFinishSymbol 14 参完整签名（makepy）：
     (SymType, LeaderType, LocX, LocY, LocZ, LaySymbol, ArrowType,
      MachAllowance, OtherVals, ProdMethod, SampleLen, MaxRoughness,
      MinRoughness, RoughnessSpacing)。
     实测 (1, 0, x, y, 0.0, 0, 0, 0.0, 0.0, '', '', '1.6', '', '') -> True；
     SymType 1=去除材料（GB 最常用）；MaxRoughness 传字符串；坐标米制。
     docstring 说 "based on last selection" 但实测无需预选。
  3. 注释：drawing.CreateText2(text, x, y, z, width, height) -> INote COMObject
     成功；返回对象无 GetPosition（是 INote 非 IAnnotation）。CreateText 旧版同在。
  4. DXF：drawing.SaveAs3(path, 0, 1) 恒返回 1（警告码）但文件真实写出——
     判据用文件存在 + 头两行含 'SECTION'，不用返回值。ASCII DXF AC1015
     （AutoCAD 2000），头 b'  0\r\nSECTION'；文本 GBK 编码；粗糙度值 '1.6'
     与注释中文文本均进文件；尺寸以 DIMENSION 实体（<> 占位）导出。
     与 PDF/PNG（返回 0）不同，DXF 恒带警告返回 1。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import gencache

from solidworks_mcp.solidworks_api import file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.utils.com import call_or_value

OUT_DIR = Path(__file__).resolve().parents[2] / "output" / "e2e-work"


def _dir_filtered(obj, keywords) -> list:
    try:
        names = dir(obj)
    except Exception as exc:
        return [f"<dir exc {exc!r:.80}>"]
    return [n for n in names if any(k.lower() in n.lower() for k in keywords)]


def _typelib_module():
    module = gencache.GetModuleForProgID("SldWorks.Application")
    if module is not None:
        return module
    import subprocess
    subprocess.run(
        [sys.executable, "-m", "win32com.client.makepy",
         "SldWorks 2026 Type Library"],
        capture_output=True, timeout=120,
    )
    return gencache.GetModuleForProgID("SldWorks.Application")


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


def phase_a_typelib(app) -> dict:
    print("=" * 20, "A. 类型库枚举", "=" * 20)
    info: dict = {}
    mods = _typelib_module()
    if mods is None:
        print("typelib module unavailable; skip phase A")
        return info
    dd_cls = mods.IDisplayDimension
    print("-- IDisplayDimension Tolerance members:")
    for n in _dir_filtered(dd_cls, ["toler"]):
        print("   ", n)
    for n in _dir_filtered(dd_cls, ["toler"]):
        attr = getattr(dd_cls, n, None)
        if attr is not None and getattr(attr, "__doc__", None):
            print(f"    doc {n}: {attr.__doc__[:200]}")
    doc_cls = mods.IDrawingDoc
    print("-- IDrawingDoc SurfaceFinish members:")
    for n in _dir_filtered(doc_cls, ["surfacefinish"]):
        print("   ", n)
        attr = getattr(doc_cls, n, None)
        if attr is not None and getattr(attr, "__doc__", None):
            print(f"    doc {n}: {attr.__doc__[:260]}")
    print("-- IDrawingDoc Text/Note members:")
    for n in _dir_filtered(doc_cls, ["text", "note"]):
        print("   ", n)
    for n in ("CreateText2", "CreateText", "InsertAnnText", "InsertNote"):
        attr = getattr(doc_cls, n, None)
        if attr is not None and getattr(attr, "__doc__", None):
            print(f"    doc {n}: {attr.__doc__[:260]}")
    # 枚举值
    print("-- swToleranceType_e members:")
    en = getattr(mods, "swToleranceType_e", None)
    plus_minus = None
    if en is not None:
        for n in dir(en):
            if n.startswith("_"):
                continue
            val = getattr(en, n)
            print(f"    {n} = {val}")
            if n == "swTolPlusMinus":
                plus_minus = val
    else:
        consts = getattr(mods, "constants", None)
        if consts is not None:
            plus_minus = getattr(consts, "swTolPlusMinus", None)
            print(f"    constants.swTolPlusMinus = {plus_minus}")
    info["swTolPlusMinus"] = plus_minus
    print("-- swSurfaceFinish* enums:")
    for n in dir(mods):
        if n.startswith("swSurfaceFinish") and not n.startswith("_"):
            en2 = getattr(mods, n)
            vals = [(m, getattr(en2, m)) for m in dir(en2)
                    if not m.startswith("_")]
            print(f"    {n}: {vals[:12]}")
    return info


def _first_dimension(drawing):
    for name, view in _walk_views(drawing):
        try:
            dds = call_or_value(view, "GetDisplayDimensions")
        except Exception:
            dds = None
        if dds:
            first = list(dds)[0]
            full = call_or_value(call_or_value(first, "GetDimension2", args=(0,)), "FullName") \
                if False else None
            try:
                dim = call_or_value(first, "GetDimension2", args=(0,))
                full = call_or_value(dim, "FullName")
            except Exception:
                dim, full = None, None
            print(f"  first dd in view {name!r}: FullName={full!r}")
            return first, full
    return None, None


def phase_b_tolerance(drawing, dd, plus_minus) -> None:
    print("=" * 20, "B. 实机公差试调用（IDimension 层）", "=" * 20)
    if dd is None:
        print("no display dimension available; skip")
        return
    try:
        dim = dd.GetDimension2(0)
        print(f"dd.GetDimension2(0) -> {dim!r:.60}")
    except Exception as exc:
        print(f"GetDimension2 EXC: {exc!r:.140}")
        return
    # 初始公差类型（makepy：IDimension.GetToleranceType）
    for cand, fn in (
        ("dim.GetToleranceType()", lambda: dim.GetToleranceType()),
        ("call_or_value GetToleranceType", lambda: call_or_value(dim, "GetToleranceType")),
    ):
        try:
            print(f"{cand} -> {fn()!r}")
            break
        except Exception as exc:
            print(f"{cand} EXC: {exc!r:.120}")
    # 上下偏差：SetToleranceValues(TolMin, TolMax)（米：-0.05mm/+0.10mm）
    for cand, fn in (
        ("SetToleranceValues(-0.00005, 0.0001)",
         lambda: dim.SetToleranceValues(-0.00005, 0.0001)),
        ("ISetToleranceValues",
         lambda: dim.ISetToleranceValues(-0.00005, 0.0001)),
    ):
        try:
            ret = fn()
            print(f"{cand} -> {ret!r}")
            break
        except Exception as exc:
            print(f"{cand} EXC: {exc!r:.140}")
    for cand, fn in (
        ("GetToleranceValues()", lambda: dim.GetToleranceValues()),
        ("GetToleranceType()", lambda: dim.GetToleranceType()),
    ):
        try:
            print(f"readback {cand} -> {fn()!r}")
        except Exception as exc:
            print(f"readback {cand} EXC: {exc!r:.120}")
    # 第 4 轮：makepy 接口类直接构造静态包装（EnsureDispatch 对子对象拒绝）
    mods = _typelib_module()
    dim_s = None
    if mods is not None:
        try:
            dim_s = mods.IDimension(dim._oleobj_)
            print(f"mods.IDimension(oleobj) -> {dim_s!r:.80}")
        except Exception as exc:
            print(f"mods.IDimension wrap EXC: {exc!r:.140}")
    if dim_s is not None:
        try:
            print(f"static GetToleranceType() -> {dim_s.GetToleranceType()!r}")
        except Exception as exc:
            print(f"static GetToleranceType EXC: {exc!r:.120}")
        # 终验（第 5 轮）：固定 PlusMinus=5。佐证：type=7 时 values 归零 → 枚举序
        # 列与 swToleranceType_e 文档一致（0=None 1=Basic 2=MIN 3=MAX 4=Symmetric
        # 5=PlusMinus 6=Limit 7=Fit），7=Fit 不吃 min/max 完全吻合。
        r1 = dim_s.SetToleranceType(5)
        r2 = dim_s.SetToleranceValues(-0.00005, 0.0001)
        rt = dim_s.GetToleranceType()
        rv = dim_s.GetToleranceValues()
        print(f"FINAL type=5: Set={r1!r}/{r2!r} readback type={rt!r} "
              f"values={rv!r}")
        try:
            call_or_value(drawing, "EditRebuild3")
        except Exception:
            pass
    # dd 层文本旁证（带参方法直接调，不用 call_or_value）
    for idx in range(4):
        try:
            print(f"dd.GetText({idx}) -> {dd.GetText(idx)!r}")
        except Exception as exc:
            print(f"dd.GetText({idx}) EXC: {exc!r:.100}")
            break
    try:
        call_or_value(drawing, "EditRebuild3")
    except Exception:
        pass


def phase_c_finish_note(drawing) -> None:
    print("=" * 20, "C. 粗糙度符号 + 注释文本", "=" * 20)
    # InsertSurfaceFinishSymbol 14 参完整签名（makepy）：
    #   (SymType, LeaderType, LocX, LocY, LocZ, LaySymbol, ArrowType,
    #    MachAllowance, OtherVals, ProdMethod, SampleLen, MaxRoughness,
    #    MinRoughness, RoughnessSpacing)
    # docstring: Creates a Surface Finish Symbol based on last selection
    variants = (
        ("sym1-strRa", lambda: drawing.InsertSurfaceFinishSymbol(
            1, 0, 0.40, 0.05, 0.0, 0, 0, 0.0, 0.0, "", "", "1.6", "", "")),
        ("sym1-numRa", lambda: drawing.InsertSurfaceFinishSymbol(
            1, 0, 0.40, 0.05, 0.0, 0, 0, 0.0, 0.0, "", "", 1.6, "", "")),
        ("sym0-basic", lambda: drawing.InsertSurfaceFinishSymbol(
            0, 0, 0.40, 0.05, 0.0, 0, 0, 0.0, 0.0, "", "", "", "", "")),
        ("sym2-noremove", lambda: drawing.InsertSurfaceFinishSymbol(
            2, 0, 0.40, 0.05, 0.0, 0, 0, 0.0, 0.0, "", "", "", "", "")),
    )
    for cand, fn in variants:
        try:
            ret = fn()
            print(f"SurfaceFinish[{cand}] -> {ret!r:.100}")
            if ret:
                print("  >> surface finish created")
                break
        except Exception as exc:
            print(f"SurfaceFinish[{cand}] EXC: {exc!r:.140}")
    # 注释文本：CreateText2 第 1 轮已通 → 复验 + 位置读回
    text = "技术要求：未注公差按 GB/T 1804-m。"
    try:
        note = drawing.CreateText2(text, 0.05, 0.03, 0.0, 0.003, 0.003)
        print(f"CreateText2 -> {note!r:.80}")
        try:
            pos = note.GetPosition()
            print(f"note.GetPosition -> {pos!r}")
        except Exception as exc:
            print(f"note.GetPosition EXC: {exc!r:.120}")
    except Exception as exc:
        print(f"CreateText2 EXC: {exc!r:.140}")
    try:
        call_or_value(drawing, "EditRebuild3")
    except Exception:
        pass


def phase_d_dxf(drawing) -> None:
    print("=" * 20, "D. DXF 导出", "=" * 20)
    dxf_path = str(OUT_DIR / "probe_n5.dxf")
    if os.path.exists(dxf_path):
        os.remove(dxf_path)
    try:
        res = drawing.SaveAs3(dxf_path, 0, 1)  # swSaveAsOptions_Silent
        print(f"SaveAs3(dxf, 0, silent) -> {res!r}")
    except Exception as exc:
        print(f"SaveAs3 EXC: {exc!r:.160}")
        return
    if os.path.exists(dxf_path):
        size = os.path.getsize(dxf_path)
        with open(dxf_path, "rb") as fh:
            head = fh.read(64)
        print(f"dxf size={size}, head bytes: {head!r}")
        try:
            text_head = head.decode("utf-8", errors="replace")
        except Exception:
            text_head = ""
        ascii_like = text_head.lstrip().startswith(("0", "999", "SECTION"))
        binary = head.startswith(b"AutoCAD Binary")
        print(f"ascii_like={ascii_like} binary={binary}")
        # 内容旁证：粗糙度 Ra 值 / 技术要求文本是否进入 DXF（中文可能转义）
        with open(dxf_path, "rb") as fh:
            blob = fh.read()
        for probe in (b"1.6", b"Ra", "技术".encode("utf-8"),
                      "技术".encode("gbk"), b"\\U+", b"+0.1", b"-0.05"):
            print(f"  contains {probe!r}: {probe in blob}")
        if b"SECTION" in blob[:2000]:
            print("  header SECTION marker OK")
    else:
        print("dxf file NOT created")


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    app = sw.app
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app.CloseAllDocuments(True)

    info = phase_a_typelib(app)

    box_path = str(OUT_DIR / "probe_n5_plate.SLDPRT")
    made = part.create_box(sw, 60.0, 40.0, 8.0, box_path, True)
    if not made.get("success"):
        print(f"create_box failed: {made}")
        return 4
    file_io.close_document(sw, False)

    templates = app.GetUserPreferenceStringValue(10)
    drawing = app.NewDocument(templates, 0, 0.0, 0.0)
    if drawing is None:
        return 5
    abs_part = os.path.abspath(box_path)
    front = drawing.CreateDrawViewFromModelView3(abs_part, "", 0.15, 0.10, 0.0)
    ext = call_or_value(drawing, "Extension")
    front_name = call_or_value(front, "Name")
    ext.SelectByID2(front_name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0,
                    pythoncom.Nothing, 0)
    drawing.CreateUnfoldedViewAt3(0.15, 0.19, 0.0, False)
    ext.SelectByID2(front_name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0,
                    pythoncom.Nothing, 0)
    drawing.CreateUnfoldedViewAt3(0.27, 0.10, 0.0, False)
    from tools.probe_drawing.probe_drawing import _mark_all_dimensions_for_drawing
    try:
        marked = _mark_all_dimensions_for_drawing(app, abs_part)
    except Exception as exc:
        marked = -1
        print(f"mark exc: {exc!r:.120}")
    print(f"marked for drawing: {marked}")
    drawing.InsertModelAnnotations2(0, True, 0, True, True, False)
    call_or_value(drawing, "EditRebuild3")
    total = sum(call_or_value(v, "GetDisplayDimensionCount") or 0
                for _, v in _walk_views(drawing))
    print(f"total dims = {total}")

    dd, _full = _first_dimension(drawing)
    phase_b_tolerance(drawing, dd, info.get("swTolPlusMinus"))
    phase_c_finish_note(drawing)
    phase_d_dxf(drawing)

    app.CloseAllDocuments(True)
    if os.path.exists(abs_part):
        os.remove(abs_part)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
