"""utils.com static-wrap contract tests (N35): the single makepy wrapper
home — Mock objects and missing caches fall back, real PyIDispatch
dispatches to the generated class."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.utils.com import static_wrap, typed_or_dynamic


class FakeGenModule:
    class IModelDoc2:
        def __init__(self, raw):
            self.raw = raw


class TestStaticWrap(unittest.TestCase):
    def test_none_for_plain_python_object(self):
        self.assertIsNone(static_wrap(object(), "IModelDoc2"))

    def test_none_for_mock_with_fake_oleobj(self):
        # Mock auto-attributes _oleobj_ — it must NOT reach the generated class.
        self.assertIsNone(static_wrap(Mock(), "IModelDoc2"))

    def test_none_when_makepy_cache_missing(self):
        with patch(
            "win32com.client.gencache.GetModuleForProgID", return_value=None
        ):
            self.assertIsNone(static_wrap(Mock(), "IModelDoc2"))

    def test_wraps_when_guard_passes_via_generated_class(self):
        raw = object()  # stand-in; the guard is patched to accept it
        obj = SimpleNamespace(_oleobj_=raw)
        with patch(
            "win32com.client.gencache.GetModuleForProgID",
            return_value=FakeGenModule,
        ), patch(
            "solidworks_mcp.utils.com._is_pyidispatch", return_value=True
        ):
            wrapped = static_wrap(obj, "IModelDoc2")
        self.assertIsInstance(wrapped, FakeGenModule.IModelDoc2)
        self.assertIs(wrapped.raw, raw)

    def test_typed_or_dynamic_falls_back_to_input(self):
        sentinel = object()
        self.assertIs(typed_or_dynamic(sentinel, "IModelDoc2"), sentinel)

    def test_typed_or_dynamic_returns_wrap_when_available(self):
        holder = SimpleNamespace(_oleobj_=object())
        with patch(
            "win32com.client.gencache.GetModuleForProgID",
            return_value=FakeGenModule,
        ), patch(
            "solidworks_mcp.utils.com._is_pyidispatch", return_value=True
        ):
            wrapped = typed_or_dynamic(holder, "IModelDoc2")
        self.assertIsInstance(wrapped, FakeGenModule.IModelDoc2)


if __name__ == "__main__":
    unittest.main()
