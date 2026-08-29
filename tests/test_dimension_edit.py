"""Dimension edit and feature deletion tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.features import delete_feature, set_dimension


class Dimension:
    def __init__(self, set_result=0):
        self.set_calls = []
        self.set_result = set_result

    def SetSystemValue3(self, value, which, names):
        self.set_calls.append((value, which, names))
        return self.set_result


class TreeFeature:
    def __init__(self, name, next_feature=None):
        self.Name = name
        self._next = next_feature

    @property
    def GetNextFeature(self):
        return self._next


class DimModel:
    """Real-machine shape: zero-arg COM members (EditRebuild3/EditDelete) are
    properties; Parameter returns the dimension object; SelectByID2 drives
    feature deletion."""

    def __init__(self, feature_names=("凸台-拉伸1", "切除-拉伸1")):
        self._names = list(feature_names)
        self.dimension = Dimension()
        self.parameter_names = []
        self.rebuild_count = 0
        self.delete_count = 0
        self.picked = True
        self.select_calls = []

    def FirstFeature(self):
        head = None
        for name in reversed(self._names):
            head = TreeFeature(name, head)
        return head

    def Parameter(self, name):
        self.parameter_names.append(name)
        return self.dimension

    @property
    def EditRebuild3(self):
        self.rebuild_count += 1
        return True

    @property
    def EditDelete(self):
        self.delete_count += 1
        if len(self._names) > 1:
            self._names.pop()
        return None

    @property
    def Extension(self):
        model = self

        class _Ext:
            def SelectByID2(self, name, type_, *args):
                model.select_calls.append((name, type_))
                return model.picked

        return _Ext()

    def ClearSelection2(self, all):
        pass


class TestSetDimension(unittest.TestCase):
    def test_sets_value_in_metres_and_rebuilds(self):
        model = DimModel()
        sw = Mock()
        sw.get_active_document.return_value = model

        result = set_dimension(sw, "D1@凸台-拉伸1", 30.0)

        self.assertTrue(result["success"])
        self.assertEqual(model.parameter_names, ["D1@凸台-拉伸1"])
        # swThisConfiguration=1; value converted mm -> metres.
        self.assertEqual(model.dimension.set_calls, [(0.03, 1, "")])
        self.assertEqual(model.rebuild_count, 1)

    def test_rejects_bad_values_and_failure_codes(self):
        model = DimModel()
        sw = Mock()
        sw.get_active_document.return_value = model
        for bad in (0, -5, float("nan")):
            self.assertEqual(
                set_dimension(sw, "D1@Sketch1", bad)["error"]["code"],
                "INVALID_PARAMETER",
            )

        model.dimension.set_result = -1  # swSetValueFailure
        result = set_dimension(sw, "D1@Sketch1", 30.0)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_handles_missing_dimension_and_com_errors(self):
        model = DimModel()
        model.Parameter = lambda name: None
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertFalse(set_dimension(sw, "D9@None", 30.0)["success"])

        sw.get_active_document.return_value = None
        self.assertFalse(set_dimension(sw, "D1@S", 30.0)["success"])
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(set_dimension(sw, "D1@S", 30.0)["success"])


class TestDeleteFeature(unittest.TestCase):
    def test_deletes_via_bodyfeature_selection(self):
        model = DimModel(("凸台-拉伸1", "切除-拉伸1"))
        sw = Mock()
        sw.get_active_document.return_value = model

        result = delete_feature(sw, "切除-拉伸1")

        self.assertTrue(result["success"])
        self.assertEqual(model.select_calls, [("切除-拉伸1", "BODYFEATURE")])
        self.assertEqual(model.delete_count, 1)
        self.assertEqual(result["data"]["deleted"], "切除-拉伸1")

    def test_missing_feature_and_rejected_selection(self):
        model = DimModel(("凸台-拉伸1",))
        sw = Mock()
        sw.get_active_document.return_value = model
        result = delete_feature(sw, "不存在")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

        model.picked = False
        result = delete_feature(sw, "凸台-拉伸1")
        self.assertFalse(result["success"])
        self.assertIn("refused", result["message"])

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(delete_feature(sw, "X")["success"])
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(delete_feature(sw, "X")["success"])


if __name__ == "__main__":
    unittest.main()
