"""Drawing tool tests (T12) — fakes follow real-machine shapes:

- NewDocument returns a dynamic dispatch exposing IModelDoc + IDrawingDoc
  members only (SelectByID2 lives on Extension with 9 params, Callout=Nothing)
- zero-arg COM members are properties (GetType/GetTitle/GetFirstView/
  GetNextView/GetDisplayDimensionCount/GetAnnotationCount/EditRebuild3)
- Create1stAngleViews2 always returns False on SW 2026 — the manual route
  (CreateDrawViewFromModelView3 + CreateUnfoldedViewAt3) is the contract
- InsertModelAnnotations2(0, True, 0, True, True, False) is the verified call
  (InsertModelAnnotations3/4 on this machine return None and insert nothing)
"""

from __future__ import annotations

import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api import drawing


def _fake_bytes(path: str) -> bytes:
    if path.lower().endswith(".pdf"):
        return b"%PDF-1.6\n" + b"0" * 40000
    header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
    header += struct.pack(">II", 1264, 694) + b"\x08\x02\x00\x00\x00"
    return header + b"\x00" * 500


class FakeView:
    def __init__(self, name, dimensions=0, annotations=0):
        self.name = name
        self.dimensions = dimensions
        self.annotations = annotations
        self.next_view = None

    @property
    def Name(self):
        return self.name

    @property
    def GetDisplayDimensionCount(self):
        return self.dimensions

    @property
    def GetAnnotationCount(self):
        return self.annotations

    @property
    def GetNextView(self):
        return self.next_view


class FakeExtension:
    def __init__(self):
        self.calls = []

    def SelectByID2(self, name, type_, x, y, z, append, mark, callout, option):
        self.calls.append((name, type_))
        return True


class FakeDrawingDoc:
    """Sheet view first (GB template title block), model views appended."""

    def __init__(self):
        self.sheet = FakeView("图纸1", annotations=82)
        self.views = [self.sheet]
        self.ext = FakeExtension()
        self.created = []  # (model_path, config)
        self.unfolded = 0
        self.insert_calls = []
        self.save_calls = []

    @property
    def GetType(self):
        return 3  # swDocDRAWING

    @property
    def GetTitle(self):
        return "工程图1 - 图纸1"

    @property
    def Extension(self):
        return self.ext

    @property
    def GetFirstView(self):
        return self.views[0] if self.views else None

    @property
    def EditRebuild3(self):
        return True

    @property
    def ViewZoomtofit2(self):
        return True

    def _relink(self):
        for left, right in zip(self.views, self.views[1:]):
            left.next_view = right

    def CreateDrawViewFromModelView3(self, model_name, config, x, y, z):
        self.created.append((model_name, config))
        view = FakeView(f"工程图视图{len(self.views)}")
        self.views.append(view)
        self._relink()
        return view

    def CreateUnfoldedViewAt3(self, x, y, z, not_aligned):
        self.unfolded += 1
        view = FakeView(f"工程图视图{len(self.views)}")
        self.views.append(view)
        self._relink()
        return view

    def InsertModelAnnotations2(self, option, all_types, types, all_views,
                                duplicate, hidden):
        self.insert_calls.append(
            (option, all_types, types, all_views, duplicate, hidden)
        )
        if all_types:  # 实机：AllTypes=True 带入全部显示尺寸
            for view in self.views[1:]:
                view.dimensions += 1
                view.annotations += 1
            return True
        return False

    def SaveAs3(self, path, version, options):
        self.save_calls.append(path)
        Path(path).write_bytes(_fake_bytes(path))
        return 0


class FakePartDoc:
    @property
    def GetType(self):
        return 1  # swDocPART

    @property
    def Extension(self):
        return FakeExtension()


class FakeApp:
    def __init__(self, template_dir: Path, doc=None):
        self.template_dir = template_dir
        self.doc = doc if doc is not None else FakeDrawingDoc()
        self.new_document_calls = []

    def GetUserPreferenceStringValue(self, pref):
        return str(self.template_dir / "gb_a0.drwdot")

    def NewDocument(self, template, paper, width, height):
        self.new_document_calls.append(template)
        return self.doc

    def CloseAllDocuments(self, include_unsaved):
        return True


class DrawingTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="swmcp_dwg_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        # 模板目录：用户默认=A0，同目录存在 A3（应优先选择）
        (self.tmp / "gb_a0.drwdot").touch()
        (self.tmp / "gb_a3.drwdot").touch()
        self.part = str(self.tmp / "probe.SLDPRT")
        Path(self.part).write_bytes(b"part")
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("SOLIDWORKS_MCP_DRAWING_TEMPLATE", None)

    def _sw(self, doc=None):
        app = FakeApp(self.tmp, doc=doc)
        sw = Mock()
        sw.app = app
        sw.get_active_document.return_value = app.doc
        return sw, app

    def _patch_checks(self):
        return (
            patch(
                "solidworks_mcp.solidworks_api.drawing.validate_path",
                side_effect=lambda path, **kwargs: (True, ""),
            ),
            patch(
                "solidworks_mcp.solidworks_api.drawing.validate_output_file",
                side_effect=lambda path, exts, oc=False: (
                    (True, "")
                    if os.path.splitext(path)[1].lower() in exts
                    else (False, f"Unsupported output extension for {exts}: "
                                 f"{os.path.splitext(path)[1]}")
                ),
            ),
            patch(
                "solidworks_mcp.solidworks_api.drawing.ensure_sink_path",
                side_effect=lambda path: (True, "", path),
            ),
        )


