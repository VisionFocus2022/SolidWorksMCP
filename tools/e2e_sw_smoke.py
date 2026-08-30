"""实机 E2E 冒烟：逐工具驱动 solidworks_api 层，计时并输出 JSON 报告。

前置：SolidWorks 2026 已启动（本脚本不自动拉起）。
用法：项目根目录下  venv\\Scripts\\python.exe tools\\e2e_sw_smoke.py
产物：output/e2e-report-<时间戳>.json（同时打印摘要）
退出码：0=全部通过；1=存在失败步骤；2=SolidWorks 未运行。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "output"
WORK_DIR = OUTPUT_DIR / "e2e-work"


def _short(result: dict) -> dict:
    out = {"success": bool(result.get("success"))}
    if result.get("message"):
        out["message"] = str(result["message"])[:200]
    if result.get("error"):
        out["error"] = result["error"]
    if isinstance(result.get("data"), dict):
        out["data_keys"] = sorted(result["data"].keys())
    return out


class E2E:
    def __init__(self) -> None:
        self.steps: list = []

    def _record(self, name: str, result: dict, elapsed: float) -> dict:
        summary = _short(result)
        summary["name"] = name
        summary["elapsed_s"] = elapsed
        self.steps.append(summary)
        print(f"[{'OK ' if summary['success'] else 'FAIL'}] {name} ({elapsed}s)")
        return result

    def step(self, name: str, fn, *args, **kwargs) -> dict:
        t0 = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # 探测脚本：异常也是数据，不中断链路
            result = {"success": False, "error": {"code": "EXCEPTION", "details": repr(exc)}}
        return self._record(name, result, round(time.perf_counter() - t0, 3))

    @property
    def failed(self) -> list:
        return [s["name"] for s in self.steps if not s["success"]]

    def write_report(self, note: str = "") -> Path:
        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total": len(self.steps),
            "passed": sum(1 for s in self.steps if s["success"]),
            "failed_steps": self.failed,
            "steps": self.steps,
        }
        if note:
            report["note"] = note
        out = OUTPUT_DIR / f"e2e-report-{datetime.now():%Y%m%d-%H%M%S}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告：{out}")
        print(f"通过 {report['passed']}/{report['total']}；失败：{report['failed_steps'] or '无'}")
        return out


def main() -> int:
    from solidworks_mcp.solidworks_api import (
        design,
        features,
        file_io,
        measure,
        part,
        topology,
    )
    from solidworks_mcp.solidworks_api.app import get_solidworks_app

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    sw = get_solidworks_app()
    e2e = E2E()

    conn = e2e.step("app.connect", sw.connect, launch_if_needed=False)
    if not conn["success"]:
        print("SolidWorks 未运行，退出码 2（不自动启动）")
        e2e.write_report(note="SolidWorks 未运行")
        return 2

    # --- 零件链 ---
    box_path = str(WORK_DIR / "e2e_box.SLDPRT")
    cyl_path = str(WORK_DIR / "e2e_cylinder.SLDPRT")
    e2e.step("design.create_new_part", design.create_new_part, sw, str(WORK_DIR / "e2e_blank.SLDPRT"), True)
    e2e.step("part.create_box", part.create_box, sw, 60.0, 40.0, 20.0, box_path, True)
    # 默认特征名随 SW 界面语言本地化（实机为中文「凸台-拉伸1」），故动态取树末特征
    listing = e2e.step("features.get_features", features.get_features, sw)
    names = (listing.get("data") or {}).get("features") or []
    boss_name = names[-1] if names else None
    if boss_name:
        e2e.step("features.rename_feature", features.rename_feature, sw, boss_name, "E2E_Boss")
    else:
        e2e.steps.append({"name": "features.rename_feature", "success": False,
                          "error": {"code": "NO_FEATURES", "details": None}})
    e2e.step("design.cut_round_hole", design.cut_round_hole, sw, 8.0, 0.0, 0.0, "top", None, True)
    e2e.step("features.set_feature_suppression", features.set_feature_suppression, sw, "E2E_Boss", False)
    details = e2e.step("features.get_feature_details", features.get_feature_details, sw)
    dims = [
        d
        for f in (details.get("data") or {}).get("features") or []
        for d in f.get("dimensions") or []
        if d.get("value_mm")
    ]
    if dims:
        e2e.step("features.set_dimension", features.set_dimension, sw, dims[0]["full_name"], 25.0)
    cut = next((n for n in names if n.startswith("切除") or "Cut" in n), None)
    if cut:
        e2e.step("features.delete_feature", features.delete_feature, sw, cut)
    e2e.step("measure.get_bounding_box", measure.get_bounding_box, sw)
    e2e.step("measure.measure_distance", measure.measure_distance, [0.0, 0.0, 0.0], [60.0, 40.0, 0.0])
    e2e.step("topology.list_bodies", topology.list_bodies, sw)
    box_listing = e2e.step("topology.list_faces", topology.list_faces, sw)
    # 盒顶/底两面（2400mm²）互不相邻：圆角其一、倒角另一，几何确定性成立
    big_faces = [f["name"] for f in (box_listing.get("data") or {}).get("faces") or []
                 if f.get("area_mm2") == 2400.0]
    if len(big_faces) >= 2:
        e2e.step("decorations.apply_fillet", decorations.apply_fillet, sw, big_faces[:1], 2.0)
        e2e.step("decorations.apply_chamfer", decorations.apply_chamfer, sw, big_faces[1:2], 1.0)
    e2e.step("part.get_mass_properties", part.get_mass_properties, sw)

    # --- 材料/属性/方程式/配置链（T17）---
    from solidworks_mcp.solidworks_api import properties as props

    e2e.step("props.set_material", props.set_material, sw, "合金钢")
    e2e.step("props.get_material", props.get_material, sw)
    e2e.step("props.set_custom_property", props.set_custom_property, sw, "PartNo", "E2E-001")
    e2e.step("props.get_custom_properties", props.get_custom_properties, sw)
    e2e.step("props.add_equation", props.add_equation, sw, '"e2e_x" = 50')
    e2e.step("props.list_equations", props.list_equations, sw)
    e2e.step("props.add_configuration", props.add_configuration, sw, "E2E_CFG")

    # --- N12 参数化闭环：方程式增删改 + 配置激活系列件最小链 ---
    e2e.step("props.edit_equation", props.edit_equation, sw, 0, '"e2e_x" = 99')
    e2e.step("props.activate_configuration", props.activate_configuration, sw, "E2E_CFG")
    if dims:
        fam_name = dims[0]["full_name"]
        e2e.step("features.set_dimension_cfg", features.set_dimension, sw, fam_name, 30.0, "E2E_CFG")

        def _read_dim(sw_app, full_name):
            model = sw_app.get_active_document()
            raw = model.Parameter(full_name).GetSystemValue3(1, "")
            from solidworks_mcp.solidworks_api.features import _system_value_m
            value_m = _system_value_m(raw)
            return {"success": value_m is not None,
                    "data": {"value_mm": round(value_m * 1000.0, 6) if value_m is not None else None}}

        e2e.step("props.activate_default", props.activate_configuration, sw, "默认")
        base = e2e.step("n12.read_default", _read_dim, sw, fam_name)
        e2e.step("props.activate_family", props.activate_configuration, sw, "E2E_CFG")
        fam = e2e.step("n12.read_family", _read_dim, sw, fam_name)
        base_mm = ((base.get("data") or {}).get("value_mm"))
        fam_mm = ((fam.get("data") or {}).get("value_mm"))
        isolated = base_mm is not None and fam_mm is not None and base_mm != fam_mm
        e2e.steps.append({"name": "n12.expect_config_isolated", "success": isolated,
                          "error": None if isolated else {"code": "CONFIG_NOT_ISOLATED",
                                                          "details": f"default={base_mm} family={fam_mm}"}})
    else:
        e2e.steps.append({"name": "n12.family_chain", "success": False,
                          "error": {"code": "NO_DIMS", "details": None}})
    e2e.step("props.delete_equation", props.delete_equation, sw, 0)

    e2e.step("file_io.export_step", file_io.export_step, sw, str(WORK_DIR / "e2e_box.step"), True)
    e2e.step("file_io.export_stl", file_io.export_stl, sw, str(WORK_DIR / "e2e_box.stl"), True)
    e2e.step("file_io.close_document", file_io.close_document, sw, True)

    e2e.step("file_io.open_document", file_io.open_document, sw, box_path)
    e2e.step("file_io.close_document2", file_io.close_document, sw, False)

    e2e.step("part.create_cylinder", part.create_cylinder, sw, 20.0, 50.0, cyl_path, True)
    e2e.step("part.create_cone", part.create_cone, sw, 30.0, 10.0, 40.0, str(WORK_DIR / "e2e_cone.SLDPRT"), True)
    e2e.step("part.create_revolved", part.create_revolved, sw, 40.0, 10.0, 20.0, "front", str(WORK_DIR / "e2e_ring.SLDPRT"), True)

    # --- 装饰链（对回转环的面做圆角/倒角；选中走 walk+Select2，T5 契约）---
    from solidworks_mcp.solidworks_api import decorations

    listing = e2e.step("topology.list_faces2", topology.list_faces, sw)
    ring_faces = [f["name"] for f in (listing.get("data") or {}).get("faces") or []]
    if len(ring_faces) >= 2:
        e2e.step("decorations.apply_fillet", decorations.apply_fillet, sw, ring_faces[:2], 2.0)
        # ring 四面环形相邻，柱面圆角后端面倒角几何求解非确定（e2e 两轮一过一败），
        # 倒角已移至盒链的对顶/底面；此处仅 shell
        e2e.step("decorations.apply_shell", decorations.apply_shell, sw, ring_faces[1:2], 2.0)
    else:
        e2e.steps.append({"name": "decorations.chain", "success": False,
                          "error": {"code": "NO_FACES", "details": None}})
    e2e.step("file_io.close_document3", file_io.close_document, sw, False)
    e2e.step("file_io.import_step", file_io.import_step, sw, str(WORK_DIR / "e2e_box.step"))
    e2e.step("file_io.close_document4", file_io.close_document, sw, False)

    # --- 装配链（T11 全自动段）：重叠→干涉非空；分离→空；BOM 聚合 ---
    from solidworks_mcp.solidworks_api import assembly as asm_api

    asm_path = str(WORK_DIR / "e2e_asm.SLDASM")
    e2e.step("assembly.new", asm_api.new_assembly, sw, asm_path, True)
    e2e.step("assembly.add_component1", asm_api.add_component, sw, box_path, 0.0, 0.0, 0.0)
    added2 = e2e.step("assembly.add_component2", asm_api.add_component, sw, box_path, 10.0, 0.0, 0.0)
    overlap = e2e.step("assembly.check_interference1", asm_api.check_interference, sw)
    overlap_ok = bool((overlap.get("data") or {}).get("has_interference"))
    e2e.steps.append({"name": "assembly.expect_overlap", "success": overlap_ok,
                      "error": None if overlap_ok else {"code": "NO_INTERFERENCE", "details": overlap.get("message")}})
    # --- N8 修复闭环：空间定位（center/bbox 非空）→ move_component 修复 → 复检归零 ---
    rows = (overlap.get("data") or {}).get("interferences") or []
    spatial_ok = bool(rows) and bool(rows[0].get("center_mm")) and bool(rows[0].get("bbox_mm"))
    e2e.steps.append({"name": "assembly.expect_spatial", "success": spatial_ok,
                      "error": None if spatial_ok else {"code": "NO_SPATIAL", "details": str(rows[:1])[:200]}})
    second = ((added2.get("data") or {}).get("component_name")) or ""
    if second:
        e2e.step("assembly.move_component", asm_api.move_component, sw, second, 100.0, 0.0, 0.0)
        fixed = e2e.step("assembly.check_interference3", asm_api.check_interference, sw)
        fixed_ok = not bool((fixed.get("data") or {}).get("has_interference"))
        e2e.steps.append({"name": "assembly.expect_repaired", "success": fixed_ok,
                          "error": None if fixed_ok else {"code": "STILL_INTERFERING", "details": fixed.get("message")}})
        dm = asm_api.delete_mate(sw, "重合999")  # 预期失败：不在树 → MATE_NOT_FOUND
        dm_ok = (dm.get("error") or {}).get("code") == "MATE_NOT_FOUND"
        e2e.steps.append({"name": "assembly.expect_mate_not_found", "success": dm_ok,
                          "error": None if dm_ok else {"code": "WRONG_ERROR", "details": dm.get("message")}})
    else:
        e2e.steps.append({"name": "assembly.expect_component_name", "success": False,
                          "error": {"code": "NO_COMPONENT_NAME", "details": str(added2)[:200]}})
    bom = e2e.step("assembly.get_bom1", asm_api.get_bom, sw)
    box_count = next((i["count"] for i in (bom.get("data") or {}).get("items") or []
                      if i.get("name") == "e2e_box"), 0)
    e2e.steps.append({"name": "assembly.expect_bom_2x", "success": box_count == 2,
                      "error": None if box_count == 2 else {"code": "BOM_MISMATCH", "details": f"count={box_count}"}})
    box_item = next((i for i in (bom.get("data") or {}).get("items") or []
                     if i.get("name") == "e2e_box"), {})
    vol_ok = isinstance(box_item.get("volume_mm3"), (int, float)) and box_item["volume_mm3"] > 0
    e2e.steps.append({"name": "assembly.expect_bom_volume", "success": vol_ok,
                      "error": None if vol_ok else {"code": "NO_VOLUME", "details": str(box_item)[:200]}})

    e2e.step("assembly.new2", asm_api.new_assembly, sw)
    e2e.step("assembly.add_component3", asm_api.add_component, sw, box_path, 0.0, 0.0, 0.0)
    e2e.step("assembly.add_component4", asm_api.add_component, sw, cyl_path, 200.0, 0.0, 0.0)
    separated = e2e.step("assembly.check_interference2", asm_api.check_interference, sw)
    sep_ok = not bool((separated.get("data") or {}).get("has_interference"))
    e2e.steps.append({"name": "assembly.expect_separated", "success": sep_ok,
                      "error": None if sep_ok else {"code": "UNEXPECTED_INTERFERENCE", "details": None}})
    e2e.step("assembly.get_bom2", asm_api.get_bom, sw)
    # 组件预开+装配引用都会锁文件，段末全量释放（含保存装配演示档）
    try:
        sw.app.CloseAllDocuments(True)
        e2e.steps.append({"name": "assembly.cleanup", "success": True})
    except Exception as exc:
        e2e.steps.append({"name": "assembly.cleanup", "success": False,
                          "error": {"code": "EXCEPTION", "details": repr(exc)}})

    # --- 工程图链（T12）：建图→投三视图→入尺寸→导 PDF/PNG---
    from solidworks_mcp.solidworks_api import drawing as drawing_api

    e2e.step("drawing.create_from_part", drawing_api.create_drawing_from_part, sw, box_path)
    e2e.step("drawing.insert_dimensions", drawing_api.insert_model_dimensions, sw)
    # N4：尺寸整理（去重+错开）与剖视图——入尺寸后、导出前
    e2e.step("drawing.organize_dimensions", drawing_api.organize_dimensions, sw)
    e2e.step("drawing.insert_section_view", drawing_api.insert_section_view, sw, "工程图视图1", 0.0, "vertical")
    # N5：公差/粗糙度/注释——导出前；公差目标=第一个显示尺寸（FullName 动态取，避免硬编码特征名）
    def _set_tol_on_first(sw_app):
        from solidworks_mcp.utils.com import call_or_value
        model = sw_app.get_active_document()
        view = call_or_value(model, "GetFirstView")
        for _ in range(50):
            if view is None:
                break
            name = call_or_value(view, "Name")
            if not isinstance(name, str):
                break
            for dd in call_or_value(view, "GetDisplayDimensions") or ():
                try:
                    full = call_or_value(dd.GetDimension2(0), "FullName")
                except Exception:
                    continue
                if isinstance(full, str):
                    return drawing_api.set_tolerance(sw_app, full, 0.10, -0.05)
            view = call_or_value(view, "GetNextView")
        return {"success": False, "data": None, "warning": None,
                "message": "no display dimension found",
                "error": {"code": "E2E_NO_DIM", "details": None}}

    e2e.step("drawing.set_tolerance", _set_tol_on_first, sw)
    e2e.step("drawing.insert_surface_finish", drawing_api.insert_surface_finish, sw, 1.6, 300.0, 40.0)
    e2e.step("drawing.insert_note", drawing_api.insert_note, sw, "技术要求：未注公差按 GB/T 1804-m。", 50.0, 25.0)
    e2e.step("drawing.export_pdf", drawing_api.export_drawing_pdf, sw, str(WORK_DIR / "e2e_box_drawing.pdf"), True)
    e2e.step("drawing.export_png", drawing_api.export_drawing_png, sw, str(WORK_DIR / "e2e_box_drawing.png"), True)
    from solidworks_mcp.solidworks_api import file_io as file_io_api
    e2e.step("drawing.export_dxf", file_io_api.export_dxf, sw, str(WORK_DIR / "e2e_box_drawing.dxf"), True)
    # 工程图会隐式打开引用零件（文件锁），收尾必须全量释放
    try:
        sw.app.CloseAllDocuments(True)
        e2e.steps.append({"name": "drawing.cleanup", "success": True})
    except Exception as exc:
        e2e.steps.append({"name": "drawing.cleanup", "success": False,
                          "error": {"code": "EXCEPTION", "details": repr(exc)}})

    # --- 钣金链（T21-3）：基体法兰 → 特征树 + bbox 断言 ---
    from solidworks_mcp.solidworks_api import sheet_metal

    sm_path = str(WORK_DIR / "e2e_flange.SLDPRT")
    e2e.step("sheet_metal.base_flange", sheet_metal.create_base_flange,
             sw, 60.0, 40.0, 2.0, 0.0, sm_path, True)
    sm_details = e2e.step("sheet_metal.get_details", features.get_feature_details, sw)
    sm_names = [f["name"] for f in (sm_details.get("data") or {}).get("features") or []]
    has_sm = any(("钣金" in n or "基体-法兰" in n or "平展" in n) for n in sm_names)
    e2e.steps.append({"name": "sheet_metal.expect_features", "success": has_sm,
                      "error": None if has_sm else {"code": "NO_SHEET_METAL",
                                                    "details": sm_names[-6:]}})
    sm_bb = e2e.step("sheet_metal.get_bbox", measure.get_bounding_box, sw)
    sm_size = (sm_bb.get("data") or {}).get("size_mm")
    e2e.steps.append({"name": "sheet_metal.expect_bbox",
                      "success": sm_size == [60.0, 2.0, 40.0],
                      "error": None if sm_size == [60.0, 2.0, 40.0]
                      else {"code": "BBOX_MISMATCH", "details": sm_size}})
    try:
        sw.app.CloseAllDocuments(True)
        e2e.steps.append({"name": "sheet_metal.cleanup", "success": True})
    except Exception as exc:
        e2e.steps.append({"name": "sheet_metal.cleanup", "success": False,
                          "error": {"code": "EXCEPTION", "details": repr(exc)}})

    # --- CSG 重建链（T16）：契约示例 → 4 特征 → bbox 断言 ---
    from solidworks_mcp.solidworks_api import design as design_api

    csg_plan = {
        "version": 1, "units": "mm",
        "operations": [
            {"op": "box", "name": "base", "size": [60, 40, 20], "at": [0, 0, 0]},
            {"op": "cylinder", "name": "boss", "diameter": 20, "height": 30,
             "at": [0, 0, 20]},
            {"op": "cut_cylinder", "name": "bore", "diameter": 8, "depth": None,
             "through": True, "at": [0, 0, 0]},
            {"op": "cone", "name": "tip", "bottom_diameter": 10,
             "top_diameter": 4, "height": 12, "at": [0, 0, 50]},
        ],
    }
    csg = e2e.step("csg.rebuild", design_api.rebuild_csg_plan, sw, csg_plan)
    applied = (csg.get("data") or {}).get("applied") or []
    e2e.steps.append({"name": "csg.expect_features",
                      "success": applied == ["base", "boss", "bore", "tip"],
                      "error": None if applied else {"code": "CSG_APPLIED", "details": applied}})
    det2 = e2e.step("csg.get_feature_details", features.get_feature_details, sw)
    tree_names = {f["name"] for f in (det2.get("data") or {}).get("features") or []}
    e2e.steps.append({"name": "csg.expect_tree",
                      "success": {"base", "boss", "bore", "tip"} <= tree_names,
                      "error": None})
    bb2 = e2e.step("csg.get_bounding_box", measure.get_bounding_box, sw)
    size2 = (bb2.get("data") or {}).get("size_mm")
    e2e.steps.append({"name": "csg.expect_bbox_60_40_62",
                      "success": size2 == [60.0, 40.0, 62.0],
                      "error": None if size2 == [60.0, 40.0, 62.0]
                      else {"code": "BBOX_MISMATCH", "details": size2}})
    try:
        sw.get_active_document().SaveAs3(str(WORK_DIR / "e2e_csg.SLDPRT"), 0, 1)
        e2e.steps.append({"name": "csg.save", "success": True})
    except Exception as exc:
        e2e.steps.append({"name": "csg.save", "success": False,
                          "error": {"code": "EXCEPTION", "details": repr(exc)}})
    try:
        sw.app.CloseAllDocuments(True)
        e2e.steps.append({"name": "csg.cleanup", "success": True})
    except Exception as exc:
        e2e.steps.append({"name": "csg.cleanup", "success": False,
                          "error": {"code": "EXCEPTION", "details": repr(exc)}})

    # --- N9 解锁链：镜像/拔模/真实螺纹原生 + 线性孔阵（数学替代）---
    # 契约来自 tools/probe_part/probe_n9_unblock.py 13 轮实机探针（2026-08-30）：
    # mirror=BODYFEATURE mark1+PLANE mark2→InsertMirrorFeature2(False,True,True,False,0)；
    # draft=拔模面 Select2(False,1)+中性面 Select2(True,2)→typed InsertMultiFaceDraft；
    # thread=顶面圆→InsertHelix→REFERENCECURVES mark4→typed InsertCutSwept5(Alignment=False)；
    # pattern 三路线均 BLOCKED → 线性孔阵走数学替代（循环 cut_round_hole）。

    def _volume_mm3(sw_app) -> "float | None":
        mp = part.get_mass_properties(sw_app)
        v = (mp.get("data") or {}).get("volume")
        return v * 1_000_000_000.0 if isinstance(v, (int, float)) else None

    def _feature_names() -> "list[str]":
        return (features.get_features(sw).get("data") or {}).get("features") or []

    # 镜像：盒+偏心穿孔→镜像切除特征→对称位出孔（ΔV≈孔体积 1005mm³，探针实测）
    e2e.step("n9.mirror_create_box", part.create_box, sw, 60.0, 40.0, 20.0,
             str(WORK_DIR / "e2e_n9_mirror.SLDPRT"), True)
    e2e.step("n9.mirror_cut_hole", design.cut_round_hole, sw, 8.0, 15.0, 0.0, "top", None, True)
    mv0 = _volume_mm3(sw)
    cut_name = next((n for n in _feature_names() if n.startswith("切除")), None)
    if cut_name and mv0 is not None:
        e2e.step("n9.mirror_feature", features.mirror_feature, sw, cut_name, "right")
        mv1 = _volume_mm3(sw)
        mirrored = mv1 is not None and 900 < (mv0 - mv1) < 1100
        e2e.steps.append({"name": "n9.mirror_expect_dv", "success": mirrored,
                          "error": None if mirrored else {"code": "DV_MISMATCH",
                                                          "details": f"{mv0} -> {mv1}"}})
    else:
        e2e.steps.append({"name": "n9.mirror_feature", "success": False,
                          "error": {"code": "NO_CUT_FEATURE", "details": cut_name}})

    # 拔模：盒侧面 3° 外拔、底面中性（探针实测 48000→50516mm³）
    # create_box 是 get-or-create 语义：每段必须先关闭上一文档，否则凸台堆料
    e2e.step("n9.mirror_doc_close", file_io.close_document, sw, False)
    e2e.step("n9.draft_create_box", part.create_box, sw, 60.0, 40.0, 20.0,
             str(WORK_DIR / "e2e_n9_draft.SLDPRT"), True)
    dfl = e2e.step("n9.draft_list_faces", topology.list_faces, sw)
    dfaces = (dfl.get("data") or {}).get("faces") or []
    d_side = next((f["name"] for f in dfaces if f.get("area_mm2") == 800.0), None)
    d_bottom = next((f["name"] for f in dfaces if f.get("area_mm2") == 2400.0), None)
    if d_side and d_bottom:
        e2e.step("n9.apply_draft", features.apply_draft, sw, d_side, d_bottom, 3.0)
        dv1 = _volume_mm3(sw)
        # SW MultiFace 拔模会传播到周向全部侧面（实机取证：4 侧面面积全变），
        # ΔV 取决于中性面选中顶/底：3773(顶)/2516(底)，断言取宽区间覆盖两种遍历序
        drafted = dv1 is not None and 2000 < (dv1 - 48000.0) < 4200
        e2e.steps.append({"name": "n9.draft_expect_dv", "success": drafted,
                          "error": None if drafted else {"code": "DV_MISMATCH",
                                                         "details": f"48000 -> {dv1}"}})
    else:
        e2e.steps.append({"name": "n9.apply_draft", "success": False,
                          "error": {"code": "NO_FACES", "details": f"side={d_side} bottom={d_bottom}"}})

    # 真实螺纹：⌀20×50 圆柱 helix 扫掠切除（探针实测 ΔV≈55，CircularProfile 半嵌入）
    e2e.step("n9.draft_doc_close", file_io.close_document, sw, False)
    e2e.step("n9.thread_create_cylinder", part.create_cylinder, sw, 20.0, 50.0,
             str(WORK_DIR / "e2e_n9_thread.SLDPRT"), True)
    tv0 = _volume_mm3(sw)
    e2e.step("n9.cut_real_thread", features.cut_real_thread, sw, 20.0, 2.5, 20.0)
    swept = any("扫描" in n for n in _feature_names())
    e2e.steps.append({"name": "n9.thread_expect_feature", "success": swept,
                      "error": None if swept else {"code": "NO_SWEEP",
                                                   "details": _feature_names()[-4:]}})
    tv1 = _volume_mm3(sw)
    threaded = tv0 is not None and tv1 is not None and 5 < (tv0 - tv1) < 500
    e2e.steps.append({"name": "n9.thread_expect_dv", "success": threaded,
                      "error": None if threaded else {"code": "DV_MISMATCH",
                                                      "details": f"{tv0} -> {tv1}"}})

    # 线性孔阵（数学替代，pattern BLOCKED 兜底）：3×⌀6 穿孔 ΔV≈1696mm³
    e2e.step("n9.thread_doc_close", file_io.close_document, sw, False)
    e2e.step("n9.holes_create_box", part.create_box, sw, 60.0, 40.0, 20.0,
             str(WORK_DIR / "e2e_n9_holes.SLDPRT"), True)
    e2e.step("n9.create_linear_holes", design.create_linear_holes,
             sw, 6.0, 10.0, 0.0, "top", 3, 8.0, "x", None, True)
    hv1 = _volume_mm3(sw)
    drilled = hv1 is not None and 1600 < (48000.0 - hv1) < 1800
    e2e.steps.append({"name": "n9.holes_expect_dv", "success": drilled,
                      "error": None if drilled else {"code": "DV_MISMATCH",
                                                     "details": f"48000 -> {hv1}"}})
    try:
        sw.app.CloseAllDocuments(True)
        e2e.steps.append({"name": "n9.cleanup", "success": True})
    except Exception as exc:
        e2e.steps.append({"name": "n9.cleanup", "success": False,
                          "error": {"code": "EXCEPTION", "details": repr(exc)}})

    e2e.write_report()
    return 1 if e2e.failed else 0


if __name__ == "__main__":
    sys.exit(main())
