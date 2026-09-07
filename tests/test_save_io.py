"""save_io contract tests (N37): the two-phase save helper pair."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.save_io import persist_part_save, prepare_part_save


class TestPreparePartSave(unittest.TestCase):
    def test_none_without_save_path(self):
        self.assertIsNone(prepare_part_save(None, False))
        self.assertIsNone(prepare_part_save("", False))

    def test_validation_failure_returns_message(self):
        with patch(
            "solidworks_mcp.solidworks_api.save_io.validate_output_file",
            return_value=(False, "outside allowed root"),
        ):
            self.assertEqual(
                prepare_part_save("x.sldprt", False), "outside allowed root"
            )

    def test_validation_pass_returns_none(self):
        with patch(
            "solidworks_mcp.solidworks_api.save_io.validate_output_file",
            return_value=(True, ""),
        ):
            self.assertIsNone(prepare_part_save("x.sldprt", True))


class TestPersistPartSave(unittest.TestCase):
    def test_none_without_save_path(self):
        result = {}
        self.assertEqual(persist_part_save(Mock(), None, result), (None, None))
        self.assertEqual(result, {})

    def test_sink_failure_is_invalid_output_path(self):
        with patch(
            "solidworks_mcp.solidworks_api.save_io.ensure_sink_path",
            return_value=(False, "resolves outside", "n/a"),
        ):
            code, message = persist_part_save(Mock(), "x.sldprt", {})
        self.assertEqual(code, "INVALID_OUTPUT_PATH")
        self.assertEqual(message, "resolves outside")

    def test_saveas3_failure_is_sw_api_error(self):
        model = Mock()
        model.SaveAs3.return_value = 1  # != swFileSaveErrorNone
        with patch(
            "solidworks_mcp.solidworks_api.save_io.ensure_sink_path",
            return_value=(True, "", "sink.sldprt"),
        ):
            code, message = persist_part_save(model, "x.sldprt", {})
        self.assertEqual(code, "SW_API_ERROR")
        self.assertIn("SaveAs3 failed", message)

    def test_success_fills_saved_to(self):
        model = Mock()
        model.SaveAs3.return_value = 0
        result = {}
        with patch(
            "solidworks_mcp.solidworks_api.save_io.ensure_sink_path",
            return_value=(True, "", "sink.sldprt"),
        ):
            code, message = persist_part_save(model, "x.sldprt", result)
        self.assertEqual((code, message), (None, None))
        self.assertEqual(result, {"saved_to": "x.sldprt"})


if __name__ == "__main__":
    unittest.main()