class TestCreateDrawing(DrawingTestCase):
    def test_projects_three_views_and_selects_front_by_name(self):
        sw, app = self._sw()
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)

        self.assertTrue(result["success"], result)
        self.assertEqual(app.new_document_calls, [str(self.tmp / "gb_a3.drwdot")])
        # 建主视图用绝对路径 + 默认配置名空串
        self.assertEqual(app.doc.created[0][0], os.path.abspath(self.part))
        self.assertEqual(app.doc.created[0][1], "")
        # 主视图按 DRAWINGVIEW 类型选中两次（顶/侧投影各一次）
        self.assertEqual(
            app.doc.ext.calls,
            [("工程图视图1", "DRAWINGVIEW"), ("工程图视图1", "DRAWINGVIEW")],
        )
        self.assertEqual(app.doc.unfolded, 2)
        self.assertEqual(result["data"]["view_count"], 4)
        self.assertEqual(result["data"]["views"][0]["name"], "图纸1")

    def test_env_template_overrides_preference(self):
        env_tpl = self.tmp / "custom.drwdot"
        env_tpl.touch()
        os.environ["SOLIDWORKS_MCP_DRAWING_TEMPLATE"] = str(env_tpl)
        sw, app = self._sw()
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertTrue(result["success"])
        self.assertEqual(app.new_document_calls, [str(env_tpl)])

    def test_missing_template_is_reported(self):
        app = FakeApp(self.tmp)
        app.GetUserPreferenceStringValue = lambda pref: ""
        sw = Mock()
        sw.app = app
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "TEMPLATE_NOT_FOUND")
        self.assertIn("SOLIDWORKS_MCP_DRAWING_TEMPLATE", result["message"])

    def test_invalid_part_path_is_rejected(self):
        sw, _ = self._sw()
        with patch(
            "solidworks_mcp.solidworks_api.drawing.validate_path",
            return_value=(False, "path outside allowed root"),
        ):
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertIn("path outside allowed root", result["message"])

    def test_new_document_failure_is_structured(self):
        sw = Mock()
        sw.app.GetUserPreferenceStringValue = lambda pref: str(
            self.tmp / "gb_a3.drwdot"
        )
        sw.app.NewDocument = Mock(side_effect=RuntimeError("COM failed"))
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertIn("COM failed", result["message"])

    def test_front_view_failure_aborts_with_views_reported(self):
        doc = FakeDrawingDoc()

        def no_front(*args):
            return None

        doc.CreateDrawViewFromModelView3 = no_front
        sw, _ = self._sw(doc=doc)
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertIn("front view", result["message"])
        self.assertEqual(doc.unfolded, 0)  # 未继续投影

    def test_select_failure_aborts_projection(self):
        doc = FakeDrawingDoc()
        doc.ext.SelectByID2 = lambda *a: False
        sw, _ = self._sw(doc=doc)
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertIn("select the front view", result["message"])

    def test_projection_failure_is_reported(self):
        doc = FakeDrawingDoc()
        doc.CreateUnfoldedViewAt3 = lambda *a: None
        sw, _ = self._sw(doc=doc)
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertIn("projected view", result["message"])

    def test_view_count_shortfall_is_reported(self):
        doc = FakeDrawingDoc()
        # 投影调用成功但视图不落链（异常实机形态：返回对象而树未变）
        doc.CreateUnfoldedViewAt3 = lambda *a: FakeView("detached")
        sw, _ = self._sw(doc=doc)
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertIn("Only 2 views", result["message"])

    def test_stale_preference_still_resolves_neighbor_template(self):
        # pref 指向不存在的 gb_a0（版本目录失效），同目录 gb_a3 仍可用
        app = FakeApp(self.tmp)
        app.GetUserPreferenceStringValue = lambda pref: str(
            self.tmp / "gb_a0.drwdot"
        )
        (self.tmp / "gb_a0.drwdot").unlink()
        sw = Mock()
        sw.app = app
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertTrue(result["success"], result)
        self.assertEqual(app.new_document_calls, [str(self.tmp / "gb_a3.drwdot")])

    def test_preference_com_error_maps_to_template_not_found(self):
        app = FakeApp(self.tmp)
        app.GetUserPreferenceStringValue = Mock(
            side_effect=RuntimeError("COM failed")
        )
        sw = Mock()
        sw.app = app
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "TEMPLATE_NOT_FOUND")

    def test_views_without_count_members_are_tolerated(self):
        class BareView(FakeView):
            @property
            def GetDisplayDimensionCount(self):
                raise AttributeError("no such member")

        doc = FakeDrawingDoc()
        doc.sheet = BareView("图纸1")
        doc.views = [doc.sheet]
        sw, _ = self._sw(doc=doc)
        vp, vo, ve = self._patch_checks()
        with vp, vo, ve:
            result = drawing.create_drawing_from_part(sw, self.part)
        self.assertTrue(result["success"], result)
        self.assertIsNone(result["data"]["views"][0]["dimensions"])


class TestInsertDimensions(DrawingTestCase):
    def test_inserts_via_v2_all_types_and_reports_delta(self):
        sw, app = self._sw()
        doc = app.doc
        doc.CreateDrawViewFromModelView3("p.SLDPRT", "", 0.15, 0.10, 0.0)
        doc.CreateUnfoldedViewAt3(0.15, 0.19, 0.0, False)
        doc.CreateUnfoldedViewAt3(0.27, 0.10, 0.0, False)

        result = drawing.insert_model_dimensions(sw)

        self.assertTrue(result["success"], result)
        self.assertEqual(
            doc.insert_calls,
            [(0, True, 0, True, True, False)],
        )
        self.assertEqual(result["data"]["dimensions_inserted"], 3)
        self.assertEqual(result["data"]["total_dimensions"], 3)

    def test_rejects_non_drawing_document(self):
        sw = Mock()
        sw.get_active_document.return_value = FakePartDoc()
        result = drawing.insert_model_dimensions(sw)
        self.assertFalse(result["success"])
        self.assertIn("not a drawing", result["message"])

    def test_no_effect_is_reported_as_failure(self):
        doc = FakeDrawingDoc()
        doc.InsertModelAnnotations2 = lambda *a: False  # SW 拒绝，无尺寸入图
        sw, _ = self._sw(doc=doc)
        result = drawing.insert_model_dimensions(sw)
        self.assertFalse(result["success"])
        self.assertIn("no dimensions", result["message"])

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(drawing.insert_model_dimensions(sw)["success"])


