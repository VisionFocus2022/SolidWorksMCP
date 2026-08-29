"""Face-based fillet/chamfer decoration tests (walk+Select2 selection)."""

from __future__ import annotations

import math
import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.decorations import (
    apply_chamfer,
    apply_fillet,
    apply_shell,
)


class Face:
    def __init__(self, name, next_face=None):
        self.name = name
        self._next = next_face
        self.select_calls = []

    @property
    def GetNextFace(self):
        return self._next

    def Select2(self, append, mark):
        self.select_calls.append((append, mark))
        return True


class Body:
    def __init__(self, first_face):
        self._first = first_face

    @property
    def GetFirstFace(self):
        return self._first


class Feature:
    def __init__(self, name, next_feature=None):
        self.Name = name
        self._next = next_feature

    @property
    def GetNextFeature(self):
        return self._next


class DecorationModel:
    """Faces named via GetEntityName; feature tree grows via FeatureFillet."""

    def __init__(self, faces, boss="凸台-拉伸1"):
        self._faces = faces
        self._tail = Feature(boss)
        self._head = self._tail
        self.clear_calls = 0
        self.fillet_args = None
        self.chamfer_args = None
        self.shell_args = None

    def GetBodies2(self, body_type, visible_only):
        return (Body(self._faces),)

    def GetEntityName(self, entity):
        return getattr(entity, "name", "")

    def ClearSelection2(self, all):
        self.clear_calls += 1

    def FirstFeature(self):
        return self._head

    def FeatureFillet(self, r1, propagate, ftyp, var_rad, overflow):
        self.fillet_args = (r1, propagate, ftyp, var_rad, overflow)
        self._tail._next = Feature("圆角1")
        self._tail = self._tail._next
        return None

    def FeatureChamfer(self, width, angle, flip):
        self.chamfer_args = (width, angle, flip)
        self._tail._next = Feature("倒角1")
        self._tail = self._tail._next
        return None

    def InsertFeatureShell(self, thickness, outward):
        self.shell_args = (thickness, outward)
        self._tail._next = Feature("抽壳1")
        self._tail = self._tail._next
        return None


def _model(face_names=("Face0", "Face1", "Face2")):
    faces = None
    for name in reversed(face_names):
        faces = Face(name, faces)
    return DecorationModel(faces)


class TestApplyFillet(unittest.TestCase):
    def test_selects_named_faces_and_applies_radius_in_metres(self):
        model = _model()
        sw = Mock()
        sw.get_active_document.return_value = model

        result = apply_fillet(sw, ["Face0", "Face2"], 5.0)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["feature_name"], "圆角1")
        self.assertEqual(model.fillet_args, (0.005, False, False, False, 0))
        self.assertEqual(model.clear_calls, 1)
        # T5 contract: walk faces, match names, Select2(append, mark=1).
        # Chain order is Face2 -> Face1 -> Face0; Face2 and Face0 selected.
        self.assertEqual(model._faces.select_calls, [(True, 1)])
        self.assertEqual(model._faces._next.select_calls, [])
        self.assertEqual(model._faces._next._next.select_calls, [(True, 1)])

    def test_missing_names_and_bad_radius_are_rejected(self):
        sw = Mock()
        sw.get_active_document.return_value = _model()
        self.assertEqual(
            apply_fillet(sw, ["Nope"], 5.0)["error"]["code"], "INVALID_PARAMETER"
        )
        self.assertEqual(
            apply_fillet(sw, [], 5.0)["error"]["code"], "INVALID_PARAMETER"
        )
        for bad in (0, -1, float("nan")):
            self.assertEqual(
                apply_fillet(sw, ["Face0"], bad)["error"]["code"],
                "INVALID_PARAMETER",
            )

    def test_rejected_fillet_reports_no_new_feature(self):
        model = _model()
        model.FeatureFillet = lambda *a: None  # SW rejects: no feature created
        sw = Mock()
        sw.get_active_document.return_value = model
        result = apply_fillet(sw, ["Face0"], 5.0)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_com_and_document_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(apply_fillet(sw, ["Face0"], 5.0)["success"])
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(apply_fillet(sw, ["Face0"], 5.0)["success"])


class TestApplyChamfer(unittest.TestCase):
    def test_applies_distance_and_angle_in_metres_and_radians(self):
        model = _model()
        sw = Mock()
        sw.get_active_document.return_value = model

        result = apply_chamfer(sw, ["Face1"], 2.0, angle_deg=45)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["feature_name"], "倒角1")
        self.assertEqual(model.chamfer_args, (0.002, math.pi / 4, False))

    def test_default_angle_and_validation(self):
        model = _model()
        sw = Mock()
        sw.get_active_document.return_value = model
        apply_chamfer(sw, ["Face0"], 1.0)
        self.assertEqual(model.chamfer_args[1], math.pi / 4)

        for bad_angle in (0, 90, 180):
            self.assertEqual(
                apply_chamfer(sw, ["Face0"], 1.0, angle_deg=bad_angle)["error"][
                    "code"
                ],
                "INVALID_PARAMETER",
            )
        for bad_dist in (0, -2):
            self.assertEqual(
                apply_chamfer(sw, ["Face0"], bad_dist)["error"]["code"],
                "INVALID_PARAMETER",
            )

    def test_rejected_chamfer_reports_no_new_feature(self):
        model = _model()
        model.FeatureChamfer = lambda *a: None
        sw = Mock()
        sw.get_active_document.return_value = model
        result = apply_chamfer(sw, ["Face0"], 2.0)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(apply_chamfer(sw, ["Face0"], 2.0)["success"])


class TestApplyShell(unittest.TestCase):
    def test_shells_with_removal_faces_and_thickness_in_metres(self):
        model = _model()
        sw = Mock()
        sw.get_active_document.return_value = model

        result = apply_shell(sw, ["Face1"], 2.0)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["feature_name"], "抽壳1")
        self.assertEqual(model.shell_args, (0.002, False))
        self.assertEqual(model.clear_calls, 1)

    def test_shell_validation_and_missing_faces(self):
        sw = Mock()
        sw.get_active_document.return_value = _model()
        for bad in (0, -1, float("nan")):
            self.assertEqual(
                apply_shell(sw, ["Face0"], bad)["error"]["code"],
                "INVALID_PARAMETER",
            )
        self.assertEqual(
            apply_shell(sw, [], 2.0)["error"]["code"], "INVALID_PARAMETER"
        )
        self.assertEqual(
            apply_shell(sw, ["Nope"], 2.0)["error"]["code"], "INVALID_PARAMETER"
        )

    def test_rejected_shell_and_com_errors_are_structured(self):
        model = _model()
        model.InsertFeatureShell = lambda *a: None  # no feature created
        sw = Mock()
        sw.get_active_document.return_value = model
        result = apply_shell(sw, ["Face0"], 2.0)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(apply_shell(sw, ["Face0"], 2.0)["success"])


if __name__ == "__main__":
    unittest.main()
