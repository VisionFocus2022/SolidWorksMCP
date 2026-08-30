"""Material, custom property, equation, and configuration tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pythoncom
from win32com.client import VARIANT

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value

logger = logging.getLogger(__name__)

MATERIAL_DATABASE = "SOLIDWORKS MATERIALS"  # read back lower-cased by SW


def _bstr_ref() -> Any:
    """BYREF BSTR for the out-params of Get*PropertyName2 / Get2 (T17 probe:
    bare calls fail with DISP_E_PARAMNOTFOUND on this machine)."""
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")


def _first_configuration(model: Any) -> Optional[str]:
    names = call_or_value(model, "GetConfigurationNames")  # zero-arg: property
    if not names:
        return None
    return names[0]


def get_material(sw_app: SolidWorksApp) -> dict:
    """Read the active part's material (name, database, configuration)."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        config = _first_configuration(model)
        if config is None:
            return error_response("No configuration found")
        db_ref = _bstr_ref()
        name = model.GetMaterialPropertyName2(config, db_ref)
        return success_response(
            data={
                "name": name or "",
                "database": db_ref.value or "",
                "configuration": config,
            },
            message=(f"Material: {name}" if name else "No material assigned"),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get material")
        return error_response(f"Failed to get material: {exc}")


def set_material(sw_app: SolidWorksApp, material_name: str) -> dict:
    """Assign a material from the standard SOLIDWORKS MATERIALS library.

    Chinese names (e.g. 合金钢) work on this install; English names are
    silently ignored by SW, so success is judged by reading the name back.
    """
    try:
        if not material_name:
            return error_response(
                "material_name must be non-empty", code="INVALID_PARAMETER"
            )
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        config = _first_configuration(model)
        if config is None:
            return error_response("No configuration found")

        model.SetMaterialPropertyName2(config, MATERIAL_DATABASE, material_name)
        call_or_value(model, "EditRebuild3")

        db_ref = _bstr_ref()
        applied = model.GetMaterialPropertyName2(config, db_ref)
        if applied != material_name:
            return error_response(
                f"SolidWorks rejected the material '{material_name}' "
                "(unknown name — use library names, e.g. 合金钢)",
                code="SW_API_ERROR",
            )
        return success_response(
            data={"name": applied, "database": db_ref.value or ""},
            message=f"Material set to {applied}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to set material")
        return error_response(f"Failed to set material: {exc}")


def set_custom_property(
    sw_app: SolidWorksApp,
    name: str,
    value: str,
) -> dict:
    """Set a document-level custom property (text type, overwrite)."""
    try:
        if not name or value == "" or value is None:
            return error_response(
                "name and value must be non-empty", code="INVALID_PARAMETER"
            )
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        cpm = model.Extension.CustomPropertyManager("")
        result = cpm.Add3(name, 30, str(value), 1)  # 30=text, 1=overwrite
        if isinstance(result, int) and result < 0:
            return error_response(
                f"SolidWorks rejected the property (code {result})",
                code="SW_API_ERROR",
            )
        return success_response(
            data={"name": name, "value": str(value)},
            message=f"Custom property '{name}' set",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to set custom property")
        return error_response(f"Failed to set custom property: {exc}")


def get_custom_properties(sw_app: SolidWorksApp) -> dict:
    """List document-level custom properties (template presets included)."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        cpm = model.Extension.CustomPropertyManager("")
        names = call_or_value(cpm, "GetNames") or ()
        properties: Dict[str, str] = {}
        for name in names:
            value_ref, resolved_ref = _bstr_ref(), _bstr_ref()
            cpm.Get2(name, value_ref, resolved_ref)
            properties[name] = resolved_ref.value or ""
        return success_response(
            data={"properties": properties, "count": len(properties)},
            message=f"Found {len(properties)} custom properties",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get custom properties")
        return error_response(f"Failed to get custom properties: {exc}")


def add_equation(sw_app: SolidWorksApp, equation: str) -> dict:
    """Append an equation or global variable, e.g. '\"x\" = 50'."""
    try:
        if not equation:
            return error_response(
                "equation must be non-empty", code="INVALID_PARAMETER"
            )
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        mgr = call_or_value(model, "GetEquationMgr")  # zero-arg: property
        index = mgr.Add2(-1, equation, True)
        if not isinstance(index, int) or index < 0:
            return error_response(
                f"SolidWorks rejected the equation '{equation}'",
                code="SW_API_ERROR",
            )
        return success_response(
            data={"index": index, "text": mgr.Equation(index)},
            message=f"Equation added at index {index}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to add equation")
        return error_response(f"Failed to add equation: {exc}")


def list_equations(sw_app: SolidWorksApp) -> dict:
    """List all equations and global variables with solved values."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        mgr = call_or_value(model, "GetEquationMgr")
        count = call_or_value(mgr, "GetCount") or 0
        equations: List[Dict[str, Any]] = []
        for index in range(count):
            equations.append({
                "text": mgr.Equation(index),
                "value": mgr.Value(index),
            })
        return success_response(
            data={"equations": equations, "count": count},
            message=f"Found {count} equation(s)",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to list equations")
        return error_response(f"Failed to list equations: {exc}")


def add_configuration(sw_app: SolidWorksApp, name: str) -> dict:
    """Add a derived configuration to the active document."""
    try:
        if not name:
            return error_response("name must be non-empty", code="INVALID_PARAMETER")
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        model.AddConfiguration(name, "", "", False, False, False, True, 0)
        configs = list(call_or_value(model, "GetConfigurationNames") or ())
        if name not in configs:
            return error_response(
                f"SolidWorks rejected the configuration '{name}'",
                code="SW_API_ERROR",
            )
        return success_response(
            data={"configurations": configs, "added": name},
            message=f"Configuration '{name}' added",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to add configuration")
        return error_response(f"Failed to add configuration: {exc}")


def _wrap_equation_mgr_static(mgr: Any) -> Any:
    """Wrap the dynamic EquationMgr in its makepy static class.

    Probe 2026-08-30: ``SetEquation``/``Delete`` are only reachable through
    the typed ``IEquationMgr`` (dynamic dispatch cannot reach the indexed
    propput); same wrap discipline as drawing's ``_wrap_dimension_static``.
    """
    try:
        from win32com.client import gencache

        mods = gencache.GetModuleForProgID("SldWorks.Application")
        if mods is None:
            return None
        return mods.IEquationMgr(mgr._oleobj_)
    except Exception:
        logger.debug("IEquationMgr static wrap failed", exc_info=True)
        return None


def edit_equation(sw_app: SolidWorksApp, index: int, new_text: str) -> dict:
    """Replace the equation text at a zero-based index (N12).

    Calls the typed ``IEquationMgr.SetEquation`` (probe 2026-08-30); the
    judgement is the ``Equation(index)`` read-back, so a silently ignored
    edit reads back as the old text and reports rejection.
    """
    try:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            return error_response(
                "index must be a non-negative integer", code="INVALID_PARAMETER"
            )
        if not new_text:
            return error_response("new_text must be non-empty", code="INVALID_PARAMETER")
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        mgr = call_or_value(model, "GetEquationMgr")
        count = call_or_value(mgr, "GetCount") or 0
        if index >= count:
            return error_response(
                f"index {index} out of range (0..{count - 1})",
                code="INVALID_PARAMETER",
            )
        old_text = mgr.Equation(index)
        target = _wrap_equation_mgr_static(mgr) or mgr
        target.SetEquation(index, new_text)
        if mgr.Equation(index) != new_text:
            return error_response(
                f"SolidWorks rejected the new equation '{new_text}'",
                code="SW_API_ERROR",
            )
        call_or_value(model, "EditRebuild3")
        return success_response(
            data={"index": index, "old_text": old_text, "new_text": new_text},
            message=f"Equation {index} edited",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to edit equation")
        return error_response(f"Failed to edit equation: {exc}")


def delete_equation(sw_app: SolidWorksApp, index_or_text) -> dict:
    """Delete an equation by zero-based index or exact text (N12).

    The judgement is the ``GetCount`` read-back (probe 2026-08-30:
    ``Delete``'s return value carries no semantics).
    """
    try:
        if isinstance(index_or_text, bool) or not isinstance(index_or_text, (int, str)):
            return error_response(
                "index_or_text must be a non-negative integer or equation text",
                code="INVALID_PARAMETER",
            )
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        mgr = call_or_value(model, "GetEquationMgr")
        count = call_or_value(mgr, "GetCount") or 0
        if isinstance(index_or_text, str):
            if not index_or_text:
                return error_response(
                    "index_or_text must be non-empty", code="INVALID_PARAMETER"
                )
            index = next(
                (i for i in range(count) if mgr.Equation(i) == index_or_text),
                None,
            )
            if index is None:
                return error_response(
                    f"No equation matches {index_or_text!r}",
                    code="INVALID_PARAMETER",
                )
        else:
            index = index_or_text
            if index < 0 or index >= count:
                return error_response(
                    f"index {index} out of range (0..{count - 1})",
                    code="INVALID_PARAMETER",
                )

        deleted_text = mgr.Equation(index)
        target = _wrap_equation_mgr_static(mgr) or mgr
        target.Delete(index)
        if (call_or_value(mgr, "GetCount") or 0) != count - 1:
            return error_response(
                "SolidWorks refused to delete the equation", code="SW_API_ERROR"
            )
        return success_response(
            data={"deleted": deleted_text, "remaining": count - 1},
            message=f"Deleted equation {deleted_text!r}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to delete equation")
        return error_response(f"Failed to delete equation: {exc}")


def activate_configuration(sw_app: SolidWorksApp, name: str) -> dict:
    """Activate a named configuration (N12).

    ``ShowConfiguration``'s return value is NOT trustworthy (probe
    2026-08-30: it returns False even on success); the judgement is the
    ``ConfigurationManager.ActiveConfiguration.Name`` read-back.
    """
    try:
        if not name:
            return error_response("name must be non-empty", code="INVALID_PARAMETER")
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        configs = list(call_or_value(model, "GetConfigurationNames") or [])
        if name not in configs:
            return error_response(
                f"Unknown configuration {name!r}; available: {configs}",
                code="INVALID_PARAMETER",
            )
        model.ShowConfiguration(name)
        cfg_mgr = call_or_value(model, "ConfigurationManager")
        active = str(call_or_value(cfg_mgr, "ActiveConfiguration").Name)
        if active != name:
            return error_response(
                f"SolidWorks refused to activate {name!r} (active: {active!r})",
                code="SW_API_ERROR",
            )
        return success_response(
            data={"active": name},
            message=f"Configuration {name!r} activated",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to activate configuration")
        return error_response(f"Failed to activate configuration: {exc}")
