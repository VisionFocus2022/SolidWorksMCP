"""Part-level SolidWorks operations."""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

import pythoncom
from win32com.client import gencache

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swDocPART,
    swFileSaveErrorNone,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.solidworks_api.geometry import (
    latest_feature_name,
    mm_to_m,
    select_plane,
)
from solidworks_mcp.solidworks_api.sketch import extrude_boss, extrude_boss_draft
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import ensure_sink_path, validate_output_file
from solidworks_mcp.utils.templates import get_part_template
from solidworks_mcp.utils.validation import finite_number, positive_number

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
TOP_PLANE_CANDIDATES = ["Top Plane", "上视基准面"]

#: Face-walk ceiling for the top-face selector (bounded like every walk).
MAX_FACE_WALK = 2000


def _select_top_face(model: Any) -> Optional[Any]:
    """Select and return the highest solid face (stacking anchor).

    Real-machine contract (T16 probe): faces walk through
    ``GetBodies2(0, False) → GetFirstFace/GetNextFace`` (zero-arg
    properties); ``face.GetBox()`` is a zero-arg member returning a
    6-tuple (xmin, ymin, zmin, xmax, ymax, zmax) in metres. The winner
    is the face with the greatest zmin; ``Select2(False, 0)`` then makes
    it the sketch plane (stacking is exact: box 20 + cylinder 30 →
    bbox z = 50).
    """
    bodies = model.GetBodies2(0, False)  # swBodyType_e.swSolidBody
    if not bodies:
        return None
    face = call_or_value(bodies[0], "GetFirstFace")
    best = None
    steps = 0
    while face is not None and steps < MAX_FACE_WALK:
        box = call_or_value(face, "GetBox")
        if not isinstance(box, (tuple, list)) or len(box) < 6:
            break  # degenerate proxy — stop immediately
        try:
            z_min = float(box[2])
        except (TypeError, ValueError):
            break
        steps += 1
        if best is None or z_min > best[0]:
            best = (z_min, face)
        face = call_or_value(face, "GetNextFace")
    if best is None:
        return None
    try:
        selected = best[1].Select2(False, 0)
    except Exception:
        logger.exception("Top-face selection failed")
        return None
    return best[1] if selected else None


