"""SolidWorks application connection lifecycle tests."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError


class FakeApp:
    def __init__(self, revision="34.2.1"):
        self.revision = revision

    def RevisionNumber(self):
        return self.revision


class TestSolidWorksApp(unittest.TestCase):
    def test_app_property_requires_connection(self):
        with self.assertRaises(SolidWorksNotRunningError):
            _ = SolidWorksApp().app

    @patch("solidworks_mcp.solidworks_api.app._is_solidworks_process_running", return_value=False)
    @patch("solidworks_mcp.solidworks_api.app.win32com.client.GetActiveObject", side_effect=RuntimeError("missing"))
    @patch("solidworks_mcp.solidworks_api.app.win32com.client.Dispatch")
    def test_connect_without_launch_reports_standard_failure(self, dispatch, _active, _running):
        result = SolidWorksApp().connect(launch_if_needed=False)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_CONNECTION_FAILED")
        dispatch.assert_not_called()

    @patch("solidworks_mcp.solidworks_api.app._is_solidworks_process_running", return_value=True)
    @patch("solidworks_mcp.solidworks_api.app.win32com.client.GetActiveObject", side_effect=RuntimeError("rot unavailable"))
    @patch("solidworks_mcp.solidworks_api.app.win32com.client.Dispatch")
    def test_connect_dispatches_to_running_process(self, dispatch, _active, _running):
        dispatch.return_value = FakeApp()
        sw = SolidWorksApp()
        result = sw.connect(launch_if_needed=False)
        self.assertTrue(result["success"])
        self.assertTrue(sw.connected)
        self.assertEqual(sw.version, "34.2.1")

    @patch("solidworks_mcp.solidworks_api.app._is_solidworks_process_running", return_value=False)
    @patch("solidworks_mcp.solidworks_api.app.win32com.client.GetActiveObject", side_effect=RuntimeError("missing"))
    @patch("solidworks_mcp.solidworks_api.app.win32com.client.Dispatch")
    def test_connect_launches_and_makes_application_visible(self, dispatch, _active, _running):
        dispatch.return_value = FakeApp()
        sw = SolidWorksApp()
        result = sw.connect(launch_if_needed=True)
        self.assertTrue(result["success"])
        self.assertTrue(dispatch.return_value.Visible)

    @patch("solidworks_mcp.solidworks_api.app.win32com.client.GetActiveObject")
    def test_stale_cached_connection_is_replaced(self, active):
        stale = Mock()
        stale.RevisionNumber.side_effect = RuntimeError("stale")
        active.return_value = FakeApp("34.3.0")
        sw = SolidWorksApp()
        sw._app = stale
        result = sw.connect(False)
        self.assertTrue(result["success"])
        self.assertEqual(sw.version, "34.3.0")

    def test_status_disconnect_and_active_document(self):
        sw = SolidWorksApp()
        self.assertEqual(sw.status(), {"connected": False, "version": None})
        app = FakeApp()
        app.ActiveDoc = object()
        sw._app = app
        self.assertTrue(sw.status()["connected"])
        self.assertIs(sw.get_active_document(), app.ActiveDoc)
        sw.disconnect()
        self.assertFalse(sw.connected)

    def test_status_clears_stale_connection_and_active_document_hides_errors(self):
        app = Mock()
        app.RevisionNumber.side_effect = RuntimeError("stale")
        sw = SolidWorksApp()
        sw._app = app
        self.assertFalse(sw.status()["connected"])
        self.assertIsNone(sw.get_active_document())


if __name__ == "__main__":
    unittest.main()
