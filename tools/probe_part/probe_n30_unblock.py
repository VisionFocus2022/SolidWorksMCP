"""N30 步骤 2：实机收敛——多边形/槽/多实体 combine/样条（2026-09-01 SW 2026 v34.2.1）。

步骤 1 取证：
  - ISketchManager.CreatePolygon(XC,YC,Zc, Xp,Yp,Zp, Sides, Inscribed) 8 参全标量
  - ISketchManager.CreateSketchSlot(SlotCreationType, SlotLengthType, Width,
    X1..Z3) 全标量；swSketchSlotCreationType_line=0 /
    swSketchSlotLengthType_CenterCenter=0（PS 反射 swconst.dll）
  - IBody2.Operations2(OperationType, ToolBody, ErrorCode可选) —— SWBODYADD
    =15903 / SWBODYCUT=15902（swBodyOperationType_e；注意不是 0/1/2）；
    首选 body 级（InsertCombineFeature 的 ToolVar 是 variant 数组输入，
    quirks 17 高危族）
  - CreateSpline(PointData (12,1) variant 数组) —— 同高危族，顺带验证
  - 双实体制造：FeatureExtrusion2 第 18 参 Merge=False（现 extrude_boss 恒 True）

判定=特征树差集+体积/实体计数。结论（运行后回填本头 + INDEX.md）。

结论（2026-09-01 实机，2/4 原生 + 1 数学替代已有 + 1 延后）：
1. **多边形 OK（0.000%）**：`ISketchManager.CreatePolygon(XC,YC,Zc, Xp,Yp,Zp,
   Sides, Inscribed)` 8 参全标量——内接六边形 R10×高 10 → 2598.08 精确
   （面积=N/2·R²·sin(2π/N)）+ FeatureExtrusion2 挤出。
2. **槽 OK（0.000%）**：`CreateSketchSlot` **14 参**（截尾有 CenterArcDirection/
   AddDimension）：line 型=0、center-center=0、第三点定宽方向；中心线 L×
   宽 W 的面积=L·W+π(W/2)²（**中心线长含半圆**——首版理论公式把 L 当端到端
   全长算错 32%），L20W6×高 8=1186.19 精确。
3. **多实体 combine BLOCKED（证据完备，9+ 变体）**：①双实体制造可行
   （FeatureExtrusion2 第 18 参 Merge=False，bodies=2 体积 72000 验证）；
   ②body 级 `IBody2.Operations/Operations2` 编组须传裸 `_oleobj_`（typed/
   dynamic wrapper 均类型不匹配 param 1），通编组后返回 ErrorCode=1
   `swBodyOperationNonApiBody`（含 body.Copy() 副本同）——**文档体不在
   body 级操作语义域**；③特征级 `fm.InsertCombineFeature(SWBODYADD, main,
   (tool,))` typed 无异常**静默零产出**（T8-mirror/pattern/rib 同族）。
   **数学替代已存在且已验证**：Merge=True 挤出即自动融合（N29 rib 板单实
   体精确验证）——AI 建模路径无需先造分离体。
4. **样条延后（双坑）**：CreateSpline(PointData (12,1) variant 数组高危族
   （quirks 17）+ dynamic dispatch 上解析为属性返回 None（'NoneType' object
   is not callable）——留待 typed 直调/ICreateSpline 路线再收敛。
5. SWBODYADD=15903/SWCUT=15902（swBodyOperationType_e，**非 0/1/2**，PS 反射）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.geometry import latest_feature_name, mm_to_m
from solidworks_mcp.utils.com import call_or_value

SWBODYADD = 15903  # swBodyOperationType_e（PS 反射，非 0/1/2）
POLY_VOL_MM3 = 3 * math.sqrt(3) / 2 * 100.0 * 10.0   # 六边形 R10 × 高10 ≈ 2598.08
SLOT_VOL_MM3 = (20.0 * 6.0 + math.pi * 9.0) * 8.0  # 中心线20×宽6+两端半圆r3，×高8 = 1186.19
COMBINE_VOL_MM3 = 60.0 * 40.0 * 20.0 + 60.0 * 20.0 * 20.0  # 48000+24000
RESULTS: list = []


def _select(model, name: str, sel_type: str, mark: int = 0, append: bool = False):
    return bool(
        model.Extension.SelectByID2(
            name, sel_type, 0, 0, 0, append, mark, pythoncom.Nothing, 0
        )
    )


def _vol(sw) -> float:
    r = part.get_mass_properties(sw)
    return r["data"]["volume"] * 1e9 if r.get("success") else -1.0


def _body_count(model) -> int:
    bodies = model.GetBodies2(0, False)
    return len(bodies) if bodies else 0


def sec_polygon(sw) -> bool:
    assert design.create_new_part(sw)["success"]
    model = sw.get_active_document()
    model.ClearSelection2(True)
    assert _select(model, "前视基准面", "PLANE")
    model.SketchManager.InsertSketch(True)
    # 内接六边形：中心原点，边参考点 (R,0)，Sides=6，Inscribed=True
    model.SketchManager.CreatePolygon(
        0.0, 0.0, 0.0, mm_to_m(10.0), 0.0, 0.0, 6, True
    )
    model.SketchManager.InsertSketch(True)
    before = latest_feature_name(model)
    feature = model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, 0.010, 0.010,
        False, False, False, False, 0, 0,
        False, False, False, False, True, True, True, 0, 0, False,
    )
    after = latest_feature_name(model)
    vol = _vol(sw)
    delta = abs(vol - POLY_VOL_MM3) / POLY_VOL_MM3
    hit = after != before and delta < 0.01
    print(
        f"[polygon] tree {before!r}->{after!r} feat={feature!r} vol={vol:.2f} "
        f"(expect {POLY_VOL_MM3:.2f}, {delta:.3%}) => {'OK' if hit else 'MISS'}"
    )
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def sec_slot(sw) -> bool:
    assert design.create_new_part(sw)["success"]
    model = sw.get_active_document()
    model.ClearSelection2(True)
    assert _select(model, "前视基准面", "PLANE")
    model.SketchManager.InsertSketch(True)
    # 直线槽：line 型(0)、中心-中心(0)、宽 6、中心线 (0,-10)→(0,10)、
    # 第三点 (5,0) 定宽方向
    model.SketchManager.CreateSketchSlot(
        0, 0, mm_to_m(6.0),
        0.0, mm_to_m(-10.0), 0.0,
        0.0, mm_to_m(10.0), 0.0,
        mm_to_m(5.0), 0.0, 0.0,
        1, False,  # CenterArcDirection(line 型不用), AddDimension
    )
    model.SketchManager.InsertSketch(True)
    before = latest_feature_name(model)
    feature = model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, 0.008, 0.008,
        False, False, False, False, 0, 0,
        False, False, False, False, True, True, True, 0, 0, False,
    )
    after = latest_feature_name(model)
    vol = _vol(sw)
    delta = abs(vol - SLOT_VOL_MM3) / SLOT_VOL_MM3
    hit = after != before and delta < 0.02
    print(
        f"[slot] tree {before!r}->{after!r} feat={feature!r} vol={vol:.2f} "
        f"(expect {SLOT_VOL_MM3:.2f}, {delta:.3%}) => {'OK' if hit else 'MISS'}"
    )
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def sec_combine(sw) -> bool:
    assert design.create_new_part(sw)["success"]
    assert part.create_box(sw, 60.0, 40.0, 20.0)["success"]
    model = sw.get_active_document()
    # 第二个 box：前视面偏移矩形（x 10..70、y -10..10），Merge=False 不并体
    model.ClearSelection2(True)
    assert _select(model, "前视基准面", "PLANE")
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCornerRectangle(
        mm_to_m(10.0), mm_to_m(-10.0), 0.0,
        mm_to_m(70.0), mm_to_m(10.0), 0.0,
    )
    model.SketchManager.InsertSketch(True)
    before = latest_feature_name(model)
    model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, 0.020, 0.020,
        False, False, False, False, 0, 0,
        False, False, False, False, False, True, True, 0, 0, False,  # Merge=False
    )
    after = latest_feature_name(model)
    count0 = _body_count(model)
    vol0 = _vol(sw)
    print(f"[combine] second body tree {before!r}->{after!r} bodies={count0} vol={vol0:.0f}")

    bodies = model.GetBodies2(0, False) or ()
    if count0 != 2 or len(bodies) != 2:
        print(f"[combine] FAIL: 期望双实体，实际 {count0}")
        RESULTS.append(False)
        file_io.close_document(sw, save_changes=False)
        return False

    combined = None
    tag_used = None
    from win32com.client import VARIANT  # noqa: PLC0415 —— 探针局部
    import pythoncom as _pc  # noqa: PLC0415
    fm = call_or_value(model, "FeatureManager")
    variants = [
        # body 级 Operations 是临时体语义（文档体报 NonApiBody）——转特征级
        ("combine_tuple", lambda: fm.InsertCombineFeature(
            SWBODYADD, bodies[0]._oleobj_, (bodies[1]._oleobj_,)
        )),
        ("combine_single", lambda: fm.InsertCombineFeature(
            SWBODYADD, bodies[0]._oleobj_, bodies[1]._oleobj_
        )),
        ("combine_dyn", lambda: model.FeatureManager.InsertCombineFeature(
            SWBODYADD, bodies[0]._oleobj_, (bodies[1]._oleobj_,)
        )),
    ]
    for tag, fn in variants:
        try:
            combined = fn()
            tag_used = tag
            break
        except Exception as exc:  # noqa: BLE001 —— 探针轮换
            print(f"[combine] {tag} EXC {exc!r}")
    count1 = _body_count(model)
    vol1 = _vol(sw)
    delta = abs(vol1 - COMBINE_VOL_MM3) / COMBINE_VOL_MM3
    hit = count1 == 1 and delta < 0.01
    print(
        f"[combine] {tag_used} ret={combined!r} bodies={count1} vol={vol1:.0f} "
        f"(expect {COMBINE_VOL_MM3:.0f}, {delta:.3%}) => {'OK' if hit else 'MISS'}"
    )
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def sec_spline(sw) -> bool:
    assert design.create_new_part(sw)["success"]
    model = sw.get_active_document()
    model.ClearSelection2(True)
    assert _select(model, "前视基准面", "PLANE")
    model.SketchManager.InsertSketch(True)
    try:
        curve = model.SketchManager.CreateSpline(
            ((0.0, 0.0, 0.0), (0.010, 0.010, 0.0), (0.020, 0.0, 0.0))
        )
        hit = curve is not None
        print(f"[spline] CreateSpline ret={curve!r} => {'OK' if hit else 'MISS'}")
    except Exception as exc:  # noqa: BLE001 —— variant 数组高危族，如实记录
        print(f"[spline] EXC {exc!r}")
        hit = False
    model.SketchManager.InsertSketch(True)
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def main() -> int:
    sw = get_solidworks_app()
    conn = sw.connect(launch_if_needed=True)
    if not conn.get("success"):
        print("!! SW 未连接")
        return 2
    poly_ok = sec_polygon(sw)
    slot_ok = sec_slot(sw)
    comb_ok = sec_combine(sw)
    spl_ok = sec_spline(sw)
    print(
        f"\nSUMMARY: polygon={'OK' if poly_ok else 'FAIL'} slot={'OK' if slot_ok else 'FAIL'} "
        f"combine={'OK' if comb_ok else 'FAIL'} spline={'OK' if spl_ok else 'FAIL'} "
        f"({sum(RESULTS)}/{len(RESULTS)})"
    )
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
