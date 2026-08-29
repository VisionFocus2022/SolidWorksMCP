"""Pure geometry, unit, and feature-tree helpers shared by design modules."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

import pythoncom

from solidworks_mcp.utils.com import call_or_value

logger = logging.getLogger(__name__)

# Upper bound for the feature-tree walk. Real parts stay far below this;
# a broken GetNextFeature chain (test doubles, degenerate COM proxies)
# must never iterate without limit -- an unbounded Mock walk once
# ballooned a stray test process to 34.86 GB of committed memory.
MAX_FEATURE_WALK = 5000


def mm_to_m(value: float) -> float:
    """Convert millimeters to SolidWorks default meter units."""
    return value / 1000.0


def linspace(start: float, end: float, count: int) -> List[float]:
    """Return ``count`` evenly spaced values from ``start`` to ``end``."""
    if count == 1:
        return [start]
    return [start + (end - start) * i / (count - 1) for i in range(count)]


def latest_feature_name(model: Any, max_features: int = MAX_FEATURE_WALK) -> Optional[str]:
    """Walk the feature tree and return the name of the last feature.

    The walk is bounded by ``max_features`` so a non-terminating
    GetNextFeature chain degrades into a warning instead of unbounded
    memory growth.
    """
    latest = None
    feat = call_or_value(model, "FirstFeature")
    steps = 0
    while feat is not None:
        latest = feat.Name
        steps += 1
        if steps >= max_features:
            logger.warning(
                "Feature walk hit the %s-step ceiling; returning the "
                "latest name seen. The model or proxy may be degenerate.",
                max_features,
            )
            break
        feat = call_or_value(feat, "GetNextFeature")
    return latest


def select_plane(
    model: Any,
    candidates: List[str],
    use_extension_fallback: bool = True,
) -> Optional[str]:
    """Select the first selectable reference plane from ``candidates``.

    Tries FeatureByName + Select2 first, then falls back to
    Extension.SelectByID2 for localized plane names when
    ``use_extension_fallback`` is enabled.
    """
    model.ClearSelection2(True)
    for plane_name in candidates:
        feature = model.FeatureByName(plane_name)
        if feature is not None and feature.Select2(False, 0):
            return plane_name
        if use_extension_fallback and model.Extension.SelectByID2(
            plane_name,
            "PLANE",
            0,
            0,
            0,
            False,
            0,
            pythoncom.Nothing,
            0,
        ):
            return plane_name
    return None
