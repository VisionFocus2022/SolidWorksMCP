"""N29 步骤 2：实机收敛——基准轴/筋/圆顶三场景（2026-09-01 SW 2026 v34.2.1）。

步骤 1 类型库取证（含 N28 白送的基准面）：
  - 基准轴：IModelDoc2.InsertAxis()（零参，返回 bool）/ InsertAxis2(AutoSize)
    ——选中驱动（圆柱面/边/两点）；swFmRefAxis=60。
  - 筋：IFeatureManager.InsertRib = 10 参 (Is2Sided, ReverseThicknessDir,
    Thickness, ReferenceEdgeIndex, ReverseMaterialDir, IsDrafted,
    DraftOutward, DraftAngle, IsNormToSketch, IsDraftedFromWall)；
    IModelDoc2 版 8 参/InsertRib2 9 参（旧代次）——生产取 FM 10 参版。
  - 圆顶：IModelDoc2.InsertDome(Height, ReverseDir, DoEllipticSurface)
    3 参全标量（dispid 65853）——选中面后直调。
  - 基准面：IFeatureManager.InsertRefPlane(8, dist)（N28 已实机验证，跳过）。

判定=特征树差集+体积（quirks 17：返回值不可靠族一律树差集）。
结论（运行后回填本头 + INDEX.md）。

结论（2026-09-01 实机，3/4 可达，2/3 一次命中）：
1. **基准轴 OK**：柱面识别=face 走查 + `call_or_value(face,'GetSurface')`
   →`IsCylinder` → `Select2(False, 0)` → **`IModelDoc2.InsertAxis()` 零参**
   （dynamic 上以属性语义取值即触发——call_or_value 拿到 bool 且树已新增；
   `InsertAxis2` 带/不带参均报「非选择性的参数」不可用）。树名「基准轴1」。
2. **圆顶 OK（mark=1 解锁）**：顶面=face 走查 zmin 最大 → `Select2(False,
   mark=1)`（**mark=0 静默零产出**）→ typed `IModelDoc2.InsertDome(height_m,
   False, False)` → ΔV=850.85mm³=球冠公式精确 0.000%。树名「圆顶1」。
3. **筋 BLOCKED（证据完备，T8-mirror/pattern 同族）**：13 变体直调全零产出
   ——面构型（上视/前视×悬空/贴壁/超壁线）× mark 0/1 × ReferenceEdgeIndex
   0/-1 × 宿主（typed FM 10 参/dynamic FM/typed doc2 InsertRib2 9 参）×
   IsNormToSketch F/T × 方向布尔 4 组合。swFeatureNameID_e 反射无 Rib 项
   → CreateDefinition 路线不可用。**生产走数学替代**（筋=薄板 box 组合，
   如实声明非参数联动特征，先例 pattern/环阵）；终极路径=宏录制器对照
   （与 T8 两 BLOCKED 同队列，需用户手工录制）。
4. 参考几何三件套集齐：基准面（N28 InsertRefPlane(8,dist)）+ 基准轴（本探
   针）——N29 生产工具的参考几何部分全部原生可达。
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
)
from solidworks_mcp.utils.com import call_or_value

DOME_VOL_MM3 = math.pi * 5.0 * (3 * 100.0 + 25.0) / 6.0  # ⌀20 顶 +5 球冠 ≈ 850.85
RESULTS: list = []


def _typed_doc2(model):
    """typed IModelDoc2（N28 教训：ModelDoc2 上 dynamic 调用编组不可靠族）。"""
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    raw = getattr(model, "_oleobj_", None)
    if mods is None or raw is None:
        return model
    return mods.IModelDoc2(raw)


def _typed_fm(model):
    """typed IFeatureManager（N8/N9 铁律：长参数列表 dynamic 编组不可靠）。"""
    fm = call_or_value(model, "FeatureManager")
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    raw = getattr(fm, "_oleobj_", None)
    if mods is None or raw is None:
        return fm
    return mods.IFeatureManager(raw)


def _vol(sw) -> float:
    r = part.get_mass_properties(sw)
    return r["data"]["volume"] * 1e9 if r.get("success") else -1.0


def _select(model, name: str, sel_type: str, mark: int, append: bool) -> bool:
    return bool(
        model.Extension.SelectByID2(
            name, sel_type, 0, 0, 0, append, mark, pythoncom.Nothing, 0
        )
    )


def _select_top_face(model, mark: int = 0):
    """N9/T16 契约：face walk，zmin 最大者 Select2(False, mark)。"""
    best = None
    best_z = -1.0
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            box = call_or_value(face, "GetBox")
            if box is not None and box[2] > best_z:
                best_z = box[2]
                best = face
            face = call_or_value(face, "GetNextFace")
    if best is None or not best.Select2(False, mark):
        return None
    return best


def _select_cylindrical_face(model):
    """第一个柱面（face.GetSurface().IsCylinder）→ Select2(False, 0)。"""
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            surface = call_or_value(face, "GetSurface")
            is_cyl = call_or_value(surface, "IsCylinder") if surface else False
            if is_cyl and face.Select2(False, 0):
                return face
            face = call_or_value(face, "GetNextFace")
    return None


def sec_ref_axis(sw) -> bool:
    """⌀20 圆柱柱面 → InsertAxis2(True) → 树新增「基准轴N」。"""
    assert design.create_new_part(sw)["success"]
    assert part.create_cylinder(sw, 20.0, 30.0)["success"]
    model = sw.get_active_document()
    face = _select_cylindrical_face(model)
    print(f"[axis] cylindrical face selected: {face is not None}")
    if face is None:
        RESULTS.append(False)
        file_io.close_document(sw, save_changes=False)
        return False
    before = latest_feature_name(model)
    ok_call = None
    axis_call = None
    for tag, fn in (
        ("InsertAxis2(True)", lambda: call_or_value(model, "InsertAxis2")(True)),
        ("InsertAxis2()", lambda: call_or_value(model, "InsertAxis2")()),
        ("InsertAxis()", lambda: call_or_value(model, "InsertAxis")()),
    ):
        try:
            ok_call = fn()
            axis_call = tag
            break
        except Exception as exc:  # noqa: BLE001 —— 探针轮换
            print(f"[axis] {tag} EXC {exc!r}")
    after = latest_feature_name(model)
    hit = after != before and "基准轴" in after
    print(
        f"[axis] call={axis_call}({ok_call!r}) tree {before!r}->{after!r} => "
        f"{'OK' if hit else 'MISS'}"
    )
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def _fresh_box(sw):
    assert design.create_new_part(sw)["success"]
    assert part.create_box(sw, 60, 40, 20)["success"]
    return sw.get_active_document()


RIB_LINE = (0.0, 0.0, 0.0, 0.0, 0.02, 0.0)  # 前视基准面竖线（底到顶全高）
RIB_VARIANTS = [
    # (tag, mark, ref_idx, caller, is2s, rev_thick, rev_mat)
    ("rev_mat", 1, 0, "fm", True, False, True),
    ("rev_thick", 1, 0, "fm", True, True, False),
    ("rev_both", 1, 0, "fm", True, True, True),
    ("1sided_rev_mat", 1, 0, "fm", False, False, True),
]


def sec_rib(sw) -> bool:
    """盒 60×40×20 + 前视基准面全高竖线 → InsertRib。方向布尔轮换。"""
    hit = False
    for tag, mark, ref_idx, caller, is2s, rev_thick, rev_mat in RIB_VARIANTS:
        model = _fresh_box(sw)
        model.ClearSelection2(True)
        if not _select(model, "前视基准面", "PLANE", 0, False):
            print(f"[rib:{tag}] FAIL: 前视基准面选不中")
            continue
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateLine(*RIB_LINE)
        model.SketchManager.InsertSketch(True)
        sketch = latest_feature_name(model)

        vol0 = _vol(sw)
        model.ClearSelection2(True)
        if not _select(model, sketch, "SKETCH", mark, False):
            print(f"[rib:{tag}] FAIL: sketch {sketch!r} 选不中")
            continue
        before = latest_feature_name(model)
        common = (is2s, rev_thick, mm_to_m(6.0), ref_idx, rev_mat, False, False, 0.0)
        try:
            if caller == "fm":
                _typed_fm(model).InsertRib(*common, False, False)
            elif caller == "fm_dyn":
                model.FeatureManager.InsertRib(*common, False, False)
            else:
                _typed_doc2(model).InsertRib2(*common, False)
        except Exception as exc:  # noqa: BLE001 —— 探针：每变体独立捕获
            print(f"[rib:{tag}] EXC {exc!r}")
            continue
        after = latest_feature_name(model)
        gained = _vol(sw) - vol0
        ok = after != before and gained > 0.0
        print(
            f"[rib:{tag}] tree {before!r}->{after!r} "
            f"ΔV={gained:.1f}mm³ => {'OK' if ok else 'MISS'}"
        )
        if ok:
            hit = True
            break
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def sec_dome(sw) -> bool:
    """⌀20×30 圆柱顶面 → InsertDome(5mm) → 球冠体积。面 mark 0/1 轮换。"""
    hit = False
    for mark in (0, 1):
        assert design.create_new_part(sw)["success"]
        assert part.create_cylinder(sw, 20.0, 30.0)["success"]
        model = sw.get_active_document()
        if _select_top_face(model, mark=mark) is None:
            print(f"[dome:m{mark}] FAIL: 顶面选不中")
            continue
        vol0 = _vol(sw)
        before = latest_feature_name(model)
        try:
            _typed_doc2(model).InsertDome(mm_to_m(5.0), False, False)
        except Exception as exc:  # noqa: BLE001
            print(f"[dome:m{mark}] EXC {exc!r}")
            continue
        after = latest_feature_name(model)
        gained = _vol(sw) - vol0
        delta = abs(gained - DOME_VOL_MM3) / DOME_VOL_MM3
        ok = after != before and delta < 0.02
        print(
            f"[dome:m{mark}] tree {before!r}->{after!r} ΔV={gained:.2f}mm³ "
            f"(expect {DOME_VOL_MM3:.2f}, {delta:.3%}) => {'OK' if ok else 'MISS'}"
        )
        if ok:
            hit = True
            break
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def main() -> int:
    sw = get_solidworks_app()
    conn = sw.connect(launch_if_needed=True)
    if not conn.get("success"):
        print("!! SW 未连接")
        return 2
    axis_ok = sec_ref_axis(sw)
    rib_ok = sec_rib(sw)
    dome_ok = sec_dome(sw)
    print(
        f"\nSUMMARY: axis={'OK' if axis_ok else 'FAIL'} "
        f"rib={'OK' if rib_ok else 'FAIL'} dome={'OK' if dome_ok else 'FAIL'} "
        f"({sum(RESULTS)}/{len(RESULTS)})"
    )
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
