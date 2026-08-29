"""Unit tests for solidworks_api.geometry feature-tree helpers.

Guards the MAX_FEATURE_WALK ceiling introduced after an unbounded
GetNextFeature walk over a Mock chain ballooned a test process to
34.86 GB of committed memory.
"""

import unittest
from unittest.mock import MagicMock

from solidworks_mcp.solidworks_api.geometry import (
    MAX_FEATURE_WALK,
    latest_feature_name,
)


class _FakeFeature:
    """Minimal feature double exposing Name and GetNextFeature."""

    def __init__(self, name, next_feat=None):
        self.Name = name
        self._next = next_feat

    def GetNextFeature(self):
        return self._next


class TestLatestFeatureName(unittest.TestCase):
    def _model_with_chain(self, names):
        head = None
        for name in reversed(names):
            head = _FakeFeature(name, head)
        model = MagicMock()
        model.FirstFeature.return_value = head
        return model

    def test_walks_full_finite_chain(self):
        model = self._model_with_chain(["Boss", "Cut", "Fillet"])
        self.assertEqual(latest_feature_name(model), "Fillet")

    def test_ceiling_stops_walk_early(self):
        # The runaway guard must break at max_features instead of
        # following a degenerate (here: overlong) chain forever.
        model = self._model_with_chain([f"F{i}" for i in range(20)])
        self.assertEqual(latest_feature_name(model, max_features=5), "F4")

    def test_empty_tree_returns_none(self):
        model = MagicMock()
        model.FirstFeature.return_value = None
        self.assertIsNone(latest_feature_name(model))

    def test_default_ceiling_is_bounded(self):
        self.assertGreater(MAX_FEATURE_WALK, 0)
        self.assertLess(MAX_FEATURE_WALK, 100_000)


if __name__ == "__main__":
    unittest.main()
