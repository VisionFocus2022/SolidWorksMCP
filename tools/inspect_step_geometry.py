from __future__ import annotations

import json
import sys
from pathlib import Path

import pythoncom
import win32com.client

from solidworks_mcp.solidworks_api.app import SolidWorksApp
from solidworks_mcp.solidworks_api.file_io import import_step


def call_or_value(obj, name: str):
    value = getattr(obj, name)
    return value() if callable(value) else value


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: inspect_step_geometry.py INPUT.stp OUTPUT.json")

    input_path = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pythoncom.CoInitialize()
    try:
        sw = SolidWorksApp()
        connection = sw.connect(launch_if_needed=False)
        if not connection.get("success"):
            output_path.write_text(
                json.dumps(connection, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return 1
        result = import_step(sw, str(input_path))
        model = sw.app.ActiveDoc if result.get("success") else None
        part = model
        if model is None:
            import_data = sw.app.GetImportFileData(str(input_path))
            errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            loaded = sw.app.LoadFile4(str(input_path), "r", import_data, errors)
            part = loaded[0] if isinstance(loaded, tuple) else loaded
            if part is None:
                output_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                return 1
            model = sw.app.ActiveDoc
            result = {
                "success": True,
                "message": "Imported STEP with LoadFile4 fallback",
                "primary_import": result,
            }
        bodies = list(part.GetBodies2(0, True) or [])
        body_boxes = []
        for index, body in enumerate(bodies, start=1):
            box = list(body.GetBodyBox() or [])
            body_boxes.append(
                {
                    "index": index,
                    "name": call_or_value(body, "Name"),
                    "box_m": box,
                    "size_mm": [
                        round((box[3] - box[0]) * 1000.0, 6),
                        round((box[4] - box[1]) * 1000.0, 6),
                        round((box[5] - box[2]) * 1000.0, 6),
                    ] if len(box) == 6 else None,
                }
            )

        features = []
        feature_error = None
        try:
            feature = model.FirstFeature()
            while feature is not None:
                features.append(
                    {
                        "name": call_or_value(feature, "Name"),
                        "type": feature.GetTypeName2(),
                        "suppressed": bool(feature.IsSuppressed2(0, None)),
                    }
                )
                feature = feature.GetNextFeature()
        except Exception as exc:
            feature_error = f"{type(exc).__name__}: {exc}"

        try:
            mass_properties = list(
                model.Extension.CreateMassProperty().GetMassProperties(1) or []
            )
            mass_error = None
        except Exception as exc:
            mass_properties = []
            mass_error = f"{type(exc).__name__}: {exc}"
        report = {
            "import": result,
            "title": call_or_value(model, "GetTitle"),
            "path": call_or_value(model, "GetPathName"),
            "body_count": len(bodies),
            "bodies": body_boxes,
            "mass_properties_si": mass_properties,
            "mass_error": mass_error,
            "features": features,
            "feature_error": feature_error,
        }
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
