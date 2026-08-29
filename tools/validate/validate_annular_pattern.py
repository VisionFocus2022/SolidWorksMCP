"""Real-machine validation for the generic annular pattern tools.

Run with SolidWorks 2026 already open:

    venv\\Scripts\\python.exe tools\\validate_annular_pattern.py

Builds a 120x80x8 plate, cuts three annular rings (one phase-optimized
against cardinal avoid angles), extrudes one boss ring, then verifies the
feature tree, mass properties (volume sanity window), saves SLDPRT+STEP
under output/, and closes the document. Exit codes: 0 = all checks passed,
1 = a check failed, 2 = SolidWorks not running, 3/4 = build step failed.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.design import (
    _save_active_model,
    create_new_part,
)
from solidworks_mcp.solidworks_api.features import get_features
from solidworks_mcp.solidworks_api.file_io import close_document, export_step
from solidworks_mcp.solidworks_api.part import create_box, get_mass_properties
from solidworks_mcp.solidworks_api.pattern import AnnularRing, create_annular_pattern

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
)

# Plate 120x80x8 mm = 76800 mm^3. Cuts remove ~2224 mm^3 and bosses add
# ~339 mm^3, so the expected volume window is roughly 7.2e-5 .. 7.7e-5 m^3.
EXPECTED_VOLUME_WINDOW_M3 = (7.0e-5, 7.7e-5)


def _show(label: str, payload) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=False, default=str)}")


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sw = get_solidworks_app()
    connection = sw.connect(launch_if_needed=False)
    _show("connect", {k: connection.get(k) for k in ("success", "data")})
    if not connection["success"]:
        return 2

    report: dict = {}

    step = create_new_part(sw)
    report["new_part"] = step["success"]
    if not step["success"]:
        _show("abort_new_part", step)
        return 3

    step = create_box(sw, 120, 80, 8)
    report["plate"] = step["success"]
    if not step["success"]:
        _show("abort_plate", step)
        return 3

    rings = [
        AnnularRing(radius_mm=20.0, count=6, diameter_mm=5.0, phase_degrees=0.0),
        AnnularRing(radius_mm=30.0, count=12, diameter_mm=3.0),
        AnnularRing(radius_mm=35.0, count=24, diameter_mm=2.0),
    ]
    step = create_annular_pattern(
        sw,
        rings,
        plane="top",
        feature_kind="cut",
        through_all=True,
        avoid_angles_degrees=[0.0, 90.0, 180.0, 270.0],
    )
    _show(
        "pattern_cut",
        {k: step.get(k) for k in ("success", "message", "warning")},
    )
    report["pattern_cut"] = step["success"]
    if not step["success"]:
        return 4

    step = create_annular_pattern(
        sw,
        [AnnularRing(radius_mm=10.0, count=4, diameter_mm=6.0, phase_degrees=45.0)],
        plane="top",
        feature_kind="boss",
        depth=3.0,
    )
    _show(
        "pattern_boss",
        {k: step.get(k) for k in ("success", "message", "warning")},
    )
    report["pattern_boss"] = step["success"]
    if not step["success"]:
        return 4

    features = get_features(sw)
    names = features.get("data", {}).get("features", [])
    report["annular_features"] = [n for n in names if n.startswith("ANNULAR_")]
    _show("annular_features", report["annular_features"])

    mass = get_mass_properties(sw)
    report["mass_ok"] = bool(mass.get("success"))
    volume = (mass.get("data") or {}).get("volume")
    report["volume_m3"] = volume
    report["volume_sane"] = bool(
        volume
        and EXPECTED_VOLUME_WINDOW_M3[0] < volume < EXPECTED_VOLUME_WINDOW_M3[1]
    )
    _show("mass", {k: report.get(k) for k in ("mass_ok", "volume_m3", "volume_sane")})

    data: dict = {}
    save_error = _save_active_model(
        model=sw.get_active_document(),
        save_path=os.path.join(OUTPUT_DIR, "annular_validation.sldprt"),
        overwrite_confirm=True,
        result=data,
    )
    report["saved_sldprt"] = save_error is None and bool(data.get("saved_to"))
    _show("save_sldprt", save_error or data)

    step = export_step(
        sw, os.path.join(OUTPUT_DIR, "annular_validation.step"), overwrite_confirm=True
    )
    report["export_step"] = step["success"]
    _show("export_step", {k: step.get(k) for k in ("success", "message")})

    step = close_document(sw, save_changes=False)
    report["closed"] = step["success"]
    _show("close", {k: step.get(k) for k in ("success", "message")})

    _show("REPORT", report)
    checks = (
        report["pattern_cut"],
        report["pattern_boss"],
        report["mass_ok"],
        report["volume_sane"],
        report["saved_sldprt"],
        report["export_step"],
        report["closed"],
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
