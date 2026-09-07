"""Part modeling operation tests with isolated COM doubles."""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.app import SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.features import get_features
from solidworks_mcp.solidworks_api.part import (
    _create_circle_sketch,
    _create_rectangle_sketch,
    _get_or_create_part,
    _select_plane,
    create_box,
    create_cone,
    create_cylinder,
    get_mass_properties,
)


class TestPartHelpers(unittest.TestCase):
    def test_reuses_active_part(self):
        model = Mock()
        model.GetType.return_value = 1
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertEqual(_get_or_create_part(sw), (model, False))

    @patch("solidworks_mcp.solidworks_api.part_support.get_part_template", return_value="part.prtdot")
    def test_creates_part_from_template(self, _template):
        created = Mock()
        sw = Mock()
        sw.get_active_document.return_value = None
        sw.app.NewDocument.return_value = created
        self.assertEqual(_get_or_create_part(sw), (created, True))

    @patch("solidworks_mcp.solidworks_api.part_support.get_part_template", return_value=None)
    def test_missing_template_raises(self, _template):
        sw = Mock()
        sw.get_active_document.return_value = None
        with self.assertRaises(RuntimeError):
            _get_or_create_part(sw)

    def test_plane_and_sketch_helpers(self):
        model = Mock()
        model.FeatureByName.side_effect = [None, SimpleNamespace(Select2=Mock(return_value=True))]
        self.assertEqual(_select_plane(model), "\u524d\u89c6\u57fa\u51c6\u9762")
        _create_circle_sketch(model, 0.01)
        model.SketchManager.CreateCircleByRadius.assert_called_once_with(0, 0, 0, 0.01)
        _create_rectangle_sketch(model, 0.04, 0.02)
        model.SketchManager.CreateCornerRectangle.assert_called_once_with(-0.02, -0.01, 0, 0.02, 0.01, 0)


class TestPartCreation(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.part._extrude_sketch")
    @patch("solidworks_mcp.solidworks_api.part._create_circle_sketch")
    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part")
    def test_create_cylinder_converts_units_and_saves(self, get_part, _plane, circle, extrude):
        model = Mock()
        model.SaveAs3.return_value = 0
        get_part.return_value = (model, True)
        extrude.return_value = SimpleNamespace(Name="Boss-Extrude1")
        with patch("solidworks_mcp.solidworks_api.save_io.validate_output_file", return_value=(True, "")):
            result = create_cylinder(Mock(), 20, 30, "part.sldprt")
        self.assertTrue(result["success"])
        circle.assert_called_once_with(model, 0.01)
        extrude.assert_called_once_with(model, 0.03)
        self.assertEqual(result["data"]["saved_to"], "part.sldprt")

    def test_create_cylinder_rejects_invalid_dimensions_and_path(self):
        self.assertEqual(create_cylinder(Mock(), 0, 2)["error"]["code"], "INVALID_PARAMETER")
        with patch("solidworks_mcp.solidworks_api.save_io.validate_output_file", return_value=(False, "bad path")):
            result = create_cylinder(Mock(), 1, 2, "bad.sldprt")
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")

    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value=None)
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part", return_value=(Mock(), True))
    def test_create_box_requires_reference_plane(self, _part, _plane):
        self.assertFalse(create_box(Mock(), 1, 2, 3)["success"])

    @patch("solidworks_mcp.solidworks_api.part._extrude_sketch", return_value=None)
    @patch("solidworks_mcp.solidworks_api.part._create_rectangle_sketch")
    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part", return_value=(Mock(), True))
    def test_create_box_reports_extrusion_failure(self, _part, _plane, _sketch, _extrude):
        self.assertIn("Extrusion", create_box(Mock(), 1, 2, 3)["message"])

    @patch("solidworks_mcp.solidworks_api.part._extrude_sketch")
    @patch("solidworks_mcp.solidworks_api.part._create_rectangle_sketch")
    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part")
    def test_create_box_success(self, get_part, _plane, rectangle, extrude):
        model = Mock()
        get_part.return_value = (model, False)
        extrude.return_value = SimpleNamespace(Name="Boss1")
        result = create_box(Mock(), 40, 20, 10)
        self.assertTrue(result["success"])
        rectangle.assert_called_once_with(model, 0.04, 0.02)
        extrude.assert_called_once_with(model, 0.01)


