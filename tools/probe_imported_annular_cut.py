from __future__ import annotations

import json
import sys
from pathlib import Path

import pythoncom
import win32com.client

from solidworks_mcp.solidworks_api.app import SolidWorksApp
from solidworks_mcp.solidworks_api.ring_light import (
    _cut_selected_sketch_through_all,
    _select_latest_sketch,
    mm_to_m,
)


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: probe_imported_annular_cut.py INPUT.SLDPRT OUTPUT.SLDPRT REPORT.json")

    source = str(Path(sys.argv[1]).resolve())
    output = str(Path(sys.argv[2]).resolve())
    report_path = Path(sys.argv[3]).resolve()
    pythoncom.CoInitialize()
    report = {}
    try:
        sw = SolidWorksApp()
        report["connection"] = sw.connect(launch_if_needed=False)
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        model = sw.app.OpenDoc6(source, 1, 1, "", errors, warnings)
        report["open"] = {"errors": errors.value, "warnings": warnings.value, "ok": model is not None}
        if model is None:
            return 1

        report["save_copy"] = model.SaveAs3(output, 0, 1)
        model.ClearSelection2(True)
        selected = model.Extension.SelectByRay(
            mm_to_m(30.0), 0.0, mm_to_m(10.0),
            0.0, 0.0, -1.0,
            mm_to_m(0.5), 2, False, 0, 0,
        )
        report["front_face_selected"] = bool(selected)
        if not selected:
            return 2

        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, mm_to_m(20.0))
        model.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, mm_to_m(38.1))
        model.SketchManager.InsertSketch(True)
        report["sketch_selected"] = bool(_select_latest_sketch(model))
        depth = mm_to_m(30.0)
        feature = model.FeatureManager.FeatureCut3(
            True, False, False, 1, 0, depth, depth,
            False, False, False, False, 0, 0,
            False, False, False, False, False,
            True, True, True, True, False, 0, 0, False,
        )
        report["cut_created"] = feature is not None
        band_feature = None
        if feature is not None:
            model.ClearSelection2(True)
            back_selected = model.Extension.SelectByRay(
                mm_to_m(39.0), 0.0, mm_to_m(-25.0),
                0.0, 0.0, 1.0,
                mm_to_m(0.5), 2, False, 0, 0,
            )
            report["back_face_selected"] = bool(back_selected)
            if back_selected:
                model.SketchManager.InsertSketch(True)
                model.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, mm_to_m(35.0))
                model.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, mm_to_m(38.1))
                model.SketchManager.InsertSketch(True)
                model.ClearSelection2(True)
                band_sketch_feature = model.FeatureByPositionReverse(0)
                report["band_feature_name"] = band_sketch_feature.Name
                report["band_sketch_selected"] = bool(band_sketch_feature.Select2(False, 0))
                height = mm_to_m(17.5)
                band_feature = model.FeatureManager.FeatureExtrusion2(
                    True, False, True, 0, 0, height, height,
                    False, False, False, False, 0, 0,
                    False, False, False, False, True, True, True, 0, 0, False,
                )
        report["band_created"] = band_feature is not None
        if feature is not None:
            feature.Name = "PROBE_ANNULAR_CUT"
        report["rebuild"] = bool(model.ForceRebuild3(False))
        report["save_result"] = model.Save3(1, errors, warnings)
        return 0 if feature is not None else 3
    finally:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
