"""N32 e2e: BOM table production tool on a two-component assembly drawing
(full chain: two parts -> fixed add_component x2 -> A3 drawing ->
drawing.insert_bom_table -> PDF lands; balloons BLOCKED — probe header)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom

from solidworks_mcp.solidworks_api import assembly, design, drawing, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.drawing import FRONT_XY, _resolve_template

OUT = Path(__file__).resolve().parents[1] / "output" / "n32_e2e"


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
    for p in (OUT / "box20.sldprt", OUT / "cyl10.sldprt"):
        r = assembly.add_component(sw, str(p))
        assert r["success"], r
    components = assembly.get_components(sw)["data"]["components"]
    print(f"asm components: {components}")
    assert len(components) == 2, components  # N32 add_component fix
    asm_path = str(OUT / "asm.sldasm")
    file_io.close_document(sw, save_changes=False)

    template = _resolve_template(sw.app)
    dwg = sw.app.NewDocument(template, 12, 0.0, 0.0)
    assert dwg is not None
    assert dwg.CreateDrawViewFromModelView3(
        os.path.abspath(asm_path), "", FRONT_XY[0], FRONT_XY[1], 0.0
    ) is not None
    model = sw.get_active_document()

    r = drawing.insert_bom_table(
        sw, view_name="工程图视图1", x_mm=240.0, y_mm=20.0
    )
    print("bom table:", r["success"], r.get("message"))
    ok = r["success"]

    pdf = OUT / "asm_bom.pdf"
    model.SaveAs3(str(pdf), 0, 1)
    size = pdf.stat().st_size if pdf.exists() else 0
    print(f"pdf: {size}B")
    ok = ok and size > 10_000
    file_io.close_document(sw, save_changes=False)
    print("E2E N32:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
