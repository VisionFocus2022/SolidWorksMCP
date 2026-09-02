"""N11: cross-engine CSG round-trip — aicad kernel <-> SolidWorks rebuild.

Pipeline (single command, real machine with SolidWorks open):

    1. subprocess (aicad venv): exec the ring script with build123d for the
       kernel ground-truth volume, and run ``csg_plan_from_script`` for the
       CSG v1 contract JSON (same exporter the /api/sw/csg route serves).
    2. main repo: ``design.rebuild_csg_plan`` rebuilds the plan as an SW
       feature tree; ``get_mass_properties`` yields the SW volume.
    3. volumes are compared within +/-1% (M5 volume gate).

Run:  venv\\Scripts\\python.exe -X utf8 tools\\validate\\csg_roundtrip.py
Exit: 0 pass · 1 volume mismatch · 2 SW connect failed · 3 stage failure.
Report: output/csg-roundtrip-<ts>.json
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
from solidworks_mcp.solidworks_api.design import rebuild_csg_plan  # noqa: E402
from solidworks_mcp.solidworks_api.part import get_mass_properties  # noqa: E402

AICAD_PY = os.path.join(ROOT, "aicad", "venv", "Scripts", "python.exe")
OUTPUT_DIR = os.path.join(ROOT, "output")
VOLUME_TOLERANCE = 0.01

# Ring (annular plate): build123d source inside the CSG v1 subset —
# centred Cylinder boss minus a taller centred Cylinder bore (through cut).
RING_SCRIPT = '''from build123d import *
PARAMS = {"od": 60.0, "id": 40.0, "t": 8.0}

def build():
    p = PARAMS
    ring = Cylinder(p["od"] / 2, p["t"])
    ring.label = "ring"
    bore = Cylinder(p["id"] / 2, p["t"] + 2)
    return ring - bore
'''

# N31 v2 case: contract-2 polygon_prism. The plan is supplied directly
# (the channel-B AST exporter does not parse profile+extrude pairs yet),
# so the kernel side only contributes the ground-truth volume.
HEX_SCRIPT = '''from build123d import *
PARAMS = {"sides": 6, "r": 10.0, "h": 8.0}

def build():
    p = PARAMS
    with BuildPart() as part:
        with BuildSketch():
            RegularPolygon(p["r"], p["sides"])
        extrude(amount=p["h"])
    return part.part
'''

HEX_PLAN = {
    "version": 2,
    "units": "mm",
    "operations": [
        {"op": "polygon_prism", "name": "nut", "sides": 6,
         "circumradius": 10.0, "height": 8.0, "at": [0.0, 0.0, 0.0]},
    ],
}

CASES = [
    # (name, build123d script, preset plan or None=export via csg_plan_from_script)
    ("ring_v1_export", RING_SCRIPT, None),
    ("hex_v2_direct", HEX_SCRIPT, HEX_PLAN),
]

# Generator executed inside the aicad venv: kernel volume + CSG contract.
# stdin: {"script": str, "plan": dict | None} — a preset plan skips the
# exporter (v2 ops are rebuild-direction only, docs/csg-plan-v1.md §v2).
GENERATOR = '''
import json, sys
sys.path.insert(0, r"{root}/aicad")
from aicad.interop.sw_features.csg_export import csg_plan_from_script

req = json.loads(sys.stdin.read())
ns = {{}}
exec(req["script"], ns)
shape = ns["build"]()
plan = req.get("plan")
if plan is None:
    plan = csg_plan_from_script(req["script"])
print(json.dumps({{"kernel_volume_mm3": shape.volume, "plan": plan}}))
'''


def _aicad_side(script: str, preset_plan) -> dict:
    """Run the generator in the aicad venv; returns its JSON payload."""
    gen_path = os.path.join(tempfile.gettempdir(), "csg_rt_gen.py")
    with open(gen_path, "w", encoding="utf-8") as fh:
        fh.write(GENERATOR.format(root=ROOT.replace("\\", "\\\\")))
    proc = subprocess.run(
        [AICAD_PY, "-X", "utf8", gen_path],
        input=json.dumps({"script": script, "plan": preset_plan}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-2000:])
        raise RuntimeError(f"aicad generator failed ({proc.returncode})")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _run_case(sw, name, script, preset_plan):
    """One aicad->SW round-trip case; returns the per-case report dict."""
    case = {"case": name}
    try:
        payload = _aicad_side(script, preset_plan)
    except Exception as exc:
        case.update({"stage": "aicad", "ok": False, "error": str(exc)})
        return case

    plan = payload["plan"]
    kernel_mm3 = float(payload["kernel_volume_mm3"])
    case["plan"] = plan
    case["kernel_volume_mm3"] = kernel_mm3

    rebuilt = rebuild_csg_plan(sw, plan)
    case["rebuild"] = {k: rebuilt.get(k) for k in ("success", "message", "data")}
    if not rebuilt.get("success"):
        case.update({"stage": "rebuild", "ok": False})
        return case

    mass = get_mass_properties(sw)
    sw_mm3 = float(mass["data"]["volume"]) * 1e9
    rel = abs(sw_mm3 - kernel_mm3) / kernel_mm3
    case.update(
        {
            "stage": "compare",
            "sw_volume_mm3": sw_mm3,
            "rel_diff": rel,
            "tolerance": VOLUME_TOLERANCE,
            "ok": rel <= VOLUME_TOLERANCE,
        }
    )
    return case


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = {
        "tool": "csg_roundtrip",
        "ts": datetime.now().isoformat(),
        "cases": [],
    }

    sw = get_solidworks_app()
    conn = sw.connect(launch_if_needed=False)
    if not conn["success"]:
        report.update({"stage": "connect", "ok": False, "error": conn.get("message")})
        _write(report)
        return 2

    exit_code = 0
    for name, script, preset_plan in CASES:
        try:
            sw.app.CloseAllDocuments(True)
        except Exception:
            pass
        case = _run_case(sw, name, script, preset_plan)
        report["cases"].append(case)
        if not case.get("ok"):
            exit_code = max(exit_code, 3)
        print(f"[{name}] {'OK' if case.get('ok') else 'FAIL'} ({case.get('stage')})")

    try:
        sw.app.CloseAllDocuments(True)
    except Exception:
        pass
    _write(report)
    return exit_code


def _write(report: dict) -> None:
    path = os.path.join(
        OUTPUT_DIR, f"csg-roundtrip-{datetime.now():%Y%m%d-%H%M%S}.json"
    )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"报告：{path}")


if __name__ == "__main__":
    sys.exit(main())
