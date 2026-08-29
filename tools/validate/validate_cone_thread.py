"""Real-machine validation for the cone and threaded-hole primitives.

Run with SolidWorks 2026 already open:

    venv\\Scripts\\python.exe tools\\validate_cone_thread.py

Stage 1 (cone): builds a frustum bottom=30 top=20 height=40 mm on a fresh
part and verifies the volume against the closed-form frustum formula
V = pi*h/3*(R^2 + R*r + r^2) within a +/-2% window, then saves SLDPRT+STEP
under output/.

Stage 2 (threaded hole): on a second fresh part builds a 40x40x8 plate,
cuts an M8 through-all threaded hole at the tap-drill diameter (6.8 mm)
and verifies:
  * plate volume minus the analytic tap-drill cylinder within +/-2%;
  * the cosmetic-thread stamp via the RETURNED BOOLEAN only -- the created
    CosmeticThread feature is NOT enumerable over FirstFeature/GetNextFeature
    (real-machine contract, see aicad sw_rebuild.py header), so tree walks
    must never be used to verify threads.

Exit codes: 0 = all checks passed, 1 = a check failed, 2 = SolidWorks not
running, 3 = a build step failed.
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.design import (
    _save_active_model,
    create_new_part,
    cut_threaded_hole,
)
from solidworks_mcp.solidworks_api.file_io import close_document, export_step
from solidworks_mcp.solidworks_api.part import create_box, create_cone, get_mass_properties

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
)

# Frustum 30/20/40: V = pi*40/3*(15^2 + 15*10 + 10^2) = 19897.75 mm^3.
CONE_BOTTOM, CONE_TOP, CONE_HEIGHT = 30.0, 20.0, 40.0
CONE_VOLUME_M3 = (
    math.pi * CONE_HEIGHT / 3.0
    * ((CONE_BOTTOM / 2) ** 2 + (CONE_BOTTOM / 2) * (CONE_TOP / 2) + (CONE_TOP / 2) ** 2)
    / 1e9
)

# Plate 40x40x8 minus M8 tap-drill cylinder (6.8 mm through 8 mm).
PLATE_W, PLATE_D, PLATE_T = 40.0, 40.0, 8.0
TAP_DRILL_M8 = 6.8
PLATE_VOLUME_M3 = (
    PLATE_W * PLATE_D * PLATE_T
    - math.pi * (TAP_DRILL_M8 / 2) ** 2 * PLATE_T
) / 1e9


def _window(expected: float, rel: float = 0.02):
    return (expected * (1 - rel), expected * (1 + rel))


def _show(label: str, payload) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=False, default=str)}")


def _volume(sw) -> float | None:
    mass = get_mass_properties(sw)
    if not mass.get("success"):
        return None
    return (mass.get("data") or {}).get("volume")


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sw = get_solidworks_app()
    connection = sw.connect(launch_if_needed=False)
    _show("connect", {k: connection.get(k) for k in ("success", "data")})
    if not connection["success"]:
        return 2

    report: dict = {}

    # ---- Stage 1: cone -------------------------------------------------
    step = create_new_part(sw)
    report["new_part_cone"] = step["success"]
    if not report["new_part_cone"]:
        _show("abort_new_part_cone", step)
        return 3

    step = create_cone(sw, CONE_BOTTOM, CONE_TOP, CONE_HEIGHT)
    _show("cone", {k: step.get(k) for k in ("success", "message", "data")})
    report["cone_built"] = step["success"]
    if not report["cone_built"]:
        return 3

    volume = _volume(sw)
    lo, hi = _window(CONE_VOLUME_M3)
    report["cone_volume_m3"] = volume
    report["cone_volume_expected_m3"] = CONE_VOLUME_M3
    report["cone_volume_sane"] = bool(volume and lo < volume < hi)
    _show(
        "cone_volume",
        {k: report.get(k) for k in ("cone_volume_m3", "cone_volume_expected_m3", "cone_volume_sane")},
    )

    data: dict = {}
    save_error = _save_active_model(
        model=sw.get_active_document(),
        save_path=os.path.join(OUTPUT_DIR, "cone_validation.sldprt"),
        overwrite_confirm=True,
        result=data,
    )
    report["cone_saved_sldprt"] = save_error is None and bool(data.get("saved_to"))
    step = export_step(
        sw, os.path.join(OUTPUT_DIR, "cone_validation.step"), overwrite_confirm=True
    )
    report["cone_export_step"] = step["success"]
    close_document(sw, save_changes=False)

    # ---- Stage 2: threaded hole ----------------------------------------
    step = create_new_part(sw)
    report["new_part_thread"] = step["success"]
    if not report["new_part_thread"]:
        _show("abort_new_part_thread", step)
        return 3

    step = create_box(sw, PLATE_W, PLATE_D, PLATE_T)
    report["plate_built"] = step["success"]
    if not report["plate_built"]:
        _show("abort_plate", step)
        return 3

    step = cut_threaded_hole(sw, "M8", 0, 0, plane="top", through_all=True)
    _show(
        "threaded_hole",
        {k: step.get(k) for k in ("success", "message", "warning")},
    )
    report["threaded_hole_built"] = step["success"]
    if not report["threaded_hole_built"]:
        return 3

    # Thread verification uses the returned boolean ONLY (CosmeticThread is
    # not tree-enumerable). A stamped thread is required for a green exit.
    thread = (step.get("data") or {}).get("thread") or {}
    report["thread_spec"] = thread.get("spec")
    report["thread_stamped"] = bool(thread.get("cosmetic_thread_stamped"))
    _show(
        "thread_check",
        {k: report.get(k) for k in ("thread_spec", "thread_stamped")},
    )

    volume = _volume(sw)
    lo, hi = _window(PLATE_VOLUME_M3)
    report["plate_volume_m3"] = volume
    report["plate_volume_expected_m3"] = PLATE_VOLUME_M3
    report["plate_volume_sane"] = bool(volume and lo < volume < hi)
    _show(
        "plate_volume",
        {k: report.get(k) for k in ("plate_volume_m3", "plate_volume_expected_m3", "plate_volume_sane")},
    )

    data = {}
    save_error = _save_active_model(
        model=sw.get_active_document(),
        save_path=os.path.join(OUTPUT_DIR, "threaded_validation.sldprt"),
        overwrite_confirm=True,
        result=data,
    )
    report["thread_saved_sldprt"] = save_error is None and bool(data.get("saved_to"))
    close_document(sw, save_changes=False)

    _show("REPORT", report)
    checks = (
        report["cone_built"],
        report["cone_volume_sane"],
        report["cone_saved_sldprt"],
        report["cone_export_step"],
        report["threaded_hole_built"],
        report["thread_stamped"],
        report["plate_volume_sane"],
        report["thread_saved_sldprt"],
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
