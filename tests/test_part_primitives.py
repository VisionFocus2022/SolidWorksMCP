"""N30 primitive tools: FakeModel contract tests (real-machine contracts
locked by tools/probe_part/probe_n30_unblock.py — polygon =
ISketchManager.CreatePolygon(8 params, all scalars) + boss extrude;
slot = CreateSketchSlot(14 params, line type/center-center) — area is
length*width + pi*(width/2)^2, the centre-line includes the end radii)."""

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

    def CreatePolygon(self, *args):
        self.calls.append(("CreatePolygon",) + args)

    def CreateSketchSlot(self, *args):
        self.calls.append(("CreateSketchSlot",) + args)


class FakeFeatureManager:
    def __init__(self):
        self.calls = []

    def FeatureExtrusion2(self, *args):
        self.calls.append(("FeatureExtrusion2",) + args)
        return SimpleNamespace(Name="凸台-拉伸1")


class FakeModel(BasePartModel):
    def __init__(self):
        super().__init__()
        self.sketch = FakeSketchManager()
        self.fm = FakeFeatureManager()


def _patched(testcase):
    patches = [
        patch(
            "solidworks_mcp.solidworks_api.part_advanced._select_plane",
            return_value=PLANE,
        ),
        patch(
            "solidworks_mcp.solidworks_api.part_advanced.latest_feature_name",
            return_value="草图1",
        ),
    ]
    for p in patches:
        p.start()
        testcase.addCleanup(p.stop)


class TestCreatePolygon(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.sw = sw_with_model(self.model)
        _patched(self)

    def test_contract_eight_scalars_in_metres(self):
        result = part.create_polygon(
            self.sw, sides=6, circumradius_mm=10.0, height_mm=10.0
        )
        self.assertTrue(result["success"], result)
        polygon = [
            c for c in self.model.sketch.calls if c[0] == "CreatePolygon"
        ]
        self.assertEqual(
            polygon,
            [("CreatePolygon", 0.0, 0.0, 0.0, 0.010, 0.0, 0.0, 6, True)],
        )
        # boss extrude by the height (Merge=True auto-combines bodies)
        extrude = self.model.fm.calls[0]
        self.assertEqual(extrude[0], "FeatureExtrusion2")
        self.assertEqual(len(extrude), 24)  # 23 params + method name
        self.assertEqual(extrude[6], 0.010)  # D1 height in metres
        self.assertTrue(extrude[18])  # Merge
        self.assertEqual(result["data"]["feature_name"], "凸台-拉伸1")

    def test_circumscribed_flag_passes_through(self):
        result = part.create_polygon(
            self.sw, sides=8, circumradius_mm=5.0, height_mm=3.0, inscribed=False
        )
        self.assertTrue(result["success"], result)
        polygon = [c for c in self.model.sketch.calls if c[0] == "CreatePolygon"]
        self.assertFalse(polygon[0][8])  # Inscribed=False

    def test_validation_rejects_bad_sides(self):
        for sides in (2, 0, -3, 61):
            result = part.create_polygon(
                self.sw, sides=sides, circumradius_mm=10.0, height_mm=10.0
            )
            self.assertFalse(result["success"], sides)
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER", sides)
            self.assertIn("sides", result["message"], sides)

    def test_rejects_non_positive_geometry(self):
        cases = [
            dict(sides=6, circumradius_mm=0, height_mm=10),
            dict(sides=6, circumradius_mm=10, height_mm=-1),
        ]
        for kwargs in cases:
            result = part.create_polygon(self.sw, **kwargs)
            self.assertFalse(result["success"], kwargs)
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER", kwargs)

    def test_only_front_plane_supported(self):
        result = part.create_polygon(
            self.sw, sides=6, circumradius_mm=10.0, height_mm=10.0, plane="top"
        )
        self.assertFalse(result["success"])
        self.assertIn("front", result["message"])


class TestCreateSlot(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.sw = sw_with_model(self.model)
        _patched(self)

    def test_contract_fourteen_params_line_type(self):
        result = part.create_slot(
            self.sw, length_mm=20.0, width_mm=6.0, height_mm=8.0
        )
        self.assertTrue(result["success"], result)
        slot = [c for c in self.model.sketch.calls if c[0] == "CreateSketchSlot"]
        # line type=0, center-center=0, width, centre line (0,-L/2)-(0,L/2),
        # third point (W/2,0) fixes the width direction, trailing pair
        self.assertEqual(
            slot,
            [
                (
                    "CreateSketchSlot", 0, 0, 0.006,
                    0.0, -0.010, 0.0,
                    0.0, 0.010, 0.0,
                    0.003, 0.0, 0.0,
                    1, False,
                )
            ],
        )
        extrude = self.model.fm.calls[0]
        self.assertEqual(extrude[6], 0.008)  # height in metres

    def test_rejects_degenerate_slot(self):
        cases = [
            dict(length_mm=6.0, width_mm=6.0, height_mm=8.0),   # must exceed width
            dict(length_mm=5.0, width_mm=6.0, height_mm=8.0),
            dict(length_mm=0.0, width_mm=6.0, height_mm=8.0),
            dict(length_mm=20.0, width_mm=0.0, height_mm=8.0),
            dict(length_mm=20.0, width_mm=6.0, height_mm=0.0),
        ]
        for kwargs in cases:
            result = part.create_slot(self.sw, **kwargs)
            self.assertFalse(result["success"], kwargs)
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER", kwargs)

    def test_extrusion_rejection_is_structured(self):
        self.model.fm.FeatureExtrusion2 = lambda *a: None
        result = part.create_slot(
            self.sw, length_mm=20.0, width_mm=6.0, height_mm=8.0
        )
        self.assertFalse(result["success"])
        self.assertIn("Extrusion", result["message"])


if __name__ == "__main__":
    unittest.main()
