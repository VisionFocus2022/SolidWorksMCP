"""Parametric design operations for SolidWorks parts."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import pythoncom

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    THREAD_SPECS,
    swDocPART,
    swFileSaveErrorNone,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.solidworks_api.geometry import (
    latest_feature_name as _latest_feature_name,
)
from solidworks_mcp.solidworks_api.geometry import (
    mm_to_m,
    select_plane,
    walk_feature_names,
)
from solidworks_mcp.solidworks_api.part import (
    create_box,
    create_cone,
    create_cylinder,
)
from solidworks_mcp.solidworks_api.sketch import cut_feature
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import ensure_sink_path, validate_output_file
from solidworks_mcp.utils.templates import get_part_template
from solidworks_mcp.utils.validation import finite_number, parse_bool, positive_number

logger = logging.getLogger(__name__)

PLANE_ALIASES = {
    "front": ["Front Plane", "前视基准面"],
    "top": ["Top Plane", "上视基准面"],
    "right": ["Right Plane", "右视基准面"],
}

# Hole-feature sketch planes: everything this repo models grows +Z from
# a Front-Plane sketch (part.PLANE_CANDIDATES: box/plate/cylinder/cone),
# so the "top" of such a part is its +Z face and a hole asked for plane
# "top" must be drilled along Z through that face. Resolving "top" to
# SW's native Top Plane (XZ sketch, Y normal) instead drills sideways
# through the plate flank -- verified on the real machine
# (tools/probe_hole_plane_context.py: a requested top hole landed
# axis -Y on the y=+40 flank, and 4 of 6 annular holes missed the
# plate entirely). Same form as aicad channel B (sw_rebuild.py
# real-machine contract: front-plane sketch + cut Dir=True).
HOLE_PLANE_ALIASES = {
    "front": ["Front Plane", "前视基准面"],
    "top": ["Front Plane", "前视基准面"],
    "right": ["Right Plane", "右视基准面"],
}


def _hole_sketch_plane(plane: str) -> str:
    """User-facing hole-plane alias -> the SW plane the sketch lands on."""
    key = plane.strip().lower()
    return "front" if key in ("top", "front") else key


def _get_active_part(sw_app: SolidWorksApp) -> Any:
    model = sw_app.get_active_document()
    if model is None or call_or_value(model, "GetType") != swDocPART:
        raise RuntimeError("No active part document")
    return model


def _select_hole_plane(model: Any, plane: str) -> Optional[str]:
    """Resolve a hole-plane alias (top means the +Z face, see above)."""
    candidates = HOLE_PLANE_ALIASES.get(plane.lower(), [plane])
    return select_plane(model, candidates)


def _select_plane(model: Any, plane: str) -> Optional[str]:
    candidates = PLANE_ALIASES.get(plane.lower(), [plane])
    return select_plane(model, candidates)


def _save_active_model(
    model: Any,
    save_path: Optional[str],
    overwrite_confirm: bool,
    result: Dict[str, Any],
) -> Optional[dict]:
    if not save_path:
        return None

    allowed, msg = validate_output_file(save_path, {".sldprt"}, overwrite_confirm)
    if not allowed:
        return error_response(msg, code="INVALID_OUTPUT_PATH")

    ok, message, sink_path = ensure_sink_path(save_path)
    if not ok:
        return error_response(message, code="INVALID_OUTPUT_PATH")
    save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
    if save_result != swFileSaveErrorNone:
        return error_response(f"SaveAs3 failed with code {save_result}")
    result["saved_to"] = save_path
    return None


def create_new_part(
    sw_app: SolidWorksApp,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a blank part document using the configured SolidWorks template."""
    try:
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")
        template = get_part_template()
        if not template:
            return error_response("Could not find a valid SolidWorks part template (.prtdot)")

        model = sw_app.app.NewDocument(template, 0, 0, 0)
        if model is None:
            return error_response("NewDocument returned None")

        data: Dict[str, Any] = {
            "title": call_or_value(model, "GetTitle"),
            "template": template,
        }
        save_error = _save_active_model(model, save_path, overwrite_confirm, data)
        if save_error:
            return save_error

        return success_response(data=data, message="Created new part document")
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to create new part")
        return error_response(f"Failed to create new part: {exc}")


