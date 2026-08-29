"""Measurement helpers: point distances and merged solid bounding boxes."""

from __future__ import annotations

import logging
import math
from typing import Sequence

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.utils.common import error_response, success_response

logger = logging.getLogger(__name__)

SW_SOLID_BODY = 0  # swBodyType_e.swSolidBody


def measure_distance(
    sw_app: SolidWorksApp,
    point1: Sequence[float],
    point2: Sequence[float],
) -> dict:
    """Euclidean distance between two model-space [x, y, z] points in mm."""
    try:
        for label, point in (("point1", point1), ("point2", point2)):
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                return error_response(
                    f"{label} must be [x, y, z] in mm", code="INVALID_PARAMETER"
                )
        if sw_app.get_active_document() is None:
            return error_response("No active document")
        deltas = [float(b) - float(a) for a, b in zip(point1, point2)]
        distance = math.sqrt(sum(d * d for d in deltas))
        return success_response(
            data={
                "distance_mm": round(distance, 6),
                "delta_mm": [round(d, 6) for d in deltas],
                "point1": [float(v) for v in point1],
                "point2": [float(v) for v in point2],
            },
            message=f"Distance = {distance:.4f} mm",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to measure distance")
        return error_response(f"Failed to measure distance: {exc}")


def get_bounding_box(sw_app: SolidWorksApp) -> dict:
    """Merged axis-aligned bounding box of all solid bodies, reported in mm."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        bodies = model.GetBodies2(SW_SOLID_BODY, False)
        if not bodies:
            return error_response("No solid bodies in active document")
        boxes = [body.GetBodyBox() for body in bodies]
        mins = [min(box[i] for box in boxes) for i in range(3)]
        maxs = [max(box[i + 3] for box in boxes) for i in range(3)]
        size = [round((maxs[i] - mins[i]) * 1000.0, 6) for i in range(3)]
        center = [round((mins[i] + maxs[i]) / 2.0 * 1000.0, 6) for i in range(3)]
        return success_response(
            data={
                "min_mm": [round(v * 1000.0, 6) for v in mins],
                "max_mm": [round(v * 1000.0, 6) for v in maxs],
                "size_mm": size,
                "center_mm": center,
                "body_count": len(boxes),
            },
            message=f"Bounding box {size[0]} x {size[1]} x {size[2]} mm",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get bounding box")
        return error_response(f"Failed to get bounding box: {exc}")
