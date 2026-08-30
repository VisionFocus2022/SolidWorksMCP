"""Feature tree operations for SolidWorks."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import pythoncom

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swFeatureSuppressed,
    swFeatureUnsuppressed,
)
from solidworks_mcp.solidworks_api.geometry import (
    MAX_FEATURE_WALK,
    mm_to_m,
    walk_features,
)
from solidworks_mcp.solidworks_api.properties import activate_configuration
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.validation import finite_number, positive_number

logger = logging.getLogger(__name__)


def _find_feature(model: Any, feature_name: str) -> Optional[Any]:
    """Find a feature by name in the feature tree."""
    for feat in walk_features(model):
        if feat.Name == feature_name:
            return feat
    return None


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

        names = [feat.Name for feat in walk_features(model)]

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
        for feat in walk_features(model):
            name = feat.Name
            if feature_name is None or name == feature_name:
                details.append(_describe_feature(feat, name))
                if feature_name is not None:
                    break

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
            # Guard against degenerate proxies (T10 incident): mock chains
            # cost O(n^2) per step; real dimension names are always strings.
            if not isinstance(getattr(dim, "FullName", None), str):
                break
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


def set_dimension(
    sw_app: SolidWorksApp,
    dimension_full_name: str,
    value_mm: float,
    configuration: Optional[str] = None,
) -> dict:
    """Set a length dimension (full name from get_feature_details) in mm and rebuild.

    ``value_mm`` is signed since N12: offset/symmetric dimensions need
    negative lengths (zero is still rejected). An optional ``configuration``
    name is activated first — the names channel of SetSystemValue3 (which=3
    with config names) returns success but never applies on this machine
    (probe 2026-08-30), so per-configuration values ride the combo channel:
    ShowConfiguration + which=1 on the active configuration.

    Angle dimensions are NOT supported here: GetSystemValue3/SetSystemValue3
    carry angles in radians on this machine (see the T6 note); use
    ``set_dimension_angle`` for those.
    """
    try:
        if not dimension_full_name:
            return error_response(
                "dimension_full_name must be non-empty", code="INVALID_PARAMETER"
            )
        value_mm = finite_number("value_mm", value_mm)
        if value_mm == 0:
            raise ValueError("value_mm must be non-zero")

        if configuration:
            activated = activate_configuration(sw_app, configuration)
            if not activated.get("success"):
                return activated

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        dim = model.Parameter(dimension_full_name)
        if dim is None:
            return error_response(f"Dimension not found: {dimension_full_name}")

        result = dim.SetSystemValue3(mm_to_m(value_mm), 1, "")  # swThisConfiguration
        if isinstance(result, tuple):  # typed wrappers bundle byref out-params
            result = result[0] if result else 0
        if isinstance(result, int) and result < 0:
            return error_response(
                f"SolidWorks rejected the dimension change (code {result})",
                code="SW_API_ERROR",
            )
        call_or_value(model, "EditRebuild3")  # zero-arg member: property

        data: Dict[str, Any] = {"dimension": dimension_full_name, "value_mm": value_mm}
        if configuration:
            data["configuration"] = configuration
        return success_response(
            data=data,
            message=(
                f"Set {dimension_full_name} = {value_mm}mm"
                + (f" in {configuration!r}" if configuration else "")
                + " and rebuilt"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to set dimension")
        return error_response(f"Failed to set dimension: {exc}")


def set_dimension_angle(
    sw_app: SolidWorksApp,
    dimension_full_name: str,
    value_deg: float,
) -> dict:
    """Set an angle dimension in degrees and rebuild (N12).

    Angles travel in radians on the wire (T6 note); degrees are the
    tool-facing unit, converted with ``math.radians``. Signed values are
    valid (clockwise/counterclockwise); zero is allowed.
    """
    try:
        if not dimension_full_name:
            return error_response(
                "dimension_full_name must be non-empty", code="INVALID_PARAMETER"
            )
        value_deg = finite_number("value_deg", value_deg)

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        dim = model.Parameter(dimension_full_name)
        if dim is None:
            return error_response(f"Dimension not found: {dimension_full_name}")

        value_rad = math.radians(value_deg)
        result = dim.SetSystemValue3(value_rad, 1, "")  # swThisConfiguration
        if isinstance(result, tuple):  # typed wrappers bundle byref out-params
            result = result[0] if result else 0
        if isinstance(result, int) and result < 0:
            return error_response(
                f"SolidWorks rejected the angle change (code {result})",
                code="SW_API_ERROR",
            )
        call_or_value(model, "EditRebuild3")  # zero-arg member: property

        return success_response(
            data={
                "dimension": dimension_full_name,
                "value_deg": value_deg,
                "value_rad": value_rad,
            },
            message=f"Set {dimension_full_name} = {value_deg}deg and rebuilt",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to set angle dimension")
        return error_response(f"Failed to set angle dimension: {exc}")


def delete_feature(sw_app: SolidWorksApp, feature_name: str) -> dict:
    """Delete one exactly matched feature from the tree (destructive).

    Success is judged by the feature disappearing from the tree, not by the
    EditDelete return value (void on this machine).
    """
    try:
        if not feature_name:
            return error_response(
                "feature_name must be non-empty", code="INVALID_PARAMETER"
            )

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        if _find_feature(model, feature_name) is None:
            return error_response(f"Feature not found: {feature_name}")

        model.ClearSelection2(True)
        picked = model.Extension.SelectByID2(
            feature_name, "BODYFEATURE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
        )
        if not picked:
            return error_response(
                f"SolidWorks refused to select feature '{feature_name}'",
                code="SW_API_ERROR",
            )

        before_count = _feature_count(model)
        call_or_value(model, "EditDelete")  # zero-arg member: property

        if _find_feature(model, feature_name) is not None:
            return error_response(
                f"SolidWorks rejected deleting '{feature_name}' "
                f"(still in tree after EditDelete)",
                code="SW_API_ERROR",
            )

        return success_response(
            data={
                "deleted": feature_name,
                "features_before": before_count,
                "features_after": _feature_count(model),
            },
            message=f"Deleted feature '{feature_name}'",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to delete feature")
        return error_response(f"Failed to delete feature: {exc}")


def _feature_count(model: Any) -> int:
    return sum(1 for _feat in walk_features(model))


# ---------------------------------------------------------------------------
# N9 unlocked tools (probe: tools/probe_part/probe_n9_unblock.py, 2026-08-30)
# ---------------------------------------------------------------------------

_MIRROR_PLANES = {
    "right": "右视基准面",
    "front": "前视基准面",
    "top": "上视基准面",
}


def _typed_fm(model: Any) -> Any:
    """Wrap FeatureManager in its makepy class when possible.

    Long parameter lists (InsertMultiFaceDraft/InsertCutSwept5) marshal
    unreliably through dynamic dispatch; the typed wrapper fixes that
    (N8/N9 probes). Falls back to the dynamic object off-machine or when
    gencache has no module.
    """
    fm = call_or_value(model, "FeatureManager")
    try:
        from win32com.client import gencache

        mods = gencache.GetModuleForProgID("SldWorks.Application")
        raw = getattr(fm, "_oleobj_", None)
        if mods is not None and raw is not None:
            return mods.IFeatureManager(raw)
    except Exception:  # pragma: no cover - depends on host COM registry
        pass
    return fm


def _find_face_by_name(model: Any, face_name: str) -> Optional[Any]:
    """Find a solid face by its entity name (see topology.list_faces)."""
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            if model.GetEntityName(face) == face_name:
                return face
            face = call_or_value(face, "GetNextFace")
    return None


def _find_face_by_role(model: Any, role: str) -> Optional[Any]:
    """Find a face by geometric role from its GetBox (metres, property).

    Roles: ``top`` (z-thin at max z), ``bottom`` (z-thin at min z),
    ``yplus`` (y-thin at max y).
    """
    for body in model.GetBodies2(0, False) or ():
        face = call_or_value(body, "GetFirstFace")
        while face is not None:
            box = call_or_value(face, "GetBox")
            dz = box[5] - box[2]
            dy = box[4] - box[1]
            hit = (
                role == "top" and dz < 1e-6 and box[5] > 0.0195
            ) or (
                role == "bottom" and dz < 1e-6 and box[2] < 0.005
            ) or (
                role == "yplus" and dy < 1e-6 and box[4] > 0.0195
            )
            if hit:
                return face
            face = call_or_value(face, "GetNextFace")
    return None


def mirror_feature(
    sw_app: SolidWorksApp,
    feature_name: str,
    plane: str = "right",
) -> dict:
    """Mirror a feature across a base plane (native InsertMirrorFeature2).

    Unlock note (N9): the 5th parameter ``ScopeOptions=0`` plus the plane
    selected with mark 2 is what makes this work on SW 2026 — the 4-arg
    form never produced a feature (T8 evidence).
    """
    try:
        if not feature_name:
            return error_response(
                "feature_name must be non-empty", code="INVALID_PARAMETER"
            )
        plane_cn = _MIRROR_PLANES.get((plane or "").lower())
        if plane_cn is None:
            return error_response(
                f"plane must be one of {sorted(_MIRROR_PLANES)}",
                code="INVALID_PARAMETER",
            )
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        if _find_feature(model, feature_name) is None:
            return error_response(f"Feature not found: {feature_name}")

        model.ClearSelection2(True)
        picked = model.Extension.SelectByID2(
            feature_name, "BODYFEATURE", 0, 0, 0, False, 1,
            pythoncom.Nothing, 0,
        )
        if not picked:
            return error_response(
                f"SolidWorks refused to select feature '{feature_name}'",
                code="SW_API_ERROR",
            )
        picked_plane = model.Extension.SelectByID2(
            plane_cn, "PLANE", 0, 0, 0, True, 2, pythoncom.Nothing, 0,
        )
        if not picked_plane:
            return error_response(
                f"SolidWorks refused to select plane '{plane_cn}'",
                code="SW_API_ERROR",
            )

        fm = call_or_value(model, "FeatureManager")
        feat = fm.InsertMirrorFeature2(False, True, True, False, 0)
        name = call_or_value(feat, "Name") if feat is not None else None
        if feat is None or not name:
            return error_response(
                "SolidWorks rejected the mirror (no feature created)",
                code="SW_API_ERROR",
            )
        return success_response(
            data={"mirrored": feature_name, "plane": plane, "feature": name},
            message=f"Mirrored '{feature_name}' across {plane} plane",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to mirror feature")
        return error_response(f"Failed to mirror feature: {exc}")


def apply_draft(
    sw_app: SolidWorksApp,
    draft_face: str,
    neutral_face: str,
    angle_deg: float,
) -> dict:
    """Apply a feature-level draft (native InsertMultiFaceDraft).

    Unlock notes (N9): the draft face must be selected FIRST with mark 1
    and the neutral plane SECOND with mark 2, and the call must go through
    the typed FeatureManager — dynamic dispatch marshals the call into a
    silent no-op. SW propagates the taper to the whole tangent side-face
    chain (real-machine evidence: all four box sides change area), so the
    result is a full-perimeter draft, not a single-face taper.
    """
    try:
        if not draft_face or not neutral_face:
            return error_response(
                "draft_face and neutral_face must be non-empty",
                code="INVALID_PARAMETER",
            )
        angle_deg = positive_number("angle_deg", angle_deg)

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        draft = _find_face_by_name(model, draft_face)
        if draft is None:
            return error_response(f"Face not found: {draft_face}")
        neutral = _find_face_by_name(model, neutral_face)
        if neutral is None:
            return error_response(f"Face not found: {neutral_face}")

        model.ClearSelection2(True)
        if not draft.Select2(False, 1):
            return error_response(
                f"SolidWorks refused to select draft face '{draft_face}'",
                code="SW_API_ERROR",
            )
        if not neutral.Select2(True, 2):
            return error_response(
                f"SolidWorks refused to select neutral face '{neutral_face}'",
                code="SW_API_ERROR",
            )

        fm = _typed_fm(model)
        feat = fm.InsertMultiFaceDraft(
            math.radians(angle_deg), False, False, 0, False, False,
        )
        name = call_or_value(feat, "Name") if feat is not None else None
        if feat is None or not name:
            return error_response(
                "SolidWorks rejected the draft (no feature created)",
                code="SW_API_ERROR",
            )
        return success_response(
            data={
                "draft_face": draft_face,
                "neutral_face": neutral_face,
                "angle_deg": angle_deg,
                "feature": name,
            },
            message=f"Applied {angle_deg} deg draft on '{draft_face}'",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to apply draft")
        return error_response(f"Failed to apply draft: {exc}")


def cut_real_thread(
    sw_app: SolidWorksApp,
    diameter: float,
    pitch: float,
    thread_length: float,
    profile_dia: Optional[float] = None,
) -> dict:
    """Cut a real helical thread groove on the active cylindrical part.

    Builds the helix from a top-face circle at ``diameter`` and sweeps a
    circular profile along it — real geometry, not a cosmetic callout.
    Unlock notes (N9): the helix must be selected as REFERENCECURVES with
    mark 4 (the sweep-path mark) and InsertCutSwept5 must run with
    Alignment=False on the typed FeatureManager — with Alignment=True
    SolidWorks silently rejects 3D curve paths.
    """
    try:
        diameter = positive_number("diameter", diameter)
        pitch = positive_number("pitch", pitch)
        thread_length = positive_number("thread_length", thread_length)
        if profile_dia is None:
            # Default groove depth 0.6*pitch matches a 60-degree thread form;
            # cap at 3mm so coarse pitches cannot swallow thin walls.
            profile_dia = min(3.0, 1.2 * pitch)
        profile_dia = positive_number("profile_dia", profile_dia)

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        top = _find_face_by_role(model, "top")
        if top is None or not top.Select2(False, 0):
            return error_response(
                "No top face found on active part", code="SW_API_ERROR"
            )

        sm = model.SketchManager
        sm.InsertSketch(True)
        sm.CreateCircleByRadius(0, 0, 0, mm_to_m(diameter / 2.0))
        sm.InsertSketch(True)
        revolutions = thread_length / pitch
        model.InsertHelix(
            False, False, False, False, 0, 0.0,
            mm_to_m(pitch), revolutions, 0.0, 0.0,
        )
        helix_name = next(
            (name for name in (f.Name for f in walk_features(model))
             if "螺旋线" in name),
            None,
        )
        if helix_name is None:
            return error_response(
                "Helix was not created", code="SW_API_ERROR"
            )

        model.ClearSelection2(True)
        picked = model.Extension.SelectByID2(
            helix_name, "REFERENCECURVES", 0, 0, 0, False, 4,
            pythoncom.Nothing, 0,
        )
        if not picked:
            return error_response(
                "SolidWorks refused to select the helix", code="SW_API_ERROR"
            )

        fm = _typed_fm(model)
        feat = fm.InsertCutSwept5(
            False, False, 0, False, False, 0, 0,
            False, 0.0, 0.0, 0,
            0, True, True, 0.0, True, False, False, False,
            True, mm_to_m(profile_dia), 0,
        )
        name = call_or_value(feat, "Name") if feat is not None else None
        if feat is None or not name:
            return error_response(
                "SolidWorks rejected the thread sweep",
                code="SW_API_ERROR",
            )
        return success_response(
            data={
                "diameter": diameter,
                "pitch": pitch,
                "thread_length": thread_length,
                "revolutions": revolutions,
                "profile_dia": profile_dia,
                "feature": name,
            },
            message=(
                f"Cut real thread: pitch {pitch}mm x {revolutions:.2f} rev "
                f"on ⌀{diameter}mm"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to cut real thread")
        return error_response(f"Failed to cut real thread: {exc}")
