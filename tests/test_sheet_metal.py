"""T21-3: sheet-metal base-flange tool tests.

实机契约（tools/probe_part/probe_sheet_metal_thread.py）：
- 顶面（上视基准面）矩形草图 → FeatureManager.InsertSheetMetalBaseFlange；
- PCBA 参必须 pythoncom.Nothing（dispatch 型，传 0 报类型不匹配 param 10）；
- 产物特征树三件套：钣金N / 基体-法兰N / 平展型式N；
- 板件 bbox = [width, thickness, depth]（厚度沿模型 Y）。
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api import sheet_metal


class FakeSketchManager:
    def __init__(self):
        self.calls = []

    def InsertSketch(self, _update):
        self.calls.append("sketch")

    def CreateCornerRectangle(self, x1, y1, _z1, x2, y2, _z2):
        self.calls.append(("rect", round(x1, 5), round(y1, 5),
                           round(x2, 5), round(y2, 5)))


class FakeFeatureManager:
    def __init__(self):
        self.calls = []

    def InsertSheetMetalBaseFlange(self, *args):
        self.calls.append(args)
        return SimpleNamespace(Name="基体-法兰1")


class FakeModel:
    def __init__(self):
        self.sketch = FakeSketchManager()
        self.fm = FakeFeatureManager()

    @property
    def GetType(self):
        return 1  # swDocPART

    @property
    def SketchManager(self):
        return self.sketch

    @property
    def FeatureManager(self):
        return self.fm


def _sw(model):
    sw = Mock()
    sw.get_active_document.return_value = model
    return sw


class TestBaseFlange(unittest.TestCase):
    @patch(
        "solidworks_mcp.solidworks_api.sheet_metal.select_plane",
        return_value="上视基准面",
    )
    def test_creates_flange_with_metre_arguments(self, _plane):
        model = FakeModel()
        result = sheet_metal.create_base_flange(
            _sw(model), width=60.0, depth=40.0, thickness=2.0
        )
        self.assertTrue(result["success"], result)
        args = model.fm.calls[0]
        self.assertEqual(args[0], 0.002)   # Thickness 米
        self.assertFalse(args[1])          # ThickenDir
        self.assertEqual(args[2], 0.0)     # Radius 默认 0（平板）
        self.assertEqual(result["data"]["feature_name"], "基体-法兰1")
        # 矩形草图中心化：-30..30mm × -20..20mm（米制）
        rect = model.sketch.calls[1]
        self.assertEqual(rect[1:], (-0.03, -0.02, 0.03, 0.02))

    def test_radius_is_forwarded_in_metres(self):
        model = FakeModel()
        with patch(
            "solidworks_mcp.solidworks_api.sheet_metal.select_plane",
            return_value="上视基准面",
        ):
            result = sheet_metal.create_base_flange(
                _sw(model), 60.0, 40.0, 2.0, radius=1.5
            )
        self.assertTrue(result["success"], result)
        self.assertEqual(model.fm.calls[0][2], 0.0015)

    @patch(
        "solidworks_mcp.solidworks_api.sheet_metal.select_plane",
        return_value=None,
    )
    def test_plane_selection_failure_is_structured(self, _plane):
        result = sheet_metal.create_base_flange(_sw(FakeModel()), 60, 40, 2)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")

    def test_flange_creation_returning_none_fails(self):
        model = FakeModel()
        model.fm.InsertSheetMetalBaseFlange = lambda *a: None
        with patch(
            "solidworks_mcp.solidworks_api.sheet_metal.select_plane",
            return_value="上视基准面",
        ):
            result = sheet_metal.create_base_flange(_sw(model), 60, 40, 2)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_validation_rejects_non_positive(self):
        sw = _sw(FakeModel())
        for args in ((0, 40, 2), (60, 0, 2), (60, 40, 0), (60, 40, -1)):
            self.assertEqual(
                sheet_metal.create_base_flange(sw, *args)["error"]["code"],
                "INVALID_PARAMETER",
            )

    def test_save_path_round_trip(self):
        model = FakeModel()
        model.save_calls = []

        def _save(path, version, options):
            model.save_calls.append(path)
            return 0

        model.SaveAs3 = _save
        with patch(
            "solidworks_mcp.solidworks_api.sheet_metal.select_plane",
            return_value="上视基准面",
        ), patch(
            "solidworks_mcp.solidworks_api.sheet_metal.validate_output_file",
            return_value=(True, ""),
        ), patch(
            "solidworks_mcp.solidworks_api.sheet_metal.ensure_sink_path",
            side_effect=lambda path: (True, "", path),
        ):
            result = sheet_metal.create_base_flange(
                _sw(model), 60.0, 40.0, 2.0, save_path="flange.SLDPRT"
            )
        self.assertTrue(result["success"], result)
        self.assertEqual(model.save_calls, ["flange.SLDPRT"])
        self.assertEqual(result["data"]["saved_to"], "flange.SLDPRT")

    def test_invalid_save_path_is_rejected_before_anything(self):
        with patch(
            "solidworks_mcp.solidworks_api.sheet_metal.validate_output_file",
            return_value=(False, "outside allowed root"),
        ):
            result = sheet_metal.create_base_flange(
                _sw(FakeModel()), 60, 40, 2, save_path="x.SLDPRT"
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")

    def test_com_error_is_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        result = sheet_metal.create_base_flange(sw, 60, 40, 2)
        self.assertFalse(result["success"])
        self.assertIn("COM failed", result["message"])


if __name__ == "__main__":
    unittest.main()
