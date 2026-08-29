"""Tests for design-plan validation and orchestration without SolidWorks."""

from __future__ import annotations

import math
import unittest
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.design import (
    cut_round_hole,
    cut_threaded_hole,
    execute_design_plan,
)
from solidworks_mcp.utils.common import error_response, success_response


class FakeSolidWorks:
    def get_active_document(self):
        return None


def _thread_model(picked=True, created=Mock(name="cosmetic-thread")):
    model = Mock()
    model.Extension.SelectByID2.return_value = picked
    model.FeatureManager.InsertCosmeticThread2.return_value = created
    return model


class TestDesignPlan(unittest.TestCase):
    def test_invalid_hole_dimension_has_invalid_parameter_code(self):
        result = cut_round_hole(FakeSolidWorks(), diameter=0, x=0, y=0)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    def test_rejects_non_object_operation(self):
        result = execute_design_plan(FakeSolidWorks(), ["hole"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    def test_false_string_is_not_treated_as_true(self, cut_round_hole):
        cut_round_hole.return_value = success_response({}, "done")
        result = execute_design_plan(
            FakeSolidWorks(),
            [
                {
                    "type": "hole",
                    "diameter": 8,
                    "depth": 5,
                    "through_all": "false",
                }
            ],
        )
        self.assertTrue(result["success"])
        self.assertFalse(cut_round_hole.call_args.kwargs["through_all"])

    @patch("solidworks_mcp.solidworks_api.design.create_new_part")
    def test_invalid_save_path_is_rejected_before_model_changes(self, create_new_part):
        result = execute_design_plan(
            FakeSolidWorks(),
            [{"type": "new_part"}],
            save_path=r"C:\Windows\forbidden.sldprt",
        )
        self.assertFalse(result["success"])
        create_new_part.assert_not_called()

    @patch("solidworks_mcp.solidworks_api.design.create_new_part")
    def test_stops_after_failed_operation(self, create_new_part):
        create_new_part.return_value = {
            "success": False,
            "data": None,
            "message": "failed",
            "warning": None,
            "error": {"code": "SW_API_ERROR", "details": None},
        }
        result = execute_design_plan(FakeSolidWorks(), [{"type": "new_part"}])
        self.assertFalse(result["success"])
        self.assertEqual(len(result["data"]["completed"]), 1)


class TestThreadedHole(unittest.TestCase):
    def test_rejects_non_string_and_unknown_specs(self):
        self.assertEqual(
            cut_threaded_hole(FakeSolidWorks(), 42, 0, 0)["error"]["code"],
            "INVALID_PARAMETER",
        )
        result = cut_threaded_hole(FakeSolidWorks(), "M99", 0, 0)
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")
        self.assertIn("M2", result["message"])

    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    def test_stamps_cosmetic_thread_at_45_degree_edge(
        self, cut_round_hole, get_active_part
    ):
        model = _thread_model()
        get_active_part.return_value = model
        cut_round_hole.return_value = success_response(
            {"feature_name": "Cut-Extrude1"}, "hole"
        )
        sw = FakeSolidWorks()
        result = cut_threaded_hole(sw, "m8", 10, 5)
        self.assertTrue(result["success"])
        cut_round_hole.assert_called_once_with(sw, 6.8, 10, 5, "top", None, True)
        # 45-degree diagonal pick mapped into MODEL space for hole plane
        # "top": the hole sketch lands on the Front Plane (HOLE_PLANE_ALIASES),
        # so sketch x->X, sketch y->Y, plane normal (Z) at 0 for the first probe.
        # M8 drills 6.8 mm, so each sketch axis offset is 3.4*cos45 mm.
        args = model.Extension.SelectByID2.call_args[0]
        self.assertEqual(args[1], "EDGE")
        self.assertAlmostEqual(args[2], 0.01 + 0.0034 * math.cos(math.pi / 4))
        self.assertAlmostEqual(args[3], 0.005 + 0.0034 * math.cos(math.pi / 4))
        self.assertAlmostEqual(args[4], 0.0)
        # Through-all thread length falls back to the nominal major diameter.
        model.FeatureManager.InsertCosmeticThread2.assert_called_once_with(
            0, 0.008, 0.008, "M8x1.25"
        )
        thread = result["data"]["thread"]
        self.assertEqual(
            thread,
            {
                "spec": "M8",
                "tap_drill_diameter": 6.8,
                "pitch": 1.25,
                "cosmetic_thread_stamped": True,
            },
        )
        self.assertIsNone(result["warning"])

    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    def test_through_all_sweeps_plane_normal_offsets(self, cut_round_hole, get_active_part):
        model = _thread_model()
        # Only a probe off the sketch plane lands on the real mouth edge.
        model.Extension.SelectByID2.side_effect = (
            lambda *a: abs(a[4]) > 0  # model Z is the front-sketch normal (hole "top")
        )
        get_active_part.return_value = model
        cut_round_hole.return_value = success_response({}, "hole")
        result = cut_threaded_hole(FakeSolidWorks(), "M8", 0, 0)
        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["thread"]["cosmetic_thread_stamped"])
        calls = model.Extension.SelectByID2.call_args_list
        self.assertGreater(len(calls), 1)
        self.assertEqual(calls[0].args[4], 0.0)
        self.assertAlmostEqual(calls[-1].args[4], 0.002)

    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    def test_blind_depth_uses_real_thread_length(self, cut_round_hole, get_active_part):
        model = _thread_model()
        get_active_part.return_value = model
        cut_round_hole.return_value = success_response({}, "hole")
        result = cut_threaded_hole(
            FakeSolidWorks(), "M6", 0, 0, depth=12, through_all=False
        )
        self.assertTrue(result["success"])
        model.FeatureManager.InsertCosmeticThread2.assert_called_once_with(
            0, 0.006, 0.012, "M6x1"
        )

    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    def test_unselectable_edge_degrades_to_warning(self, cut_round_hole, get_active_part):
        model = _thread_model(picked=False)
        get_active_part.return_value = model
        cut_round_hole.return_value = success_response({}, "hole")
        result = cut_threaded_hole(FakeSolidWorks(), "M8", 0, 0)
        self.assertTrue(result["success"])
        self.assertFalse(result["data"]["thread"]["cosmetic_thread_stamped"])
        self.assertIn("Cosmetic thread", result["warning"])
        model.FeatureManager.InsertCosmeticThread2.assert_not_called()

    @patch("solidworks_mcp.solidworks_api.design._get_active_part")
    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    def test_thread_feature_returning_none_is_not_fatal(
        self, cut_round_hole, get_active_part
    ):
        model = _thread_model(created=None)
        get_active_part.return_value = model
        cut_round_hole.return_value = success_response({}, "hole")
        result = cut_threaded_hole(FakeSolidWorks(), "M8", 0, 0)
        self.assertTrue(result["success"])
        self.assertFalse(result["data"]["thread"]["cosmetic_thread_stamped"])

    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    def test_cut_failure_is_propagated_before_threading(self, cut_round_hole):
        cut_round_hole.return_value = error_response("no active part", code="SW_API_ERROR")
        result = cut_threaded_hole(FakeSolidWorks(), "M8", 0, 0)
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")


class TestDesignPlanNewOperations(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.design.create_cone")
    def test_cone_dispatch_converts_values(self, create_cone):
        create_cone.return_value = success_response({}, "done")
        sw = FakeSolidWorks()
        result = execute_design_plan(
            sw,
            [{"type": "cone", "bottom_diameter": 20, "top_diameter": 10, "height": 30}],
        )
        self.assertTrue(result["success"])
        create_cone.assert_called_once_with(sw, 20.0, 10.0, 30.0)

    @patch("solidworks_mcp.solidworks_api.design.cut_threaded_hole")
    def test_threaded_hole_dispatch_and_alias(self, cut_threaded_hole):
        cut_threaded_hole.return_value = success_response({}, "done")
        sw = FakeSolidWorks()
        result = execute_design_plan(
            sw,
            [
                {
                    "type": "threaded_hole",
                    "spec": "M6",
                    "x": 10,
                    "y": -5,
                    "depth": 8,
                    "through_all": False,
                }
            ],
        )
        self.assertTrue(result["success"])
        cut_threaded_hole.assert_called_once_with(
            sw, spec="M6", x=10.0, y=-5.0, plane="top", depth=8.0, through_all=False
        )
        result = execute_design_plan(sw, [{"type": "thread_hole", "spec": "M6"}])
        self.assertTrue(result["success"])

    @patch("solidworks_mcp.solidworks_api.pattern.create_annular_pattern")
    def test_annular_pattern_dispatch_forwards_rings(self, create_annular_pattern):
        create_annular_pattern.return_value = success_response({}, "done")
        sw = FakeSolidWorks()
        rings = [{"radius_mm": 30, "count": 6}]
        result = execute_design_plan(
            sw, [{"type": "ring_pattern", "rings": rings}]
        )
        self.assertTrue(result["success"])
        create_annular_pattern.assert_called_once_with(
            sw,
            rings,
            plane="top",
            feature_kind="cut",
            depth=None,
            through_all=True,
            avoid_angles_degrees=None,
        )

    def test_annular_pattern_requires_rings_list(self):
        result = execute_design_plan(sw := FakeSolidWorks(), [{"type": "annular_pattern"}])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")
        self.assertIn("rings", result["message"])

    def test_unsupported_operation_lists_new_types(self):
        result = execute_design_plan(FakeSolidWorks(), [{"type": "sphere"}])
        self.assertFalse(result["success"])
        for expected in ("cone", "threaded_hole", "annular_pattern"):
            self.assertIn(expected, result["message"])

    @patch("solidworks_mcp.solidworks_api.pattern.create_annular_pattern")
    @patch("solidworks_mcp.solidworks_api.design.cut_threaded_hole")
    @patch("solidworks_mcp.solidworks_api.design.cut_round_hole")
    @patch("solidworks_mcp.solidworks_api.design.create_cone")
    @patch("solidworks_mcp.solidworks_api.design.create_cylinder")
    @patch("solidworks_mcp.solidworks_api.design.create_plate")
    def test_mixed_plan_runs_five_feature_kinds(
        self, plate, cylinder, cone, hole, threaded, ring
    ):
        for stub in (plate, cylinder, cone, hole, threaded, ring):
            stub.return_value = success_response({}, "done")
        result = execute_design_plan(
            FakeSolidWorks(),
            [
                {"type": "plate", "width": 100, "depth": 100, "thickness": 10},
                {"type": "cylinder", "diameter": 30, "height": 20},
                {"type": "cone", "bottom_diameter": 20, "top_diameter": 8, "height": 15},
                {"type": "hole", "diameter": 6, "x": 40, "y": 40},
                {
                    "type": "threaded_hole",
                    "spec": "M8",
                    "x": -40,
                    "y": -40,
                    "depth": 10,
                    "through_all": False,
                },
                {"type": "annular_pattern", "rings": [{"radius_mm": 45, "count": 8}]},
            ],
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]["operations"]), 6)
        self.assertEqual(
            [entry["operation"] for entry in result["data"]["operations"]],
            ["plate", "cylinder", "cone", "hole", "threaded_hole", "annular_pattern"],
        )


if __name__ == "__main__":
    unittest.main()
