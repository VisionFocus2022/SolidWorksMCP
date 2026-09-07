"""Reference geometry: offset planes and axes from named cylindrical
faces (N29, split from part.py in N35)."""

from __future__ import annotations

import logging

import pythoncom

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.geometry import latest_feature_name, mm_to_m
from solidworks_mcp.solidworks_api.part_support import MAX_FACE_WALK, _get_or_create_part, _select_plane
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.validation import positive_number

logger = logging.getLogger(__name__)


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


