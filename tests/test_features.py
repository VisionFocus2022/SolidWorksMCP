"""Feature tree operation tests."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.features import (
    get_feature_details,
    get_features,
    rename_feature,
    set_feature_suppression,
)


class Feature:
    def __init__(self, name, next_feature=None, suppression_result=True):
        self.Name = name
        self._next = next_feature
        self.suppression_result = suppression_result

    def GetNextFeature(self):
        return self._next

    def SetSuppression2(self, state, config_option, names):
        self.suppression_args = (state, config_option, names)
        return self.suppression_result


class Model:
    def __init__(self, first=None):
        self.first = first

    def FirstFeature(self):
        return self.first


class TestFeatureOperations(unittest.TestCase):
    def test_get_features_and_rename(self):
        second = Feature("Boss")
        first = Feature("Origin", second)
        sw = Mock()
        sw.get_active_document.return_value = Model(first)
        listed = get_features(sw)
        self.assertEqual(listed["data"]["features"], ["Origin", "Boss"])
        renamed = rename_feature(sw, "Boss", "Body")
        self.assertTrue(renamed["success"])
        self.assertEqual(second.Name, "Body")

    def test_rename_validates_and_handles_missing_document_or_feature(self):
        sw = Mock()
        self.assertEqual(rename_feature(sw, "", "New")["error"]["code"], "INVALID_PARAMETER")
        same = rename_feature(sw, "Same", "Same")
        self.assertTrue(same["success"])
        sw.get_active_document.return_value = None
        self.assertFalse(rename_feature(sw, "Old", "New")["success"])
        sw.get_active_document.return_value = Model()
        self.assertIn("not found", rename_feature(sw, "Old", "New")["message"])

    def test_suppress_and_unsuppress(self):
        feature = Feature("Boss")
        sw = Mock()
        sw.get_active_document.return_value = Model(feature)
        self.assertTrue(set_feature_suppression(sw, "Boss", True)["success"])
        self.assertEqual(feature.suppression_args[0], 0)
        self.assertTrue(set_feature_suppression(sw, "Boss", False)["success"])
        self.assertEqual(feature.suppression_args[0], 1)

    def test_suppression_rejection_and_no_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(set_feature_suppression(sw, "Boss", True)["success"])
        feature = Feature("Boss", suppression_result=False)
        sw.get_active_document.return_value = Model(feature)
        result = set_feature_suppression(sw, "Boss", True)
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")

    def test_com_errors_become_tool_errors(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(get_features(sw)["success"])
        self.assertFalse(rename_feature(sw, "A", "B")["success"])
        self.assertFalse(set_feature_suppression(sw, "A", True)["success"])


class Dimension:
    def __init__(self, full_name, value_m):
        self.FullName = full_name
        self._value = value_m

    def GetSystemValue3(self, option, names):
        # Real-machine shape (dynamic dispatch): the bare system value.
        return self._value


class TypedDimension(Dimension):
    def GetSystemValue3(self, option, names):
        # Makepy-wrapper shape: (values_array, retval).
        return (self._value,), 0


class DisplayDimension:
    def __init__(self, dim, next_disp=None):
        self._dim = dim
        self._next = next_disp

    def GetDimension2(self, index):
        return self._dim


class DetailFeature(Feature):
    """Real-machine shape: makepy wrappers expose zero-arg COM members as properties."""

    def __init__(self, name, next_feature=None, type_name="Extrusion", disp_dims=None):
        super().__init__(name, next_feature)
        self._type_name = type_name
        self._first_disp = disp_dims

    @property
    def GetTypeName2(self):
        return self._type_name

    @property
    def IsSuppressed(self):
        return False

    @property
    def GetFirstDisplayDimension(self):
        return self._first_disp

    def GetNextDisplayDimension(self, disp):
        return disp._next


class TestFeatureDetails(unittest.TestCase):
    def test_details_include_type_and_dimensions_in_mm(self):
        d1 = DisplayDimension(Dimension("D1@Sketch1", 0.008))
        d2 = DisplayDimension(Dimension("D2@Boss-Extrude1", 0.02), d1)
        feat = DetailFeature("Boss-Extrude1", disp_dims=d2)
        sw = Mock()
        sw.get_active_document.return_value = Model(feat)
        result = get_feature_details(sw)
        self.assertTrue(result["success"])
        entry = result["data"]["features"][0]
        self.assertEqual(entry["name"], "Boss-Extrude1")
        self.assertEqual(entry["type_name"], "Extrusion")
        self.assertFalse(entry["suppressed"])
        self.assertEqual(entry["dimensions"][0]["full_name"], "D2@Boss-Extrude1")
        self.assertEqual(entry["dimensions"][0]["value_mm"], 20.0)
        self.assertEqual(entry["dimensions"][1]["value_mm"], 8.0)

    def test_single_feature_filter_and_not_found(self):
        feat = DetailFeature("Boss-Extrude1")
        other = DetailFeature("Other")
        feat._next = other
        sw = Mock()
        sw.get_active_document.return_value = Model(feat)
        result = get_feature_details(sw, feature_name="Other")
        self.assertEqual(result["data"]["count"], 1)
        self.assertEqual(result["data"]["features"][0]["name"], "Other")
        missing = get_feature_details(sw, feature_name="Nope")
        self.assertIn("not found", missing["message"])

    def test_typed_wrapper_dimension_shape_is_normalized(self):
        d1 = DisplayDimension(TypedDimension("D1@Sketch1", 0.008))
        feat = DetailFeature("Boss-Extrude1", disp_dims=d1)
        sw = Mock()
        sw.get_active_document.return_value = Model(feat)
        result = get_feature_details(sw)
        self.assertEqual(result["data"]["features"][0]["dimensions"][0]["value_mm"], 8.0)

    def test_details_handle_com_error_and_no_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(get_feature_details(sw)["success"])
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(get_feature_details(sw)["success"])


if __name__ == "__main__":
    unittest.main()
