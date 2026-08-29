"""Bare-Mock / degenerate-proxy tolerance — T10 memory-explosion regression suite.

Incident (T10): walking a Mock for the bounded feature loop made mock's
call bookkeeping propagate each call up its parent chain — O(n^2) records,
gigabytes of RAM, minutes of CPU; a couple of older loops had NO step
ceiling at all (infinite loops). Every public entry point must return
promptly with a structured response when fed bare/degenerate mocks, and
the whole suite's memory delta must stay bounded so tests can never
starve other software running on this machine.
"""

from __future__ import annotations

import ctypes
import unittest
import ctypes.wintypes as wt
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.assembly import (
    check_interference,
    get_bom,
    new_assembly,
)
from solidworks_mcp.solidworks_api.decorations import (
    apply_chamfer,
    apply_fillet,
    apply_shell,
)
from solidworks_mcp.solidworks_api.design import execute_design_plan
from solidworks_mcp.solidworks_api.drawing import (
    create_drawing_from_part,
    export_drawing_pdf,
    insert_model_dimensions,
)
from solidworks_mcp.solidworks_api.features import (
    delete_feature,
    get_feature_details,
    get_features,
    rename_feature,
    set_dimension,
    set_feature_suppression,
)
from solidworks_mcp.solidworks_api.topology import list_bodies, list_faces


class _PMC(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_psapi = ctypes.WinDLL("psapi")
_psapi.GetProcessMemoryInfo.restype = wt.BOOL
_psapi.GetProcessMemoryInfo.argtypes = [
    wt.HANDLE, ctypes.POINTER(_PMC), wt.DWORD
]


def _rss_mb() -> float:
    # wt.HANDLE(-1) is the current-process pseudo-handle; without the
    # explicit argtypes above the call silently fails and returns 0
    # (verified on this machine — error 6, invalid handle).
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(_PMC)
    ok = _psapi.GetProcessMemoryInfo(
        wt.HANDLE(-1), ctypes.byref(pmc), pmc.cb
    )
    if not ok:
        raise RuntimeError(
            "GetProcessMemoryInfo failed — memory guard cannot assert; "
            f"GetLastError={ctypes.GetLastError()}"
        )
    return pmc.WorkingSetSize / 1e6


RSS_BUDGET_MB = 200.0  # the O(n^2) incident measured in gigabytes


class TestBareMockTolerance(unittest.TestCase):
    """Every entry point returns promptly on bare Mock documents."""

    def test_feature_walk_entry_points(self):
        sw = Mock()
        for call in (
            lambda: get_features(sw),
            lambda: get_feature_details(sw),
            lambda: get_feature_details(sw, feature_name="X"),
            lambda: rename_feature(sw, "A", "B"),
            lambda: set_feature_suppression(sw, "A", True),
            lambda: delete_feature(sw, "A"),
            lambda: set_dimension(sw, "D1@X", 10.0),
        ):
            result = call()
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)

    def test_iterable_mock_bodies_do_not_explode(self):
        # GetBodies2 returning an iterable of Mocks is the adversarial
        # case: the face walks become reachable and every step makes mock
        # calls (the exact O(n^2) trigger).
        sw = Mock()
        sw.get_active_document.return_value.GetBodies2.return_value = (Mock(),)
        for call in (
            lambda: list_faces(sw),
            lambda: list_bodies(sw),
            lambda: apply_fillet(sw, ["Face0"], 2.0),
            lambda: apply_chamfer(sw, ["Face0"], 1.0),
            lambda: apply_shell(sw, ["Face0"], 2.0),
        ):
            result = call()
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)

    def test_dimension_walk_stops_on_non_string_full_name(self):
        # A display-dimension chain of Mocks must break on the first
        # FullName that is not a string.
        from tests.test_features import DetailFeature, Model

        feat = DetailFeature("F", disp_dims=Mock())
        sw = Mock()
        sw.get_active_document.return_value = Model(feat)
        result = get_feature_details(sw)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["features"][0]["dimensions"], [])

    def test_plan_failure_path_on_mock_document(self):
        from solidworks_mcp.utils.common import error_response
        from unittest.mock import patch

        with patch(
            "solidworks_mcp.solidworks_api.design.create_plate",
            return_value=error_response("x", code="SW_API_ERROR"),
        ):
            result = execute_design_plan(
                Mock(), [{"type": "plate", "width": 1, "depth": 1, "height": 1}]
            )
        self.assertFalse(result["success"])

    def test_drawing_entry_points(self):
        # create bails at path validation; insert bails at the doc-type check
        # or the view-walk str sentinel; export bails at SaveAs3 != 0.
        sw = Mock()
        sw.get_active_document.return_value.GetType.return_value = 3
        for call in (
            lambda: create_drawing_from_part(sw, "missing.SLDPRT"),
            lambda: insert_model_dimensions(sw),
            lambda: export_drawing_pdf(sw, "x.pdf"),
        ):
            result = call()
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)

    def test_assembly_entry_points(self):
        # interference/bom bail at the doc-type check; new_assembly bails at
        # the missing template (patched away) before touching NewDocument.
        sw = Mock()
        with patch(
            "solidworks_mcp.solidworks_api.assembly.get_assembly_template",
            return_value=None,
        ):
            self.assertFalse(new_assembly(sw)["success"])
        for call in (lambda: check_interference(sw), lambda: get_bom(sw)):
            result = call()
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)

    def test_memory_delta_stays_bounded(self):
        """The whole battery must not move the process RSS measurably."""
        before = _rss_mb()
        self.test_feature_walk_entry_points()
        self.test_iterable_mock_bodies_do_not_explode()
        self.test_dimension_walk_stops_on_non_string_full_name()
        self.test_plan_failure_path_on_mock_document()
        self.test_drawing_entry_points()
        self.test_assembly_entry_points()
        delta = _rss_mb() - before
        self.assertLess(
            delta,
            RSS_BUDGET_MB,
            f"memory delta {delta:.1f}MB exceeds budget — the O(n^2) "
            "mock-call explosion may be back",
        )


if __name__ == "__main__":
    unittest.main()
