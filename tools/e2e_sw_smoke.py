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
    e2e.step("measure.measure_distance", measure.measure_distance, sw, [0.0, 0.0, 0.0], [60.0, 40.0, 0.0])
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

    # --- 装配链（可选段：当前无新建装配文档的 API，见 T11）---
    from solidworks_mcp.solidworks_api import assembly
    from solidworks_mcp.utils.com import call_or_value

    active = sw.get_active_document()
    # GetType 在实机是属性（零参 COM 成员铁律），须经 call_or_value 取值
    doc_type = call_or_value(active, "GetType") if active is not None else 0
    if doc_type == 2:  # swDocASSEMBLY
        e2e.step("assembly.add_component", assembly.add_component, sw, box_path, 0.0, 0.0, 0.0)
        e2e.step("assembly.add_component2", assembly.add_component, sw, cyl_path, 30.0, 0.0, 0.0)
        e2e.step("assembly.get_components", assembly.get_components, sw)
        e2e.step("file_io.close_document5", file_io.close_document, sw, True)
    else:
        e2e.steps.append({"name": "assembly.chain", "success": True, "skipped": True,
                          "note": "无活动装配文档且无新建装配 API（T11 将补 create_assembly）"})

    # --- 工程图链（T12）：建图→投三视图→入尺寸→导 PDF/PNG---
    from solidworks_mcp.solidworks_api import drawing as drawing_api

    e2e.step("drawing.create_from_part", drawing_api.create_drawing_from_part, sw, box_path)
    e2e.step("drawing.insert_dimensions", drawing_api.insert_model_dimensions, sw)
    e2e.step("drawing.export_pdf", drawing_api.export_drawing_pdf, sw, str(WORK_DIR / "e2e_box_drawing.pdf"), True)
    e2e.step("drawing.export_png", drawing_api.export_drawing_png, sw, str(WORK_DIR / "e2e_box_drawing.png"), True)
    # 工程图会隐式打开引用零件（文件锁），收尾必须全量释放
    try:
        sw.app.CloseAllDocuments(True)
        e2e.steps.append({"name": "drawing.cleanup", "success": True})
    except Exception as exc:
        e2e.steps.append({"name": "drawing.cleanup", "success": False,
                          "error": {"code": "EXCEPTION", "details": repr(exc)}})

    e2e.write_report()
    return 1 if e2e.failed else 0


if __name__ == "__main__":
    sys.exit(main())
