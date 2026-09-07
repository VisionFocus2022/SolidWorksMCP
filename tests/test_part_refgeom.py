"""N29 ref-geometry / dome / rib tools: FakeModel contract tests.

Real-machine contracts locked by tools/probe_part/probe_n29_unblock.py:
ref axis = face walk + Select2(False, 0) + zero-arg InsertAxis (fires via
property-get semantics on dynamic dispatch); dome = named-face Select2
mark=1 (mark=0 is silently ignored) + typed InsertDome(3 params); rib =
math substitute for the BLOCKED InsertRib family — offset ref-plane +
rectangle sketch + boss extrude (ADR-0011)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api import decorations
from solidworks_mcp.solidworks_api import part_advanced, part_refgeom as part

FRONT = "前视基准面"
TOP = "上视基准面"


class FakeSketchManager:
    def __init__(self):
        self.calls = []

    def InsertSketch(self, toggle):
        self.calls.append(("InsertSketch", toggle))

    def CreateCornerRectangle(self, *args):
        self.calls.append(("CreateCornerRectangle",) + args)


class FakeFeatureManager:
    def __init__(self):
        self.calls = []

    def InsertRefPlane(self, *args):
        self.calls.append(("InsertRefPlane",) + args)
        return SimpleNamespace(Name="基准面1")


class FakeExtension:
    def __init__(self):
        self.selects = []

    def SelectByID2(self, name, sel_type, x, y, z, append, mark, callout, opts):
        self.selects.append((name, sel_type, append, mark))
        return True


class FakeSurface:
    def IsCylinder(self):
        return True


class FakeFace:
    def __init__(self, name, cylindrical=True):
        self._name = name
        self._cylindrical = cylindrical
        self.selects = []

    def GetSurface(self):
        return FakeSurface() if self._cylindrical else None

    def GetNextFace(self):
        return None

    def Select2(self, append, mark):
        self.selects.append((append, mark))
        return True


class FakeBody:
    def __init__(self, faces):
        self._faces = list(faces)

    def GetFirstFace(self):
        return self._faces[0] if self._faces else None


class FakeModel:
    def __init__(self, faces=()):
        self.sketch = FakeSketchManager()
        self.fm = FakeFeatureManager()
        self.ext = FakeExtension()
        self._faces = list(faces)
        self.insert_axis_fired = False
        self.dome_calls = []

    @property
    def GetType(self):
        return 1  # swDocPART

    @property
    def SketchManager(self):
        return self.sketch

    @property
    def FeatureManager(self):
        return self.fm

    @property
    def Extension(self):
        return self.ext

    def ClearSelection2(self, all):
        pass

    def GetBodies2(self, kind, visible):
        return [FakeBody(self._faces)]

    def GetEntityName(self, face):
        return face._name

    # Zero-arg members surface as properties on dynamic dispatch: reading
    # the attribute fires the call (N29 probe) — modelled as a property.
    @property
    def InsertAxis(self):
        self.insert_axis_fired = True
        return True

    def InsertDome(self, *args):
        self.dome_calls.append(args)
        return SimpleNamespace(Name="圆顶1")


def _sw(model):
    sw = Mock()
    sw.get_active_document.return_value = model
    return sw


def _names(*names):
    return list(names)


class TestCreateRefPlane(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.sw = _sw(self.model)
        patches = [
            patch(
                "solidworks_mcp.solidworks_api.part_refgeom._select_plane",
                return_value=FRONT,
            ),
            patch(
                "solidworks_mcp.solidworks_api.part_refgeom.latest_feature_name",
                side_effect=_names("基准面1"),
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_contract_distance_constraint_in_metres(self):
        result = part.create_ref_plane(self.sw, offset_mm=30.0)
        self.assertTrue(result["success"], result)
        # One offset plane: Distance constraint 8, 30mm → metres (loft family)
        self.assertEqual(
            self.model.fm.calls,
            [("InsertRefPlane", 8, 0.030, 0, 0, 0, 0)],
        )
        # The base plane is re-selected as the InsertRefPlane reference
        plane_selects = [s for s in self.model.ext.selects if s[1] == "PLANE"]
        self.assertEqual(plane_selects, [(FRONT, "PLANE", False, 0)])
        self.assertEqual(result["data"]["feature_name"], "基准面1")

    def test_rejects_non_positive_offset(self):
        for offset in (0.0, -5.0):
            result = part.create_ref_plane(self.sw, offset_mm=offset)
            self.assertFalse(result["success"], offset)
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    def test_only_front_plane_supported(self):
        result = part.create_ref_plane(self.sw, offset_mm=10.0, plane="top")
        self.assertFalse(result["success"])
        self.assertIn("front", result["message"])

    def test_rejection_is_structured(self):
        self.model.fm.InsertRefPlane = lambda *a: None
        result = part.create_ref_plane(self.sw, offset_mm=10.0)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])


class TestCreateRefAxis(unittest.TestCase):
    def setUp(self):
        self.face = FakeFace("Face1")
        self.model = FakeModel(faces=[self.face])
        self.sw = _sw(self.model)

    def _run(self, **overrides):
        names = _names("凸台-拉伸1", "基准轴1")
        with patch(
            "solidworks_mcp.solidworks_api.part_refgeom.latest_feature_name",
            side_effect=lambda *a, **k: names.pop(0) if names else "基准轴1",
        ):
            return part.create_ref_axis(self.sw, face_name="Face1", **overrides)

    def test_contract_face_walk_then_zero_arg_axis(self):
        result = self._run()
        self.assertTrue(result["success"], result)
        # Cylindrical face selected via Select2(False, 0) — walk, not SelectByID2
        self.assertEqual(self.face.selects, [(False, 0)])
        self.assertTrue(self.model.insert_axis_fired)
        self.assertEqual(result["data"]["feature_name"], "基准轴1")

    def test_face_not_found(self):
        result = part.create_ref_axis(self.sw, face_name="Missing")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")
        self.assertIn("not found", result["message"])

    def test_rejects_non_cylindrical_face(self):
        self.model._faces = [FakeFace("Face1", cylindrical=False)]
        result = part.create_ref_axis(self.sw, face_name="Face1")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")
        self.assertIn("cylindrical", result["message"])

    def test_rejection_is_structured(self):
        # Tree unchanged after the call → SW refused the axis
        with patch(
            "solidworks_mcp.solidworks_api.part_refgeom.latest_feature_name",
            return_value="凸台-拉伸1",
        ):
            result = part.create_ref_axis(self.sw, face_name="Face1")
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])


class TestCreateRib(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.sw = _sw(self.model)
        extrude = patch(
            "solidworks_mcp.solidworks_api.part_advanced._extrude_sketch",
            side_effect=lambda model, height: (
                self.model.extrudes.append(height),
                SimpleNamespace(Name="凸台-拉伸2"),
            )[1],
        )
        self.model.extrudes = []
        extrude.start()
        self.addCleanup(extrude.stop)

    def _patch_latest(self, *names):
        p = patch(
            "solidworks_mcp.solidworks_api.part_advanced.latest_feature_name",
            side_effect=_names(*names),
        )
        p.start()
        self.addCleanup(p.stop)

    def test_contract_offset_plane_rect_and_extrude(self):
        self._patch_latest("基准面1")
        with patch(
            "solidworks_mcp.solidworks_api.part_advanced.select_plane",
            return_value=TOP,
        ) as mock_select:
            result = part_advanced.create_rib(
                self.sw,
                length_mm=60.0,
                height_mm=10.0,
                thickness_mm=6.0,
                base_z_mm=20.0,
            )
        self.assertTrue(result["success"], result)
        # Offset sketch plane at base_z: 20mm → metres
        self.assertEqual(
            self.model.fm.calls,
            [("InsertRefPlane", 8, 0.020, 0, 0, 0, 0)],
        )
        # Plate rectangle centred on the sketch origin, metres
        rect = [
            c for c in self.model.sketch.calls if c[0] == "CreateCornerRectangle"
        ]
        self.assertEqual(len(rect), 1)
        x1, y1, _z, x2, y2 = rect[0][1:6]
        self.assertAlmostEqual(x1, -0.030)
        self.assertAlmostEqual(y1, -0.003)
        self.assertAlmostEqual(x2, 0.030)
        self.assertAlmostEqual(y2, 0.003)
        # Boss extruded by the rib height
        self.assertEqual(self.model.extrudes, [0.010])
        self.assertIn("math substitute", result["message"])  # honest contract
        mock_select.assert_called()

    def test_base_z_zero_sketches_on_top_plane_itself(self):
        self._patch_latest()
        with patch(
            "solidworks_mcp.solidworks_api.part_advanced.select_plane",
            return_value=TOP,
        ):
            result = part_advanced.create_rib(
                self.sw, length_mm=30.0, height_mm=8.0, thickness_mm=4.0
            )
        self.assertTrue(result["success"], result)
        self.assertEqual(self.model.fm.calls, [])  # no offset plane needed

    def test_validation_rejects_bad_geometry(self):
        cases = [
            dict(length_mm=0, height_mm=8, thickness_mm=4),
            dict(length_mm=30, height_mm=0, thickness_mm=4),
            dict(length_mm=30, height_mm=8, thickness_mm=0),
            dict(length_mm=30, height_mm=8, thickness_mm=4, base_z_mm=-1),
        ]
        for kwargs in cases:
            result = part_advanced.create_rib(self.sw, **kwargs)
            self.assertFalse(result["success"], kwargs)
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER", kwargs)


class TestApplyDome(unittest.TestCase):
    def setUp(self):
        self.face = FakeFace("Face1")
        self.model = FakeModel(faces=[self.face])
        self.sw = _sw(self.model)

    def test_contract_named_face_mark1_and_typed_dome(self):
        names = _names("凸台-拉伸1", "圆顶1")

        def latest(*args, **kwargs):
            return names.pop(0) if names else "圆顶1"

        with patch(
            "solidworks_mcp.solidworks_api.geometry.latest_feature_name",
            latest,
        ), patch(
            "solidworks_mcp.solidworks_api.decorations.latest_feature_name",
            latest,
        ):
            result = decorations.apply_dome(
                self.sw, face_name="Face1", height_mm=5.0
            )
        self.assertTrue(result["success"], result)
        # mark=1 is the unlock (mark=0 silently rejected, N29 probe)
        self.assertEqual(self.face.selects, [(True, 1)])
        self.assertEqual(self.model.dome_calls, [(0.005, False, False)])
        self.assertEqual(result["data"]["feature_name"], "圆顶1")

    def test_face_missing(self):
        result = decorations.apply_dome(
            self.sw, face_name="Missing", height_mm=5.0
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    def test_rejection_is_structured(self):
        with patch(
            "solidworks_mcp.solidworks_api.decorations.latest_feature_name",
            return_value="凸台-拉伸1",
        ):
            result = decorations.apply_dome(
                self.sw, face_name="Face1", height_mm=5.0
            )
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_rejects_non_positive_height(self):
        result = decorations.apply_dome(
            self.sw, face_name="Face1", height_mm=0.0
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")


if __name__ == "__main__":
    unittest.main()
