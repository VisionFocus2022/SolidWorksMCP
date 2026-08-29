"""Feature tree operations for SolidWorks."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swFeatureSuppressed,
    swFeatureUnsuppressed,
)
from solidworks_mcp.solidworks_api.geometry import MAX_FEATURE_WALK
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value

logger = logging.getLogger(__name__)


def _find_feature(model: Any, feature_name: str) -> Optional[Any]:
    """Find a feature by name in the feature tree."""
    feat = _first_feature(model)
    while feat is not None:
        if feat.Name == feature_name:
            return feat
        feat = _next_feature(feat)
    return None


def _first_feature(model: Any) -> Optional[Any]:
    return call_or_value(model, "FirstFeature")


def _next_feature(feature: Any) -> Optional[Any]:
    return call_or_value(feature, "GetNextFeature")


def rename_feature(
    sw_app: SolidWorksApp,
    old_name: str,
    new_name: str,
) -> dict:
    """Rename a feature in the active document."""
    try:
        if not old_name or not new_name:
            return error_response(
                "old_name and new_name must be non-empty strings",
                code="INVALID_PARAMETER",
            )
        if old_name == new_name:
            return success_response(
                data={"old_name": old_name, "new_name": new_name},
                message="Feature already has the requested name",
            )
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        feat = _find_feature(model, old_name)
        if feat is None:
            return error_response(f"Feature not found: {old_name}")

        feat.Name = new_name
        return success_response(
            data={"old_name": old_name, "new_name": new_name},
            message=f"Renamed feature '{old_name}' to '{new_name}'",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to rename feature")
        return error_response(f"Failed to rename feature: {exc}")


def set_feature_suppression(
    sw_app: SolidWorksApp,
    feature_name: str,
    suppressed: bool,
) -> dict:
    """Suppress or unsuppress a feature."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        feat = _find_feature(model, feature_name)
        if feat is None:
            return error_response(f"Feature not found: {feature_name}")

        # SetSuppression2(state, configuration_option, configuration_names)
        state = swFeatureSuppressed if suppressed else swFeatureUnsuppressed
        result = feat.SetSuppression2(state, 0, "")
        if not result:
            return error_response(
                f"SolidWorks rejected the suppression change for '{feature_name}'",
                code="SW_API_ERROR",
            )

        status = "suppressed" if suppressed else "unsuppressed"
        return success_response(
            data={"feature_name": feature_name, "suppressed": suppressed, "result": result},
            message=f"Feature '{feature_name}' {status}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to set feature suppression")
        return error_response(f"Failed to set feature suppression: {exc}")


def get_features(sw_app: SolidWorksApp) -> dict:
    """Return a list of feature names in the active document."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        names = []
        feat = _first_feature(model)
        while feat is not None:
            names.append(feat.Name)
            feat = _next_feature(feat)

        return success_response(
            data={"features": names, "count": len(names)},
            message=f"Found {len(names)} features",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get features")
        return error_response(f"Failed to get features: {exc}")


def get_feature_details(
    sw_app: SolidWorksApp,
    feature_name: Optional[str] = None,
) -> dict:
    """Return type, dimensions, and suppression state for features.

    With ``feature_name`` set, describe that single feature; otherwise
    describe every feature in the tree. Dimension values come back in mm.
    """
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        details: List[Dict[str, Any]] = []
        steps = 0
        feat = _first_feature(model)
        while feat is not None and steps < MAX_FEATURE_WALK:
            name = feat.Name
            if feature_name is None or name == feature_name:
                details.append(_describe_feature(feat, name))
                if feature_name is not None:
                    break
            steps += 1
            feat = _next_feature(feat)

        if feature_name is not None and not details:
            return error_response(f"Feature not found: {feature_name}")

        return success_response(
            data={"features": details, "count": len(details)},
            message=f"Described {len(details)} feature(s)",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get feature details")
        return error_response(f"Failed to get feature details: {exc}")


def _describe_feature(feat: Any, name: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {"name": name}
    # makepy wrappers expose zero-arg COM members as properties; dynamic
    # dispatch exposes them as methods — call_or_value covers both.
    try:
        info["type_name"] = call_or_value(feat, "GetTypeName2")
    except Exception:
        info["type_name"] = None
    try:
        suppressed = call_or_value(feat, "IsSuppressed")
        if isinstance(suppressed, tuple):
            suppressed = suppressed[0]
        info["suppressed"] = bool(suppressed)
    except Exception:
        info["suppressed"] = None
    info["dimensions"] = _feature_dimensions(feat)
    return info


def _system_value_m(raw: Any) -> Optional[float]:
    """Normalize GetSystemValue3 return shapes across dispatch modes.

    Dynamic dispatch returns the bare system value; makepy wrappers
    return ``(values_array, retval)``.
    """
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, (tuple, list)):
        if raw and isinstance(raw[0], (tuple, list)):
            return float(raw[0][0]) if raw[0] else None
        if raw and isinstance(raw[0], (int, float)):
            return float(raw[0])
    return None


def _feature_dimensions(feat: Any) -> List[Dict[str, Any]]:
    dims: List[Dict[str, Any]] = []
    try:
        disp = call_or_value(feat, "GetFirstDisplayDimension")
    except Exception:
        return dims
    steps = 0
    while disp is not None and steps < MAX_FEATURE_WALK:
        try:
            dim = disp.GetDimension2(0)
            value_m = _system_value_m(dim.GetSystemValue3(1, ""))  # metres
            dims.append({
                "full_name": dim.FullName,
                "value_mm": round(value_m * 1000.0, 6) if value_m is not None else None,
            })
        except Exception as exc:
            dims.append({"full_name": None, "error": str(exc)})
            break
        try:
            disp = feat.GetNextDisplayDimension(disp)
        except Exception:
            break
        steps += 1
    return dims
