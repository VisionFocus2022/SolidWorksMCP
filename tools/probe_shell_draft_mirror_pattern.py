"""实机探针：抽壳/镜像/拔模/线性阵列（T8 步骤 1，2026-08-29）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_shell_draft_mirror_pattern.py
四段各自 try/except 互不阻断；选中遵循 T5/T7 契约（面=walk+Select2；
特征/基准面=SelectByID2 或 FeatureByName+Select2，BODYFEATURE/PLANE 按名可选）。
typelib 权威签名（计划候选作废）：
  ModelDoc2.InsertFeatureShell(Thickness米, Outward)
  IFeatureManager.InsertMirrorFeature(BMirrorBody, BGeometryPattern, BMerge, BKnit)
  IBody2.DraftBody(NumOfFaces, FaceList, EdgeList, DraftAngle弧度)   # body 级
  ModelDoc2.FeatureLinearPattern(Num1, Spacing1米, Num2, Spacing2米,
                                 FlipDir1, FlipDir2, DName1, DName2)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.features import get_features
from solidworks_mcp.solidworks_api.geometry import latest_feature_name
from solidworks_mcp.solidworks_api.part import get_mass_properties
from solidworks_mcp.solidworks_api.topology import list_faces
from solidworks_mcp.utils.com import call_or_value

RESULTS: list = []


def _note(section: str, ok: bool, detail: str) -> None:
    RESULTS.append(ok)
    print(f"[{section}] {'OK' if ok else 'FAIL'}: {detail}")


def _select_faces(model, names) -> int:
    model.ClearSelection2(True)
    n = 0
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            if model.GetEntityName(face) in names:
                n += bool(face.Select2(True, 1))
            face = call_or_value(face, "GetNextFace")
    return n


def _fresh_box(sw, with_hole=False):
    assert design.create_new_part(sw)["success"]
    assert part.create_box(sw, 60, 40, 20)["success"]
    if with_hole:
        r = design.cut_round_hole(sw, 8.0, 15.0, 10.0, "top", None, True)
        assert r["success"], r
    return sw.get_active_document()


def _vol(sw) -> float:
    r = get_mass_properties(sw)
    return r["data"]["volume"] * 1e9 if r["success"] else -1.0


def sec_shell(sw):
    try:
        model = _fresh_box(sw)
        names = [f["name"] for f in list_faces(sw)["data"]["faces"]]
        # 顶面 = bbox z=20 的面：取面积 2400 的两面之一；直接用第 5 个名（2400 面）
        big = [f["name"] for f in list_faces(sw)["data"]["faces"] if f["area_mm2"] == 2400.0]
        v0 = _vol(sw)
        picked = _select_faces(model, [big[0]])
        before = latest_feature_name(model)
        model.InsertFeatureShell(0.002, False)
        after = latest_feature_name(model)
        v1 = _vol(sw)
        ok = after != before and v1 < v0 * 0.4
        _note("shell", ok,
              f"picked={picked} feat={after!r} v {v0:.0f}->{v1:.1f} (壳≈11712)")
    except Exception as exc:
        _note("shell", False, repr(exc)[:120])


def sec_mirror(sw):
    try:
        model = _fresh_box(sw, with_hole=True)
        feats = get_features(sw)["data"]["features"]
        cut = next(n for n in feats if n.startswith("切除") or "Cut" in n)
        v0 = _vol(sw)
        before = latest_feature_name(model)
        model.ClearSelection2(True)
        ok1 = model.Extension.SelectByID2(
            cut, "BODYFEATURE", 0, 0, 0, True, 1, pythoncom.Nothing, 0
        )
        plane = model.FeatureByName("前视基准面")
        ok2 = bool(plane.Select2(True, 2)) if plane is not None else False
        model.FeatureManager.InsertMirrorFeature(False, True, True, False)
        after = latest_feature_name(model)
        v1 = _vol(sw)
        ok = after != before and v1 < v0
        _note("mirror", ok,
              f"sel feat={ok1} plane={ok2} feat={after!r} v {v0:.1f}->{v1:.1f}")
    except Exception as exc:
        _note("mirror", False, repr(exc)[:120])


def sec_pattern(sw):
    try:
        model = _fresh_box(sw, with_hole=True)
        feats = get_features(sw)["data"]["features"]
        cut = next(n for n in feats if n.startswith("切除") or "Cut" in n)
        v0 = _vol(sw)
        before = latest_feature_name(model)
        model.ClearSelection2(True)
        sel = model.Extension.SelectByID2(
            cut, "BODYFEATURE", 0, 0, 0, False, 1, pythoncom.Nothing, 0
        )
        found = None
        for dname in ("", "X 轴", "X轴", "X Axis"):
            model.ClearSelection2(True)
            model.Extension.SelectByID2(
                cut, "BODYFEATURE", 0, 0, 0, False, 1, pythoncom.Nothing, 0
            )
            try:
                model.FeatureLinearPattern(3, 0.01, 1, 0.01, False, False, dname, "")
            except Exception as exc:
                _note("pattern", False, f"dname={dname!r} EXC {repr(exc)[:80]}")
                if not sw.connect(launch_if_needed=False)["success"]:
                    raise
                continue
            after = latest_feature_name(model)
            if after != before:
                found = dname
                break
        v1 = _vol(sw)
        after = latest_feature_name(model)
        ok = found is not None and v1 < v0
        _note("pattern", ok,
              f"sel={sel} dname={found!r} feat={after!r} v {v0:.1f}->{v1:.1f}")
    except Exception as exc:
        _note("pattern", False, repr(exc)[:120])


def sec_draft(sw):
    try:
        model = _fresh_box(sw)
        body = model.GetBodies2(0, False)[0]
        faces = []
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            faces.append(face)
            face = call_or_value(face, "GetNextFace")
        v0 = _vol(sw)
        ok_ret = None
        for probe in (
            lambda: body.DraftBody(1, (faces[0],), (), 0.05),
            lambda: body.DraftBody(1, faces[:1], [], 0.05),
        ):
            try:
                ok_ret = probe()
                break
            except Exception as exc:
                ok_ret = f"EXC {repr(exc)[:60]}"
                if not sw.connect(launch_if_needed=False)["success"]:
                    raise
        v1 = _vol(sw)
        call_or_value(model, "EditRebuild3")
        mass = get_mass_properties(sw)
        _note("draft", mass["success"] and isinstance(ok_ret, (bool, int)),
              f"ret={ok_ret!r} v {v0:.1f}->{v1:.1f} rebuild_ok={mass['success']}")
    except Exception as exc:
        _note("draft", False, repr(exc)[:120])


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    for sec in (sec_shell, sec_mirror, sec_pattern, sec_draft):
        sec(sw)
        try:
            file_io.close_document(sw, save_changes=False)
        except Exception:
            pass
    print(f"SUMMARY: {sum(RESULTS)}/4 sections OK")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
