"""File import and export behavior tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.file_io import (
    FILE_LOAD_ERROR_NON_SW,
    _format_load_error,
    _guess_document_type,
    export_step,
    export_stl,
    import_step,
    open_document,
)


class TestOpenDocument(unittest.TestCase):
    @patch(
        "solidworks_mcp.solidworks_api.file_io.validate_path",
        return_value=(True, ""),
    )
    def test_rejects_unknown_extension_before_calling_solidworks(self, _validate_path):
        sw_app = Mock()

        result = open_document(sw_app, r"C:\models\notes.txt")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")
        sw_app.app.OpenDoc6.assert_not_called()

    def test_document_type_detection_and_load_error_formatting(self):
        self.assertEqual(_guess_document_type("part.SLDPRT"), 1)
        self.assertEqual(_guess_document_type("assembly.sldasm"), 2)
        self.assertEqual(_guess_document_type("drawing.slddrw"), 3)
        self.assertEqual(_guess_document_type("model.step"), 1)
        self.assertIn("3DInterconnect", _format_load_error(FILE_LOAD_ERROR_NON_SW))
        self.assertEqual(_format_load_error(7), "load error code 7")

    @patch("solidworks_mcp.solidworks_api.file_io.validate_path", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.file_io._make_error_variants")
    def test_opens_supported_document(self, variants, _validate):
        variants.return_value = (SimpleNamespace(value=0), SimpleNamespace(value=2))
        model = SimpleNamespace(GetTitle=lambda: "Part1")
        sw = Mock()
        sw.app.OpenDoc6.return_value = model
        result = open_document(sw, r"C:\models\part.sldprt")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["title"], "Part1")
        self.assertEqual(result["data"]["warnings"], 2)

    @patch("solidworks_mcp.solidworks_api.file_io.validate_path", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.file_io._make_error_variants")
    def test_open_reports_solidworks_load_failure(self, variants, _validate):
        variants.return_value = (
            SimpleNamespace(value=FILE_LOAD_ERROR_NON_SW),
            SimpleNamespace(value=0),
        )
        sw = Mock()
        sw.app.OpenDoc6.return_value = None
        result = open_document(sw, r"C:\models\part.step")
        self.assertFalse(result["success"])
        self.assertIn("3DInterconnect", result["message"])

    @patch("solidworks_mcp.solidworks_api.file_io.validate_path", return_value=(False, "unsafe"))
    def test_open_rejects_invalid_path(self, _validate):
        self.assertEqual(open_document(Mock(), "bad.sldprt")["message"], "unsafe")


class TestImportExport(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.file_io.validate_path", return_value=(True, ""))
    def test_import_step_validates_extension(self, _validate):
        result = import_step(Mock(), "part.iges")
        self.assertFalse(result["success"])
        self.assertIn("Expected .step", result["message"])

    @patch("solidworks_mcp.solidworks_api.file_io.validate_path", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.file_io._make_error_variants")
    def test_import_step_success_and_failure(self, variants, _validate):
        variants.return_value = (SimpleNamespace(value=0), SimpleNamespace(value=0))
        sw = Mock()
        sw.app.OpenDoc6.return_value = SimpleNamespace(GetTitle="Imported")
        self.assertTrue(import_step(sw, "part.step")["success"])
        sw.app.OpenDoc6.return_value = None
        self.assertFalse(import_step(sw, "part.stp")["success"])

    def test_export_validates_output_and_active_document(self):
        with patch(
            "solidworks_mcp.solidworks_api.file_io.validate_output_file",
            return_value=(False, "bad"),
        ):
            result = export_step(Mock(), "part.stl")
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")
        sw = Mock()
        sw.get_active_document.return_value = None
        with patch(
            "solidworks_mcp.solidworks_api.file_io.validate_output_file",
            return_value=(True, ""),
        ):
            self.assertFalse(export_stl(sw, "part.stl")["success"])

    def test_export_step_and_stl_success_and_save_error(self):
        model = Mock()
        sw = Mock()
        sw.get_active_document.return_value = model
        with patch(
            "solidworks_mcp.solidworks_api.file_io.validate_output_file",
            return_value=(True, ""),
        ):
            model.SaveAs3.return_value = 0
            self.assertTrue(export_step(sw, "part.step")["success"])
            self.assertTrue(export_stl(sw, "part.stl")["success"])
            model.SaveAs3.return_value = 9
            self.assertFalse(export_step(sw, "part.step")["success"])
            self.assertFalse(export_stl(sw, "part.stl")["success"])

    def test_com_exceptions_are_structured(self):
        with patch(
            "solidworks_mcp.solidworks_api.file_io.validate_path",
            side_effect=RuntimeError("COM"),
        ):
            self.assertFalse(open_document(Mock(), "part.sldprt")["success"])
            self.assertFalse(import_step(Mock(), "part.step")["success"])
        with patch(
            "solidworks_mcp.solidworks_api.file_io.validate_output_file",
            side_effect=RuntimeError("COM"),
        ):
            self.assertFalse(export_step(Mock(), "part.step")["success"])
            self.assertFalse(export_stl(Mock(), "part.stl")["success"])


if __name__ == "__main__":
    unittest.main()
