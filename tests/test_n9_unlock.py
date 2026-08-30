"""N9 unlocked tools: mirror / draft / real thread / linear holes."""

from __future__ import annotations

import math
import unittest
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api import design, features


# ---- fakes (walk_features protocol + face/extension/FM shapes) ------------

class Node:
    def __init__(self, name, next_feature=None):
        self.Name = name
        self._next = next_feature

    def GetNextFeature(self):
        return self._next


class Face:
    def __init__(self, name, box_mm=(0, 0, 0, 0, 0, 0), next_face=None):
        self.entity_name = name
        self.box_mm = box_mm
        self._next = next_face
        self.select_calls = []

    @property
    def GetBox(self):
        return [v / 1000.0 for v in self.box_mm]

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


class Extension:
    def __init__(self, reject=()):
        self.calls = []
        self._reject = set(reject)

    def SelectByID2(self, name, sel_type, x, y, z, append, mark, callout, opt):
        self.calls.append((name, sel_type, append, mark))
        return (name, sel_type) not in self._reject


class SketchManager:
    def __init__(self):
        self.calls = []

    def InsertSketch(self, close):
        self.calls.append(("InsertSketch", close))

    def CreateCircleByRadius(self, x, y, z, r):
        self.calls.append(("circle", r))


class FM:
    def __init__(self, mirror=None, draft=None, sweep=None):
        self.mirror_args = None
        self.draft_args = None
        self.sweep_args = None
        self._mirror = mirror
        self._draft = draft
        self._sweep = sweep

    def InsertMirrorFeature2(self, *args):
        self.mirror_args = args
        return self._mirror

    def InsertMultiFaceDraft(self, *args):
        self.draft_args = args
        return self._draft

    def InsertCutSwept5(self, *args):
        self.sweep_args = args
        return self._sweep


class Model:
    def __init__(self, nodes=(), faces=(), fm=None, reject=()):
        self._first = nodes[0] if nodes else None
        self._faces = list(faces)
        self.fm = fm or FM()
        self.ext = Extension(reject=reject)
        self.sketch = SketchManager()
        self.helix_args = None
        self.cleared = 0

    def FirstFeature(self):
        return self._first

    def GetBodies2(self, kind, visible):
        return (Body(self._faces[0]),) if self._faces else ()

    def GetEntityName(self, entity):
        return getattr(entity, "entity_name", None)

    def ClearSelection2(self, tol):
        self.cleared += 1

    def InsertHelix(self, *args):
        self.helix_args = args
        return True

    @property
    def FeatureManager(self):
        return self.fm

    @property
    def Extension(self):
        return self.ext

    @property
    def SketchManager(self):
        return self.sketch


def _sw(model):
    sw = Mock()
    sw.get_active_document.return_value = model
    return sw