class TestConeCreation(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.part._extrude_draft_sketch")
    @patch("solidworks_mcp.solidworks_api.part._create_circle_sketch")
    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part")
    def test_create_cone_converts_units_and_derives_draft(
        self, get_part, _plane, circle, extrude
    ):
        model = Mock()
        model.SaveAs3.return_value = 0
        get_part.return_value = (model, True)
        extrude.return_value = SimpleNamespace(Name="Boss-Extrude1")
        with patch("solidworks_mcp.solidworks_api.save_io.validate_output_file", return_value=(True, "")):
            result = create_cone(Mock(), 20, 10, 30, "cone.sldprt")
        self.assertTrue(result["success"])
        # Sketch carries the bottom radius: 20 mm -> 0.01 m.
        circle.assert_called_once_with(model, 0.01)
        # Draft follows the real-machine contract: radians, far end narrows.
        expected_angle = math.atan2(5.0, 30.0)
        extrude.assert_called_once_with(model, 0.03, True, False, expected_angle)
        self.assertEqual(result["data"]["feature_name"], "Boss-Extrude1")
        self.assertEqual(
            result["data"]["draft_angle_degrees"],
            round(math.degrees(expected_angle), 4),
        )
        self.assertEqual(result["data"]["saved_to"], "cone.sldprt")

    @patch("solidworks_mcp.solidworks_api.part._extrude_draft_sketch")
    @patch("solidworks_mcp.solidworks_api.part._create_circle_sketch")
    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part")
    def test_create_cone_equal_diameters_disables_draft(
        self, get_part, _plane, _circle, extrude
    ):
        model = Mock()
        get_part.return_value = (model, True)
        extrude.return_value = SimpleNamespace(Name="Boss-Extrude1")
        result = create_cone(Mock(), 20, 20, 30)
        self.assertTrue(result["success"])
        extrude.assert_called_once_with(model, 0.03, False, False, 0.0)
        self.assertEqual(result["data"]["draft_angle_degrees"], 0.0)

    def test_create_cone_rejects_invalid_dimensions(self):
        self.assertEqual(
            create_cone(Mock(), 20, -5, 30)["error"]["code"], "INVALID_PARAMETER"
        )
        self.assertEqual(
            create_cone(Mock(), 0, 10, 30)["error"]["code"], "INVALID_PARAMETER"
        )
        self.assertEqual(
            create_cone(Mock(), 20, float("nan"), 30)["error"]["code"],
            "INVALID_PARAMETER",
        )

    @patch("solidworks_mcp.solidworks_api.part._extrude_draft_sketch", return_value=None)
    @patch("solidworks_mcp.solidworks_api.part._create_circle_sketch")
    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part", return_value=(Mock(), True))
    def test_create_cone_reports_extrusion_failure(self, _part, _plane, _sketch, _extrude):
        self.assertIn("Drafted", create_cone(Mock(), 20, 10, 30)["message"])


class TestConeEdgeCases(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.save_io.validate_output_file", return_value=(False, "bad path"))
    def test_create_cone_rejects_invalid_save_path(self, _validate):
        self.assertEqual(
            create_cone(Mock(), 20, 10, 30, "cone.sldprt")["error"]["code"],
            "INVALID_OUTPUT_PATH",
        )

    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value=None)
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part", return_value=(Mock(), True))
    def test_create_cone_reports_missing_reference_plane(self, _part, _plane):
        self.assertIn("reference plane", create_cone(Mock(), 20, 10, 30)["message"])

    @patch("solidworks_mcp.solidworks_api.save_io.ensure_sink_path")
    @patch("solidworks_mcp.solidworks_api.save_io.validate_output_file", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.part._extrude_draft_sketch")
    @patch("solidworks_mcp.solidworks_api.part._create_circle_sketch")
    @patch("solidworks_mcp.solidworks_api.part._select_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.part._get_or_create_part")
    def test_create_cone_reports_sink_and_save_failures(
        self, get_part, _plane, _sketch, extrude, _validate, sink
    ):
        model = Mock()
        get_part.return_value = (model, True)
        extrude.return_value = SimpleNamespace(Name="Boss")
        sink.return_value = (False, "bad sink", None)
        self.assertIn("bad sink", create_cone(Mock(), 20, 10, 30, "cone.sldprt")["message"])
        sink.return_value = (True, "", "cone.sldprt")
        model.SaveAs3.return_value = 9
        self.assertIn("SaveAs3 failed", create_cone(Mock(), 20, 10, 30, "cone.sldprt")["message"])

    def test_create_cone_wraps_com_and_not_running_errors(self):
        sw = Mock()
        sw.get_active_document.side_effect = SolidWorksNotRunningError("down")
        self.assertIn("down", create_cone(sw, 20, 10, 30)["message"])
        sw.get_active_document.side_effect = RuntimeError("COM")
        self.assertIn("Failed to create cone", create_cone(sw, 20, 10, 30)["message"])


class TestMassPropertiesEdgeCases(unittest.TestCase):
    def test_mass_properties_handles_missing_mass_object_and_not_running(self):
        sw = Mock()
        sw.get_active_document.side_effect = SolidWorksNotRunningError("down")
        self.assertIn("down", get_mass_properties(sw)["message"])

        sw = Mock()
        model = Mock()
        model.GetBodies2.return_value = [object()]
        model.Extension.CreateMassProperty.return_value = None
        sw.get_active_document.return_value = model
        self.assertIn("Could not create", get_mass_properties(sw)["message"])


class TestPartInspection(unittest.TestCase):
    def test_mass_properties_success_and_missing_states(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(get_mass_properties(sw)["success"])
        model = Mock()
        model.GetBodies2.return_value = []
        sw.get_active_document.return_value = model
        self.assertIn("No bodies", get_mass_properties(sw)["message"])
        model.GetBodies2.return_value = [object()]
        mass = SimpleNamespace(Volume=1.0, SurfaceArea=2.0, Mass=3.0, CenterOfMass=(0.1, 0.2, 0.3))
        model.Extension.CreateMassProperty.return_value = mass
        result = get_mass_properties(sw)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["center_of_mass"], [0.1, 0.2, 0.3])

    def test_feature_listing(self):
        second = SimpleNamespace(Name="Boss", GetNextFeature=lambda: None)
        first = SimpleNamespace(Name="Origin", GetNextFeature=lambda: second)
        model = SimpleNamespace(FirstFeature=lambda: first)
        sw = Mock()
        sw.get_active_document.return_value = model
        result = get_features(sw)
        self.assertEqual(result["data"]["count"], 2)

    def test_inspection_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM")
        self.assertFalse(get_mass_properties(sw)["success"])
        self.assertFalse(get_features(sw)["success"])


if __name__ == "__main__":
    unittest.main()
