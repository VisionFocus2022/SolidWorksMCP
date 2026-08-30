"""实机探针 N8 第七轮（终轮）：mate 加/定位/删除全链（IEntity 面选择）。

第六轮定论：
  - 装配上下文面选择唯一可靠路径 = mods.IEntity(face._oleobj_).Select2(append, 0)；
  - SetTransformAndSolve3 + EditRebuild3 → 干涉归零（修复闭环成立）；
  - body.GetMassProperties(1.0)[3] = 体积 m³（BOM 素材）；
  - SelectByID2 按名（FACE/PLANE/BODYFEATURE@装配）在 SW 2026 全面退化。

终轮验证：
  1. IEntity 两面 -> AddMate5 coincident -> mate 特征在 MateGroup 子树的名字/类型；
  2. 删除路径：SelectByID2(mate_name, "BODYFEATURE"/"FEATURE") vs
     IFeature.Select(False, Nothing) + EditDelete；树复检消失；
  3. 删除后再加一个 distance mate 重复验证（稳定性）。
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
from solidworks_mcp.utils.templates import get_assembly_template

OUT_DIR = Path(__file__).resolve().parents[2] / "output" / "e2e-work"


def _try(obj, member, args=(), tag=""):
    try:
        val = getattr(obj, member)
        if callable(val):
            val = val(*args)
        print(f"[{tag}] {member}{args if args else ''} -> {val!r:.240}")
        return val
    except Exception as exc:
        print(f"[{tag}] {member} EXC: {exc!r:.240}")
        return None


def _walk_tree(model):
    """Yield every feature incl. one level of sub-features as (name, type, feat)."""
    feat = call_or_value(model, "FirstFeature")
    while feat is not None:
        yield (str(call_or_value(feat, "Name")), str(call_or_value(feat, "GetTypeName2")), feat)
        sub = call_or_value(feat, "GetFirstSubFeature")
        while sub is not None:
            yield (str(call_or_value(sub, "Name")), str(call_or_value(sub, "GetTypeName2")), sub)
            sub = call_or_value(sub, "GetNextSubFeature")
        feat = call_or_value(feat, "GetNextFeature")


def _mate_add(asm, face_a, face_b, mate_type, dist=0.0):
    asm.ClearSelection2(True)
    if not (face_a.Select2(False, 0) and face_b.Select2(True, 0)):
        print("  !! entity select failed")
        return None
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    mate = asm.AddMate5(mate_type, 0, False, dist, dist, dist, 0, 0, 0, 0, 0, False, False, 0, err)
    name = str(call_or_value(mate, "Name")) if mate is not None else None
    print(f"  AddMate5(type={mate_type}) -> {name!r} err={err.value}")
    asm.ClearSelection2(True)
    return name


def _delete_mate(asm, mate_name):
    for etype in ("BODYFEATURE", "FEATURE", "MATE"):
        asm.ClearSelection2(True)
        picked = asm.Extension.SelectByID2(
            mate_name, etype, 0, 0, 0, False, 0, pythoncom.Nothing, 0
        )
        print(f"  SelectByID2({mate_name!r}, {etype}) -> {picked}")
        if picked:
            break
    if not picked:
        # 对象选择兜底：遍历树找 mate 特征 -> IFeature.Select
        for fname, ftype, feat in _walk_tree(asm):
            if fname == mate_name:
                picked = _try(feat, "Select", (False, pythoncom.Nothing), f"feat[{fname}]")
                break
    if not picked:
        print("  !! no selection path worked")
        return False
    call_or_value(asm, "EditDelete")
    gone = not any(n == mate_name for n, _, _ in _walk_tree(asm))
    print(f"  EditDelete -> gone from tree: {gone}")
    return gone


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    app = sw.app
    mods = gencache.GetModuleForProgID("SldWorks.Application")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app.CloseAllDocuments(True)
    template = get_assembly_template()
    if not template or not os.path.isfile(template):
        print("!! 无装配模板")
        return 3

    box_path = str(OUT_DIR / "probe_it_box.SLDPRT")
    part.create_box(sw, 60.0, 40.0, 20.0, box_path, True)
    file_io.close_document(sw, False)

    file_io._open_doc6(app, box_path, 1)
    asm = app.NewDocument(template, 0, 0, 0)
    if asm is None:
        print("!! NewDocument failed")
        return 4
    c1 = asm.AddComponent4(box_path, "", 0.0, 0.0, 0.0)
    c2 = asm.AddComponent4(box_path, "", 0.0, 0.05, 0.0)  # Y 分离，避免再撞干涉判定

    comp_cls, body_cls = mods.IComponent2, mods.IBody2
    faces = []
    for c in (c1, c2):
        tb = body_cls(comp_cls(c._oleobj_).GetBody()._oleobj_)
        face = tb.GetFirstFace()
        faces.append(mods.IEntity(face._oleobj_))
    print(f"faces wrapped: {len(faces)}")

    print("\n== mate #1: coincident ==")
    m1 = _mate_add(asm, faces[0], faces[1], 0)
    print("  tree now:", [(n, t) for n, t, _ in _walk_tree(asm) if "ate" in t or "ate" in n])
    if m1:
        print(" == delete #1 ==")
        _delete_mate(asm, m1)

    print("\n== mate #2: distance 0.01 (stability re-run) ==")
    m2 = _mate_add(asm, faces[0], faces[1], 5, 0.01)  # 5=swMateDISTANCE（主仓常量）
    if m2:
        print(" == delete #2 ==")
        _delete_mate(asm, m2)

    app.CloseAllDocuments(True)
    print("\ndone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
