"""N28 步骤 4 实机 e2e：loft/sweep 生产工具直调 + 体积窗口断言。

Parameters mirror the probe (tools/probe_part/probe_n28_unblock.py) so the
volume windows are analytic: sweep ⌀10 along an R20 90° arc → 250π²;
loft ⌀20→⌀30 sections 30mm apart → frustum πh/3·(r1²+r1r2+r2²)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solidworks_mcp.solidworks_api import file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app

SWEEP_VOL_MM3 = math.pi * 25.0 * (math.pi * 20.0 / 2.0)  # ≈ 2467.40
LOFT_VOL_MM3 = math.pi * 30.0 / 3.0 * (100.0 + 150.0 + 225.0)  # ≈ 14922.57


def _volume_mm3(sw) -> float:
    r = part.get_mass_properties(sw)
    assert r["success"], r
    return r["data"]["volume"] * 1e9


def main() -> int:
    sw = get_solidworks_app()
    assert sw.connect(launch_if_needed=True)["success"]
    ok = True

    r = part.create_swept(
        sw, diameter_mm=10.0, path_type="arc", radius_mm=20.0, angle_deg=90.0
    )
    print(
        "sweep:", r["success"],
        (r.get("data") or {}).get("feature_name"), r.get("message"),
    )
    if r["success"]:
        volume = _volume_mm3(sw)
        delta = abs(volume - SWEEP_VOL_MM3) / SWEEP_VOL_MM3
        print(f"  volume {volume:.2f} vs {SWEEP_VOL_MM3:.2f} ({delta:.3%})")
        ok = ok and delta < 0.01
    else:
        ok = False
    file_io.close_document(sw, save_changes=False)

    r = part.create_loft(
        sw, profile_diameters_mm=[20.0, 30.0], section_spacing_mm=30.0
    )
    print(
        "loft:", r["success"],
        (r.get("data") or {}).get("feature_name"), r.get("message"),
    )
    if r["success"]:
        volume = _volume_mm3(sw)
        delta = abs(volume - LOFT_VOL_MM3) / LOFT_VOL_MM3
        print(f"  volume {volume:.2f} vs {LOFT_VOL_MM3:.2f} ({delta:.3%})")
        ok = ok and delta < 0.01
    else:
        ok = False
    file_io.close_document(sw, save_changes=False)

    print("E2E N28:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
