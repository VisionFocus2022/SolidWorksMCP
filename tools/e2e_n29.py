"""N29 步骤 4 实机 e2e：ref-plane / ref-axis / dome / rib 生产工具直调。

Parameters mirror the probe (tools/probe_part/probe_n29_unblock.py) so the
volume windows are analytic: dome ⌀20 top + 5mm → spherical cap
πh(3a²+h²)/6 = 850.85; rib 60×6×10 plate on a 60×40×20 box top →
ΔV = 60·6·10 = 3600 (boss-extrude plate, math substitute for InsertRib)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solidworks_mcp.solidworks_api import decorations, design, file_io, part, topology
from solidworks_mcp.solidworks_api.app import get_solidworks_app

DOME_VOL_MM3 = math.pi * 5.0 * (3 * 100.0 + 25.0) / 6.0  # ≈ 850.85
RIB_VOL_MM3 = 60.0 * 6.0 * 10.0  # boss plate on the box top


def _volume_mm3(sw) -> float:
    r = part.get_mass_properties(sw)
    assert r["success"], r
    return r["data"]["volume"] * 1e9


def _fresh_box(sw):
    assert part.create_box(sw, 60.0, 40.0, 20.0)["success"]


def _fresh_cylinder(sw):
    assert part.create_cylinder(sw, 20.0, 30.0)["success"]


def main() -> int:
    sw = get_solidworks_app()
    assert sw.connect(launch_if_needed=True)["success"]
    ok = True

    # 1. Reference plane: offset off the front plane of a fresh box part
    design.create_new_part(sw)
    _fresh_box(sw)
    r = part.create_ref_plane(sw, offset_mm=30.0)
    print("ref_plane:", r["success"], (r.get("data") or {}).get("feature_name"))
    ok = ok and r["success"]
    file_io.close_document(sw, save_changes=False)

    # 2. Reference axis from the named cylindrical face of a ⌀20 cylinder
    design.create_new_part(sw)
    _fresh_cylinder(sw)
    faces = topology.list_faces(sw)
    assert faces["success"], faces
    names = {f["name"]: f.get("area_mm2", 0.0) for f in faces["data"]["faces"]}
    # The cylindrical face has by far the largest area (⌀20×30 side)
    face_name = max(names, key=lambda n: names[n])
    print(f"  cylinder faces: {names} -> axis source {face_name!r}")
    r = part.create_ref_axis(sw, face_name=face_name)
    print("ref_axis:", r["success"], (r.get("data") or {}).get("feature_name"))
    ok = ok and r["success"]
    # Non-cylindrical face must be rejected with a structured error
    flat = min(names, key=lambda n: names[n])
    r2 = part.create_ref_axis(sw, face_name=flat)
    rejected = (
        not r2["success"]
        and r2["error"]["code"] == "INVALID_PARAMETER"
        and "cylindrical" in r2["message"]
    )
    print(f"  non-cylindrical rejection: {rejected}")
    ok = ok and rejected
    file_io.close_document(sw, save_changes=False)

    # 3. Dome: 5mm cap on the ⌀20 cylinder top → exact spherical cap volume
    design.create_new_part(sw)
    _fresh_cylinder(sw)
    faces = topology.list_faces(sw)
    top_name = max(
        (f for f in faces["data"]["faces"] if f.get("area_mm2") < 400.0),
        key=lambda f: f.get("area_mm2", 0.0),
    )["name"]
    volume0 = _volume_mm3(sw)
    r = decorations.apply_dome(sw, face_name=top_name, height_mm=5.0)
    print(
        "dome:", r["success"],
        (r.get("data") or {}).get("feature_name"), f"face={top_name!r}",
    )
    if r["success"]:
        gained = _volume_mm3(sw) - volume0
        delta = abs(gained - DOME_VOL_MM3) / DOME_VOL_MM3
        print(f"  ΔV {gained:.2f} vs {DOME_VOL_MM3:.2f} ({delta:.3%})")
        ok = ok and delta < 0.01
    else:
        ok = False
    file_io.close_document(sw, save_changes=False)

    # 4. Rib (math substitute): 60×6 plate, 10mm tall, standing on the box top
    design.create_new_part(sw)
    _fresh_box(sw)
    volume0 = _volume_mm3(sw)
    r = part.create_rib(
        sw,
        length_mm=60.0,
        height_mm=10.0,
        thickness_mm=6.0,
        base_z_mm=20.0,
    )
    print(
        "rib:", r["success"],
        (r.get("data") or {}).get("feature_name"), r.get("message"),
    )
    if r["success"]:
        gained = _volume_mm3(sw) - volume0
        delta = abs(gained - RIB_VOL_MM3) / RIB_VOL_MM3
        print(f"  ΔV {gained:.2f} vs {RIB_VOL_MM3:.2f} ({delta:.3%})")
        ok = ok and delta < 0.01
    else:
        ok = False
    file_io.close_document(sw, save_changes=False)

    print("E2E N29:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
