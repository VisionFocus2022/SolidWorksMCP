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


def walk_feature_names(model: Any, max_features: int = MAX_FEATURE_WALK) -> List[str]:
    """Walk the feature tree in order and return the feature names.

    The walk is bounded by ``max_features`` so a non-terminating
    GetNextFeature chain degrades into a warning instead of unbounded
    memory growth. A feature whose ``Name`` is not a string (e.g. a test
    double or degenerate proxy) stops the walk immediately: real feature
    names are always strings, and walking mock objects costs quadratic
    call-bookkeeping (T10 memory-explosion incident).
    """
    names: List[str] = []
    feat = call_or_value(model, "FirstFeature")
    while feat is not None:
        name = getattr(feat, "Name", None)
        if not isinstance(name, str):
            break
        names.append(name)
        if len(names) >= max_features:
            logger.warning(
                "Feature walk hit the %s-step ceiling; the model or proxy "
                "may be degenerate.",
                max_features,
            )
            break
        feat = call_or_value(feat, "GetNextFeature")
    return names


def latest_feature_name(model: Any, max_features: int = MAX_FEATURE_WALK) -> Optional[str]:
    """Return the name of the last feature in the tree (see walk_feature_names)."""
    names = walk_feature_names(model, max_features)
    return names[-1] if names else None


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
