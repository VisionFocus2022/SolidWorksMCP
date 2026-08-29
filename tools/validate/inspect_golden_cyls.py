"""Print every cylindrical face of the golden flange STEP with span."""

from __future__ import annotations

import sys
from pathlib import Path

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.BRep import BRep_Tool
from OCP.TopoDS import TopoDS_Face


def face_span(face: TopoDS_Face):
    umin, umax = BRep_Tool.UBounds_s(face) if hasattr(BRep_Tool, "UBounds_s") else (None, None)
    return umin, umax


def main() -> None:
    step = Path(sys.argv[1] if len(sys.argv) > 1 else "aicad/output/golden_flange.step")
    reader = STEPControl_Reader()
    reader.ReadFile(str(step))
    reader.TransferRoots()
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(reader.OneShape(), TopAbs_FACE, m)
    print(f"faces={m.Extent()}")
    for i in range(1, m.Extent() + 1):
        face = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(face)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder()
        ax, loc = cyl.Axis().Direction(), cyl.Location()
        u0, u1, v0, v1 = ad.FirstUParameter(), ad.LastUParameter(), ad.FirstVParameter(), ad.LastVParameter()
        print(
            f"CYL r={cyl.Radius():.3f} "
            f"axis=({ax.X():.2f},{ax.Y():.2f},{ax.Z():.2f}) "
            f"loc=({loc.X():.2f},{loc.Y():.2f},{loc.Z():.2f}) "
            f"u-range=({u0:.3f},{u1:.3f}) "
            f"v-range=({v0:.2f},{v1:.2f})",
            flush=True,
        )


if __name__ == "__main__":
    main()
