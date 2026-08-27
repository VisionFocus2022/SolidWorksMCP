"""Parametric design operations for SolidWorks parts."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pythoncom

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swDocPART,
    swFileSaveErrorNone,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.solidworks_api.geometry import (
    latest_feature_name as _latest_feature_name,
)
from solidworks_mcp.solidworks_api.geometry import mm_to_m, select_plane
from solidworks_mcp.solidworks_api.part import create_box, create_cylinder
from solidworks_mcp.solidworks_api.sketch import cut_feature
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import validate_output_file
from solidworks_mcp.utils.templates import get_part_template
from solidworks_mcp.utils.validation import finite_number, parse_bool, positive_number

logger = logging.getLogger(__name__)

PLANE_ALIASES = {
    "front": ["Front Plane", "前视基准面"],
    "top": ["Top Plane", "上视基准面"],
    "right": ["Right Plane", "右视基准面"],
}


def _get_active_part(sw_app: SolidWorksApp) -> Any:
    model = sw_app.get_active_document()
    if model is None or call_or_value(model, "GetType") != swDocPART:
        raise RuntimeError("No active part document")
    return model


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

    save_result = model.SaveAs3(save_path, 0, swSaveAsOptions_Silent)
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
        selected_plane = _select_plane(model, plane)
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


def execute_design_plan(
    sw_app: SolidWorksApp,
    operations: List[Dict[str, Any]],
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Execute a small ordered design plan made of supported operations."""
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

    results: List[dict] = []
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
            elif op_type == "new_part":
                result = create_new_part(sw_app)
            else:
                return error_response(
                    f"Unsupported operation at index {index}: {op_type}. "
                    "Supported types: new_part, box, plate, cylinder, hole."
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
            return error_response(
                f"Design plan stopped at operation {index}: {result.get('message')}",
                data={"completed": results},
            )

    active = sw_app.get_active_document()
    if active is not None and save_path:
        save_error = _save_active_model(active, save_path, overwrite_confirm, {})
        if save_error:
            return save_error

    return success_response(
        data={"operations": results, "saved_to": save_path},
        message=f"Executed {len(operations)} design operations",
    )