def create_plate(
    sw_app: SolidWorksApp,
    width: float,
    depth: float,
    thickness: float,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a rectangular plate using width/depth/thickness in millimeters."""
    try:
        width = positive_number("width", width)
        depth = positive_number("depth", depth)
        thickness = positive_number("thickness", thickness)
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    return create_box(sw_app, width, depth, thickness, save_path, overwrite_confirm)


def cut_round_hole(
    sw_app: SolidWorksApp,
    diameter: float,
    x: float,
    y: float,
    plane: str = "top",
    depth: Optional[float] = None,
    through_all: bool = True,
) -> dict:
    """Cut a round hole from a named base plane or user-supplied plane name."""
    try:
        diameter = positive_number("diameter", diameter)
        x = finite_number("x", x)
        y = finite_number("y", y)
        through_all = parse_bool("through_all", through_all)
        if not isinstance(plane, str) or not plane.strip():
            return error_response("plane must be a non-empty string", code="INVALID_PARAMETER")
        if not through_all:
            if depth is None:
                return error_response(
                    "depth is required when through_all is False",
                    code="INVALID_PARAMETER",
                )
            depth = positive_number("depth", depth)

        model = _get_active_part(sw_app)
        selected_plane = _select_hole_plane(model, plane)
        if selected_plane is None:
            return error_response(f"Could not select plane: {plane}")

        radius = mm_to_m(diameter) / 2.0
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateCircleByRadius(mm_to_m(x), mm_to_m(y), 0, radius)
        model.SketchManager.InsertSketch(True)

        sketch_name = _latest_feature_name(model)
        if not sketch_name:
            return error_response("Could not identify the hole sketch")

        model.ClearSelection2(True)
        selected = model.Extension.SelectByID2(
            sketch_name,
            "SKETCHCONTOUR",
            0,
            0,
            0,
            True,
            4,
            pythoncom.Nothing,
            0,
        )
        if not selected:
            selected = model.Extension.SelectByID2(
                sketch_name,
                "SKETCH",
                0,
                0,
                0,
                False,
                0,
                pythoncom.Nothing,
                0,
            )
        if not selected:
            return error_response(f"Could not select hole sketch: {sketch_name}")

        cut_depth = mm_to_m(diameter if depth is None else depth)
        end_condition = 1 if through_all else 0
        feature = cut_feature(model, True, through_all, end_condition, cut_depth)
        if feature is None:
            return error_response("Cut feature creation failed")

        return success_response(
            data={
                "feature_name": feature.Name,
                "diameter": diameter,
                "center": [x, y],
                "plane": selected_plane,
                "through_all": through_all,
                "depth": None if through_all else depth,
            },
            message="Created round cut hole",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to cut round hole")
        return error_response(f"Failed to cut round hole: {exc}")


# Through-all hole mouths sit at unknown distances along the sketch-plane
# normal (they meet the part surfaces, not the sketch plane), so the
# coordinate-based EDGE pick sweeps these offsets in metres.
_NORMAL_OFFSETS_THROUGH_ALL_M = (
    0.0, 0.002, -0.002, 0.005, -0.005, 0.01, -0.01,
    0.02, -0.02, 0.04, -0.04, 0.08, -0.08, 0.16, -0.16, 0.32, -0.32,
)


def _mouth_point_model_coords(
    x_m: float, y_m: float, plane: str, normal_m: float
) -> tuple:
    """Map the 45-degree sketch-space mouth point into MODEL coordinates.

    Sketch (x, y) live on the named base plane; SelectByID2 wants model
    (X, Y, Z). Blind-hole mouths sit on the sketch plane itself (offset 0);
    through-all mouths sit wherever the hole meets the part surfaces.
    """
    key = plane.strip().lower()
    if key == "top":  # sketch x->X, sketch y->Z, normal along Y
        return (x_m, normal_m, y_m)
    if key == "right":  # sketch x->Y, sketch y->Z, normal along X
        return (normal_m, x_m, y_m)
    # front (and unknown planes): sketch x->X, sketch y->Y, normal along Z
    return (x_m, y_m, normal_m)


def _stamp_cosmetic_thread(
    model: Any,
    spec: str,
    drill_diameter: float,
    x: float,
    y: float,
    depth: Optional[float],
    plane: str = "front",
) -> bool:
    """Best-effort cosmetic thread on the hole-mouth edge (never fatal).

    The circular edge is picked by coordinates at 45 degrees off the
    sketch axes, mapped into model space for the sketch plane (real-machine
    probe contract); the major diameter comes from the spec name itself
    ("M8" -> 8 mm). The created feature is NOT enumerable over
    FirstFeature/GetNextFeature, so callers must verify via the returned
    boolean, never via a tree walk.
    """
    radius_m = mm_to_m(drill_diameter) / 2.0
    diagonal = radius_m * math.cos(math.pi / 4.0)
    # Blind holes carry their real depth; through holes fall back to the
    # nominal diameter as a conservative annotation length.
    major_m = float(spec[1:]) / 1000.0
    depth_m = mm_to_m(depth) if depth else major_m
    note = f"{spec}x{THREAD_SPECS[spec][1]:g}"
    sx = mm_to_m(x) + diagonal
    sy = mm_to_m(y) + diagonal
    offsets = (0.0,) if depth else _NORMAL_OFFSETS_THROUGH_ALL_M
    sketch_plane = _hole_sketch_plane(plane)
    model.ClearSelection2(True)
    picked = False
    for offset in offsets:
        px, py, pz = _mouth_point_model_coords(sx, sy, sketch_plane, offset)
        picked = model.Extension.SelectByID2(
            "",
            "EDGE",
            px,
            py,
            pz,
            False,
            0,
            pythoncom.Nothing,
            0,
        )
        if picked:
            break
    if not picked:
        logger.debug("thread mouth edge for %s not selected", spec)
        return False
    try:
        created = model.FeatureManager.InsertCosmeticThread2(
            0,
            major_m,
            depth_m,
            note,
        )
    except Exception:
        logger.debug("InsertCosmeticThread2 failed", exc_info=True)
        return False
    return created is not None


def cut_threaded_hole(
    sw_app: SolidWorksApp,
    spec: str,
    x: float,
    y: float,
    plane: str = "top",
    depth: Optional[float] = None,
    through_all: bool = True,
) -> dict:
    """Cut an ISO coarse-thread hole at its tap-drill diameter with a cosmetic thread.

    The hole itself is a plain ``cut_round_hole`` at the ISO 273 tap-drill
    diameter; the thread is stamped as a best-effort cosmetic annotation
    (HoleWizard requires interactive panels this channel cannot drive).
    """
    try:
        if not isinstance(spec, str) or not spec.strip():
            return error_response(
                "spec must be a non-empty string like 'M6'",
                code="INVALID_PARAMETER",
            )
        spec_key = spec.strip().upper()
        thread_spec = THREAD_SPECS.get(spec_key)
        if thread_spec is None:
            supported = ", ".join(sorted(THREAD_SPECS))
            return error_response(
                f"Unsupported thread spec: {spec}. Supported: {supported}",
                code="INVALID_PARAMETER",
            )
        drill_diameter, pitch = thread_spec

        cut = cut_round_hole(sw_app, drill_diameter, x, y, plane, depth, through_all)
        if not cut.get("success"):
            return cut

        stamped = _stamp_cosmetic_thread(
            _get_active_part(sw_app), spec_key, drill_diameter, x, y, depth, plane
        )

        data: Dict[str, Any] = dict(cut.get("data") or {})
        data["thread"] = {
            "spec": spec_key,
            "tap_drill_diameter": drill_diameter,
            "pitch": pitch,
            "cosmetic_thread_stamped": stamped,
        }
        return success_response(
            data=data,
            message=(
                f"Created {spec_key} threaded hole "
                f"(tap drill {drill_diameter}mm on plane {plane})"
            ),
            warning=(
                None
                if stamped
                else "Cosmetic thread annotation was skipped (hole mouth edge not selectable)."
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to cut threaded hole")
        return error_response(f"Failed to cut threaded hole: {exc}")


def execute_design_plan(
    sw_app: SolidWorksApp,
    operations: List[Dict[str, Any]],
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    atomic: bool = True,
) -> dict:
    """Execute a small ordered design plan made of supported operations.

    With ``atomic=True`` (default) any failed operation triggers a rollback:
    features added since the plan started are deleted in reverse tree order,
    so retrying a plan never stacks half-applied features. Rollback failures
    never mask the original error — they surface as ``rollback_warning``.
    """
    if not operations:
        return error_response(
            "operations must contain at least one operation",
            code="INVALID_PARAMETER",
        )
    if not isinstance(operations, list):
        return error_response("operations must be a list", code="INVALID_PARAMETER")
    if save_path:
        valid, message = validate_output_file(
            save_path, {".sldprt"}, overwrite_confirm
        )
        if not valid:
            return error_response(message, code="INVALID_OUTPUT_PATH")

    initial_model = sw_app.get_active_document()
    before = _snapshot_feature_names(initial_model)
    results: List[dict] = []
    applied: List[int] = []
    for index, operation in enumerate(operations, start=1):
        try:
            if not isinstance(operation, dict):
                return error_response(
                    f"Operation {index} must be an object",
                    code="INVALID_PARAMETER",
                )
            op_type = str(operation.get("type", "")).lower()
            if op_type in {"box", "block", "plate"}:
                thickness = operation.get("thickness", operation.get("height"))
                if thickness is None:
                    return error_response(
                        f"Operation {index} requires thickness or height"
                    )
                result = create_plate(
                    sw_app,
                    float(operation["width"]),
                    float(operation["depth"]),
                    float(thickness),
                )
            elif op_type == "cylinder":
                result = create_cylinder(
                    sw_app,
                    float(operation["diameter"]),
                    float(operation["height"]),
                )
            elif op_type in {"hole", "round_hole", "cut_hole"}:
                result = cut_round_hole(
                    sw_app,
                    diameter=float(operation["diameter"]),
                    x=float(operation.get("x", 0.0)),
                    y=float(operation.get("y", 0.0)),
                    plane=str(operation.get("plane", "top")),
                    depth=(
                        None
                        if operation.get("depth") is None
                        else float(operation.get("depth"))
                    ),
                    through_all=parse_bool(
                        "through_all", operation.get("through_all", True)
                    ),
                )
            elif op_type == "cone":
                result = create_cone(
                    sw_app,
                    float(operation["bottom_diameter"]),
                    float(operation.get("top_diameter", 0.0)),
                    float(operation["height"]),
                )
            elif op_type in {"threaded_hole", "thread_hole"}:
                result = cut_threaded_hole(
                    sw_app,
                    spec=str(operation["spec"]),
                    x=float(operation.get("x", 0.0)),
                    y=float(operation.get("y", 0.0)),
                    plane=str(operation.get("plane", "top")),
                    depth=(
                        None
                        if operation.get("depth") is None
                        else float(operation.get("depth"))
                    ),
                    through_all=parse_bool(
                        "through_all", operation.get("through_all", True)
                    ),
                )
            elif op_type in {"annular_pattern", "ring_pattern"}:
                # Imported here (not at module top) because pattern.py itself
                # imports plane aliases and save helpers from this module.
                from solidworks_mcp.solidworks_api.pattern import create_annular_pattern

                rings = operation.get("rings")
                if not isinstance(rings, list) or not rings:
                    return error_response(
                        f"Operation {index} requires a non-empty 'rings' list",
                        code="INVALID_PARAMETER",
                    )
                result = create_annular_pattern(
                    sw_app,
                    rings,
                    plane=str(operation.get("plane", "top")),
                    feature_kind=str(operation.get("feature_kind", "cut")),
                    depth=(
                        None
                        if operation.get("depth") is None
                        else float(operation.get("depth"))
                    ),
                    through_all=parse_bool(
                        "through_all", operation.get("through_all", True)
                    ),
                    avoid_angles_degrees=operation.get("avoid_angles_degrees"),
                )
            elif op_type == "new_part":
                result = create_new_part(sw_app)
            else:
                return error_response(
                    f"Unsupported operation at index {index}: {op_type}. "
                    "Supported types: new_part, box, plate, cylinder, cone, "
                    "hole, threaded_hole, annular_pattern."
                )
        except KeyError as exc:
            return error_response(
                f"Operation {index} is missing required key: {exc}",
                code="INVALID_PARAMETER",
            )
        except (TypeError, ValueError) as exc:
            return error_response(
                f"Operation {index} has invalid parameter values: {exc}",
                code="INVALID_PARAMETER",
            )

        results.append({"index": index, "operation": op_type, "result": result})
        if not result.get("success"):
            data = {
                "completed": results,
                "applied": applied,
                "failed": index,
                "rolled_back": None,
            }
            if atomic:
                rolled_back, warning = _delete_new_features(sw_app, before)
                data["rolled_back"] = rolled_back
                if warning:
                    data["rollback_warning"] = warning
            return error_response(
                f"Design plan stopped at operation {index}: {result.get('message')}",
                data=data,
            )
        applied.append(index)

    active = sw_app.get_active_document()
    if active is not None and save_path:
        save_error = _save_active_model(active, save_path, overwrite_confirm, {})
        if save_error:
            return save_error

    return success_response(
        data={"operations": results, "saved_to": save_path},
        message=f"Executed {len(operations)} design operations",
    )


def _snapshot_feature_names(model: Optional[Any]) -> set:
    """Snapshot the feature-name set for later diffing (atomic plans)."""
    if model is None:
        return set()
    return set(walk_feature_names(model))


_ROLLBACK_LIST_CAP = 200  # keep responses/logs bounded under pathological trees


def _cap_names(names: List[str]) -> List[str]:
    if len(names) > _ROLLBACK_LIST_CAP:
        return names[:_ROLLBACK_LIST_CAP] + [f"…and {len(names) - _ROLLBACK_LIST_CAP} more"]
    return names


def _delete_new_features(
    sw_app: SolidWorksApp, before: set
) -> tuple:
    """Delete every feature added after the snapshot, in reverse tree order.

    Selection tries BODYFEATURE first and SKETCH second — real-machine
    evidence (T10): a plate step creates a sketch plus an extrusion, and
    SelectByID2 only resolves sketches under the "SKETCH" type (an empty
    type string does not wildcard).
    Returns ``(deleted_names, warning)``; both are capped so a pathological
    tree cannot explode the response payload; the warning never masks the
    original plan error.
    """
    deleted: List[str] = []
    try:
        model = sw_app.get_active_document()
        if model is None:
            return deleted, None
        new_names = [n for n in walk_feature_names(model) if n not in before]
        for name in reversed(new_names):
            picked = False
            for type_string in ("BODYFEATURE", "SKETCH"):
                model.ClearSelection2(True)
                picked = model.Extension.SelectByID2(
                    name, type_string, 0, 0, 0, False, 0, pythoncom.Nothing, 0
                )
                if picked:
                    break
            if not picked:
                continue
            call_or_value(model, "EditDelete")
            deleted.append(name)
        remaining = [n for n in walk_feature_names(model) if n not in before]
        warning = (
            "rollback incomplete, "
            f"{len(remaining)} feature(s) left in tree: {_cap_names(remaining)}"
            if remaining
            else None
        )
        return _cap_names(deleted), warning
    except Exception as exc:
        logger.exception("Design-plan rollback failed")
        return _cap_names(deleted), f"rollback error: {exc}"
