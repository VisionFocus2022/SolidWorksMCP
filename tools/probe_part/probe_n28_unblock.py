"""N28 步骤 2：实机收敛——sweep 免轮廓扫描 + loft 老式 Blend（2026-09-01 SW 2026 v34.2.1）。

步骤 1 取证修正（关键）：SW 把凸台放样叫 **Blend**——IModelDoc2.
InsertProtrusionBlend(2/3/4) 与 IFeatureManager.InsertProtrusionBlend(2) 均存在
（步骤 1 关键词只搜 Loft/Swept 漏 "Blend"，误报「无直接 API」；swFmBlend=9、
swFmSweep=17 佐证——PowerShell 反射 SolidWorks.Interop.swconst.dll 取
swFeatureNameID_e，makepy/swconst.tlb 均不生成枚举值）。

本探针两场景（每场景独立零件、结束即 close——实机坑：文档挂着 SaveAs3 报 1）：
  1. sweep：前视基准面 90° 圆弧路径 R20 → SelectByID2(SKETCH, mark) →
     typed fm.InsertProtrusionSwept4(20 参, CircularProfile=True, ⌀10)
     期望体积 250π² ≈ 2467.40 mm³（圆截面 × 弧长 10π）
  2. loft：前视 R10 圆 + 偏移 30mm 基准面 R15 圆 → 两剖面选中 →
     typed doc2.InsertProtrusionBlend2(False, False, False)
     期望体积圆台 π·30/3·(10²+10·15+15²) ≈ 14922.57 mm³
  判定 = 特征树差集 + 体积窗口（±1%）；strategies 轮换（N9 模式）先
  高概率组合，命中即停。

结论（运行后回填本头 + INDEX.md）。

结论（2026-09-01 实机 2/2 一次收敛，两场景均策略组首候选命中）：
1. **sweep 生产契约锁定**：路径草图（弧/线均可）`SelectByID2(名, "SKETCH",
   mark=4)` → typed `fm.InsertProtrusionSwept4(Propagate=False, Alignment=False,
   TwistCtrlOption=0(FollowPath), KeepTangency=False, BAdvancedSmoothing=False,
   Start/EndMatchingType=0, IsThinBody=False, T1/T2=0, ThinType=0, PathAlign=0,
   Merge=True, UseFeatScope=True, UseAutoSelect=True, TwistAngle=0,
   BMergeSmoothFaces=True, CircularProfile=True, Dia(m), Direction=True)`。
   mark4+Alignment=False 与 N9 helix/CutSwept5 先例完全同款；R20 90°弧×⌀10
   实测体积 2467.40 = 理论 250π² 精确命中，树名「扫描1」。
2. **loft 生产契约锁定（老式 Blend 直调，无需 CreateDefinition）**：
   `fm.InsertRefPlane(8, dist_m, 0,0,0,0)`（Distance=8 约束，选中参考面后；
   InsertRefPlane 属 IFeatureManager 6 参——IModelDoc2 上无此成员，实证）建
   剖面基准面 → 各剖面 `SelectByID2(名, "SKETCH", mark=1)`（append 累加）→
   typed `doc2.InsertProtrusionBlend2(False, False, False)`。r10→r15 距 30
   实测体积 14922.04（理论圆台 14922.57，差 0.35%——放样插值非严格线性，
   TDD 窗口按 ±1%），树名「放样1」。
3. 附带取证（N29 参考几何首数据点）：IFeatureManager.InsertRefPlane 可用。
4. 草图 API 注意：弧=ISketchManager.CreateArc（10 参标量版；CreateArc2 是
   ModelDoc 老接口的，SketchManager 上无）；圆=CreateCircleByRadius（4 参）。
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

SWEEP_VOL_MM3 = math.pi * 25.0 * (math.pi * 20.0 / 2.0)  # 250π² ≈ 2467.40
LOFT_VOL_MM3 = math.pi * 30.0 / 3.0 * (100.0 + 150.0 + 225.0)  # ≈ 14922.57
FRONT = "前视基准面"
RESULTS: list = []


def _typed(obj, iface: str):
    """Wrap dynamic dispatch in its makepy static class (N5 pattern)."""
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    raw = getattr(obj, "_oleobj_", None)
    if mods is None or raw is None:
        return obj
    return getattr(mods, iface)(raw)


def _vol_mm3(sw) -> float:
    r = part.get_mass_properties(sw)
    return r["data"]["volume"] * 1e9 if r.get("success") else -1.0


def _sketch_names(model) -> list:
    return [n for n in walk_feature_names(model) if "草图" in n or "Sketch" in n]


def _select(model, name: str, sel_type: str, mark: int, append: bool) -> bool:
    return bool(
        model.Extension.SelectByID2(
            name, sel_type, 0, 0, 0, append, mark, pythoncom.Nothing, 0
        )
    )


def _circle_on_plane(model, plane: str, radius_m: float) -> str | None:
    model.ClearSelection2(True)
    if not _select(model, plane, "PLANE", 0, False):
        print(f"  !! 平面选不中: {plane}")
        return None
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, radius_m)
    model.SketchManager.InsertSketch(True)
    names = _sketch_names(model)
    return names[-1] if names else None


def sec_sweep(sw) -> bool:
    assert design.create_new_part(sw)["success"]
    model = sw.get_active_document()
    model.ClearSelection2(True)
    assert _select(model, FRONT, "PLANE", 0, False)
    model.SketchManager.InsertSketch(True)
    # 90° 圆弧路径：圆心原点、起 (20,0)、终 (0,20)、逆时针
    # （ISketchManager.CreateArc 10 参；CreateArc2 是 ModelDoc 老接口的，不在 SketchManager 上）
    model.SketchManager.CreateArc(
        0.0, 0.0, 0.0,
        mm_to_m(20.0), 0.0, 0.0,
        0.0, mm_to_m(20.0), 0.0,
        1,
    )
    model.SketchManager.InsertSketch(True)
    sk = _sketch_names(model)[-1]
    fm = _typed(call_or_value(model, "FeatureManager"), "IFeatureManager")

    variants = [
        ("m4_alignF", 4, False),  # N9 helix 先例：路径 mark4 + Alignment=False
        ("m4_alignT", 4, True),
        ("m1_alignF", 1, False),
        ("m2_alignF", 2, False),
    ]
    hit = False
    for tag, mark, alignment in variants:
        model.ClearSelection2(True)
        if not _select(model, sk, "SKETCH", mark, False):
            print(f"[sweep:{tag}] FAIL: sketch {sk} 选不中 (mark={mark})")
            continue
        before = latest_feature_name(model)
        try:
            feat = fm.InsertProtrusionSwept4(
                False, alignment, 0, False, False, 0, 0,
                False, 0.0, 0.0, 0, 0, True, True, True, 0.0, True,
                True, mm_to_m(10.0), True,
            )
        except Exception as exc:  # noqa: BLE001 —— 探针：每变体独立捕获互不阻断
            print(f"[sweep:{tag}] EXC {exc!r}")
            continue
        after = latest_feature_name(model)
        vol = _vol_mm3(sw)
        ok = after != before and abs(vol - SWEEP_VOL_MM3) / SWEEP_VOL_MM3 < 0.01
        print(
            f"[sweep:{tag}] feat={feat!r} tree {before!r}->{after!r} "
            f"vol={vol:.2f} (expect {SWEEP_VOL_MM3:.2f}) => "
            f"{'OK' if ok else 'MISS'}"
        )
        if ok:
            hit = True
            break
    RESULTS.append(hit)
    file_io.close_document(sw, save_changes=False)
    return hit


def sec_loft_blend(sw) -> bool:
    assert design.create_new_part(sw)["success"]
    model = sw.get_active_document()

    n1 = _circle_on_plane(model, FRONT, mm_to_m(10.0))
    if n1 is None:
        print("[loft] FAIL: 剖面1草图未建成")
        RESULTS.append(False)
        file_io.close_document(sw, save_changes=False)
        return False

    # 偏移 30mm 平行基准面（swRefPlaneReferenceConstraint_Distance=8）
    # InsertRefPlane 属 IFeatureManager（6 参），不在 IModelDoc2 上（实证）
    model.ClearSelection2(True)
    if not _select(model, FRONT, "PLANE", 0, False):
        print("[loft] FAIL: 前视基准面选不中")
    fm = _typed(call_or_value(model, "FeatureManager"), "IFeatureManager")
    try:
        refplane = fm.InsertRefPlane(8, mm_to_m(30.0), 0, 0, 0, 0)
    except Exception as exc:  # noqa: BLE001
        refplane = None
        print(f"[loft] InsertRefPlane EXC {exc!r}")
    new_planes = [
        n
        for n in walk_feature_names(model)
        if "基准面" in n and "视" not in n
    ]
    print(f"[loft] refplane={refplane!r} new_planes={new_planes}")
    if not new_planes:
        print("[loft] FAIL: 偏移基准面未建成——下轮收敛建面")
        RESULTS.append(False)
        file_io.close_document(sw, save_changes=False)
        return False

    n2 = _circle_on_plane(model, new_planes[-1], mm_to_m(15.0))
    if n2 is None:
        print("[loft] FAIL: 剖面2草图未建成")
        RESULTS.append(False)
        file_io.close_document(sw, save_changes=False)
        return False

    doc2 = _typed(model, "IModelDoc2")
    variants = [
        ("m1m1", 1, 1),
        ("m1m2", 1, 2),
        ("m2m2", 2, 2),
        ("m4m4", 4, 4),
    ]
    hit = False
    for tag, m1, m2 in variants:
        model.ClearSelection2(True)
        if not _select(model, n1, "SKETCH", m1, False):
            print(f"[loft:{tag}] FAIL: {n1} 选不中")
            continue
        if not _select(model, n2, "SKETCH", m2, True):
            print(f"[loft:{tag}] FAIL: {n2} append 选不中")
            continue
        before = latest_feature_name(model)
        try:
            feat = doc2.InsertProtrusionBlend2(False, False, False)
        except Exception as exc:  # noqa: BLE001
            print(f"[loft:{tag}] EXC {exc!r}")
            continue
        after = latest_feature_name(model)
        vol = _vol_mm3(sw)
        ok = after != before and abs(vol - LOFT_VOL_MM3) / LOFT_VOL_MM3 < 0.01
        print(
            f"[loft:{tag}] feat={feat!r} tree {before!r}->{after!r} "
            f"vol={vol:.2f} (expect {LOFT_VOL_MM3:.2f}) => "
            f"{'OK' if ok else 'MISS'}"
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
    sweep_ok = sec_sweep(sw)
    loft_ok = sec_loft_blend(sw)
    print(f"\nSUMMARY: sweep={'OK' if sweep_ok else 'FAIL'} "
          f"loft={'OK' if loft_ok else 'FAIL'} ({sum(RESULTS)}/{len(RESULTS)})")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
