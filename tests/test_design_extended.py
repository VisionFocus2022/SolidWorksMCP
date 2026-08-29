"""Parametric design helper and orchestration tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.design import (
    _get_active_part,
    _latest_feature_name,
    _save_active_model,
    _select_plane,
    create_new_part,
    create_plate,
    cut_round_hole,
    execute_design_plan,
    mm_to_m,
)
from solidworks_mcp.utils.common import error_response, success_response


class TestDesignHelpers(unittest.TestCase):
    def test_mm_conversion_and_active_part(self):
        self.assertEqual(mm_to_m(25), 0.025)
        sw = Mock()
        sw.get_active_document.return_value = None
        with self.assertRaises(RuntimeError):
            _get_active_part(sw)
        model = Mock()
        model.GetType.return_value = 1
        sw.get_active_document.return_value = model
        self.assertIs(_get_active_part(sw), model)

    def test_select_plane_uses_feature_then_extension(self):
        model = Mock()
        model.FeatureByName.return_value = SimpleNamespace(Select2=Mock(return_value=True))
        self.assertEqual(_select_plane(model, "front"), "Front Plane")
        model.FeatureByName.return_value = None
        model.Extension.SelectByID2.side_effect = [False, True]
        self.assertEqual(_select_plane(model, "top"), "\u4e0a\u89c6\u57fa\u51c6\u9762")

    def test_latest_feature_name(self):
        second = SimpleNamespace(Name="Boss", GetNextFeature=lambda: None)
        first = SimpleNamespace(Name="Sketch", GetNextFeature=lambda: second)
        model = SimpleNamespace(FirstFeature=lambda: first)
        self.assertEqual(_latest_feature_name(model), "Boss")

    def test_save_active_model_states(self):
        model = Mock()
        result = {}
        self.assertIsNone(_save_active_model(model, None, False, result))
        with patch("solidworks_mcp.solidworks_api.design.validate_output_file", return_value=(False, "bad")):
            self.assertEqual(_save_active_model(model, "bad.sldprt", False, result)["error"]["code"], "INVALID_OUTPUT_PATH")
        with patch("solidworks_mcp.solidworks_api.design.validate_output_file", return_value=(True, "")):
            model.SaveAs3.return_value = 5
            self.assertFalse(_save_active_model(model, "part.sldprt", False, result)["success"])
            model.SaveAs3.return_value = 0
            self.assertIsNone(_save_active_model(model, "part.sldprt", False, result))
            self.assertEqual(result["saved_to"], "part.sldprt")


class TestNewPartAndPlate(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.design.get_part_template", return_value=None)
    def test_new_part_requires_template(self, _template):
        self.assertFalse(create_new_part(Mock())["success"])

    @patch("solidworks_mcp.solidworks_api.design.get_part_template", return_value="part.prtdot")
    def test_new_part_handles_none_and_success(self, _template):
        sw = Mock()
        sw.app.NewDocument.return_value = None
        self.assertFalse(create_new_part(sw)["success"])
        model = Mock()
        model.GetTitle.return_value = "Part1"
        sw.app.NewDocument.return_value = model
        self.assertTrue(create_new_part(sw)["success"])

    def test_new_part_validates_output_before_creation(self):
        with patch("solidworks_mcp.solidworks_api.design.validate_output_file", return_value=(False, "bad")):
            result = create_new_part(Mock(), "bad.sldprt")
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")

    @patch("solidworks_mcp.solidworks_api.design.create_box")
    def test_plate_validates_and_delegates(self, create_box):
        self.assertEqual(create_plate(Mock(), 0, 2, 3)["error"]["code"], "INVALID_PARAMETER")
        create_box.return_value = success_response({}, "box")
        self.assertTrue(create_plate(Mock(), 10, 20, 3)["success"])
        create_box.assert_called_once()


class TestRoundHole(unittest.TestCase):
    def test_validates_plane_and_blind_depth(self):
        sw = Mock()
        self.assertEqual(cut_round_hole(sw, 5, 0, 0, plane="")["error"]["code"], "INVALID_PARAMETER")
        self.assertEqual(cut_round_hole(sw, 5, 0, 0, through_all=False)["error"]["code"], "INVALID_PARAMETER")

    # cut_round_hole resolves hole-plane aliases through _select_hole_plane
    # (HOLE_PLANE_ALIASES); patching the legacy _select_plane is a no-op and
    # once let the real path run against a bare Mock, whose feature tree
    # never terminates (the 34.86 GB runaway repro).
    @patch("solidworks_mcp.solidworks_api.design._select_hole_plane", return_value=None)
    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    def test_requires_selectable_plane(self, _part, _plane):
        self.assertFalse(cut_round_hole(Mock(), 5, 0, 0)["success"])

    @patch("solidworks_mcp.solidworks_api.design._latest_feature_name", return_value=None)
    @patch("solidworks_mcp.solidworks_api.design._select_hole_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    def test_requires_identifiable_sketch(self, get_part, _plane, _latest):
        get_part.return_value = Mock()
        self.assertFalse(cut_round_hole(Mock(), 5, 0, 0)["success"])

    @patch("solidworks_mcp.solidworks_api.design._latest_feature_name", return_value="Sketch2")
    @patch("solidworks_mcp.solidworks_api.design._select_hole_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    def test_creates_blind_hole_with_selection_fallback(self, get_part, _plane, _latest):
        model = Mock()
        model.Extension.SelectByID2.side_effect = [False, True]
        model.FeatureManager.FeatureCut3.return_value = SimpleNamespace(Name="Cut1")
        get_part.return_value = model
        result = cut_round_hole(Mock(), 10, 2, 3, depth=4, through_all=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["depth"], 4.0)
        model.SketchManager.CreateCircleByRadius.assert_called_once_with(0.002, 0.003, 0, 0.005)

    @patch("solidworks_mcp.solidworks_api.design._latest_feature_name", return_value="Sketch2")
    @patch("solidworks_mcp.solidworks_api.design._select_hole_plane", return_value="Front Plane")
    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    def test_reports_sketch_selection_and_cut_failure(self, get_part, _plane, _latest):
        model = Mock()
        model.Extension.SelectByID2.return_value = False
        get_part.return_value = model
        self.assertIn("select hole sketch", cut_round_hole(Mock(), 10, 0, 0)["message"])
        model.Extension.SelectByID2.return_value = True
        model.FeatureManager.FeatureCut3.return_value = None
        self.assertIn("Cut feature", cut_round_hole(Mock(), 10, 0, 0)["message"])


class TestDesignPlanBranches(unittest.TestCase):
    def test_empty_non_list_unsupported_and_missing_key(self):
        sw = Mock()
        self.assertEqual(execute_design_plan(sw, [])["error"]["code"], "INVALID_PARAMETER")
        self.assertEqual(execute_design_plan(sw, "box")["error"]["code"], "INVALID_PARAMETER")
        self.assertIn("Unsupported", execute_design_plan(sw, [{"type": "loft"}])["message"])
        self.assertEqual(execute_design_plan(sw, [{"type": "box", "depth": 2, "height": 3}])["error"]["code"], "INVALID_PARAMETER")

    @patch("solidworks_mcp.solidworks_api.design.create_cylinder", return_value=success_response({}, "cylinder"))
    @patch("solidworks_mcp.solidworks_api.design.create_plate", return_value=success_response({}, "plate"))
    def test_executes_plate_and_cylinder(self, plate, cylinder):
        result = execute_design_plan(Mock(), [
            {"type": "plate", "width": 10, "depth": 20, "thickness": 2},
            {"type": "cylinder", "diameter": 5, "height": 10},
        ])
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]["operations"]), 2)
        plate.assert_called_once()
        cylinder.assert_called_once()

    @patch("solidworks_mcp.solidworks_api.design.create_new_part", return_value=success_response({}, "new"))
    def test_saves_completed_plan(self, _new):
        model = Mock()
        model.SaveAs3.return_value = 0
        sw = Mock()
        sw.get_active_document.return_value = model
        with patch("solidworks_mcp.solidworks_api.design.validate_output_file", return_value=(True, "")):
            result = execute_design_plan(sw, [{"type": "new_part"}], "part.sldprt")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["saved_to"], "part.sldprt")

    @patch("solidworks_mcp.solidworks_api.design.create_plate", return_value=error_response("failed"))
    def test_stops_when_plate_fails(self, _plate):
        result = execute_design_plan(Mock(), [{"type": "plate", "width": 1, "depth": 2, "height": 3}])
        self.assertFalse(result["success"])
        self.assertEqual(len(result["data"]["completed"]), 1)


if __name__ == "__main__":
    unittest.main()
