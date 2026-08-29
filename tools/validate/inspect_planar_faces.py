from __future__ import annotations

import json
import sys
from pathlib import Path

import pythoncom
import win32com.client


def value(obj, name: str):
    member = getattr(obj, name)
    try:
        return member() if callable(member) else member
    except Exception:
        return member


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: inspect_planar_faces.py INPUT.SLDPRT OUTPUT.json")

    source = str(Path(sys.argv[1]).resolve())
    output = Path(sys.argv[2]).resolve()
    pythoncom.CoInitialize()
    try:
        app = win32com.client.GetActiveObject("SldWorks.Application")
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        model = app.OpenDoc6(source, 1, 1, "", errors, warnings)
        bodies = list(model.GetBodies2(0, True) or [])
        records = []
        for body_index, body in enumerate(bodies, start=1):
            for face_index, face in enumerate(list(value(body, "GetFaces") or []), start=1):
                surface = value(face, "GetSurface")
                is_plane = bool(value(surface, "IsPlane"))
                if not is_plane:
                    continue
                records.append(
                    {
                        "body": body_index,
                        "face": face_index,
                        "area_mm2": round(float(value(face, "GetArea")) * 1_000_000.0, 6),
                        "box_mm": [round(float(v) * 1000.0, 6) for v in list(value(face, "GetBox") or [])],
                        "plane_params": [round(float(v), 9) for v in list(value(surface, "PlaneParams") or [])],
                    }
                )
        records.sort(key=lambda item: item["area_mm2"], reverse=True)
        report = {
            "source": source,
            "body_count": len(bodies),
            "planar_face_count": len(records),
            "planar_faces": records,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
