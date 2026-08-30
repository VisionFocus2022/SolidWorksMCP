"""N11: acceptance checklist #5 — triple artifact (views.svg + .sldprt + .step).

Same ring script drives both engines (single command, real machine with
SolidWorks open):

    1. subprocess (aicad venv): exec the ring script with build123d, export
       the BRep, run the sandbox HLR entry (``project_brep_to_json``) and
       ``render_sheet`` -> ``ring.svg``; also emit the CSG v1 contract JSON
       (same exporter the /api/sw/csg route serves).
    2. main repo: ``design.rebuild_csg_plan`` rebuilds the SW feature tree,
       the model is saved as ``ring.sldprt`` and exported as ``ring.step``.

Assertions (exit 0 only when ALL pass):
    * ``ring.svg`` exists, non-empty, polyline layer present (``<path`` in
      the SVG and ``stats.edge_count > 0``);
    * ``ring.sldprt`` saved (SaveAs3 via ``_save_active_model``);
    * ``ring.step`` exported (``export_step`` success, non-empty file).

Run:  venv\\Scripts\\python.exe -X utf8 tools\\validate\\triple_artifact.py
Exit: 0 all three artifacts verified · 1 an assertion failed ·
      2 SW connect failed · 3 a stage failed.
Report: output/triple-artifact-<ts>/report.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from solidworks_mcp.solidworks_api.app import get_solidworks_app  # noqa: E402
from solidworks_mcp.solidworks_api.design import (  # noqa: E402
    _save_active_model,
    rebuild_csg_plan,
)
from solidworks_mcp.solidworks_api.file_io import export_step  # noqa: E402

AICAD_PY = os.path.join(ROOT, "aicad", "venv", "Scripts", "python.exe")
OUTPUT_DIR = os.path.join(ROOT, "output")

# Same ring as csg_roundtrip.py so both scripts verify one geometry and the
# reports stay comparable.
RING_SCRIPT = '''from build123d import *
PARAMS = {"od": 60.0, "id": 40.0, "t": 8.0}

def build():
    p = PARAMS
    ring = Cylinder(p["od"] / 2, p["t"])
    ring.label = "ring"
    bore = Cylinder(p["id"] / 2, p["t"] + 2)
    return ring - bore
'''

# Generator executed inside the aicad venv: drawing SVG + CSG contract.
# argv[1] is the report directory; the ring script arrives on stdin.
GENERATOR = '''
import json, os, sys
sys.path.insert(0, r"{root}/aicad")
from build123d import export_brep
from aicad.drawing.hlr import (
    load_views,
    project_brep_to_json,
    render_sheet,
)
from aicad.interop.sw_features.csg_export import csg_plan_from_script

workdir = sys.argv[1]
src = sys.stdin.read()
ns = {{}}
exec(src, ns)
shape = ns["build"]()

brep = os.path.join(workdir, "model.brep")
views_json = os.path.join(workdir, "views.json")
export_brep(shape, brep)
project_brep_to_json(brep, views_json)
views = load_views(views_json)
bb = shape.bounding_box()
size = [bb.max.X - bb.min.X, bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z]
svg, stats = render_sheet(views, size)
with open(os.path.join(workdir, "ring.svg"), "wb") as fh:
    fh.write(svg)
plan = csg_plan_from_script(src)
print(json.dumps({{"stats": stats, "plan": plan}}))
'''


def _aicad_side(out_dir: str) -> dict:
    """Run the generator in the aicad venv; returns its JSON payload."""
    gen_path = os.path.join(tempfile.gettempdir(), "triple_gen.py")
    with open(gen_path, "w", encoding="utf-8") as fh:
        fh.write(GENERATOR.format(root=ROOT.replace("\\", "\\\\")))
    proc = subprocess.run(
        [AICAD_PY, "-X", "utf8", gen_path, out_dir],
        input=RING_SCRIPT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-2000:])
        raise RuntimeError(f"aicad generator failed ({proc.returncode})")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> int:
    ts = datetime.now()
    out_dir = os.path.join(OUTPUT_DIR, f"triple-artifact-{ts:%Y%m%d-%H%M%S}")
    os.makedirs(out_dir, exist_ok=True)
    report: dict = {"tool": "triple_artifact", "ts": ts.isoformat(), "dir": out_dir}

    try:
        payload = _aicad_side(out_dir)
    except Exception as exc:
        report.update({"stage": "aicad", "ok": False, "error": str(exc)})
        _write(report)
        return 3

    plan = payload["plan"]
    stats = payload["stats"]

    # --- Artifact 1: views.svg exists with a non-empty polyline layer ----
    svg_path = os.path.join(out_dir, "ring.svg")
    try:
        with open(svg_path, encoding="utf-8") as fh:
            svg_text = fh.read()
        svg_ok = (
            len(svg_text) > 0
            and "<path" in svg_text
            and int(stats.get("edge_count", 0)) > 0
        )
    except OSError:
        svg_ok = False
    report["views_svg"] = {"path": svg_path, "stats": stats, "ok": svg_ok}

    sw = get_solidworks_app()
    conn = sw.connect(launch_if_needed=False)
    if not conn.get("success"):
        report.update({"stage": "connect", "ok": False, "error": conn.get("message")})
        _write(report)
        return 2
    try:
        sw.app.CloseAllDocuments(True)
    except Exception:
        pass

    rebuilt = rebuild_csg_plan(sw, plan)
    report["rebuild"] = rebuilt
    if not rebuilt.get("success"):
        report.update({"stage": "rebuild", "ok": False})
        _write(report)
        return 3

    # --- Artifact 2: .sldprt saved through SaveAs3 -----------------------
    sldprt_path = os.path.join(out_dir, "ring.sldprt")
    data: dict = {}
    save_error = _save_active_model(
        model=sw.get_active_document(),
        save_path=sldprt_path,
        overwrite_confirm=True,
        result=data,
    )
    sldprt_ok = (
        save_error is None
        and bool(data.get("saved_to"))
        and os.path.isfile(sldprt_path)
        and os.path.getsize(sldprt_path) > 0
    )
    report["sldprt"] = {"path": sldprt_path, "ok": sldprt_ok}

    # --- Artifact 3: .step exported --------------------------------------
    step_path = os.path.join(out_dir, "ring.step")
    step = export_step(sw, step_path, overwrite_confirm=True)
    step_ok = (
        bool(step.get("success"))
        and os.path.isfile(step_path)
        and os.path.getsize(step_path) > 0
    )
    report["step"] = {
        "path": step_path,
        "ok": step_ok,
        "message": step.get("message"),
    }

    report["ok"] = bool(svg_ok and sldprt_ok and step_ok)
    _write(report)
    try:
        sw.app.CloseAllDocuments(True)
    except Exception:
        pass
    return 0 if report["ok"] else 1


def _write(report: dict) -> None:
    path = os.path.join(report["dir"], "report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    print(f"报告：{path}")


if __name__ == "__main__":
    sys.exit(main())
