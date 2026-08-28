"""Generic annular feature patterns for parts (bolt circles, hole rings)."""

from __future__ import annotations

import bisect
import logging
import math
from typing import Any, List, Optional, Sequence

import pythoncom
from pydantic import BaseModel, Field, ValidationError

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.design import (
    PLANE_ALIASES,
    _get_active_part,
    _save_active_model,
)
from solidworks_mcp.solidworks_api.geometry import (
    latest_feature_name,
    mm_to_m,
    select_plane,
)
from solidworks_mcp.solidworks_api.sketch import cut_feature, extrude_boss
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.security import validate_output_file
from solidworks_mcp.utils.validation import finite_number, parse_bool, positive_number

logger = logging.getLogger(__name__)

MAX_RING_COUNT = 100
MAX_INSTANCES_PER_RING = 1000
MAX_TOTAL_INSTANCES = 5000
MAX_AVOID_ANGLES = 72
MAX_DIMENSION_MM = 1_000_000


class AnnularRing(BaseModel):
    """One concentric ring of circular features."""

    radius_mm: float = Field(
        gt=0,
        le=MAX_DIMENSION_MM,
        allow_inf_nan=False,
        description="Ring radius from the sketch origin in millimeters",
    )
    count: int = Field(
        gt=0,
        le=MAX_INSTANCES_PER_RING,
        description="Number of features on this ring",
    )
    diameter_mm: float = Field(
        gt=0,
        le=MAX_DIMENSION_MM,
        allow_inf_nan=False,
        description="Circular feature diameter in millimeters",
    )
    phase_degrees: Optional[float] = Field(
        default=None,
        ge=0,
        le=360,
        allow_inf_nan=False,
        description=(
            "Optional starting angle in degrees. When omitted and avoid "
            "angles are configured, the phase is chosen to maximize "
            "clearance from them."
        ),
    )


def _angular_distance_degrees(a: float, b: float) -> float:
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def _min_angular_distance(angle: float, sorted_blocked: Sequence[float]) -> float:
    """Nearest angular distance from ``angle`` to a sorted, deduplicated list."""
    if not sorted_blocked:
        return math.inf
    index = bisect.bisect_left(sorted_blocked, angle)
    before = sorted_blocked[index - 1] if index else sorted_blocked[-1]
    after = sorted_blocked[index] if index < len(sorted_blocked) else sorted_blocked[0]
    return min(
        _angular_distance_degrees(angle, before),
        _angular_distance_degrees(angle, after),
    )


def _best_phase(count: int, sorted_blocked: Sequence[float]) -> float:
    """Pick the phase that maximizes the minimum angular clearance.

    Same deterministic 72-step search proven on the ring-light product,
    with a bisect nearest-neighbor lookup so cost stays O(steps x count).
    """
    pitch = 360.0 / count
    best_phase = 0.0
    best_clearance = -1.0
    for index in range(72):
        phase = pitch * index / 72.0
        clearance = min(
            _min_angular_distance(phase + k * pitch, sorted_blocked)
            for k in range(count)
        )
        if clearance > best_clearance:
            best_phase = phase
            best_clearance = clearance
    return best_phase


def _overlap_warnings(rows: List[dict]) -> List[str]:
    warnings: List[str] = []
    for row in rows:
        if row["count"] > 1:
            chord = 2.0 * row["radius_mm"] * math.sin(math.pi / row["count"])
            if chord < row["diameter_mm"]:
                warnings.append(
                    f"Ring {row['ring_index']}: adjacent features overlap "
                    f"(chord {chord:.2f}mm < diameter {row['diameter_mm']}mm); "
                    "SolidWorks may merge them."
                )
    for i, first in enumerate(rows):
        for second in rows[i + 1:]:
            gap = abs(first["radius_mm"] - second["radius_mm"])
            touching = (first["diameter_mm"] + second["diameter_mm"]) / 2.0
            if gap < touching:
                warnings.append(
                    f"Rings {first['ring_index']} and {second['ring_index']} "
                    f"overlap radially (gap {gap:.2f}mm < {touching:.2f}mm); "
                    "SolidWorks may merge features."
                )
    return warnings


def build_annular_layout(
    rings: Sequence[Any],
    avoid_angles_degrees: Optional[Sequence[float]] = None,
) -> dict:
    """Return the deterministic annular layout in millimeters."""
    try:
        ring_list = [
            ring if isinstance(ring, AnnularRing) else AnnularRing.model_validate(ring)
            for ring in rings
        ]
    except TypeError as exc:
        raise ValueError(
            "rings must be a sequence of ring objects or dicts"
        ) from exc
    if not 1 <= len(ring_list) <= MAX_RING_COUNT:
        raise ValueError(f"rings must contain between 1 and {MAX_RING_COUNT} entries")
    raw_blocked = list(avoid_angles_degrees or [])
    if len(raw_blocked) > MAX_AVOID_ANGLES:
        raise ValueError(
            f"avoid_angles_degrees must contain at most {MAX_AVOID_ANGLES} entries"
        )
    blocked = sorted(
        {
            round(finite_number("avoid_angles_degrees", angle) % 360.0, 9)
            for angle in raw_blocked
        }
    )
    if sum(ring.count for ring in ring_list) > MAX_TOTAL_INSTANCES:
        raise ValueError(f"total feature count exceeds {MAX_TOTAL_INSTANCES}")

    rows = []
    for index, ring in enumerate(ring_list, start=1):
        phase = ring.phase_degrees
        if phase is None:
            phase = _best_phase(ring.count, blocked) if blocked else 0.0
        positions = []
        for k in range(ring.count):
            angle = math.radians(phase + 360.0 * k / ring.count)
            positions.append(
                (
                    round(ring.radius_mm * math.cos(angle), 6),
                    round(ring.radius_mm * math.sin(angle), 6),
                )
            )
        rows.append(
            {
                "ring_index": index,
                "radius_mm": ring.radius_mm,
                "count": ring.count,
                "diameter_mm": ring.diameter_mm,
                "phase_degrees": round(phase % 360.0, 6),
                "positions_xy_mm": positions,
            }
        )

    return {
        "pattern": "annular",
        "rings": rows,
        "total_feature_count": sum(row["count"] for row in rows),
        "avoid_angles_degrees": blocked,
        "warnings": _overlap_warnings(rows),
    }


