"""Body/face enumeration and entity naming (selection-based automation base)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.geometry import MAX_FEATURE_WALK
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value

logger = logging.getLogger(__name__)

SW_SOLID_BODY = 0  # swBodyType_e.swSolidBody


def _surface_type(surface: Any) -> str:
    try:
        if call_or_value(surface, "IsPlane"):
            return "PLANE"
        if call_or_value(surface, "IsCylinder"):
            return "CYLINDER"
        if call_or_value(surface, "IsSphere"):
            return "SPHERE"
    except Exception:
        pass
    return "OTHER"


def _count_faces(body: Any) -> int:
    count = 0
    face = call_or_value(body, "GetFirstFace")
    while face is not None and count < MAX_FEATURE_WALK:
        count += 1
        face = call_or_value(face, "GetNextFace")
    return count


def list_bodies(sw_app: SolidWorksApp) -> dict:
    """List solid bodies with entity names and face counts."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        bodies = model.GetBodies2(SW_SOLID_BODY, False)
        rows: List[Dict[str, Any]] = []
        for index, body in enumerate(bodies or ()):
            rows.append({
                "index": index,
                "name": model.GetEntityName(body) or "",
                "face_count": _count_faces(body),
            })
        return success_response(
            data={"bodies": rows, "count": len(rows)},
            message=f"Found {len(rows)} solid body(ies)",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to list bodies")
        return error_response(f"Failed to list bodies: {exc}")


def list_faces(sw_app: SolidWorksApp, name_prefix: str = "Face") -> dict:
    """Enumerate solid faces; unnamed faces get stable SetEntityName names.

    Named faces become referenceable from mates, fillets, and other
    selection-based features. Real-machine evidence (T5 probe, 2026-08-29):
    naming lives on ModelDoc2 (``model.SetEntityName``), NOT on
    ``model.Extension``; SelectByID2 cannot resolve named faces on SW 2026,
    so selection-based consumers should walk faces and call
    ``face.Select2`` (see tools/probe_face_naming.py).
    """
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        bodies = model.GetBodies2(SW_SOLID_BODY, False)
        rows: List[Dict[str, Any]] = []
        renamed = 0
        counter = 0
        for body in bodies or ():
            face = call_or_value(body, "GetFirstFace")
            walked = 0
            while face is not None and walked < MAX_FEATURE_WALK:
                name = model.GetEntityName(face)
                if not name:
                    candidate = f"{name_prefix}{counter}"
                    if model.SetEntityName(face, candidate):
                        name = candidate
                        renamed += 1
                    else:
                        name = ""
                rows.append({
                    "name": name,
                    "surface_type": _surface_type(call_or_value(face, "GetSurface")),
                    "area_mm2": round(call_or_value(face, "GetArea") * 1_000_000.0, 6),
                })
                counter += 1
                walked += 1
                face = call_or_value(face, "GetNextFace")
        return success_response(
            data={"faces": rows, "count": len(rows), "renamed": renamed},
            message=f"Found {len(rows)} face(s), {renamed} newly named",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to list faces")
        return error_response(f"Failed to list faces: {exc}")
