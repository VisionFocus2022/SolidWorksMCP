"""Concave ring-light v3 geometry tests."""

from __future__ import annotations

import math
import unittest

from solidworks_mcp.solidworks_api.ring_light_v3 import (
    build_concave_dish_bands,
    build_ring_light_v3_layout,
    _band_crosses_mount_zone,
)
from solidworks_mcp.server import mcp


class TestRingLightV3Layout(unittest.TestCase):
    def test_defaults_follow_step_and_confirmed_led_requirements(self):
        layout = build_ring_light_v3_layout()

        self.assertEqual(layout["surface_profile"], "spherical_concave_dish")
        self.assertEqual(layout["outer_diameter_mm"], 80.0)
        self.assertEqual(layout["center_hole_diameter_mm"], 40.0)
        self.assertAlmostEqual(layout["reference_total_depth_mm"], 18.0025, places=4)
        self.assertEqual(layout["row_counts"], list(range(21, 30)))
        self.assertEqual(layout["total_led_count"], 225)
        self.assertEqual(layout["led_diameter_mm"], 2.6)
        self.assertEqual(layout["native_approximation"]["inner_row_marker_style"], "raised_boss")
        self.assertEqual(layout["native_approximation"]["inner_row_marker_height_mm"], 0.3)
        self.assertEqual(layout["rows"][0]["angle_degrees"], 30.0)
        self.assertEqual(layout["rows"][-1]["angle_degrees"], 60.0)

    def test_rows_form_one_concave_sphere_and_point_inward(self):
        layout = build_ring_light_v3_layout()
        sphere_radius = layout["dish"]["sphere_radius_mm"]
        outer_z = layout["dish"]["outer_row_z_mm"]

        self.assertAlmostEqual(sphere_radius, 44.0, places=6)
        heights = [row["z_mm"] for row in layout["rows"]]
        self.assertEqual(heights, sorted(heights))
        self.assertLess(heights[0], heights[-1])
        self.assertAlmostEqual(heights[-1], outer_z, places=6)
        for row in layout["rows"]:
            theta = math.radians(row["angle_degrees"])
            self.assertAlmostEqual(row["radius_mm"], sphere_radius * math.sin(theta), places=5)
            self.assertAlmostEqual(
                row["z_mm"], outer_z + sphere_radius * (math.cos(math.radians(60.0)) - math.cos(theta)), places=5
            )
            axis = row["sample_led_axis"]
            self.assertLess(axis[0], 0.0)
            self.assertAlmostEqual(axis[2], math.cos(theta), places=6)

    def test_inner_edge_stays_inside_step_body(self):
        layout = build_ring_light_v3_layout()

        self.assertAlmostEqual(layout["dish"]["inner_edge_z_mm"], -15.691836, places=5)
        self.assertAlmostEqual(layout["dish"]["minimum_back_thickness_mm"], 0.308164, places=5)
        self.assertGreater(layout["dish"]["minimum_back_thickness_mm"], 0.3)

    def test_48_blind_cut_bands_deepen_toward_center(self):
        layout = build_ring_light_v3_layout()
        bands = build_concave_dish_bands(layout, step_count=48)

        self.assertEqual(len(bands), 48)
        self.assertAlmostEqual(bands[0]["outer_radius_mm"], layout["rows"][-1]["radius_mm"], places=6)
        self.assertAlmostEqual(bands[-1]["inner_radius_mm"], 21.13, places=6)
        depths = [band["cut_depth_mm"] for band in bands]
        self.assertEqual(depths, sorted(depths))
        self.assertGreater(depths[-1], 16.8)
        self.assertLess(depths[-1], 17.2)

    def test_all_dish_bands_keep_cardinal_ribs_continuous(self):
        layout = build_ring_light_v3_layout()
        for band in build_concave_dish_bands(layout, step_count=48):
            self.assertTrue(
                _band_crosses_mount_zone(band["inner_radius_mm"], band["outer_radius_mm"])
            )

    def test_all_led_centers_clear_step_mounting_holes_and_ribs(self):
        layout = build_ring_light_v3_layout()
        led_radius = layout["led_diameter_mm"] / 2.0
        holes = layout["mounting"]["holes"]

        for row in layout["rows"]:
            self.assertEqual(len(row["led_angles_degrees"]), row["count"])
            radius = row["radius_mm"]
            for angle_degrees in row["led_angles_degrees"]:
                phi = math.radians(angle_degrees)
                x = radius * math.cos(phi)
                y = radius * math.sin(phi)
                for hole in holes:
                    clearance = math.hypot(x - hole["x_mm"], y - hole["y_mm"])
                    self.assertGreaterEqual(clearance, led_radius + hole["radius_mm"] + 1.5)
                nearest_axis = min(
                    abs((angle_degrees - cardinal + 180.0) % 360.0 - 180.0)
                    for cardinal in (0.0, 90.0, 180.0, 270.0)
                )
                self.assertGreaterEqual(nearest_axis, 8.0)


class TestRingLightV3ServerRegistration(unittest.TestCase):
    def test_v3_tool_is_registered(self):
        tools = {tool.name for tool in mcp._tool_manager.list_tools()}
        self.assertIn("solidworks_part_create_ring_light_v3", tools)

if __name__ == "__main__":
    unittest.main()