class TestExport(DrawingTestCase):
    def test_export_pdf_reports_size(self):
        sw, _ = self._sw()
        out = str(self.tmp / "out.pdf")
        _, vo, ve = self._patch_checks()
        with vo, ve:
            result = drawing.export_drawing_pdf(sw, out)
        self.assertTrue(result["success"], result)
        self.assertGreater(result["data"]["size_bytes"], 10 * 1024)

    def test_export_png_reports_resolution(self):
        sw, _ = self._sw()
        out = str(self.tmp / "out.png")
        _, vo, ve = self._patch_checks()
        with vo, ve:
            result = drawing.export_drawing_png(sw, out)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["data"]["resolution"], {"width": 1264, "height": 694})

    def test_export_rejects_wrong_extension(self):
        sw, _ = self._sw()
        _, vo, _ = self._patch_checks()
        with vo, patch(
            "solidworks_mcp.solidworks_api.drawing.ensure_sink_path",
            side_effect=lambda path: (True, "", path),
        ):
            result = drawing.export_drawing_pdf(sw, str(self.tmp / "out.txt"))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")

    def test_export_save_failure_is_reported(self):
        doc = FakeDrawingDoc()
        doc.SaveAs3 = lambda *a: 2  # 非 0 错误码
        sw, _ = self._sw(doc=doc)
        _, vo, ve = self._patch_checks()
        with vo, ve:
            result = drawing.export_drawing_pdf(sw, str(self.tmp / "bad.pdf"))
        self.assertFalse(result["success"])
        self.assertIn("code 2", result["message"])

    def test_export_requires_active_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        _, vo, ve = self._patch_checks()
        with vo, ve:
            result = drawing.export_drawing_pdf(sw, str(self.tmp / "x.pdf"))
        self.assertFalse(result["success"])

    def test_export_png_with_bad_header_reports_null_resolution(self):
        doc = FakeDrawingDoc()

        def _save(path, *args):
            Path(path).write_bytes(b"junk-not-png")
            return 0

        doc.SaveAs3 = _save
        sw, _ = self._sw(doc=doc)
        _, vo, ve = self._patch_checks()
        with vo, ve:
            result = drawing.export_drawing_png(sw, str(self.tmp / "bad.png"))
        self.assertTrue(result["success"], result)
        self.assertIsNone(result["data"]["resolution"])

    def test_export_com_error_is_structured(self):
        doc = FakeDrawingDoc()
        doc.SaveAs3 = Mock(side_effect=RuntimeError("COM failed"))
        sw, _ = self._sw(doc=doc)
        _, vo, ve = self._patch_checks()
        with vo, ve:
            result = drawing.export_drawing_pdf(sw, str(self.tmp / "boom.pdf"))
        self.assertFalse(result["success"])
        self.assertIn("COM failed", result["message"])


class TestNotRunningPaths(unittest.TestCase):
    def test_all_tools_report_not_running(self):
        from solidworks_mcp.solidworks_api.app import SolidWorksNotRunningError

        sw = Mock()
        sw.get_active_document.side_effect = SolidWorksNotRunningError("not running")
        self.assertFalse(drawing.insert_model_dimensions(sw)["success"])
        self.assertFalse(drawing.export_drawing_pdf(sw, "x.pdf")["success"])
        self.assertFalse(drawing.export_drawing_png(sw, "x.png")["success"])

    def test_bare_mock_view_walk_breaks_on_sentinel(self):
        # 视图走查遇退化代理必须立即停（Name 非 str），空结果报 SW_NO_EFFECT
        sw = Mock()
        sw.get_active_document.return_value.GetType.return_value = 3
        result = drawing.insert_model_dimensions(sw)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_NO_EFFECT")


if __name__ == "__main__":
    unittest.main()
