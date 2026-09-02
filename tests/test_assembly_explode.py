"""N33 explode tool: FakeModel contract tests (real-machine contract
locked by tools/probe_assembly/probe_n33_explode.py — typed IAssemblyDoc.
AutoExplode() is zero-arg (property semantics on dynamic), builds an
automatic exploded view; GetExplodedViewCount/Names read it back;
ShowExploded(True) switches the display state)."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api import assembly


class FakeAsmDoc:
    def __init__(self):
        self.show_calls = []

    @property
    def GetType(self):
        return 2  # swDocASSEMBLY

    # Zero-arg member surfaces as a property on dynamic dispatch (probe).
    @property
    def AutoExplode(self):
        return True

    def GetExplodedViewCount(self):
        return 1

    def GetExplodedViewNames(self):
        return ("爆炸视图1",)

    def ShowExploded(self, show):
        self.show_calls.append(show)
        return True


def _sw(model):
    sw = Mock()
    sw.get_active_document.return_value = model
    return sw


class TestExplode(unittest.TestCase):
    def setUp(self):
        self.model = FakeAsmDoc()
        self.sw = _sw(self.model)

    def test_contract_auto_explode_and_show(self):
        result = assembly.explode(self.sw)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["data"]["explode_views"], ["爆炸视图1"])
        self.assertEqual(result["data"]["count"], 1)
        # the display switches to the exploded state
        self.assertEqual(self.model.show_calls, [True])

    def test_names_normalization(self):
        self.model.GetExplodedViewNames = lambda: "爆炸视图1"  # bare string
        result = assembly.explode(self.sw)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["data"]["explode_views"], ["爆炸视图1"])

    def test_rejection_is_structured(self):
        # AutoExplode returns False → rejected
        type(self.model).AutoExplode = property(lambda self: False)
        try:
            result = assembly.explode(self.sw)
        finally:
            type(self.model).AutoExplode = property(lambda self: True)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_requires_assembly_document(self):
        class _Part(FakeAsmDoc):
            @property
            def GetType(self):
                return 1

        result = assembly.explode(_sw(_Part()))
        self.assertFalse(result["success"])
        self.assertIn("assembly", result["message"])

    def test_no_views_after_success_is_reported(self):
        self.model.GetExplodedViewCount = lambda: 0
        self.model.GetExplodedViewNames = lambda: ()
        result = assembly.explode(self.sw)
        self.assertFalse(result["success"])
        self.assertIn("no exploded view", result["message"])


if __name__ == "__main__":
    unittest.main()
