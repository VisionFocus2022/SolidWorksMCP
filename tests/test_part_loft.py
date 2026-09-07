"""N28 loft/sweep tools: FakeModel contract tests (real-machine contract
locked by tools/probe_part/probe_n28_unblock.py — sweep = InsertProtrusionSwept4
with mark-4 path + Alignment=False + CircularProfile; loft = InsertRefPlane(8,
distance) + mark-1 sections + InsertProtrusionBlend2)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.part_fakes import BasePartModel, sw_with_model
from solidworks_mcp.solidworks_api import part_advanced as part

PLANE = "前视基准面"


class FakeSketchManager:
    def __init__(self):
        self.calls = []

    def InsertSketch(self, toggle):
        self.calls.append(("InsertSketch", toggle))

    def CreateArc(self, *args):
        self.calls.append(("CreateArc",) + args)

    def CreateLine(self, *args):
        self.calls.append(("CreateLine",) + args)

    def CreateCircleByRadius(self, *args):
        self.calls.append(("CreateCircleByRadius",) + args)


class FakeFeatureManager:
    def __init__(self):
        self.calls = []

    def InsertProtrusionSwept4(self, *args):
        self.calls.append(("InsertProtrusionSwept4",) + args)
        return SimpleNamespace(Name="扫描1")

    def InsertProtrusionBlend2(self, *args):
        self.calls.append(("InsertProtrusionBlend2",) + args)
        return SimpleNamespace(Name="放样1")

    def InsertRefPlane(self, *args):
        self.calls.append(("InsertRefPlane",) + args)
        return SimpleNamespace(Name="基准面1")


class FakeModel(BasePartModel):
    def __init__(self):
        super().__init__()
        self.sketch = FakeSketchManager()
        self.fm = FakeFeatureManager()

    def InsertProtrusionBlend2(self, *args):
        # Blend boss lives on IModelDoc2 (not the feature manager).
        return self.fm.InsertProtrusionBlend2(*args)


def _names(*names):
    """side_effect sequence for latest_feature_name."""
    return list(names)


class TestCreateSweptArc(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.sw = sw_with_model(self.model)
        patches = [
            patch(
                "solidworks_mcp.solidworks_api.part_advanced._select_plane",
                return_value=PLANE,
            ),
            patch(
                "solidworks_mcp.solidworks_api.part_advanced.latest_feature_name",
                side_effect=_names("草图1"),
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _swept_calls(self):
        return [c for c in self.model.fm.calls if c[0] == "InsertProtrusionSwept4"]

    def test_arc_contract_metre_and_marks(self):
        result = part.create_swept(
            self.sw,
            diameter_mm=20.0,
            path_type="arc",
            radius_mm=20.0,
            angle_deg=90.0,
        )
        self.assertTrue(result["success"], result)
        swept = self._swept_calls()
        self.assertEqual(len(swept), 1)
        args = swept[0][1:]
        self.assertEqual(len(args), 20)  # InsertProtrusionSwept4 = 20 params
        self.assertFalse(args[1])        # Alignment=False (unlock, N28 probe)
        self.assertTrue(args[12])         # Merge
        self.assertTrue(args[17])         # CircularProfile=True
        self.assertEqual(args[18], 0.020)  # diameter 20mm → metres
        self.assertTrue(args[19])          # Direction
        self.assertEqual(result["data"]["feature_name"], "扫描1")
        # Path sketch selected as SKETCH with mark=4 (probe contract)
        sketch_selects = [s for s in self.model.ext.selects if s[1] == "SKETCH"]
        self.assertEqual(sketch_selects, [("草图1", "SKETCH", False, 4)])
        # Arc geometry: centre origin, start (r,0), end on +90°, metres
        arc = [c for c in self.model.sketch.calls if c[0] == "CreateArc"][0]
        self.assertEqual(arc[1:4], (0.0, 0.0, 0.0))
        self.assertAlmostEqual(arc[4], 0.020)
        self.assertAlmostEqual(arc[7], 0.0, places=9)   # end x = r·cos90°
        self.assertAlmostEqual(arc[8], 0.020)            # end y = r·sin90°
        self.assertEqual(arc[10], 1)                     # counter-clockwise

    def test_line_path_uses_create_line(self):
        result = part.create_swept(
            self.sw,
            diameter_mm=10.0,
            path_type="line",
            length_mm=30.0,
        )
        self.assertTrue(result["success"], result)
        line = [c for c in self.model.sketch.calls if c[0] == "CreateLine"]
        self.assertEqual(len(line), 1)
        self.assertEqual(line[0][1:], (0.0, 0.0, 0.0, 0.030, 0.0, 0.0))

    def test_validation_rejects_bad_paths(self):
        cases = [
            (dict(diameter_mm=0, path_type="line", length_mm=30), "diameter"),
            (dict(diameter_mm=10, path_type="helix"), "path_type"),
            (dict(diameter_mm=10, path_type="arc"), "arc path needs radius"),
            (dict(diameter_mm=10, path_type="arc", radius_mm=20, angle_deg=0), "angle"),
            (dict(diameter_mm=10, path_type="line"), "line path needs length"),
        ]
        for kwargs, hint in cases:
            result = part.create_swept(self.sw, **kwargs)
            self.assertFalse(result["success"], kwargs)
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER", kwargs)
            self.assertIn(hint, result["message"], kwargs)

    def test_feature_rejection_is_structured(self):
        self.model.fm.InsertProtrusionSwept4 = lambda *a: None
        result = part.create_swept(
            self.sw, diameter_mm=10, path_type="line", length_mm=30
        )
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_sketch_selection_failure_is_structured(self):
        self.model.ext.SelectByID2 = lambda *a: False
        result = part.create_swept(
            self.sw, diameter_mm=10, path_type="line", length_mm=30
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")


class TestCreateLoft(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.sw = sw_with_model(self.model)
        patches = [
            patch(
                "solidworks_mcp.solidworks_api.part_advanced._select_plane",
                return_value=PLANE,
            ),
            patch(
                "solidworks_mcp.solidworks_api.part_advanced.latest_feature_name",
                side_effect=_names("草图1", "基准面1", "草图2", "草图2", "放样1"),
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _loft_calls(self, name):
        return [c for c in self.model.fm.calls if c[0] == name]

    def test_two_section_loft_contract(self):
        result = part.create_loft(
            self.sw,
            profile_diameters_mm=[20.0, 30.0],
            section_spacing_mm=30.0,
        )
        self.assertTrue(result["success"], result)
        # One offset ref-plane: Distance constraint 8, 30mm → metres
        refplanes = self._loft_calls("InsertRefPlane")
        self.assertEqual(refplanes, [("InsertRefPlane", 8, 0.030, 0, 0, 0, 0)])
        # Blend: closed/keep-tangency/force-non-rational all False (probe)
        blends = self._loft_calls("InsertProtrusionBlend2")
        self.assertEqual(blends, [("InsertProtrusionBlend2", False, False, False)])
        self.assertEqual(result["data"]["feature_name"], "放样1")
        # Circles: radii in metres, first on the base plane
        circles = [
            c for c in self.model.sketch.calls if c[0] == "CreateCircleByRadius"
        ]
        self.assertEqual([c[4] for c in circles], [0.010, 0.015])
        # Sections selected as SKETCH mark=1, accumulating (first not append)
        sketch_selects = [s for s in self.model.ext.selects if s[1] == "SKETCH"]
        self.assertEqual(
            sketch_selects,
            [("草图1", "SKETCH", False, 1), ("草图2", "SKETCH", True, 1)],
        )

    def test_three_sections_two_refplanes(self):
        with patch(
            "solidworks_mcp.solidworks_api.part_advanced.latest_feature_name",
            side_effect=_names(
                "草图1", "基准面1", "草图2", "基准面2", "草图3", "草图3", "放样1"
            ),
        ):
            result = part.create_loft(
                self.sw,
                profile_diameters_mm=[20.0, 30.0, 20.0],
                section_spacing_mm=25.0,
            )
        self.assertTrue(result["success"], result)
        refplanes = self._loft_calls("InsertRefPlane")
        self.assertEqual(
            [c[2] for c in refplanes], [0.025, 0.050]  # 1× and 2× spacing
        )

    def test_rejects_fewer_than_two_sections(self):
        result = part.create_loft(
            self.sw, profile_diameters_mm=[20.0], section_spacing_mm=30.0
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")
        self.assertIn("2", result["message"])

    def test_rejects_bad_spacing_and_diameters(self):
        cases = [
            ([20.0, 0.0], 30.0),
            ([20.0, 30.0], 0.0),
            ([20.0, 30.0], -5.0),
        ]
        for diameters, spacing in cases:
            result = part.create_loft(
                self.sw,
                profile_diameters_mm=diameters,
                section_spacing_mm=spacing,
            )
            self.assertFalse(result["success"], (diameters, spacing))
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    def test_feature_rejection_is_structured(self):
        # Blend2 returns None even on success; rejection shows as an
        # unchanged tree (before == after).
        with patch(
            "solidworks_mcp.solidworks_api.part_advanced.latest_feature_name",
            side_effect=_names("草图1", "基准面1", "草图2", "草图2", "草图2"),
        ):
            result = part.create_loft(
                self.sw, profile_diameters_mm=[20.0, 30.0], section_spacing_mm=30.0
            )
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])


if __name__ == "__main__":
    unittest.main()
