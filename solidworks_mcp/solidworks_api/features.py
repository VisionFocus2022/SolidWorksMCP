"""Feature tree operations for SolidWorks."""

from __future__ import annotations

import logging
from typing import Any, Optional

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swFeatureSuppressed,
    swFeatureUnsuppressed,
)
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
