"""Feature tree operation tests."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.features import get_features, rename_feature, set_feature_suppression


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


if __name__ == "__main__":
    unittest.main()
