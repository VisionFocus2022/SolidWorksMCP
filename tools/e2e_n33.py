"""N33 e2e: assembly.explode production tool on a two-component assembly
(contract: tools/probe_assembly/probe_n33_explode.py — AutoExplode builds
an automatic exploded view; drawing projection via the empty-string
configuration works, exploded-state projection is an observed follow-up)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solidworks_mcp.solidworks_api import assembly, design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app

OUT = Path(__file__).resolve().parents[1] / "output" / "n33_e2e"


def main() -> int:
    sw = get_solidworks_app()
    assert sw.connect(launch_if_needed=True)["success"]
    try:
        sw.app.CloseAllDocuments(True)
    except Exception:
        pass
    OUT.mkdir(exist_ok=True)

    for name, builder in (
        ("box20", lambda: part.create_box(
            sw, 40.0, 30.0, 10.0, save_path=str(OUT / "box20.sldprt"),
            overwrite_confirm=True)),
        ("cyl10", lambda: part.create_cylinder(
            sw, 16.0, 25.0, save_path=str(OUT / "cyl10.sldprt"),
            overwrite_confirm=True)),
    ):
        assert design.create_new_part(sw)["success"], name
        assert builder()["success"], name
        file_io.close_document(sw, save_changes=False)

    assert assembly.new_assembly(
        sw, save_path=str(OUT / "asm.sldasm"), overwrite_confirm=True
    )["success"]
    assert assembly.add_component(sw, str(OUT / "box20.sldprt"))["success"]
    assert assembly.add_component(
        sw, str(OUT / "cyl10.sldprt"), x=60.0, y=0.0, z=10.0
    )["success"]

    r = assembly.explode(sw)
    print("explode:", r["success"], (r.get("data") or {}))
    ok = (
        r["success"]
        and r["data"]["count"] >= 1
        and r["data"]["explode_views"]
    )
    file_io.close_document(sw, save_changes=False)
    print("E2E N33:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
