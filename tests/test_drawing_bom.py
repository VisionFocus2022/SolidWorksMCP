"""N32 BOM table tool: FakeModel contract tests (real-machine contract
locked by tools/probe_drawing/probe_n32_bom_balloon.py — IView.
InsertBomTable5(11 params) builds the table on an assembly drawing view;
swBomType_PartsOnly=1 / TopLevelOnly=2, anchor TopLeft=1. The AutoBalloon
family is BLOCKED on this machine — see the probe header.)"""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api import drawing


class FakeView:
    def __init__(self):
        self.calls = []

    def InsertBomTable5(self, *args):
        self.calls.append(args)
        return object()  # truthy table


class FakeSelectionManager:
    def __init__(self, view):
        self._view = view

    def GetSelectedObject6(self, index, mark):
        return self._view


class FakeExtension:
    def __init__(self):
        self.selects = []

    def SelectByID2(self, name, sel_type, x, y, z, append, mark, callout, opts):
        self.selects.append((name, sel_type))
        return True


class FakeDrawingModel:
    def __init__(self):
        self.view = FakeView()
        self.sel_mgr = FakeSelectionManager(self.view)
        self.ext = FakeExtension()

    @property
    def GetType(self):
        return 3  # swDocDRAWING

    @property
    def SelectionManager(self):
        return self.sel_mgr

    @property
    def Extension(self):
        return self.ext


def _sw(model):
    sw = Mock()
    sw.get_active_document.return_value = model
    return sw


class TestInsertBomTable(unittest.TestCase):
    def setUp(self):
        self.model = FakeDrawingModel()
        self.sw = _sw(self.model)

    def test_contract_eleven_params_metres(self):
        result = drawing.insert_bom_table(
            self.sw, view_name="工程图视图1", x_mm=240.0, y_mm=20.0
        )
        self.assertTrue(result["success"], result)
        self.assertEqual(
            self.model.view.calls,
            [(False, 0.240, 0.020, 1, 1, "", "", False, 0, False, False)],
        )
        # UseAnchorPoint=False + TopLeft anchor + PartsOnly, no template
        args = self.model.view.calls[0]
        self.assertFalse(args[0])
        self.assertEqual(args[3], 1)  # anchor
        self.assertEqual(args[4], 1)  # parts only
        self.assertEqual(self.model.ext.selects, [("工程图视图1", "DRAWINGVIEW")])
        self.assertEqual(result["data"]["view"], "工程图视图1")

    def test_top_level_type_maps_to_two(self):
        result = drawing.insert_bom_table(
            self.sw, view_name="工程图视图1", bom_type="top_level"
        )
        self.assertTrue(result["success"], result)
        self.assertEqual(self.model.view.calls[0][4], 2)

    def test_rejects_bad_type_and_names(self):
        cases = [
            dict(view_name="", bom_type="parts_only"),
            dict(view_name="v", bom_type="indented"),
            dict(view_name="v", bom_type="parts_only", x_mm=float("nan")),
        ]
        for kwargs in cases:
            result = drawing.insert_bom_table(self.sw, **kwargs)
            self.assertFalse(result["success"], kwargs)
            self.assertEqual(result["error"]["code"], "INVALID_PARAMETER", kwargs)

    def test_view_selection_failure_is_structured(self):
        self.model.ext.SelectByID2 = lambda *a: False
        result = drawing.insert_bom_table(self.sw, view_name="工程图视图1")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")

    def test_table_rejection_is_structured(self):
        self.model.view.InsertBomTable5 = lambda *a: None
        result = drawing.insert_bom_table(self.sw, view_name="工程图视图1")
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_requires_drawing_document(self):
        class _PartModel(FakeDrawingModel):
            @property
            def GetType(self):
                return 1  # a part

        result = drawing.insert_bom_table(_sw(_PartModel()), view_name="v")
        self.assertFalse(result["success"])
        self.assertIn("drawing", result["message"])


if __name__ == "__main__":
    unittest.main()
