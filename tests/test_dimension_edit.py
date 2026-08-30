"""Dimension edit and feature deletion tests."""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.features import (
    delete_feature,
    set_dimension,
    set_dimension_angle,
)


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
        self.shown_config = None

    def ShowConfiguration(self, name):
        # 探针 2026-08-30：组合通道（激活后 which=1 设配置特定值）
        self.shown_config = name
        return False

    @property
    def ConfigurationManager(self):
        return SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name=self.shown_config or "默认")
        )

    @property
    def GetConfigurationNames(self):
        return tuple(getattr(self, "configs", ("默认",)))

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
        for bad in (0, float("nan"), float("inf")):
            self.assertEqual(
                set_dimension(sw, "D1@Sketch1", bad)["error"]["code"],
                "INVALID_PARAMETER",
            )

        model.dimension.set_result = -1  # swSetValueFailure
        result = set_dimension(sw, "D1@Sketch1", 30.0)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_negative_values_are_signed_but_nonzero(self):
        # N12：去 PositiveMM 约束 —— 偏移/对称尺寸需要负长度
        model = DimModel()
        sw = Mock()
        sw.get_active_document.return_value = model

        result = set_dimension(sw, "D1@Sketch1", -12.5)

        self.assertTrue(result["success"])
        self.assertEqual(model.dimension.set_calls, [(-0.0125, 1, "")])

    def test_set_dimension_with_configuration_activates_first(self):
        # 探针 2026-08-30：SetSystemValue3(v, 3, names) 通道返回 0 但不生效；
        # 组合通道 = ShowConfiguration(name) 后 which=1 设配置特定值
        model = DimModel()
        model.configs = ("默认", "CFG_B")
        sw = Mock()
        sw.get_active_document.return_value = model

        result = set_dimension(sw, "D1@凸台-拉伸1", 50.0, configuration="CFG_B")

        self.assertTrue(result["success"])
        self.assertEqual(model.shown_config, "CFG_B")
        self.assertEqual(model.dimension.set_calls, [(0.05, 1, "")])
        self.assertEqual(result["data"]["configuration"], "CFG_B")

        # 未知配置在激活校验时被拒
        model2 = DimModel()
        model2.configs = ("默认",)
        sw2 = Mock()
        sw2.get_active_document.return_value = model2
        self.assertFalse(
            set_dimension(sw2, "D1@S", 30.0, configuration="没有")["success"]
        )


class TestSetDimensionAngle(unittest.TestCase):
    def test_degrees_converted_to_radians(self):
        model = DimModel()
        sw = Mock()
        sw.get_active_document.return_value = model

        result = set_dimension_angle(sw, "D1@旋转1", 90.0)

        self.assertTrue(result["success"])
        self.assertEqual(len(model.dimension.set_calls), 1)
        value, which, names = model.dimension.set_calls[0]
        self.assertAlmostEqual(value, math.pi / 2, places=12)
        self.assertEqual((which, names), (1, ""))
        self.assertEqual(model.rebuild_count, 1)
        self.assertEqual(result["data"]["value_deg"], 90.0)

    def test_negative_and_invalid_degrees(self):
        model = DimModel()
        sw = Mock()
        sw.get_active_document.return_value = model

        ok = set_dimension_angle(sw, "D1@旋转1", -45.0)
        self.assertTrue(ok["success"])
        self.assertAlmostEqual(
            model.dimension.set_calls[-1][0], -math.pi / 4, places=12
        )

        for bad in (float("nan"), float("inf")):
            self.assertEqual(
                set_dimension_angle(sw, "D1@旋转1", bad)["error"]["code"],
                "INVALID_PARAMETER",
            )
        self.assertEqual(
            set_dimension_angle(sw, "", 90.0)["error"]["code"],
            "INVALID_PARAMETER",
        )

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
