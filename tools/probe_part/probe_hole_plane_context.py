"""Minimal repro: does a cylinder boss corrupt later hole sketch planes?

Part A: new_part -> plate 80x80x8 -> cut_round_hole O6 @(15,0) top
Part B: new_part -> plate 80x80x8 -> cylinder O20x5 -> same hole

Both exported as STEP; the OCCT probe prints every cylinder face
(radius/axis/location) so the hole axis difference is visible.

Run with SolidWorks open from the repo root:
    venv\\Scripts\\python.exe tools\\probe_hole_plane_context.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.design import (
    create_new_part,
    cut_threaded_hole,
    execute_design_plan,
)
from solidworks_mcp.solidworks_api.file_io import export_step
from solidworks_mcp.solidworks_api.part import create_cylinder

OUT = Path(__file__).resolve().parents[2] / "output"

HOLE = {"type": "hole", "diameter": 6.0, "x": 15.0, "y": 0.0,
        "plane": "top", "through_all": True}


def probe(step_path: Path) -> None:
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    reader = STEPControl_Reader()
    reader.ReadFile(str(step_path))
    reader.TransferRoots()
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(reader.OneShape(), TopAbs_FACE, m)
    for i in range(1, m.Extent() + 1):
        face = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(face)
        if ad.GetType() == GeomAbs_Cylinder:
            cyl = ad.Cylinder()
            ax, loc = cyl.Axis().Direction(), cyl.Location()
            print(
                f"  CYL r={cyl.Radius():.3f} "
                f"axis=({ax.X():.2f},{ax.Y():.2f},{ax.Z():.2f}) "
                f"loc=({loc.X():.2f},{loc.Y():.2f},{loc.Z():.2f})",
                flush=True,
            )


def build(tag: str, with_boss: bool) -> None:
    sw = get_solidworks_app()
    sw.connect(launch_if_needed=False)
    step = OUT / f"probe_hole_{tag}.step"
    step.unlink(missing_ok=True)
    print(f"--- {tag} (boss={with_boss}) ---", flush=True)
    ops = [
        {"type": "new_part"},
        {"type": "plate", "width": 80.0, "depth": 80.0, "thickness": 8.0},
    ]
    if with_boss:
        ops.append({"type": "cylinder", "diameter": 20.0, "height": 5.0})
    ops.append(HOLE)
    report = execute_design_plan(sw, ops)
    print("plan:", report.get("success"), report.get("message"), flush=True)
    if not report.get("success"):
        return
    result = export_step(sw, str(step))
    print("step:", result.get("success"), flush=True)
    if result.get("success"):
        probe(step)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    build("plate_only", with_boss=False)
    build("with_boss", with_boss=True)
    # Extra: threaded hole after a boss (same sketch path as M10).
    sw = get_solidworks_app()
    sw.connect(launch_if_needed=False)
    step = OUT / "probe_hole_thread_after_boss.step"
    step.unlink(missing_ok=True)
    print("--- thread_after_boss ---", flush=True)
    assert create_new_part(sw)["success"]
    from solidworks_mcp.solidworks_api.design import create_plate
    assert create_plate(sw, 80.0, 80.0, 8.0)["success"]
    assert create_cylinder(sw, 20.0, 5.0)["success"]
    r = cut_threaded_hole(sw, "M10", 0.0, 0.0, plane="top", through_all=True)
    print("thread:", r.get("success"), flush=True)
    if export_step(sw, str(step)).get("success"):
        probe(step)


if __name__ == "__main__":
    main()