def create_annular_pattern(
    sw_app: SolidWorksApp,
    rings: Sequence[Any],
    plane: str = "top",
    feature_kind: str = "cut",
    depth: Optional[float] = None,
    through_all: bool = True,
    avoid_angles_degrees: Optional[Sequence[float]] = None,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create concentric rings of circular cuts or bosses on a named plane.

    Cuts support through-all or blind depth; bosses are always blind.
    """
    try:
        if feature_kind not in {"cut", "boss"}:
            return error_response(
                "feature_kind must be 'cut' or 'boss'", code="INVALID_PARAMETER"
            )
        if not isinstance(plane, str) or not plane.strip():
            return error_response(
                "plane must be a non-empty string", code="INVALID_PARAMETER"
            )
        through_all = parse_bool("through_all", through_all)
        if depth is not None:
            try:
                depth = positive_number("depth", depth)
            except ValueError as exc:
                return error_response(str(exc), code="INVALID_PARAMETER")
        if feature_kind == "cut" and not through_all and depth is None:
            return error_response(
                "depth is required when through_all is False",
                code="INVALID_PARAMETER",
            )
        if feature_kind == "boss" and depth is None:
            return error_response(
                "depth is required for boss features (bosses are always blind)",
                code="INVALID_PARAMETER",
            )
        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        layout = build_annular_layout(rings, avoid_angles_degrees)
        model = _get_active_part(sw_app)

        plane_names = PLANE_ALIASES.get(plane.lower(), [plane])
        selected_plane: Optional[str] = None
        nominal_depth = max(
            [10.0] + [row["diameter_mm"] for row in layout["rings"]]
        )
        feature_names: List[str] = []
        for row in layout["rings"]:
            # Re-select the plane for every ring: the previous ring's
            # sketch selection and feature creation consumed the selection
            # (same proven sequence as the ring-light LED markers).
            plane_name = select_plane(model, plane_names)
            if plane_name is None:
                return error_response(f"Could not select plane: {plane}")
            if selected_plane is None:
                selected_plane = plane_name

            hole_radius = row["diameter_mm"] / 2.0
            model.SketchManager.InsertSketch(True)
            for x_mm, y_mm in row["positions_xy_mm"]:
                model.SketchManager.CreateCircleByRadius(
                    mm_to_m(x_mm), mm_to_m(y_mm), 0, mm_to_m(hole_radius)
                )
            model.SketchManager.InsertSketch(True)

            sketch_name = latest_feature_name(model)
            if not sketch_name:
                return error_response(
                    "Could not identify the ring sketch", code="SW_API_ERROR"
                )
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(
                sketch_name,
                "SKETCH",
                0,
                0,
                0,
                False,
                0,
                pythoncom.Nothing,
                0,
            ):
                return error_response(
                    f"Could not select ring sketch: {sketch_name}",
                    code="SW_API_ERROR",
                )

            if feature_kind == "boss":
                feature = extrude_boss(model, mm_to_m(depth))
            else:
                feature = cut_feature(
                    model,
                    True,
                    through_all,
                    1 if through_all else 0,
                    mm_to_m(depth if depth is not None else nominal_depth),
                )
            if feature is None:
                return error_response(
                    "Annular "
                    f"{feature_kind} feature creation failed for ring "
                    f"{row['ring_index']}",
                    code="SW_API_ERROR",
                )
            feature.Name = (
                f"ANNULAR_{feature_kind.upper()}_RING_{row['ring_index']:02d}_"
                f"R{row['radius_mm']:.2f}_N{row['count']}"
            )
            feature_names.append(feature.Name)

        data = {
            "features": feature_names,
            "feature_kind": feature_kind,
            "plane": selected_plane,
            "ring_count": len(feature_names),
            "total_feature_count": layout["total_feature_count"],
            "through_all": bool(through_all) if feature_kind == "cut" else None,
            "depth_mm": None if (feature_kind == "cut" and through_all) else depth,
            "layout": layout,
        }
        if save_path:
            save_error = _save_active_model(
                model, save_path, overwrite_confirm, data
            )
            if save_error:
                return save_error

        return success_response(
            data=data,
            message=(
                f"Created annular {feature_kind} pattern: "
                f"{layout['total_feature_count']} features on "
                f"{len(feature_names)} rings"
            ),
            warning="; ".join(layout["warnings"]) or None,
        )
    except (SolidWorksNotRunningError, ValueError, ValidationError) as exc:
        if isinstance(exc, SolidWorksNotRunningError):
            return error_response(str(exc))
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create annular pattern")
        return error_response(f"Failed to create annular pattern: {exc}")
