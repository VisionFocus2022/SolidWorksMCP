"""Face-based fillet and chamfer decorations (selection via walk+Select2)."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Sequence, Tuple

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.geometry import latest_feature_name, mm_to_m
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.validation import finite_number, positive_number

logger = logging.getLogger(__name__)

SW_SOLID_BODY = 0  # swBodyType_e.swSolidBody


def _select_named_faces(model: Any, face_names: Sequence[str]) -> Tuple[int, List[str]]:
    """Select the named solid faces, T5 contract: walk + Select2(append, mark=1).

    SelectByID2 cannot resolve named faces on SW 2026 (see
    tools/probe_face_naming.py), so selection walks the face lists and
    matches ``GetEntityName`` directly on the face objects.
    """
    model.ClearSelection2(True)
    wanted = list(face_names)
    selected = 0
    for body in model.GetBodies2(SW_SOLID_BODY, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            name = model.GetEntityName(face)
            if name in wanted:
                if face.Select2(True, 1):
                    selected += 1
                wanted.remove(name)
            face = call_or_value(face, "GetNextFace")
    return selected, wanted


def apply_fillet(
    sw_app: SolidWorksApp,
    face_names: Sequence[str],
    radius_mm: float,
) -> dict:
    """Fillet all edges of the named faces with a constant radius (mm).

    Uses the legacy IModelDoc2::FeatureFillet — the modern variant-array
    overloads (FeatureFillet3+) marshal unstably under pywin32 (real-machine
    evidence, T7 probe). The call returns None; success is judged by a new
    feature appearing in the tree.
    """
    try:
        radius_mm = positive_number("radius_mm", radius_mm)
        if not face_names:
            return error_response("face_names must be non-empty", code="INVALID_PARAMETER")

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        selected, missing = _select_named_faces(model, face_names)
        if missing:
            return error_response(
                f"Face(s) not found: {', '.join(missing)}",
                code="INVALID_PARAMETER",
            )

        before = latest_feature_name(model)
        model.FeatureFillet(mm_to_m(radius_mm), False, False, False, 0)
        after = latest_feature_name(model)
        if after == before:
            return error_response(
                f"SolidWorks rejected the fillet (radius {radius_mm}mm on "
                f"{selected} face(s))",
                code="SW_API_ERROR",
            )

        return success_response(
            data={"feature_name": after, "faces": list(face_names)},
            message=f"Applied R{radius_mm}mm fillet to {selected} face(s): {after}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to apply fillet")
        return error_response(f"Failed to apply fillet: {exc}")


def apply_chamfer(
    sw_app: SolidWorksApp,
    face_names: Sequence[str],
    distance_mm: float,
    angle_deg: float = 45.0,
) -> dict:
    """Chamfer all edges of the named faces by distance (mm) and angle (deg).

    FeatureChamfer takes the width in metres and the angle in radians.
    Like FeatureFillet the return value is unreliable (None on success);
    a new feature in the tree is the success criterion.
    """
    try:
        distance_mm = positive_number("distance_mm", distance_mm)
        angle_deg = finite_number("angle_deg", angle_deg)
        if not 0 < angle_deg < 90:
            return error_response(
                "angle_deg must be in (0, 90)", code="INVALID_PARAMETER"
            )
        if not face_names:
            return error_response("face_names must be non-empty", code="INVALID_PARAMETER")

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        selected, missing = _select_named_faces(model, face_names)
        if missing:
            return error_response(
                f"Face(s) not found: {', '.join(missing)}",
                code="INVALID_PARAMETER",
            )

        before = latest_feature_name(model)
        model.FeatureChamfer(mm_to_m(distance_mm), math.radians(angle_deg), False)
        after = latest_feature_name(model)
        if after == before:
            return error_response(
                f"SolidWorks rejected the chamfer ({distance_mm}mm at "
                f"{angle_deg}deg on {selected} face(s))",
                code="SW_API_ERROR",
            )

        return success_response(
            data={"feature_name": after, "faces": list(face_names)},
            message=(
                f"Applied {distance_mm}mm {angle_deg}deg chamfer to "
                f"{selected} face(s): {after}"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to apply chamfer")
        return error_response(f"Failed to apply chamfer: {exc}")
