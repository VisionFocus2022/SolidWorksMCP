"""Ring-light layout and SolidWorks tool contract tests."""

from __future__ import annotations

import math
import unittest
from pathlib import Path
from unittest.mock import Mock

from solidworks_mcp.examples.ring_light import (
    DEFAULT_ROW_COUNTS,
    build_ring_light_layout,
    build_spherical_dome_bands,
    create_ring_light,
)
from solidworks_mcp.server import mcp


class TestRingLightLayout(unittest.TestCase):
    def test_default_layout_matches_confirmed_requirements(self):
        layout = build_ring_light_layout()

        self.assertEqual([row["count"] for row in layout["rows"]], list(range(21, 30)))
        self.assertEqual(layout["total_led_count"], 225)
        self.assertEqual(len(layout["rows"]), 9)
        self.assertAlmostEqual(layout["rows"][0]["angle_degrees"], 30.0)
        self.assertAlmostEqual(layout["rows"][-1]["angle_degrees"], 60.0)
        self.assertEqual(layout["led_diameter_mm"], 2.6)
        self.assertEqual(layout["carrier_thickness_mm"], 60.0)

    def test_row_geometry_is_monotonic_and_keeps_ring_clearances(self):
        layout = build_ring_light_layout()
        radii = [row["radius_mm"] for row in layout["rows"]]
        heights = [row["z_mm"] for row in layout["rows"]]

        self.assertEqual(radii, sorted(radii))
        self.assertEqual(heights, sorted(heights, reverse=True))
        self.assertGreaterEqual(radii[0] - layout["center_hole_diameter_mm"] / 2.0, 1.9)
        self.assertGreaterEqual(layout["outer_diameter_mm"] / 2.0 - radii[-1], 1.8)

    def test_rows_lie_on_one_spherical_cap_and_normals_match_angles(self):
        layout = build_ring_light_layout()
        sphere_radius = layout["dome"]["sphere_radius_mm"]
        sphere_center_z = layout["dome"]["sphere_center_z_mm"]

        self.assertEqual(layout["dome"]["profile"], "spherical_cap")
        self.assertAlmostEqual(sphere_radius, 44.0, places=6)
        for row in layout["rows"]:
            angle = math.radians(row["angle_degrees"])
            self.assertAlmostEqual(row["radius_mm"], sphere_radius * math.sin(angle), places=5)
            self.assertAlmostEqual(row["z_mm"], sphere_center_z + sphere_radius * math.cos(angle), places=5)

        self.assertGreater(layout["rows"][0]["z_mm"], layout["rows"][-1]["z_mm"])
        self.assertAlmostEqual(layout["rows"][-1]["z_mm"], 0.0, places=6)

    def test_native_dome_bands_approximate_same_spherical_profile(self):
        layout = build_ring_light_layout()
        bands = build_spherical_dome_bands(layout, step_count=48)

        self.assertEqual(len(bands), 48)
        self.assertAlmostEqual(
            bands[0]["inner_radius_mm"],
            layout["center_hole_diameter_mm"] / 2.0,
            places=6,
        )
        self.assertAlmostEqual(
            bands[-1]["outer_radius_mm"],
            layout["rows"][-1]["radius_mm"],
            places=6,
        )
        heights = [band["extrusion_height_mm"] for band in bands]
        self.assertEqual(heights, sorted(heights, reverse=True))
        self.assertGreater(heights[0], layout["carrier_thickness_mm"])
        self.assertGreaterEqual(heights[-1], layout["carrier_thickness_mm"])
    def test_custom_row_count_must_have_nine_rows(self):
        with self.assertRaises(ValueError):
            build_ring_light_layout(row_counts=[21, 22])

    def test_phase_offsets_avoid_four_m3_mounting_axes(self):
        layout = build_ring_light_layout()
        forbidden = {45.0, 135.0, 225.0, 315.0}
        for row in layout["rows"]:
            first = row["phase_degrees"] % 360.0
            for blocked in forbidden:
                distance = abs(((first - blocked + 180.0) % 360.0) - 180.0)
                self.assertGreaterEqual(distance, 3.0)


class TestRingLightCreate(unittest.TestCase):
    def test_invalid_output_path_is_rejected_before_solidworks_changes(self):
        sw = Mock()
        result = create_ring_light(sw, save_path=r"C:\Windows\bad.sldprt")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")
        sw.get_active_document.assert_not_called()

    def test_existing_sldprt_requires_overwrite_confirmation(self):
        existing = (
            Path(__file__).resolve().parents[1]
            / "output"
            / "audit_plate_20260721_094417.SLDPRT"
        )
        if not existing.exists():
            self.skipTest("fixture output file is not present")

        result = create_ring_light(Mock(), save_path=str(existing), overwrite_confirm=False)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")


class TestRingLightServerRegistration(unittest.TestCase):
    def test_ring_light_tool_is_registered(self):
        tools = {tool.name for tool in mcp._tool_manager.list_tools()}

        self.assertIn("solidworks_part_create_ring_light", tools)
        tool = mcp._tool_manager.get_tool("solidworks_part_create_ring_light")
        self.assertEqual(tool.parameters["properties"]["outer_diameter"]["exclusiveMinimum"], 0)
        self.assertIsNotNone(tool.output_schema)

    def test_default_row_counts_are_21_to_29(self):
        self.assertEqual(DEFAULT_ROW_COUNTS, tuple(range(21, 30)))


if __name__ == "__main__":
    unittest.main()
