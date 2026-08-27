from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pythoncom
import win32com.client

from solidworks_mcp.solidworks_api.app import SolidWorksApp
from solidworks_mcp.solidworks_api.design import mm_to_m


def cut_band(model, inner_radius_mm: float, outer_radius_mm: float, depth_mm: float):
    sample = (inner_radius_mm + outer_radius_mm) / 2.0
    angle = math.radians(22.5)
    model.ClearSelection2(True)
    selected = model.Extension.SelectByRay(
        mm_to_m(sample * math.cos(angle)),
        mm_to_m(sample * math.sin(angle)),
        mm_to_m(10.0),
        0.0,
        0.0,
        -1.0,
        mm_to_m(0.2),
        2,
        False,
        0,
        0,
    )
    if not selected:
        return None, "front face selection failed"
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, mm_to_m(inner_radius_mm))
    model.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, mm_to_m(outer_radius_mm))
    model.SketchManager.InsertSketch(True)
    model.ClearSelection2(True)
    sketch_feature = model.FeatureByPositionReverse(0)
    if sketch_feature is None or not sketch_feature.Select2(False, 0):
        return None, "new sketch selection failed"
    depth = mm_to_m(depth_mm)
    feature = model.FeatureManager.FeatureCut3(
        True, False, False, 0, 0, depth, depth,
        False, False, False, False, 0, 0,
        False, False, False, False, False,
        True, True, True, True, False, 0, 0, False,
    )
    return feature, None if feature is not None else "blind cut failed"


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: probe_front_blind_bands.py INPUT.SLDPRT OUTPUT.SLDPRT REPORT.json")
    source = str(Path(sys.argv[1]).resolve())
    output = str(Path(sys.argv[2]).resolve())
    report_path = Path(sys.argv[3]).resolve()
    report = {}
    pythoncom.CoInitialize()
    try:
        sw = SolidWorksApp()
        report["connection"] = sw.connect(launch_if_needed=False)
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        model = sw.app.OpenDoc6(source, 1, 1, "", errors, warnings)
        if model is None:
            return 1
        report["save_copy"] = model.SaveAs3(output, 0, 1)
        report["bands"] = []
        for index, (r0, r1, depth) in enumerate(((35.0, 38.0, 0.5), (30.0, 35.0, 5.0)), start=1):
            feature, error = cut_band(model, r0, r1, depth)
            report["bands"].append({"index": index, "created": feature is not None, "error": error})
            if feature is None:
                return 2
            feature.Name = f"PROBE_DISH_BAND_{index:02d}"
        report["rebuild"] = bool(model.ForceRebuild3(False))
        report["save_result"] = model.Save3(1, errors, warnings)
        model.ShowNamedView2("*Isometric", 7)
        model.ViewZoomtofit2()
        report["preview"] = bool(model.SaveBMP(str(report_path.with_suffix(".bmp")), 1200, 900))
        return 0
    finally:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
