"""Part-level SolidWorks operations."""

from __future__ import annotations

import logging
from typing import Any, Optional

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swDocPART,
    swFileSaveErrorNone,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.solidworks_api.geometry import mm_to_m, select_plane
from solidworks_mcp.solidworks_api.sketch import extrude_boss
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import normalize_path, validate_output_file
from solidworks_mcp.utils.templates import get_part_template
from solidworks_mcp.utils.validation import positive_number

logger = logging.getLogger(__name__)


def _get_or_create_part(sw_app: SolidWorksApp) -> tuple[Any, bool]:
    """Return the active part document, creating a new one if necessary.

    Returns:
        (model_doc, was_created)
    """
    model = sw_app.get_active_document()
    if model is not None and call_or_value(model, "GetType") == swDocPART:
        return model, False

    template = get_part_template()
    if not template:
        raise RuntimeError("Could not find a valid SolidWorks part template (.prtdot)")

    model = sw_app.app.NewDocument(template, 0, 0, 0)
    if model is None:
        raise RuntimeError("NewDocument returned None")
    return model, True


PLANE_CANDIDATES = ["Front Plane", "前视基准面"]


def _select_plane(model: Any) -> Optional[str]:
    """Select a reference plane by common Chinese/English names."""
    return select_plane(model, PLANE_CANDIDATES, use_extension_fallback=False)


def _create_circle_sketch(model: Any, radius: float) -> None:
    """Create a circle sketch on the currently selected plane."""
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCircleByRadius(0, 0, 0, radius)
    model.SketchManager.InsertSketch(True)


def _create_rectangle_sketch(
    model: Any,
    width: float,
    depth: float,
) -> None:
    """Create a rectangle sketch centered at origin."""
    model.SketchManager.InsertSketch(True)
    half_w = width / 2.0
    half_d = depth / 2.0
    # Create a rectangle by corners: (-w/2, -d/2) to (w/2, d/2)
    model.SketchManager.CreateCornerRectangle(
        -half_w, -half_d, 0,
        half_w, half_d, 0,
    )
    model.SketchManager.InsertSketch(True)


def _extrude_sketch(model: Any, height: float) -> Any:
    """Extrude the active sketch by the given height."""
    return extrude_boss(model, height)


def create_cylinder(
    sw_app: SolidWorksApp,
    diameter: float,
    height: float,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a cylinder with the given diameter and height (in mm)."""
    try:
        diameter = positive_number("diameter", diameter)
        height = positive_number("height", height)
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        model, _was_created = _get_or_create_part(sw_app)

        plane_name = _select_plane(model)
        if plane_name is None:
            return error_response("Could not select a reference plane (tried: Front Plane, 前视基准面)")

        radius = mm_to_m(diameter) / 2.0
        height_m = mm_to_m(height)

        _create_circle_sketch(model, radius)
        feature = _extrude_sketch(model, height_m)

        if feature is None:
            return error_response("Extrusion feature creation failed")

        result = {"feature_name": feature.Name}

        if save_path:
            save_result = model.SaveAs3(
                normalize_path(save_path), 0, swSaveAsOptions_Silent
            )
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=f"Created cylinder with diameter={diameter}mm, height={height}mm",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create cylinder")
        return error_response(f"Failed to create cylinder: {exc}")


def create_box(
    sw_app: SolidWorksApp,
    width: float,
    depth: float,
    height: float,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a box with the given width, depth, and height (in mm)."""
    try:
        width = positive_number("width", width)
        depth = positive_number("depth", depth)
        height = positive_number("height", height)
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        model, _was_created = _get_or_create_part(sw_app)

        plane_name = _select_plane(model)
        if plane_name is None:
            return error_response("Could not select a reference plane (tried: Front Plane, 前视基准面)")

        width_m = mm_to_m(width)
        depth_m = mm_to_m(depth)
        height_m = mm_to_m(height)

        _create_rectangle_sketch(model, width_m, depth_m)
        feature = _extrude_sketch(model, height_m)

        if feature is None:
            return error_response("Extrusion feature creation failed")

        result = {"feature_name": feature.Name}

        if save_path:
            save_result = model.SaveAs3(
                normalize_path(save_path), 0, swSaveAsOptions_Silent
            )
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=(
                f"Created box with width={width}mm, depth={depth}mm, "
                f"height={height}mm"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create box")
        return error_response(f"Failed to create box: {exc}")


def get_mass_properties(sw_app: SolidWorksApp) -> dict:
    """Read mass properties of the active part."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        bodies = model.GetBodies2(0, False)  # swAllBodies = 0
        if not bodies:
            return error_response("No bodies found in active document")

        mass_prop = call_or_value(model.Extension, "CreateMassProperty")
        if mass_prop is None:
            return error_response("Could not create mass property object")

        return success_response(
            data={
                "volume": mass_prop.Volume,
                "surface_area": mass_prop.SurfaceArea,
                "mass": mass_prop.Mass,
                "center_of_mass": list(mass_prop.CenterOfMass),
                "units": {
                    "volume": "m^3",
                    "surface_area": "m^2",
                    "mass": "kg",
                    "center_of_mass": "m",
                },
            },
            message="Mass properties computed",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get mass properties")
        return error_response(f"Failed to get mass properties: {exc}")
