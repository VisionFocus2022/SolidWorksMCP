"""Shared sketch-extrusion and cut feature call primitives.

These wrappers exist so the long FeatureExtrusion2 / FeatureCut3 argument
vectors are written once; every caller passes the few values it varies.
"""

from __future__ import annotations

from typing import Any


def extrude_boss(model: Any, height_m: float, reverse: bool = True) -> Any:
    """Extrude the selected sketch by ``height_m`` meters (FeatureExtrusion2)."""
    return model.FeatureManager.FeatureExtrusion2(
        reverse, False, False, 0, 0, height_m, height_m,
        False, False, False, False, 0, 0,
        False, False, False, False, True, True, True, 0, 0, False,
    )


def extrude_boss_draft(
    model: Any,
    height_m: float,
    draft_check: bool,
    draft_outward: bool,
    draft_angle_rad: float,
) -> Any:
    """Extrude the selected sketch with a taper (FeatureExtrusion2 draft slot).

    Mirrors the real-machine contract verified by the aicad channel-B
    probe on SW 2026: draft angles are RADIANS and ``Ddir1=True`` widens
    the far end (a frustum whose top radius exceeds its bottom radius
    extrudes as an expanding solid; volumes verified exact).
    """
    return model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, height_m, height_m,
        draft_check, False, draft_outward, False, draft_angle_rad, 0.0,
        False, False, False, False, True, True, True, 0, 0, False,
    )


def cut_feature(
    model: Any,
    reverse: bool,
    through_all: bool,
    end_condition: int,
    depth_m: float,
) -> Any:
    """Cut the selected sketch (FeatureCut3) with the shared tail arguments."""
    return model.FeatureManager.FeatureCut3(
        reverse, False, through_all, end_condition, 0, depth_m, depth_m,
        False, False, False, False, 0, 0,
        False, False, False, False, False,
        True, True, True, True, False, 0, 0, False,
    )