class TestMirrorFeature(unittest.TestCase):
    def test_mirrors_feature_across_plane(self):
        mirror_feat = Node("镜向1")
        model = Model(nodes=(Node("切除-拉伸1"),), fm=FM(mirror=mirror_feat))
        result = features.mirror_feature(_sw(model), "切除-拉伸1", "right")
        self.assertTrue(result["success"], result)
        self.assertEqual(model.fm.mirror_args, (False, True, True, False, 0))
        self.assertEqual(result["data"]["feature"], "镜向1")
        self.assertEqual(model.ext.calls[0],
                         ("切除-拉伸1", "BODYFEATURE", False, 1))
        self.assertEqual(model.ext.calls[1],
                         ("右视基准面", "PLANE", True, 2))

    def test_mirrors_default_plane_and_other_planes(self):
        feat = Node("镜向1")
        model = Model(nodes=(Node("Cut"),), fm=FM(mirror=feat))
        r = features.mirror_feature(_sw(model), "Cut")
        self.assertTrue(r["success"])
        self.assertEqual(model.ext.calls[1][0], "右视基准面")
        model2 = Model(nodes=(Node("Cut"),), fm=FM(mirror=feat))
        r2 = features.mirror_feature(_sw(model2), "Cut", "front")
        self.assertTrue(r2["success"])
        self.assertEqual(model2.ext.calls[1][0], "前视基准面")

    def test_mirror_validates(self):
        sw = _sw(Model())
        self.assertEqual(
            features.mirror_feature(sw, "", "right")["error"]["code"],
            "INVALID_PARAMETER")
        self.assertEqual(
            features.mirror_feature(sw, "Cut", "diag")["error"]["code"],
            "INVALID_PARAMETER")
        sw.get_active_document.return_value = None
        self.assertFalse(features.mirror_feature(sw, "Cut")["success"])

    def test_mirror_missing_feature_and_rejections(self):
        sw = _sw(Model(nodes=(Node("Origin"),)))
        self.assertIn("not found",
                      features.mirror_feature(sw, "Cut")["message"])
        model = Model(nodes=(Node("Cut"),), reject={("Cut", "BODYFEATURE")})
        self.assertEqual(
            features.mirror_feature(_sw(model), "Cut")["error"]["code"],
            "SW_API_ERROR")
        model2 = Model(nodes=(Node("Cut"),),
                       reject={("右视基准面", "PLANE")})
        self.assertEqual(
            features.mirror_feature(_sw(model2), "Cut")["error"]["code"],
            "SW_API_ERROR")
        model3 = Model(nodes=(Node("Cut"),), fm=FM(mirror=None))
        self.assertFalse(features.mirror_feature(_sw(model3), "Cut")["success"])

    def test_mirror_com_error_is_tool_error(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(features.mirror_feature(sw, "Cut")["success"])


class TestApplyDraft(unittest.TestCase):
    def _faces(self):
        draft_face = Face("Face_yplus", box_mm=(0, 20, 0, 60, 20, 20))
        neutral = Face("Face_bottom", box_mm=(0, 0, 0, 60, 40, 0))
        draft_face._next = neutral
        return draft_face, neutral

    def test_draft_selects_faces_in_order_and_calls_fm(self):
        draft_face, neutral = self._faces()
        model = Model(faces=(draft_face,), fm=FM(draft=Node("拔模1")))
        result = features.apply_draft(_sw(model), "Face_yplus",
                                      "Face_bottom", 3.0)
        self.assertTrue(result["success"], result)
        self.assertEqual(draft_face.select_calls, [(False, 1)])
        self.assertEqual(neutral.select_calls, [(True, 2)])
        self.assertEqual(model.fm.draft_args[0], math.radians(3.0))
        self.assertEqual(model.fm.draft_args[3], 0)
        self.assertEqual(result["data"]["feature"], "拔模1")

    def test_draft_validations(self):
        sw = _sw(Model())
        self.assertEqual(
            features.apply_draft(sw, "", "N", 3.0)["error"]["code"],
            "INVALID_PARAMETER")
        self.assertEqual(
            features.apply_draft(sw, "D", "", 3.0)["error"]["code"],
            "INVALID_PARAMETER")
        self.assertEqual(
            features.apply_draft(sw, "D", "N", 0.0)["error"]["code"],
            "INVALID_PARAMETER")
        sw.get_active_document.return_value = None
        self.assertFalse(features.apply_draft(sw, "D", "N", 3.0)["success"])

    def test_draft_missing_faces_and_rejection(self):
        draft_face, neutral = self._faces()
        model = Model(faces=(draft_face,))
        self.assertIn("not found",
                      features.apply_draft(_sw(model), "Face_yplus",
                                           "Face_missing", 3.0)["message"])
        model2 = Model(faces=(draft_face,), fm=FM(draft=None))
        self.assertFalse(
            features.apply_draft(_sw(model2), "Face_yplus",
                                 "Face_bottom", 3.0)["success"])

    def test_draft_com_error_is_tool_error(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(features.apply_draft(sw, "D", "N", 3.0)["success"])


class TestCutRealThread(unittest.TestCase):
    def _model(self, sweep=None):
        top = Face("Face_top", box_mm=(-10, -10, 50, 10, 10, 50))
        helix_node = Node("螺旋线/涡状线1")
        nodes = (Node("凸台-拉伸1", helix_node), helix_node)
        return Model(nodes=nodes, faces=(top,),
                     fm=FM(sweep=sweep or Node("切除-扫描1")))

    def test_cuts_helix_sweep_thread(self):
        model = self._model()
        result = features.cut_real_thread(_sw(model), 20.0, 2.5, 20.0)
        self.assertTrue(result["success"], result)
        self.assertEqual(model.sketch.calls,
                         [("InsertSketch", True), ("circle", 0.01),
                          ("InsertSketch", True)])
        self.assertAlmostEqual(model.helix_args[6], 0.0025)  # pitch metres
        self.assertAlmostEqual(model.helix_args[7], 8.0)     # 20mm / 2.5mm
        self.assertIn(("螺旋线/涡状线1", "REFERENCECURVES", False, 4),
                      model.ext.calls)
        sweep = model.fm.sweep_args
        self.assertFalse(sweep[1])   # Alignment=False (N9 probe key)
        self.assertTrue(sweep[19])   # CircularProfile (20th of 22 args)
        self.assertAlmostEqual(sweep[20], 0.003)  # profile dia metres
        self.assertEqual(sweep[21], 0)  # Direction
        self.assertEqual(result["data"]["feature"], "切除-扫描1")

    def test_thread_validations(self):
        sw = _sw(Model())
        self.assertEqual(
            features.cut_real_thread(sw, 0, 2.5, 20)["error"]["code"],
            "INVALID_PARAMETER")
        self.assertEqual(
            features.cut_real_thread(sw, 20, 0, 20)["error"]["code"],
            "INVALID_PARAMETER")
        self.assertEqual(
            features.cut_real_thread(sw, 20, 2.5, 0)["error"]["code"],
            "INVALID_PARAMETER")
        sw.get_active_document.return_value = None
        self.assertFalse(features.cut_real_thread(sw, 20, 2.5, 20)["success"])

    def test_thread_without_top_face_or_helix(self):
        model = Model(nodes=(Node("凸台-拉伸1"),))
        r = features.cut_real_thread(_sw(model), 20, 2.5, 20)
        self.assertFalse(r["success"])  # no top face
        top = Face("Face_top", box_mm=(0, 0, 50, 1, 1, 50))
        model2 = Model(nodes=(Node("凸台-拉伸1"),), faces=(top,),
                       fm=FM(sweep=Node("x")))
        r2 = features.cut_real_thread(_sw(model2), 20, 2.5, 20)
        self.assertFalse(r2["success"])  # no helix feature in tree

    def test_thread_helix_select_failure(self):
        model = self._model()
        model.ext._reject.add(("螺旋线/涡状线1", "REFERENCECURVES"))
        r = features.cut_real_thread(_sw(model), 20, 2.5, 20)
        self.assertEqual(r["error"]["code"], "SW_API_ERROR")

    def test_thread_com_error_is_tool_error(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(features.cut_real_thread(sw, 20, 2.5, 20)["success"])


class TestLinearHoles(unittest.TestCase):
    def test_loops_cut_round_hole_along_x(self):
        sw = Mock()
        calls = []

        def fake_cut(sw_app, dia, x, y, plane, depth, through_all):
            calls.append((dia, x, y, plane, depth, through_all))
            return {"success": True}

        with patch.object(design, "cut_round_hole", side_effect=fake_cut):
            r = design.create_linear_holes(sw, 8.0, 10.0, 0.0, "top",
                                           3, 8.0, "x")
        self.assertTrue(r["success"], r)
        self.assertEqual(len(calls), 3)
        self.assertEqual([c[1] for c in calls], [10.0, 18.0, 26.0])
        self.assertFalse(r["data"]["native"])

    def test_loops_along_y_and_stops_on_failure(self):
        sw = Mock()
        calls = []

        def fake_cut(sw_app, dia, x, y, plane, depth, through_all):
            calls.append(y)
            return {"success": len(calls) < 2}

        with patch.object(design, "cut_round_hole", side_effect=fake_cut):
            r = design.create_linear_holes(sw, 8.0, 0.0, 5.0, "top",
                                           3, 6.0, "y")
        self.assertFalse(r["success"])
        self.assertEqual(calls, [5.0, 11.0])

    def test_validations(self):
        sw = Mock()
        self.assertEqual(
            design.create_linear_holes(sw, 8, 0, 0, "top", 0, 8)["error"][
                "code"], "INVALID_PARAMETER")
        self.assertEqual(
            design.create_linear_holes(sw, 8, 0, 0, "top", 3, 8, "z")[
                "error"]["code"], "INVALID_PARAMETER")
        self.assertEqual(
            design.create_linear_holes(sw, 8, 0, 0, "top", 3, 0)["error"][
                "code"], "INVALID_PARAMETER")

    def test_com_error_is_tool_error(self):
        sw = Mock()

        def boom(*a, **k):
            raise RuntimeError("COM failed")

        with patch.object(design, "cut_round_hole", side_effect=boom):
            r = design.create_linear_holes(sw, 8.0, 0, 0, "top", 2, 8.0)
        self.assertFalse(r["success"])


if __name__ == "__main__":
    unittest.main()
