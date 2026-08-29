"""Revolved feature creation tests (centerline sketch + FeatureRevolve2)."""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.part import create_revolved


class TestCreateRevolved(unittest.TestCase):
    def _run(self, outer, height, bore=0, **kwargs):
        model = Mock()
        axis = Mock()
        model.SketchManager.CreateLine.return_value = axis
        model.FeatureManager.FeatureRevolve2.return_value = SimpleNamespace(
            Name="Revolve1"
        )
        sw = Mock()
        with patch(
            "solidworks_mcp.solidworks_api.part._get_or_create_part",
            return_value=(model, True),
        ), patch(
            "solidworks_mcp.solidworks_api.part._select_plane",
            return_value="前视基准面",
        ):
            result = create_revolved(sw, outer, height, bore, **kwargs)
        return result, model, axis

    def test_ring_sketch_and_revolve_call_sequence(self):
        result, model, axis = self._run(40, 20, bore=10)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["feature_name"], "Revolve1")
        # Axis: centerline along sketch-y, half-height in metres.
        model.SketchManager.CreateLine.assert_called_once_with(
            0, -0.01, 0, 0, 0.01, 0
        )
        self.assertTrue(axis.ConstructionGeometry)
        # Profile: inner radius to outer radius, half-height, in metres.
        model.SketchManager.CreateCornerRectangle.assert_called_once_with(
            0.005, -0.01, 0, 0.02, 0.01, 0
        )
        # Revolve: full circle in radians rides in the Dir1Angle slot.
        args = model.FeatureManager.FeatureRevolve2.call_args.args
        self.assertEqual(len(args), 20)
        self.assertEqual(args[8], 2 * math.pi)
        # Sketch entered and exited exactly once each.
        self.assertEqual(model.SketchManager.InsertSketch.call_count, 2)

    def test_solid_cone_of_revolution_starts_at_axis(self):
        result, model, _axis = self._run(30, 10)
        self.assertTrue(result["success"])
        model.SketchManager.CreateCornerRectangle.assert_called_once_with(
            0.0, -0.005, 0, 0.015, 0.005, 0
        )

    def test_revolve_reports_failure_and_saves_when_asked(self):
        model = Mock()
        axis = Mock()
        model.SketchManager.CreateLine.return_value = axis
        model.FeatureManager.FeatureRevolve2.return_value = None
        sw = Mock()
        with patch(
            "solidworks_mcp.solidworks_api.part._get_or_create_part",
            return_value=(model, True),
        ), patch(
            "solidworks_mcp.solidworks_api.part._select_plane",
            return_value="前视基准面",
        ):
            failed = create_revolved(sw, 40, 20, 10)
        self.assertFalse(failed["success"])
        self.assertIn("Revolve", failed["message"])

        model.FeatureManager.FeatureRevolve2.return_value = SimpleNamespace(
            Name="Revolve1"
        )
        model.SaveAs3.return_value = 0
        with patch(
            "solidworks_mcp.solidworks_api.part._get_or_create_part",
            return_value=(model, True),
        ), patch(
            "solidworks_mcp.solidworks_api.part._select_plane",
            return_value="前视基准面",
        ), patch(
            "solidworks_mcp.solidworks_api.part.validate_output_file",
            return_value=(True, ""),
        ), patch(
            "solidworks_mcp.solidworks_api.part.ensure_sink_path",
            return_value=(True, "", "ring.sldprt"),
        ):
            saved = create_revolved(sw, 40, 20, 10, save_path="ring.sldprt")
        self.assertTrue(saved["success"])
        self.assertEqual(saved["data"]["saved_to"], "ring.sldprt")

    def test_revolve_validates_parameters(self):
        sw = Mock()
        checks = [
            create_revolved(sw, 0, 20),
            create_revolved(sw, 40, 0),
            create_revolved(sw, 40, 20, -1),
            create_revolved(sw, 40, 20, 40),
            create_revolved(sw, 40, 20, plane="top"),
        ]
        for result in checks:
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    def test_revolve_rejects_invalid_save_path_and_reports_sink_failures(self):
        model = Mock()
        model.SketchManager.CreateLine.return_value = Mock()
        model.FeatureManager.FeatureRevolve2.return_value = SimpleNamespace(
            Name="Revolve1"
        )
        sw = Mock()
        with patch(
            "solidworks_mcp.solidworks_api.part.validate_output_file",
            return_value=(False, "bad path"),
        ):
            result = create_revolved(sw, 40, 20, 10, save_path="ring.sldprt")
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")

        with patch(
            "solidworks_mcp.solidworks_api.part._get_or_create_part",
            return_value=(model, True),
        ), patch(
            "solidworks_mcp.solidworks_api.part._select_plane",
            return_value="前视基准面",
        ), patch(
            "solidworks_mcp.solidworks_api.part.validate_output_file",
            return_value=(True, ""),
        ), patch(
            "solidworks_mcp.solidworks_api.part.ensure_sink_path",
            return_value=(False, "bad sink", None),
        ):
            result = create_revolved(sw, 40, 20, 10, save_path="ring.sldprt")
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")

    def test_revolve_wraps_com_errors(self):
        model = Mock()
        model.SketchManager.CreateLine.side_effect = RuntimeError("COM failed")
        sw = Mock()
        with patch(
            "solidworks_mcp.solidworks_api.part._get_or_create_part",
            return_value=(model, True),
        ), patch(
            "solidworks_mcp.solidworks_api.part._select_plane",
            return_value="前视基准面",
        ):
            result = create_revolved(sw, 40, 20, 10)
        self.assertFalse(result["success"])
        self.assertIn("Failed to create revolved part", result["message"])

    def test_revolve_handles_missing_document_and_com_errors(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(create_revolved(sw, 40, 20)["success"])

        model = Mock()
        sw = Mock()
        sw.get_active_document.return_value = model
        with patch(
            "solidworks_mcp.solidworks_api.part.get_part_template",
            return_value=None,
        ):
            # No active part and no template -> part creation fails.
            self.assertFalse(create_revolved(sw, 40, 20)["success"])
        with patch(
            "solidworks_mcp.solidworks_api.part._get_or_create_part",
            return_value=(model, True),
        ), patch(
            "solidworks_mcp.solidworks_api.part._select_plane",
            return_value=None,
        ):
            result = create_revolved(sw, 40, 20)
        self.assertFalse(result["success"])
        self.assertIn("reference plane", result["message"])


if __name__ == "__main__":
    unittest.main()
