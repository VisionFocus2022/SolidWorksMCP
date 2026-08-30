"""N9 步骤 2：针对性实机探针——四子项最小调用收敛（13 轮迭代终态）。

已解锁契约（SUMMARY 3/4，2026-08-30 SW 2026 v34.2.1 实机）：
  mirror OK: cut SelectByID2(BODYFEATURE, mark=1) + "右视基准面"
    SelectByID2(PLANE, append=True, mark=2) → dynamic
    fm.InsertMirrorFeature2(False, True, True, False, 0)——第 5 参
    ScopeOptions=0 是解锁关键（T8 只试 4 参版 9 组合零产出）；
    树新增“镜向1”，ΔV 精确 1005mm³（⌀8 孔镜像）。
  draft OK: 拔模面 face.Select2(False, 1) 先 + 中性面
    face.Select2(True, 2) 后（draft_first 顺序）→ typed
    fm.InsertMultiFaceDraft(math.radians(3.0), False, False, 0,
    False, False)（typed FM 铁律：长参数列表 dynamic 编组不可靠）；
    树新增“拔模1”，3° 外拔模 48000→50516mm³。
  thread OK: 顶面 ⌀20 圆 → model.InsertHelix(..., helixdef=0, pitch,
    revolution, ...) → helix SelectByID2(REFERENCECURVES, mark=4) →
    typed fm.InsertCutSwept5(False, Alignment=False, ..., CircularProfile=
    True, dia)——**Alignment=False 是 helix 3D 路径解锁关键**（True 时
    SW 静默拒收）；mark=4 是扫描路径标记（mark=1 无产出）。组合曲线
    包装（model.InsertCompositeCurve 属性语义返回 bool）不改变拒收。
  pattern BLOCKED（证据完备）：FeatureLinearPattern4（20 参）直调
    typed/dynamic × 边线/基准面/DName 参考方式 × mark 1/2/4/8 × Num2
    0/1 全组合静默零产出；FeatureData 路线 AccessSelections 一律
    RPC_E_SERVERFAULT（TopDoc dynamic/typed 均同）；纯属性
    PatternFeatureArray put 单对象 serverfault / tuple “内存已锁定”；
    枚举值 swFmLPattern=6 / swFmLocalLPattern=108（PowerShell 反射
    swconst.dll 拿值）。生产兑底=数学替代：循环调用 cut_round_hole
    （环形阵列先例）。

方法论沉淀：
  - 类型库枚举（makepy def + PowerShell 反射 swconst.dll 枚举值）先于盲试
  - call_or_value：同名 COM 成员方法/属性二义（FirstFeature 属性 get
    直接调 () 会 MEMBERNOTFOUND；InsertCompositeCurve 属性语义返 bool）
  - typed FM（gencache IFeatureManager 包装）解决长参数列表 dynamic 编组

判定：特征树差集 + 体积变化；每段 try/except 互不阻断。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import gencache

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.geometry import (
    latest_feature_name,
    mm_to_m,
    walk_feature_names,
)
from solidworks_mcp.utils.com import call_or_value

HOLE_VOL_MM3 = math.pi * 4.0 * 4.0 * 20.0  # ⌀8 通孔 × 高 20
RESULTS: list = []


def _typed_fm(model):
    """typed IFeatureManager（N8 教训：长参数列表 dynamic 编组不可靠，
    CreateTransform VARIANT 数组 dynamic 直接 RPC fault）。"""
    fm = call_or_value(model, "FeatureManager")
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    raw = getattr(fm, "_oleobj_", None)
    if mods is None or raw is None:
        return fm  # 回退 dynamic
    return mods.IFeatureManager(raw)


def _note(section: str, ok: bool, detail: str) -> None:
    RESULTS.append(ok)
    print(f"[{section}] {'OK' if ok else 'FAIL'}: {detail}")


def _vol(sw) -> float:
    r = part.get_mass_properties(sw)
    return r["data"]["volume"] * 1e9 if r.get("success") else -1.0


def _fresh_box_with_hole(sw, x_mm=10.0):
    assert design.create_new_part(sw)["success"]
    assert part.create_box(sw, 60, 40, 20)["success"]
    r = design.cut_round_hole(sw, 8.0, x_mm, 0.0, "top", None, True)
    assert r["success"], r
    return sw.get_active_document()


def _cut_feature_name(model):
    for n in walk_feature_names(model):
        if "切除" in n or "Cut" in n:
            return n
    return None


def _find_face(model, role: str):
    """role: bottom(z 厚≈0 且 zmin≈0) / top / yplus(y 厚≈0 且 ymax≈40mm)。"""
    best = None
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            box = call_or_value(face, "GetBox")  # T16 契约：零参属性 6 元组米
            dx, dy, dz = (box[3] - box[0]), (box[4] - box[1]), (box[5] - box[2])
            hit = (
                role == "bottom" and dz < 1e-6 and box[2] < 0.005
            ) or (
                role == "top" and dz < 1e-6 and box[5] > 0.0195
            ) or (
                role == "yplus" and dy < 1e-6 and box[4] > 0.0195
            )
            if hit:
                best = face
                break
            face = call_or_value(face, "GetNextFace")
        if best is not None:
            break
    return best


def _find_x_edge(model):
    """沿 X 方向的直线边（方向参考候选）。"""
    for body in model.GetBodies2(0, False) or ():
        for edge in call_or_value(body, "GetEdges") or ():
            try:
                s = call_or_value(call_or_value(edge, "GetStartVertex"), "GetPoint")
                t = call_or_value(call_or_value(edge, "GetEndVertex"), "GetPoint")
            except Exception:
                continue
            if not s or not t:
                continue
            if (abs(t[0] - s[0]) > 0.05
                    and abs(t[1] - s[1]) < 1e-6
                    and abs(t[2] - s[2]) < 1e-6):
                return edge
    return None


def _dump_face_boxes(model, tag: str) -> None:
    print(f"  [{tag}] face boxes:")
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            try:
                box = call_or_value(face, "GetBox")
                print(f"    {[round(v * 1000, 1) for v in box]}")
            except Exception as exc:
                print(f"    GetBox EXC {exc!r}")
                break
            face = call_or_value(face, "GetNextFace")


def sec_pattern(sw):
    try:
        model = _fresh_box_with_hole(sw, x_mm=10.0)
        cut = _cut_feature_name(model)
        v0 = _vol(sw)
        fm = _typed_fm(model)
        found = None
        # 五轮教训：FEATURE 选不中；默认轴三种名 AXIS 均选不中（sel_axis=False）。
        # 六轮教训：typed FM + edge/plane/DName 选中成功仍零产出。
        # 七轮：dynamic fm 对照 + Num2=0 变体 + CreateDefinition 探测
        x_edge = _find_x_edge(model)
        dyn_fm = call_or_value(model, "FeatureManager")
        strategies = [
            ("dyn_edge_n1", dyn_fm, "edge", 1),
            ("dyn_edge_n0", dyn_fm, "edge", 0),
            ("dyn_plane_n1", dyn_fm, "plane", 1),
            ("dyn_dname_n1", dyn_fm, "dname", 1),
            ("typed_edge_n0", fm, "edge", 0),
        ]
        for tag, fm_obj, kind, num2 in strategies:
            dname = "基准轴1" if kind == "dname" else ""
            extra = ("右视基准面", "PLANE") if kind == "plane" else x_edge
            before = latest_feature_name(model)
            model.ClearSelection2(True)
            sel = model.Extension.SelectByID2(
                cut, "BODYFEATURE", 0, 0, 0, False, 1,
                pythoncom.Nothing, 0,
            )
            sel_ref = True
            if isinstance(extra, tuple):
                sel_ref = model.Extension.SelectByID2(
                    extra[0], extra[1], 0, 0, 0, True, 2,
                    pythoncom.Nothing, 0,
                )
            elif extra is not None:
                sel_ref = extra.Select2(True, 2)
            try:
                feat = fm_obj.FeatureLinearPattern4(
                    3, mm_to_m(8.0), num2, mm_to_m(8.0), False, False,
                    dname, "", False, False,
                    False, False, False, False, False, False,
                    0.0, 0.0, 0.0, 0.0,
                )
            except Exception as exc:
                print(f"  {tag} EXC {repr(exc)[:90]}")
                continue
            after = latest_feature_name(model)
            if after != before and feat is not None:
                found = (tag, after)
                break
            print(f"  {tag} sel={sel}/{sel_ref} feat={feat!r} no_delta")
        if found is None:
            # 八轮：FeatureData 路线（swFmLPattern=6 / swFmLocalLPattern=108，
            # PowerShell 反射 SolidWorks.Interop.swconst.dll 拿枚举值）。
            # 九轮：makepy 类直接包装 fdef（八轮 dynamic 下 AccessSelections
            # 抛 RPC_E_SERVERFAULT）+ Component 传 None
            mods = gencache.GetModuleForProgID("SldWorks.Application")
            fd_cls = {6: mods.ILinearPatternFeatureData,
                      108: mods.ILocalLinearPatternFeatureData}
            for sid in (6, 108):
                try:
                    fdef_raw = fm.CreateDefinition(sid)
                except Exception as exc:
                    print(f"  CreateDefinition({sid}) EXC {repr(exc)[:90]}")
                    continue
                if fdef_raw is None:
                    print(f"  CreateDefinition({sid}) -> None")
                    continue
                try:
                    fdef = fd_cls[sid](fdef_raw._oleobj_)
                except Exception as exc:
                    print(f"  wrap fdef({sid}) EXC {repr(exc)[:90]}")
                    continue
                print(f"  CreateDefinition({sid}) -> {type(fdef).__name__}")
                for feat_mark, ref_mark in ((1, 2), (4, 8), (1, 4), (2, 4)):
                    model.ClearSelection2(True)
                    model.Extension.SelectByID2(
                        cut, "BODYFEATURE", 0, 0, 0, False, feat_mark,
                        pythoncom.Nothing, 0,
                    )
                    if x_edge is not None:
                        x_edge.Select2(True, ref_mark)
                    try:
                        acc = fdef.AccessSelections(model, None)
                    except Exception as exc:
                        print(f"  sid={sid} m={feat_mark}/{ref_mark} "
                              f"AccessSel EXC {repr(exc)[:90]}")
                        continue
                    try:
                        axis = fdef.D1Axis
                        axis_type = fdef.GetD1AxisType()
                    except Exception:
                        axis, axis_type = "?", "?"
                    if not acc or axis is None:
                        print(f"  sid={sid} m={feat_mark}/{ref_mark} "
                              f"acc={acc!r} D1Axis={axis!r} type={axis_type}")
                        continue
                    try:
                        fdef.D1TotalInstances = 3
                        fdef.D1Spacing = mm_to_m(8.0)
                        fdef.GeometryPattern = False
                        fdef.D2TotalInstances = 1
                    except Exception as exc:
                        print(f"  sid={sid} setprops EXC {repr(exc)[:90]}")
                        continue
                    before = latest_feature_name(model)
                    try:
                        feat = fm.CreateFeature(fdef)
                    except Exception as exc:
                        print(f"  sid={sid} CreateFeature EXC {repr(exc)[:90]}")
                        continue
                    after = latest_feature_name(model)
                    if after != before and feat is not None:
                        found = (f"fdef{sid}", feat_mark, ref_mark, after)
                        break
                    print(f"  sid={sid} m={feat_mark}/{ref_mark} "
                          f"feat={feat!r} no_delta")
                # 十三轮：TopDoc 传 typed IModelDoc2（dynamic CDispatch 下
                # AccessSelections 一律 serverfault）
                try:
                    typed_model = mods.IModelDoc2(model._oleobj_)
                except Exception:
                    typed_model = model
                model.ClearSelection2(True)
                model.Extension.SelectByID2(
                    cut, "BODYFEATURE", 0, 0, 0, False, 1,
                    pythoncom.Nothing, 0,
                )
                if x_edge is not None:
                    x_edge.Select2(True, 2)
                try:
                    acc = fdef.AccessSelections(typed_model, None)
                    print(f"  sid={sid} typedTopDoc acc={acc!r}")
                    if acc:
                        fdef.D1TotalInstances = 3
                        fdef.D1Spacing = mm_to_m(8.0)
                        fdef.GeometryPattern = False
                        fdef.D2TotalInstances = 1
                        before = latest_feature_name(model)
                        feat = fm.CreateFeature(fdef)
                        after = latest_feature_name(model)
                        if after != before and feat is not None:
                            found = (f"accessT{sid}", after)
                            break
                        print(f"  sid={sid} typedTopDoc feat={feat!r} "
                              f"no_delta")
                except Exception as exc:
                    print(f"  sid={sid} typedTopDoc EXC {repr(exc)[:90]}")
                if found:
                    break
        if found is None:
            # 十轮：纯属性路线（绕过 AccessSelections serverfault）；
            # 十一轮：整块 try + traceback 定位 MEMBERNOTFOUND 行
            import traceback
            try:
                cut_obj = None
                # 十二轮：FirstFeature 在此 dynamic 对象上是属性 get
                # （直接调 () 会 MEMBERNOTFOUND），走 call_or_value
                fobj = call_or_value(model, "FirstFeature")
                while fobj is not None:
                    nm = call_or_value(fobj, "Name") or ""
                    if "切除" in nm or "Cut" in nm:
                        cut_obj = fobj
                        break
                    fobj = call_or_value(fobj, "GetNextFeature")
                print(f"  prop-route cut_obj={cut_obj is not None}")
                if cut_obj is not None and x_edge is not None:
                    for sid in (6, 108):
                        try:
                            fdef = fd_cls[sid](fm.CreateDefinition(sid)._oleobj_)
                        except Exception as exc:
                            print(f"  prop-route sid={sid} EXC {repr(exc)[:90]}")
                            continue
                        arr_ok = False
                        for arr_val in (cut_obj, (cut_obj,)):
                            try:
                                fdef.PatternFeatureArray = arr_val
                                arr_ok = True
                                break
                            except Exception as exc:
                                print(f"  arr sid={sid} "
                                      f"{type(arr_val).__name__} EXC "
                                      f"{repr(exc)[:70]}")
                        if not arr_ok:
                            continue
                        try:
                            fdef.D1Axis = x_edge
                            fdef.D1TotalInstances = 3
                            fdef.D1Spacing = mm_to_m(8.0)
                            fdef.GeometryPattern = False
                            fdef.D2TotalInstances = 1
                        except Exception as exc:
                            print(f"  prop-set sid={sid} EXC {repr(exc)[:90]}")
                            continue
                        before = latest_feature_name(model)
                        try:
                            feat = fm.CreateFeature(fdef)
                        except Exception as exc:
                            print(f"  prop CreateFeature({sid}) EXC {repr(exc)[:90]}")
                            continue
                        after = latest_feature_name(model)
                        if after != before and feat is not None:
                            found = (f"prop{sid}", after)
                            break
                        print(f"  prop-route sid={sid} feat={feat!r} no_delta")
            except Exception:
                traceback.print_exc()
        v1 = _vol(sw)
        ok = found is not None and abs((v0 - v1) - 2 * HOLE_VOL_MM3) < 400
        _note("pattern", ok,
              f"found={found} v {v0:.0f}->{v1:.0f} "
              f"(期望 ΔV≈{2 * HOLE_VOL_MM3:.0f})")
    except Exception as exc:
        _note("pattern", False, repr(exc)[:160])


def sec_mirror(sw):
    try:
        model = _fresh_box_with_hole(sw, x_mm=10.0)
        cut = _cut_feature_name(model)
        v0 = _vol(sw)
        fm = call_or_value(model, "FeatureManager")
        found = None
        for plane_mark in (2, 4, 1):
            for scope in (0, 1, 2):
                before = latest_feature_name(model)
                model.ClearSelection2(True)
                model.Extension.SelectByID2(
                    cut, "BODYFEATURE", 0, 0, 0, False, 1,
                    pythoncom.Nothing, 0,
                )
                ok_plane = model.Extension.SelectByID2(
                    "右视基准面", "PLANE", 0, 0, 0, True, plane_mark,
                    pythoncom.Nothing, 0,
                )
                try:
                    feat = fm.InsertMirrorFeature2(False, True, True, False, scope)
                except Exception as exc:
                    print(f"  pm={plane_mark} scope={scope} EXC {repr(exc)[:100]}")
                    continue
                after = latest_feature_name(model)
                if after != before:
                    found = (plane_mark, scope, after)
                    break
            if found:
                break
        v1 = _vol(sw)
        ok = found is not None and abs((v0 - v1) - HOLE_VOL_MM3) < 300
        _note("mirror", ok,
              f"found={found} v {v0:.0f}->{v1:.0f} (期望 ΔV≈{HOLE_VOL_MM3:.0f})")
    except Exception as exc:
        _note("mirror", False, repr(exc)[:160])


def sec_draft(sw):
    try:
        assert design.create_new_part(sw)["success"]
        assert part.create_box(sw, 60, 40, 20)["success"]
        model = sw.get_active_document()
        bottom = _find_face(model, "bottom")
        yplus = _find_face(model, "yplus")
        v0 = _vol(sw)
        fm = _typed_fm(model)
        found = None
        combos = (
            (2, 1, "draft_first", 0), (2, 1, "neutral_first", 0),
            (1, 1, "neutral_first", 0), (2, 1, "draft_first", 1),
            (2, 1, "neutral_first", 1),
        )
        for neutral_mark, draft_mark, order, prop in combos:
            before = latest_feature_name(model)
            model.ClearSelection2(True)
            picks = (
                [(yplus, draft_mark), (bottom, neutral_mark)]
                if order == "draft_first"
                else [(bottom, neutral_mark), (yplus, draft_mark)]
            )
            sel_ok = all(
                f.Select2(i > 0, mark) if hasattr(f, "Select2") else False
                for i, (f, mark) in enumerate(picks)
            )
            if not sel_ok:
                print(f"  nm={neutral_mark} dm={draft_mark} o={order} p={prop} "
                      f"SEL_FAIL")
                continue
            try:
                feat = fm.InsertMultiFaceDraft(
                    math.radians(3.0), False, False, prop, False, False,
                )
            except Exception as exc:
                print(f"  nm={neutral_mark} dm={draft_mark} o={order} p={prop} "
                      f"EXC {repr(exc)[:100]}")
                continue
            after = latest_feature_name(model)
            if after != before and feat is not None:
                found = (neutral_mark, draft_mark, order, prop, after)
                break
        v1 = _vol(sw)
        ok = found is not None and v1 != v0 and v1 > 0
        _note("draft", ok, f"found={found} v {v0:.0f}->{v1:.0f}")
    except Exception as exc:
        _note("draft", False, repr(exc)[:160])


def sec_thread(sw):
    try:
        rod = str(Path(__file__).resolve().parents[2] / "output" / "e2e-work"
                  / "probe_n9_thread.SLDPRT")
        part.create_cylinder(sw, 20.0, 50.0, rod, True)
        model = sw.get_active_document()
        top = part._select_top_face(model)
        sm = model.SketchManager
        sm.InsertSketch(True)
        sm.CreateCircleByRadius(0, 0, 0, mm_to_m(10.0))
        sm.InsertSketch(True)
        helix_ret = model.InsertHelix(
            False, False, False, False, 0, 0.0,
            mm_to_m(2.5), 8.0, 0.0, 0.0,
        )
        helix_name = next(
            (n for n in walk_feature_names(model) if "螺旋线" in n), None,
        )
        v0 = _vol(sw)
        fm = _typed_fm(model)
        found = None
        # 五轮解锁：SKETCH mark=4 是扫描路径标记（mark=1 无产出）。
        # 六轮主测：helix REFERENCECURVES mark=4 + ⌀3 圆弧槽；直线兜底。
        top_face = part._select_top_face(model)
        sm2 = model.SketchManager
        sm2.InsertSketch(True)
        sm2.CreateLine(mm_to_m(5.0), 0.0, 0.0, mm_to_m(15.0), 0.0, 0.0)
        line_sketch = latest_feature_name(model)
        sm2.InsertSketch(True)
        # 八轮：helix 转组合曲线（InsertCompositeCurve 零参，基于选择）
        model.ClearSelection2(True)
        ok_h = model.Extension.SelectByID2(
            helix_name, "REFERENCECURVES", 0, 0, 0, False, 1,
            pythoncom.Nothing, 0,
        )
        comp_ret = None
        if ok_h:
            try:
                comp_ret = call_or_value(model, "InsertCompositeCurve")
            except Exception as exc:
                print(f"  InsertCompositeCurve EXC {repr(exc)[:90]}")
        comp_name = next(
            (n for n in walk_feature_names(model) if "组合曲线" in n), None,
        )
        print(f"  composite: sel={ok_h} ret={comp_ret!r} name={comp_name!r}")
        attempts = [
            # 九轮：组合曲线创建成功；swSelectType_e 无 COMPOSITE——组合曲线
            # 也用 REFERENCECURVES（26）选中
            (comp_name, "REFERENCECURVES", 3.0, 4),
            (comp_name, "REFERENCECURVES", 3.0, 1),
            (helix_name, "REFERENCECURVES", 3.0, 4),
            (line_sketch, "SKETCH", 4.0, 4),
        ]
        attempts = [a for a in attempts if a[0] is not None]
        for sel_name, sel_type, dia, mark in attempts:
            before = latest_feature_name(model)
            model.ClearSelection2(True)
            ok_sel = model.Extension.SelectByID2(
                sel_name, sel_type, 0, 0, 0, False, mark,
                pythoncom.Nothing, 0,
            )
            try:
                feat = fm.InsertCutSwept5(
                    False, True, 0, False, False, 0, 0,
                    False, 0.0, 0.0, 0,
                    0, True, True, 0.0, True, False, False, False,
                    True, mm_to_m(dia), 0,
                )
            except Exception as exc:
                print(f"  {sel_type}/m{mark} EXC {repr(exc)[:90]}")
                continue
            after = latest_feature_name(model)
            v_now = _vol(sw)
            print(f"  {sel_name!r}/{sel_type}/m{mark} sel={ok_sel} "
                  f"feat={feat!r} delta={after != before} "
                  f"v {v0:.0f}->{v_now:.0f}")
            if after != before and feat is not None:
                found = (sel_name, sel_type, dia, mark, after)
                break
        if found is None or found[1] != "REFERENCECURVES":
            # 十一轮：helix 3D 路径参数变体（Alignment/PathAlign 语义）
            for path_name in (comp_name, helix_name):
                if path_name is None:
                    continue
                for align, path_align in ((False, 0), (False, 1), (True, 1)):
                    before = latest_feature_name(model)
                    model.ClearSelection2(True)
                    ok_sel = model.Extension.SelectByID2(
                        path_name, "REFERENCECURVES", 0, 0, 0, False, 4,
                        pythoncom.Nothing, 0,
                    )
                    try:
                        feat = fm.InsertCutSwept5(
                            False, align, 0, False, False, 0, 0,
                            False, 0.0, 0.0, 0,
                            path_align, True, True, 0.0, True, False, False, False,
                            True, mm_to_m(3.0), 0,
                        )
                    except Exception as exc:
                        print(f"  VAR a={align}/pa={path_align} EXC "
                              f"{repr(exc)[:80]}")
                        continue
                    after = latest_feature_name(model)
                    if after != before and feat is not None:
                        found = (path_name, "REFERENCECURVES", 3.0, 4, after)
                        break
                    print(f"  VAR {path_name!r} a={align}/pa={path_align} "
                          f"sel={ok_sel} no_delta")
                if found is not None and found[1] == "REFERENCECURVES":
                    break
        v1 = _vol(sw)
        # 直线兑底成功仅证明 API 活着；helix 路径成功才是本于项解锁
        # （十一轮：Alignment=False 是 helix 3D 路径的解锁关键；
        # ΔV 由 CircularProfile 直径/对齐语义在实现阶段调优）
        helix_ok = found is not None and found[1] != "SKETCH"
        ok = helix_ok and (v0 - v1) > 20
        _note("thread", ok,
              f"helix={helix_name!r} ret={helix_ret!r} found={found} "
              f"v {v0:.0f}->{v1:.0f}")
    except Exception as exc:
        _note("thread", False, repr(exc)[:160])


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=True)["success"]:
        print("SolidWorks 不可用，退出码 2")
        return 2
    for sec in (sec_pattern, sec_mirror, sec_draft, sec_thread):
        sec(sw)
        try:
            file_io.close_document(sw, save_changes=False)
        except Exception:
            pass
    print(f"SUMMARY: {sum(RESULTS)}/4 sections OK")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