def create_cylinder_on_face(
    sw_app: SolidWorksApp,
    diameter: float,
    height: float,
) -> dict:
    """Stack a cylinder on the current body's top face (CSG v1 op)."""
    try:
        diameter = positive_number("diameter", diameter)
        height = positive_number("height", height)
        model = sw_app.get_active_document()
        if model is None or call_or_value(model, "GetType") != swDocPART:
            return error_response("No active part document")
        top = _select_top_face(model)
        if top is None:
            return error_response(
                "No top face to stack on (the document has no solid body)",
                code="SW_API_ERROR",
            )
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateCircleByRadius(0, 0, 0, mm_to_m(diameter) / 2.0)
        model.SketchManager.InsertSketch(True)
        feature = extrude_boss(model, mm_to_m(height))
        if feature is None:
            return error_response(
                "Stacked extrusion feature creation failed", code="SW_API_ERROR"
            )
        return success_response(
            data={"feature_name": feature.Name},
            message=f"Stacked cylinder Ø{diameter}×{height}mm on the top face",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to stack cylinder")
        return error_response(f"Failed to stack cylinder: {exc}")


def create_cone_on_face(
    sw_app: SolidWorksApp,
    bottom_diameter: float,
    top_diameter: float,
    height: float,
) -> dict:
    """Stack a drafted cone on the current body's top face (CSG v1 op).

    Draft semantics mirror ``create_cone`` (real-machine contract):
    angle = ``atan2(|r_top - r_bottom|, height)``; outward draft when the
    top is wider.
    """
    try:
        bottom_diameter = positive_number("bottom_diameter", bottom_diameter)
        top_diameter = positive_number("top_diameter", top_diameter)
        height = positive_number("height", height)
        model = sw_app.get_active_document()
        if model is None or call_or_value(model, "GetType") != swDocPART:
            return error_response("No active part document")
        top = _select_top_face(model)
        if top is None:
            return error_response(
                "No top face to stack on (the document has no solid body)",
                code="SW_API_ERROR",
            )
        r_bottom = bottom_diameter / 2.0
        r_top = top_diameter / 2.0
        draft_angle_rad = math.atan2(abs(r_top - r_bottom), height)
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateCircleByRadius(0, 0, 0, mm_to_m(bottom_diameter) / 2.0)
        model.SketchManager.InsertSketch(True)
        feature = extrude_boss_draft(
            model,
            mm_to_m(height),
            top_diameter != bottom_diameter,
            r_top > r_bottom,
            draft_angle_rad,
        )
        if feature is None:
            return error_response(
                "Stacked drafted extrusion feature creation failed",
                code="SW_API_ERROR",
            )
        return success_response(
            data={
                "feature_name": feature.Name,
                "draft_angle_degrees": round(math.degrees(draft_angle_rad), 4),
            },
            message=(
                f"Stacked cone Ø{bottom_diameter}→Ø{top_diameter}×{height}mm "
                "on the top face"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to stack cone")
        return error_response(f"Failed to stack cone: {exc}")


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


def _extrude_draft_sketch(
    model: Any,
    height_m: float,
    draft_check: bool,
    draft_outward: bool,
    draft_angle_rad: float,
) -> Any:
    """Extrude the active sketch with a taper (draft slot of FeatureExtrusion2)."""
    return extrude_boss_draft(
        model, height_m, draft_check, draft_outward, draft_angle_rad
    )


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
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
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
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
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


def create_cone(
    sw_app: SolidWorksApp,
    bottom_diameter: float,
    top_diameter: float,
    height: float,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a cone/frustum from a bottom-radius circle with a drafted extrusion.

    The draft form follows the real-machine contract probed on SW 2026:
    the draft angle is ``atan2(|r_top - r_bottom|, height)`` in radians
    and ``Ddir1`` widens the far end, so ``top_diameter > bottom_diameter``
    grows an expanding frustum. ``top_diameter=0`` requests a pointed
    cone (SolidWorks may refuse a fully degenerate apex; prefer a small
    positive top diameter for machined parts).
    """
    try:
        bottom_diameter = positive_number("bottom_diameter", bottom_diameter)
        height = positive_number("height", height)
        top_diameter = finite_number("top_diameter", top_diameter)
        if top_diameter < 0:
            return error_response(
                "top_diameter must be a non-negative number",
                code="INVALID_PARAMETER",
            )
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

        radius = mm_to_m(bottom_diameter) / 2.0
        height_m = mm_to_m(height)
        r_bottom = bottom_diameter / 2.0
        r_top = top_diameter / 2.0
        draft_angle_rad = math.atan2(abs(r_top - r_bottom), height)
        draft_check = top_diameter != bottom_diameter
        draft_outward = r_top > r_bottom

        _create_circle_sketch(model, radius)
        feature = _extrude_draft_sketch(
            model, height_m, draft_check, draft_outward, draft_angle_rad
        )

        if feature is None:
            return error_response("Drafted extrusion feature creation failed")

        result = {
            "feature_name": feature.Name,
            "draft_angle_degrees": round(math.degrees(draft_angle_rad), 4),
        }

        if save_path:
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=(
                f"Created cone with bottom_diameter={bottom_diameter}mm, "
                f"top_diameter={top_diameter}mm, height={height}mm"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create cone")
        return error_response(f"Failed to create cone: {exc}")


def create_revolved(
    sw_app: SolidWorksApp,
    outer_diameter: float,
    height: float,
    bore_diameter: float = 0.0,
    plane: str = "front",
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a revolved disc/ring/shaft segment with a real feature tree.

    Sketch on the front plane: a construction centerline along sketch-y is
    the revolve axis; the rectangle profile spans [bore/2, outer/2] in
    radius and ±height/2. The part therefore revolves around the model Y
    axis (diameter in X/Z, height along Y). FeatureRevolve2 takes the
    full-circle angle in radians (real-machine contract, T6 probe).
    """
    try:
        outer_diameter = positive_number("outer_diameter", outer_diameter)
        height = positive_number("height", height)
        bore_diameter = finite_number("bore_diameter", bore_diameter)
        if bore_diameter < 0 or bore_diameter >= outer_diameter:
            return error_response(
                "bore_diameter must be in [0, outer_diameter)",
                code="INVALID_PARAMETER",
            )
        if plane != "front":
            return error_response(
                "Only the front plane revolve is supported",
                code="INVALID_PARAMETER",
            )
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

        half_height_m = mm_to_m(height) / 2.0
        outer_radius_m = mm_to_m(outer_diameter) / 2.0
        bore_radius_m = mm_to_m(bore_diameter) / 2.0

        model.SketchManager.InsertSketch(True)
        axis = model.SketchManager.CreateLine(
            0, -half_height_m, 0, 0, half_height_m, 0
        )
        axis.ConstructionGeometry = True
        model.SketchManager.CreateCornerRectangle(
            bore_radius_m, -half_height_m, 0,
            outer_radius_m, half_height_m, 0,
        )
        model.SketchManager.InsertSketch(True)

        feature = model.FeatureManager.FeatureRevolve2(
            True,   # SingleDir
            True,   # IsSolid
            False,  # IsThin
            False,  # IsCut
            False,  # ReverseDir
            False,  # BothDirectionUpToSameEntity
            0,      # Dir1Type = swEndCondBlind
            0,      # Dir2Type
            2 * math.pi,  # Dir1Angle（弧度，全周）
            0.0,    # Dir2Angle
            False,  # OffsetReverse1
            False,  # OffsetReverse2
            0.0,    # OffsetDistance1
            0.0,    # OffsetDistance2
            0,      # ThinType
            0.0,    # ThinThickness1
            0.0,    # ThinThickness2
            True,   # Merge
            True,   # UseFeatScope
            True,   # UseAutoSelect
        )
        if feature is None:
            return error_response("Revolve feature creation failed")

        result = {"feature_name": feature.Name}

        if save_path:
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=(
                f"Created revolved part with outer_diameter={outer_diameter}mm, "
                f"bore_diameter={bore_diameter}mm, height={height}mm"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create revolved part")
        return error_response(f"Failed to create revolved part: {exc}")


def _typed_doc2(model: Any) -> Any:
    """Wrap in the makepy IModelDoc2 class when possible.

    The blend boss rejects dynamic calls with a silent None (N28 e2e,
    same family as quirks 28-3: ModelDoc2 dynamic arity issues); fakes
    and cache-less hosts fall through to the raw dispatch."""
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    raw = getattr(model, "_oleobj_", None)
    if mods is None or raw is None:
        return model
    return mods.IModelDoc2(raw)


def _sweep_path_sketch(model: Any, path_type: str, radius_mm, angle_deg, length_mm) -> None:
    """Draw the sweep path sketch on the currently selected plane."""
    model.SketchManager.InsertSketch(True)
    if path_type == "arc":
        radius_m = mm_to_m(radius_mm)
        end_angle = math.radians(angle_deg)
        model.SketchManager.CreateArc(
            0.0, 0.0, 0.0,
            radius_m, 0.0, 0.0,
            radius_m * math.cos(end_angle), radius_m * math.sin(end_angle), 0.0,
            1,
        )
    else:
        model.SketchManager.CreateLine(
            0.0, 0.0, 0.0, mm_to_m(length_mm), 0.0, 0.0
        )
    model.SketchManager.InsertSketch(True)


def create_swept(
    sw_app: SolidWorksApp,
    diameter_mm: float,
    path_type: str = "arc",
    radius_mm: Optional[float] = None,
    angle_deg: float = 90.0,
    length_mm: Optional[float] = None,
    plane: str = "front",
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Swept protrusion: circular profile along an arc or line sketch path.

    Real-machine contract (N28 probe, 2026-09-01): the path sketch is
    selected as SKETCH with mark=4, and the boss call is
    InsertProtrusionSwept4 with Alignment=False and CircularProfile=True,
    so the diameter rides the call and no profile sketch is needed."""
    try:
        diameter_mm = positive_number("diameter_mm", diameter_mm)
        if path_type not in ("arc", "line"):
            return error_response(
                "path_type must be 'arc' or 'line'", code="INVALID_PARAMETER"
            )
        if plane != "front":
            return error_response(
                "Only the front plane sweep is supported",
                code="INVALID_PARAMETER",
            )
        if path_type == "arc":
            if radius_mm is None or not math.isfinite(radius_mm) or radius_mm <= 0:
                return error_response(
                    "arc path needs radius_mm > 0", code="INVALID_PARAMETER"
                )
            if not math.isfinite(angle_deg) or not 0 < abs(angle_deg) <= 360:
                return error_response(
                    "angle_deg must be in (0, 360]", code="INVALID_PARAMETER"
                )
        else:
            if length_mm is None or not math.isfinite(length_mm) or length_mm <= 0:
                return error_response(
                    "line path needs length_mm > 0", code="INVALID_PARAMETER"
                )
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        model, _was_created = _get_or_create_part(sw_app)
        if _select_plane(model) is None:
            return error_response("Could not select a reference plane")

        _sweep_path_sketch(model, path_type, radius_mm, angle_deg, length_mm)

        model.ClearSelection2(True)
        sketch_name = latest_feature_name(model)
        if not model.Extension.SelectByID2(
            sketch_name, "SKETCH", 0, 0, 0, False, 4, pythoncom.Nothing, 0
        ):
            return error_response(
                f"Could not select sweep path sketch {sketch_name!r}",
                code="SW_API_ERROR",
            )

        feature = model.FeatureManager.InsertProtrusionSwept4(
            False,  # Propagate
            False,  # Alignment — False is the unlock for sketch paths (N28 probe)
            0,      # TwistCtrlOption = swTwistControlFollowPath
            False,  # KeepTangency
            False,  # BAdvancedSmoothing
            0,      # StartMatchingType
            0,      # EndMatchingType
            False,  # IsThinBody
            0.0,    # Thickness1
            0.0,    # Thickness2
            0,      # ThinType
            0,      # PathAlign
            True,   # Merge
            True,   # UseFeatScope
            True,   # UseAutoSelect
            0.0,    # TwistAngle
            True,   # BMergeSmoothFaces
            True,   # CircularProfile — no profile sketch needed
            mm_to_m(diameter_mm),  # CircularProfileDiameter
            True,   # Direction
        )
        if feature is None:
            return error_response("Swept feature creation rejected")

        result = {"feature_name": feature.Name}
        if save_path:
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=(
                f"Created swept protrusion diameter={diameter_mm}mm along "
                f"a {path_type} path"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create swept protrusion")
        return error_response(f"Failed to create swept protrusion: {exc}")


def create_loft(
    sw_app: SolidWorksApp,
    profile_diameters_mm,
    section_spacing_mm,
    plane: str = "front",
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Lofted protrusion between circular sections on parallel planes.

    Real-machine contract (N28 probe, 2026-09-01): SW names a loft a
    "blend" — the boss call is IModelDoc2.InsertProtrusionBlend2(Closed,
    KeepTangency, ForceNonRational) with the sections selected as SKETCH
    mark=1, accumulating. Intermediate planes are FeatureManager.
    InsertRefPlane(8, distance) offsets parallel to the base plane."""
    try:
        if len(profile_diameters_mm) < 2:
            return error_response(
                "loft needs at least 2 profile sections",
                code="INVALID_PARAMETER",
            )
        for diameter in profile_diameters_mm:
            positive_number("profile_diameters_mm", diameter)
        section_spacing_mm = positive_number(
            "section_spacing_mm", section_spacing_mm
        )
        if plane != "front":
            return error_response(
                "Only the front plane loft is supported",
                code="INVALID_PARAMETER",
            )
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        model, _was_created = _get_or_create_part(sw_app)
        base_plane = _select_plane(model)
        if base_plane is None:
            return error_response("Could not select a reference plane")

        section_names = []
        for index, diameter in enumerate(profile_diameters_mm):
            if index == 0:
                plane_name = base_plane
            else:
                model.ClearSelection2(True)
                if not model.Extension.SelectByID2(
                    base_plane, "PLANE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
                ):
                    return error_response(
                        f"Could not re-select {base_plane!r} for offset",
                        code="SW_API_ERROR",
                    )
                if model.FeatureManager.InsertRefPlane(
                    8, mm_to_m(section_spacing_mm * index), 0, 0, 0, 0
                ) is None:
                    return error_response("Offset reference plane rejected")
                plane_name = latest_feature_name(model)
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(
                plane_name, "PLANE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
            ):
                return error_response(
                    f"Could not select section plane {plane_name!r}",
                    code="SW_API_ERROR",
                )
            _create_circle_sketch(model, mm_to_m(diameter) / 2.0)
            section_names.append(latest_feature_name(model))

        model.ClearSelection2(True)
        for position, name in enumerate(section_names):
            if not model.Extension.SelectByID2(
                name, "SKETCH", 0, 0, 0, position > 0, 1, pythoncom.Nothing, 0
            ):
                return error_response(
                    f"Could not select loft section {name!r}",
                    code="SW_API_ERROR",
                )

        # Blend2's return value is unreliable (returns None on success —
        # same family as FeatureFillet, quirks 17): the verdict is the tree.
        before = latest_feature_name(model)
        _typed_doc2(model).InsertProtrusionBlend2(False, False, False)
        after = latest_feature_name(model)
        if after == before:
            return error_response("Loft feature creation rejected")

        result = {"feature_name": after}
        if save_path:
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=(
                f"Created lofted protrusion with {len(profile_diameters_mm)} "
                f"circular sections, spacing {section_spacing_mm}mm"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create lofted protrusion")
        return error_response(f"Failed to create lofted protrusion: {exc}")


def create_ref_plane(
    sw_app: SolidWorksApp,
    offset_mm: float,
    plane: str = "front",
) -> dict:
    """Reference plane parallel to the front plane at an offset distance.

    FeatureManager.InsertRefPlane(8, distance) — the Distance constraint,
    same call the loft tool uses for its section planes (N28 probe)."""
    try:
        offset_mm = positive_number("offset_mm", offset_mm)
        if plane != "front":
            return error_response(
                "Only the front plane offset is supported",
                code="INVALID_PARAMETER",
            )
        model, _was_created = _get_or_create_part(sw_app)
        base_plane = _select_plane(model)
        if base_plane is None:
            return error_response("Could not select a reference plane")

        model.ClearSelection2(True)
        if not model.Extension.SelectByID2(
            base_plane, "PLANE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
        ):
            return error_response(
                f"Could not re-select {base_plane!r} as the offset reference",
                code="SW_API_ERROR",
            )
        if model.FeatureManager.InsertRefPlane(
            8, mm_to_m(offset_mm), 0, 0, 0, 0
        ) is None:
            return error_response(
                "Reference plane creation rejected", code="SW_API_ERROR"
            )
        return success_response(
            data={"feature_name": latest_feature_name(model)},
            message=f"Created reference plane {offset_mm}mm off {base_plane}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create reference plane")
        return error_response(f"Failed to create reference plane: {exc}")


def _cylindrical_face_by_name(model: Any, face_name: str) -> tuple:
    """Walk the solid faces matching GetEntityName == face_name.

    Returns ``(face, None)`` on a hit, ``(None, "not_found")`` /
    ``(None, "not_cylindrical")`` otherwise. SelectByID2 cannot resolve
    named faces (T5 contract), and the axis call demands a cylindrical
    face."""
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        walked = 0
        while face is not None and walked < MAX_FACE_WALK:
            name = model.GetEntityName(face)
            if not isinstance(name, str):  # scalar sentinel (T10 incident)
                break
            if name == face_name:
                surface = call_or_value(face, "GetSurface")
                cylindrical = surface is not None and call_or_value(
                    surface, "IsCylinder"
                )
                return (face, None) if cylindrical else (None, "not_cylindrical")
            walked += 1
            face = call_or_value(face, "GetNextFace")
    return None, "not_found"


def create_ref_axis(sw_app: SolidWorksApp, face_name: str) -> dict:
    """Reference axis from a named cylindrical face.

    Real-machine contract (N29 probe): the face is selected via
    Select2(False, 0), then the zero-arg ``IModelDoc2.InsertAxis`` fires
    through property-get semantics on dynamic dispatch (``InsertAxis2``
    marshals broken with DISP_E_PARAMNOTFOUND); the tree diff is the
    verdict."""
    try:
        if not face_name:
            return error_response("face_name must be non-empty", code="INVALID_PARAMETER")
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        face, why = _cylindrical_face_by_name(model, face_name)
        if why == "not_found":
            return error_response(
                f"Face {face_name!r} not found", code="INVALID_PARAMETER"
            )
        if why == "not_cylindrical":
            return error_response(
                f"Face {face_name!r} is not cylindrical — an axis needs a "
                "cylindrical face (see list_faces)",
                code="INVALID_PARAMETER",
            )
        model.ClearSelection2(True)
        if not face.Select2(False, 0):
            return error_response(
                f"Could not select face {face_name!r}", code="SW_API_ERROR"
            )

        before = latest_feature_name(model)
        call_or_value(model, "InsertAxis")  # property-get fires the call
        after = latest_feature_name(model)
        if after == before:
            return error_response(
                "Reference axis creation rejected", code="SW_API_ERROR"
            )
        return success_response(
            data={"feature_name": after},
            message=f"Created reference axis from cylindrical face {face_name}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create reference axis")
        return error_response(f"Failed to create reference axis: {exc}")


def create_rib(
    sw_app: SolidWorksApp,
    length_mm: float,
    height_mm: float,
    thickness_mm: float,
    base_z_mm: float = 0.0,
    x_center_mm: float = 0.0,
    y_center_mm: float = 0.0,
) -> dict:
    """Rib as a rectangular boss plate — MATH SUBSTITUTE for the native rib.

    The InsertRib family is BLOCKED on this machine (13 direct-call
    variants all silently rejected, T8 family; no Rib entry in
    swFeatureNameID_e so the FeatureData route is closed — ADR-0011).
    The plate is sketched on the top plane (or an offset reference plane
    at ``base_z_mm``) and boss-extruded upward, so it IS parameter
    linked, but unlike a true rib it does not adapt to adjacent walls."""
    try:
        length_mm = positive_number("length_mm", length_mm)
        height_mm = positive_number("height_mm", height_mm)
        thickness_mm = positive_number("thickness_mm", thickness_mm)
        base_z_mm = finite_number("base_z_mm", base_z_mm)
        x_center_mm = finite_number("x_center_mm", x_center_mm)
        y_center_mm = finite_number("y_center_mm", y_center_mm)
        if base_z_mm < 0:
            return error_response(
                "base_z_mm must be non-negative", code="INVALID_PARAMETER"
            )
        model, _was_created = _get_or_create_part(sw_app)

        if base_z_mm > 0:
            top_name = select_plane(model, TOP_PLANE_CANDIDATES)
            if top_name is None:
                return error_response(
                    "Could not select a reference plane "
                    "(tried: Top Plane, 上视基准面)"
                )
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(
                top_name, "PLANE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
            ):
                return error_response(
                    f"Could not re-select {top_name!r} as the offset reference",
                    code="SW_API_ERROR",
                )
            if model.FeatureManager.InsertRefPlane(
                8, mm_to_m(base_z_mm), 0, 0, 0, 0
            ) is None:
                return error_response(
                    "Offset reference plane rejected", code="SW_API_ERROR"
                )
            plane_name = latest_feature_name(model)
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(
                plane_name, "PLANE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
            ):
                return error_response(
                    f"Could not select sketch plane {plane_name!r}",
                    code="SW_API_ERROR",
                )
        else:
            if select_plane(model, TOP_PLANE_CANDIDATES) is None:
                return error_response(
                    "Could not select a reference plane "
                    "(tried: Top Plane, 上视基准面)"
                )

        x1 = mm_to_m(x_center_mm - length_mm / 2.0)
        y1 = mm_to_m(y_center_mm - thickness_mm / 2.0)
        x2 = mm_to_m(x_center_mm + length_mm / 2.0)
        y2 = mm_to_m(y_center_mm + thickness_mm / 2.0)
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateCornerRectangle(x1, y1, 0, x2, y2, 0)
        model.SketchManager.InsertSketch(True)

        feature = _extrude_sketch(model, mm_to_m(height_mm))
        if feature is None:
            return error_response("Extrusion feature creation failed")

        return success_response(
            data={"feature_name": feature.Name},
            message=(
                f"Created rib plate {length_mm}x{thickness_mm}x{height_mm}mm "
                f"at z={base_z_mm}mm (math substitute — not wall-adaptive, "
                "ADR-0011)"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create rib")
        return error_response(f"Failed to create rib: {exc}")


def create_polygon(
    sw_app: SolidWorksApp,
    sides: int,
    circumradius_mm: float,
    height_mm: float,
    inscribed: bool = True,
    plane: str = "front",
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Regular N-sided prism: polygon sketch + boss extrude (merged).

    Real-machine contract (N30 probe): ISketchManager.CreatePolygon takes 8
    scalars — the edge reference point is (circumradius, 0). Inscribed=True
    makes the polygon inscribed in that circle (volume = N/2·R²·sin(2π/N)·h);
    False circumscribes it (R is then the inradius)."""
    try:
        if not isinstance(sides, int) or isinstance(sides, bool) or not 3 <= sides <= 60:
            return error_response(
                "sides must be an integer in [3, 60]", code="INVALID_PARAMETER"
            )
        circumradius_mm = positive_number("circumradius_mm", circumradius_mm)
        height_mm = positive_number("height_mm", height_mm)
        if plane != "front":
            return error_response(
                "Only the front plane polygon is supported",
                code="INVALID_PARAMETER",
            )
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        model, _was_created = _get_or_create_part(sw_app)
        if _select_plane(model) is None:
            return error_response("Could not select a reference plane")

        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreatePolygon(
            0.0, 0.0, 0.0,
            mm_to_m(circumradius_mm), 0.0, 0.0,
            sides, inscribed,
        )
        model.SketchManager.InsertSketch(True)

        feature = _extrude_sketch(model, mm_to_m(height_mm))
        if feature is None:
            return error_response("Extrusion feature creation failed")

        result = {"feature_name": feature.Name}
        if save_path:
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=(
                f"Created {sides}-sided prism (circumradius {circumradius_mm}mm, "
                f"height {height_mm}mm)"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create polygon prism")
        return error_response(f"Failed to create polygon prism: {exc}")


def create_slot(
    sw_app: SolidWorksApp,
    length_mm: float,
    width_mm: float,
    height_mm: float,
    plane: str = "front",
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Obround (slot) plate: straight-slot sketch + boss extrude (merged).

    Real-machine contract (N30 probe): CreateSketchSlot line-type(0) /
    center-center(0); the slot area is length·width + π(width/2)² — the
    centre-line length includes the end radii, so length must exceed
    width."""
    try:
        length_mm = positive_number("length_mm", length_mm)
        width_mm = positive_number("width_mm", width_mm)
        height_mm = positive_number("height_mm", height_mm)
        if length_mm <= width_mm:
            return error_response(
                "length_mm must exceed width_mm (the centre line includes the "
                "end radii)",
                code="INVALID_PARAMETER",
            )
        if plane != "front":
            return error_response(
                "Only the front plane slot is supported",
                code="INVALID_PARAMETER",
            )
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        model, _was_created = _get_or_create_part(sw_app)
        if _select_plane(model) is None:
            return error_response("Could not select a reference plane")

        half_length_m = mm_to_m(length_mm) / 2.0
        width_m = mm_to_m(width_mm)
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateSketchSlot(
            0, 0, width_m,
            0.0, -half_length_m, 0.0,
            0.0, half_length_m, 0.0,
            width_m / 2.0, 0.0, 0.0,
            1, False,
        )
        model.SketchManager.InsertSketch(True)

        feature = _extrude_sketch(model, mm_to_m(height_mm))
        if feature is None:
            return error_response("Extrusion feature creation failed")

        result = {"feature_name": feature.Name}
        if save_path:
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if save_result != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {save_result}")
            result["saved_to"] = save_path

        return success_response(
            data=result,
            message=(
                f"Created slot plate {length_mm}x{width_mm}mm (centre line), "
                f"height {height_mm}mm"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create slot plate")
        return error_response(f"Failed to create slot plate: {exc}")


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
