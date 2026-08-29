"""T16: cross-engine CSG rebuild (contract v1) — dispatch, stacking
semantics, atomic rollback, and plan validation."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api import design
from solidworks_mcp.solidworks_api.design import rebuild_csg_plan


PLAN = {
    "version": 1,
    "units": "mm",
    "operations": [
        {"op": "box", "name": "base", "size": [60, 40, 20], "at": [0, 0, 0]},
        {"op": "cylinder", "name": "boss", "diameter": 20, "height": 30,
         "at": [0, 0, 20]},
        {"op": "cut_cylinder", "name": "bore", "diameter": 8, "depth": None,
         "through": True, "at": [0, 0, 0]},
        {"op": "cone", "name": "tip", "bottom_diameter": 10, "top_diameter": 4,
         "height": 12, "at": [0, 0, 50]},
    ],
}


def _ok(feature_name):
    return {"success": True, "data": {"feature_name": feature_name}}


class RebuildTestCase(unittest.TestCase):
    def setUp(self):
        self.model = Mock()
        self.model.GetType.return_value = 1  # swDocPART
        self.sw = Mock()
        self.sw.get_active_document.return_value = self.model
        # 设计器只读特征树快照/回滚——真实实现走 T10 机器，这里旁路
        snapshot = patch.object(
            design, "_snapshot_feature_names", return_value=set()
        )
        snapshot.start()
        self.addCleanup(snapshot.stop)

    def _patches(self, **overrides):
        calls = Mock()

        def _stub(recorder, feature_name):
            def _fn(*args):
                recorder(*args[1:])  # drop sw_app
                return _ok(feature_name)
            return _fn

        mapping = {
            "create_box": _stub(calls.box, "凸台-拉伸1"),
            "create_cylinder": _stub(calls.cyl, "凸台-拉伸2"),
            "create_cylinder_on_face": _stub(calls.cyl_face, "凸台-拉伸3"),
            "create_cone": _stub(calls.cone, "凸台-拉伸4"),
            "create_cone_on_face": _stub(calls.cone_face, "凸台-拉伸5"),
        }
        mapping.update(overrides)
        for name, fn in mapping.items():
            stopped = patch(
                f"solidworks_mcp.solidworks_api.part.{name}", side_effect=fn
            )
            stopped.start()
            self.addCleanup(stopped.stop)

        def _cut(sw_, d, x, y, plane, depth, through):
            calls.cut(d, x, y, plane, depth, through)
            return _ok("切除-拉伸1")

        cut = patch(
            "solidworks_mcp.solidworks_api.design.cut_round_hole",
            side_effect=_cut,
        )
        cut.start()
        self.addCleanup(cut.stop)

        def _rename(sw_, old, new):
            calls.rename(old, new)
            return _ok(new)

        rename = patch(
            "solidworks_mcp.solidworks_api.design.rename_feature",
            side_effect=_rename,
        )
        rename.start()
        self.addCleanup(rename.stop)
        return calls


class TestValidPlan(RebuildTestCase):
    def test_dispatches_in_contract_order(self):
        calls = self._patches()
        result = rebuild_csg_plan(self.sw, PLAN)
        self.assertTrue(result["success"], result)
        calls.box.assert_called_once_with(60, 40, 20)
        calls.cyl_face.assert_called_once_with(20, 30)
        calls.cut.assert_called_once_with(8, 0, 0, "top", None, True)
        calls.cone_face.assert_called_once_with(10, 4, 12)
        self.assertEqual(
            result["data"]["applied"], ["base", "boss", "bore", "tip"]
        )
        self.assertEqual(result["data"]["stack_top_mm"], 62.0)

    def test_names_are_assigned_by_rename(self):
        calls = self._patches()
        rebuild_csg_plan(self.sw, PLAN)
        renamed = {c.args[-1] for c in calls.rename.call_args_list}
        self.assertEqual(renamed, {"base", "boss", "bore", "tip"})

    def test_first_solid_op_uses_plane_primitive(self):
        calls = self._patches()
        plan = {
            "version": 1,
            "units": "mm",
            "operations": [
                {"op": "cylinder", "name": "rod", "diameter": 10, "height": 5,
                 "at": [0, 0, 0]},
            ],
        }
        result = rebuild_csg_plan(self.sw, plan)
        self.assertTrue(result["success"], result)
        calls.cyl.assert_called_once_with(10, 5)
        calls.cyl_face.assert_not_called()

    def test_no_active_part_creates_one(self):
        calls = self._patches()
        sw = Mock()
        sw.get_active_document.return_value = None
        with patch.object(
            design.part_module, "_get_or_create_part",
            return_value=(self.model, True),
        ):
            result = rebuild_csg_plan(sw, PLAN)
        self.assertTrue(result["success"], result)
        calls.box.assert_called_once()

    def test_part_creation_failure_is_structured(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        with patch.object(
            design.part_module, "_get_or_create_part",
            side_effect=RuntimeError("no template"),
        ):
            result = rebuild_csg_plan(sw, PLAN)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")
        self.assertIn("no template", result["message"])

    def test_rename_failure_keeps_actual_feature_name(self):
        calls = self._patches()
        with patch(
            "solidworks_mcp.solidworks_api.design.rename_feature",
            return_value={"success": False, "message": "rename refused"},
        ):
            result = rebuild_csg_plan(self.sw, PLAN)
        self.assertTrue(result["success"], result)
        self.assertEqual(
            result["data"]["applied"],
            ["凸台-拉伸1", "凸台-拉伸3", "切除-拉伸1", "凸台-拉伸5"],
        )
        calls.box.assert_called_once()

    def test_not_running_is_reported(self):
        from solidworks_mcp.solidworks_api.app import SolidWorksNotRunningError

        sw = Mock()
        sw.get_active_document.side_effect = SolidWorksNotRunningError("off")
        result = rebuild_csg_plan(sw, PLAN)
        self.assertFalse(result["success"])


class TestValidation(RebuildTestCase):
    def _assert_invalid(self, plan, fragment):
        result = rebuild_csg_plan(self.sw, plan)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")
        self.assertIn(fragment, result["message"])

    def test_rejects_bad_version_units_and_shape(self):
        self._assert_invalid({"version": 2, "units": "mm", "operations": []}, "version")
        self._assert_invalid({"version": 1, "units": "inch", "operations": []}, "units")
        self._assert_invalid({"version": 1, "units": "mm", "operations": []}, "operations")
        self._assert_invalid("not-a-dict", "dict")

    def test_rejects_unknown_op_and_missing_fields(self):
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "sphere", "name": "s", "at": [0, 0, 0]}]},
            "sphere",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "box", "name": "b", "at": [0, 0, 0]}]},
            "size",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "cylinder", "name": "c", "diameter": 5,
                             "height": 2, "at": "bad"}]},
            "at",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm", "operations": ["not-a-dict"]},
            "dict",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "box", "name": "", "size": [1, 1, 1],
                             "at": [0, 0, 0]}]},
            "name",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "cone", "name": "k", "bottom_diameter": 3,
                             "height": 2, "at": [0, 0, 0]}]},
            "top_diameter",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "cut_cylinder", "name": "h", "diameter": 4,
                             "depth": -1, "through": False, "at": [0, 0, 0]}]},
            "depth",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "cut_cylinder", "name": "h", "diameter": 4,
                             "at": [0, 0, 0]}]},
            "through",
        )
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [{"op": "cylinder", "name": "c", "diameter": 5,
                             "height": 2, "at": [0, 0]}]},
            "three numbers",
        )

    def test_rejects_duplicate_and_empty_names(self):
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [
                 {"op": "box", "name": "a", "size": [1, 1, 1], "at": [0, 0, 0]},
                 {"op": "cylinder", "name": "a", "diameter": 1, "height": 1,
                  "at": [0, 0, 1]},
             ]},
            "unique",
        )

    def test_box_must_be_first_at_origin(self):
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [
                 {"op": "cylinder", "name": "c", "diameter": 5, "height": 2,
                  "at": [0, 0, 0]},
                 {"op": "box", "name": "b", "size": [1, 1, 1], "at": [0, 0, 2]},
             ]},
            "first",
        )

    def test_stacking_z_must_match_current_top(self):
        self._assert_invalid(
            {"version": 1, "units": "mm",
             "operations": [
                 {"op": "box", "name": "b", "size": [10, 10, 10], "at": [0, 0, 0]},
                 {"op": "cylinder", "name": "c", "diameter": 5, "height": 2,
                  "at": [0, 0, 7]},
             ]},
            "stack",
        )


class TestAtomicRollback(RebuildTestCase):
    def test_failure_deletes_new_features_and_reports(self):
        calls = self._patches(
            create_cylinder_on_face=lambda sw, d, h: {
                "success": False, "error": {"code": "SW_API_ERROR"},
                "message": "no face",
            }
        )
        rollback = patch.object(
            design, "_delete_new_features", return_value=(True, None)
        )
        rollback.start()
        self.addCleanup(rollback.stop)
        result = rebuild_csg_plan(self.sw, PLAN)
        self.assertFalse(result["success"])
        self.assertIn("no face", result["message"])
        self.assertTrue(result["data"]["rolled_back"])
        calls.cone_face.assert_not_called()

    def test_rollback_failure_is_surfaced_as_warning(self):
        self._patches(
            create_cylinder_on_face=lambda sw, d, h: {
                "success": False, "error": {"code": "SW_API_ERROR"},
                "message": "boom",
            }
        )
        rollback = patch.object(
            design, "_delete_new_features", return_value=(False, "delete failed")
        )
        rollback.start()
        self.addCleanup(rollback.stop)
        result = rebuild_csg_plan(self.sw, PLAN)
        self.assertFalse(result["success"])
        self.assertIn("boom", result["message"])
        self.assertIn("rollback_warning", result["data"])


class TestDegenerateInput(unittest.TestCase):
    def test_bare_mocks_return_promptly(self):
        sw = Mock()
        result = rebuild_csg_plan(sw, {"version": 1, "units": "mm",
                                       "operations": [
                                           {"op": "box", "name": "b",
                                            "size": [1, 1, 1],
                                            "at": [0, 0, 0]}]})
        # 裸 Mock part 函数返回 Mock（无 success 键）→ 结构化失败不挂
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)


if __name__ == "__main__":
    unittest.main()


# --- 堆叠原语直测（实机形态 fake：GetBox 6 元组属性 + Select2） ---

import math
from types import SimpleNamespace

from solidworks_mcp.solidworks_api import part as part_api


class FakeFace:
    def __init__(self, box):
        self._box = box
        self.selected = False
        self.next_face = None

    @property
    def GetBox(self):
        return self._box

    @property
    def GetNextFace(self):
        return self.next_face

    def Select2(self, append, mark):
        self.selected = True
        return True


class FakeBody:
    def __init__(self, faces):
        self._faces = faces

    @property
    def GetFirstFace(self):
        return self._faces[0] if self._faces else None


class FakeSketchManager:
    def __init__(self):
        self.calls = []

    def InsertSketch(self, _update):
        self.calls.append("sketch")

    def CreateCircleByRadius(self, x, y, z, r):
        self.calls.append(("circle", round(r, 5)))


class FakeStackModel:
    def __init__(self, faces):
        self._body = FakeBody(faces) if faces is not None else None
        self.sketch_manager = FakeSketchManager()
        self.type = 1

    @property
    def GetType(self):
        return self.type

    def GetBodies2(self, kind, visible):
        return [self._body] if self._body is not None else None

    @property
    def SketchManager(self):
        return self.sketch_manager


class TestStackedPrimitives(unittest.TestCase):
    def setUp(self):
        self.faces = [
            FakeFace((-0.03, -0.02, 0.0, -0.03, 0.02, 0.02)),   # 侧面
            FakeFace((-0.03, -0.02, 0.02, 0.03, 0.02, 0.02)),   # 顶面 z=20mm
        ]
        self.faces[0].next_face = self.faces[1]
        self.model = FakeStackModel(self.faces)
        self.sw = Mock()
        self.sw.get_active_document.return_value = self.model

    def test_cylinder_on_face_selects_top_and_extrudes(self):
        with patch(
            "solidworks_mcp.solidworks_api.part.extrude_boss",
            return_value=SimpleNamespace(Name="凸台-拉伸2"),
        ) as boss:
            result = part_api.create_cylinder_on_face(self.sw, 20.0, 30.0)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["data"]["feature_name"], "凸台-拉伸2")
        self.assertTrue(self.faces[1].selected)   # 顶面被选中
        self.assertFalse(self.faces[0].selected)
        self.assertEqual(
            self.model.sketch_manager.calls,
            ["sketch", ("circle", 0.01), "sketch"],
        )
        boss.assert_called_once_with(self.model, 0.03)

    def test_cone_on_face_passes_draft_parameters(self):
        with patch(
            "solidworks_mcp.solidworks_api.part.extrude_boss_draft",
            return_value=SimpleNamespace(Name="凸台-拉伸3"),
        ) as boss:
            result = part_api.create_cone_on_face(self.sw, 10.0, 4.0, 12.0)
        self.assertTrue(result["success"], result)
        height_m, draft_check, outward, angle = boss.call_args[0][1:]
        self.assertEqual(height_m, 0.012)
        self.assertTrue(draft_check)
        self.assertFalse(outward)  # top < bottom
        self.assertAlmostEqual(angle, math.atan2(3.0, 12.0))

    def test_no_body_is_a_structured_error(self):
        empty = FakeStackModel(None)
        sw = Mock()
        sw.get_active_document.return_value = empty
        result = part_api.create_cylinder_on_face(sw, 20.0, 30.0)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")
        self.assertIn("No top face", result["message"])

    def test_non_part_document_is_rejected(self):
        model = FakeStackModel(self.faces)
        model.type = 3
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertFalse(part_api.create_cone_on_face(sw, 1, 1, 1)["success"])

    def test_validation_errors_are_parameter_codes(self):
        for call in (
            lambda: part_api.create_cylinder_on_face(self.sw, 0, 10),
            lambda: part_api.create_cone_on_face(self.sw, 10, 4, -1),
        ):
            self.assertEqual(call()["error"]["code"], "INVALID_PARAMETER")

    def test_extrusion_failure_is_reported(self):
        with patch(
            "solidworks_mcp.solidworks_api.part.extrude_boss",
            return_value=None,
        ):
            result = part_api.create_cylinder_on_face(self.sw, 20.0, 30.0)
        self.assertFalse(result["success"])
        self.assertIn("Stacked extrusion", result["message"])
