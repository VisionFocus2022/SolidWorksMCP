"""N30 e2e: polygon/slot production tools with analytic volume windows
(contract: tools/probe_part/probe_n30_unblock.py — hexagon R10×h10 →
N/2·R²·sin(2π/N)·h = 2598.08; slot centre-line 20×width 6×h8 →
(L·W + π(W/2)²)·h = 1186.19)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app

POLY_VOL_MM3 = 6 / 2 * 100.0 * math.sin(2 * math.pi / 6) * 10.0  # ≈ 2598.08
SLOT_VOL_MM3 = (20.0 * 6.0 + math.pi * 9.0) * 8.0  # ≈ 1186.19


def _volume_mm3(sw) -> float:
    r = part.get_mass_properties(sw)
    assert r["success"], r
    return r["data"]["volume"] * 1e9


def main() -> int:
    sw = get_solidworks_app()
    assert sw.connect(launch_if_needed=True)["success"]
    ok = True

    design.create_new_part(sw)
    r = part.create_polygon(sw, sides=6, circumradius_mm=10.0, height_mm=10.0)
    print("polygon:", r["success"], (r.get("data") or {}).get("feature_name"))
    if r["success"]:
        volume = _volume_mm3(sw)
        delta = abs(volume - POLY_VOL_MM3) / POLY_VOL_MM3
        print(f"  volume {volume:.2f} vs {POLY_VOL_MM3:.2f} ({delta:.3%})")
        ok = ok and delta < 0.01
    else:
        ok = False
    file_io.close_document(sw, save_changes=False)

    design.create_new_part(sw)
    r = part.create_slot(sw, length_mm=20.0, width_mm=6.0, height_mm=8.0)
    print("slot:", r["success"], (r.get("data") or {}).get("feature_name"))
    if r["success"]:
        volume = _volume_mm3(sw)
        delta = abs(volume - SLOT_VOL_MM3) / SLOT_VOL_MM3
        print(f"  volume {volume:.2f} vs {SLOT_VOL_MM3:.2f} ({delta:.3%})")
        ok = ok and delta < 0.01
    else:
        ok = False
    file_io.close_document(sw, save_changes=False)

    print("E2E N30:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
