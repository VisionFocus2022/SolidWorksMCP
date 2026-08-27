"""Tests for design-plan validation and orchestration without SolidWorks."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from solidworks_mcp.solidworks_api.design import cut_round_hole, execute_design_plan
from solidworks_mcp.utils.common import success_response


class FakeSolidWorks:
    def get_active_document(self):
        return None


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


if __name__ == "__main__":
    unittest.main()
