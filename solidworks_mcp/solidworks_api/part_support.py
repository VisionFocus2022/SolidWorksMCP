"""Shared part-document helpers (N35): document acquisition, plane
selection, sketch/extrude primitives — the common layer under
part.py / part_advanced.py / part_refgeom.py (no cross imports)."""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from solidworks_mcp.solidworks_api.app import SolidWorksApp
from solidworks_mcp.solidworks_api.constants import swDocPART
from solidworks_mcp.solidworks_api.geometry import mm_to_m, select_plane
from solidworks_mcp.solidworks_api.sketch import extrude_boss, extrude_boss_draft
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.templates import get_part_template

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

