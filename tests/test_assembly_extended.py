"""Assembly creation, component, mate, and inspection tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.assembly import (
    _get_or_create_assembly,
    add_component,
    add_mate,
    get_components,
)


class TestAssemblyCreation(unittest.TestCase):
    def test_reuses_active_assembly(self):
        model = Mock()
        model.GetType.return_value = 2
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertIs(_get_or_create_assembly(sw), model)

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template", return_value="assembly.asmdot")
    def test_creates_assembly_from_template(self, _template):
        created = Mock()
        sw = Mock()
        sw.get_active_document.return_value = None
        sw.app.NewDocument.return_value = created
        self.assertIs(_get_or_create_assembly(sw), created)

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template", return_value=None)
    def test_missing_template_raises(self, _template):
        sw = Mock()
        sw.get_active_document.return_value = None
        with self.assertRaises(RuntimeError):
            _get_or_create_assembly(sw)

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template", return_value="assembly.asmdot")
    def test_new_document_none_raises(self, _template):
        sw = Mock()
        sw.get_active_document.return_value = None
        sw.app.NewDocument.return_value = None
        with self.assertRaises(RuntimeError):
            _get_or_create_assembly(sw)


class TestComponentOperations(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(False, "unsafe"))
    def test_rejects_invalid_path(self, _path):
        self.assertEqual(add_component(Mock(), "bad.sldprt")["message"], "unsafe")

    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension", return_value=(False, "wrong type"))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(True, ""))
    def test_rejects_invalid_extension(self, _path, _extension):
        result = add_component(Mock(), "bad.txt")
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    @patch("solidworks_mcp.solidworks_api.assembly._get_or_create_assembly")
    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(True, ""))
    def test_adds_component_with_meter_coordinates(self, _path, _extension, get_assembly):
        model = Mock()
        model.AddComponent4.return_value = SimpleNamespace(Name2="Part1-1")
        get_assembly.return_value = model
        result = add_component(Mock(), "part.sldprt", 10, 20, 30, "Default")
        self.assertTrue(result["success"])
        model.AddComponent4.assert_called_once_with("part.sldprt", "Default", 0.01, 0.02, 0.03)

    @patch("solidworks_mcp.solidworks_api.assembly._get_or_create_assembly")
    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(True, ""))
    def test_reports_component_insertion_failure(self, _path, _extension, get_assembly):
        get_assembly.return_value.AddComponent4.return_value = None
        self.assertFalse(add_component(Mock(), "part.sldprt")["success"])


class TestMateAndComponents(unittest.TestCase):
    def test_mate_requires_active_assembly_and_supported_type(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(add_mate(sw, "coincident", "A", "B")["success"])
        model = Mock()
        model.GetType.return_value = 2
        sw.get_active_document.return_value = model
        self.assertIn("Unsupported", add_mate(sw, "angle", "A", "B")["message"])

    def test_distance_mate_validates_distance(self):
        model = Mock()
        model.GetType.return_value = 2
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertEqual(add_mate(sw, "distance", "A", "B")["error"]["code"], "INVALID_PARAMETER")
        self.assertEqual(add_mate(sw, "distance", "A", "B", -1)["error"]["code"], "INVALID_PARAMETER")
        self.assertEqual(add_mate(sw, "distance", "A", "B", float("nan"))["error"]["code"], "INVALID_PARAMETER")

    @patch("solidworks_mcp.solidworks_api.assembly.win32com.client.VARIANT")
    def test_selection_and_mate_failures_are_structured(self, variant):
        variant.return_value = SimpleNamespace(value=7)
        model = Mock()
        model.GetType.return_value = 2
        model.GetTitle.return_value = "Assembly1"
        model.Extension.SelectByID2.return_value = False
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertIn("select", add_mate(sw, "coincident", "A", "B")["message"])
        model.Extension.SelectByID2.return_value = True
        model.AddMate5.return_value = None
        result = add_mate(sw, "coincident", "A", "B", entity1_type="FACE", entity2_type="FACE")
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")

    def test_get_components_success_empty_and_wrong_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(get_components(sw)["success"])
        model = Mock()
        model.GetType.return_value = 2
        model.GetComponents.return_value = [SimpleNamespace(Name2="A-1"), SimpleNamespace(Name2="B-1")]
        sw.get_active_document.return_value = model
        self.assertEqual(get_components(sw)["data"]["components"], ["A-1", "B-1"])
        model.GetComponents.return_value = None
        self.assertEqual(get_components(sw)["data"]["count"], 0)

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM")
        self.assertFalse(add_mate(sw, "coincident", "A", "B")["success"])
        self.assertFalse(get_components(sw)["success"])


if __name__ == "__main__":
    unittest.main()
