"""Assembly-level SolidWorks operations."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import pythoncom
import win32com.client

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swDocASSEMBLY,
    swMateCOINCIDENT,
    swMateCONCENTRIC,
    swMateDISTANCE,
)
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import validate_extension, validate_path
from solidworks_mcp.utils.templates import get_assembly_template
from solidworks_mcp.utils.validation import finite_number

logger = logging.getLogger(__name__)

ENTITY_TYPES = ("FACE", "PLANE", "AXIS", "EDGE", "VERTEX")
REFERENCE_PLANE_ALIASES = {
    "Front Plane": "前视基准面",
    "Top Plane": "上视基准面",
    "Right Plane": "右视基准面",
    "前视基准面": "Front Plane",
    "上视基准面": "Top Plane",
    "右视基准面": "Right Plane",
}


def _get_or_create_assembly(sw_app: SolidWorksApp) -> Any:
    """Return the active assembly document, creating a new one if necessary."""
    model = sw_app.get_active_document()
    if model is not None and call_or_value(model, "GetType") == swDocASSEMBLY:
        return model

    template = get_assembly_template()
    if not template:
        raise RuntimeError(
            "Could not find a valid SolidWorks assembly template (.asmdot)"
        )

    model = sw_app.app.NewDocument(template, 0, 0, 0)
    if model is None:
        raise RuntimeError("NewDocument returned None for assembly")
    return model


def add_component(
    sw_app: SolidWorksApp,
    file_path: str,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    config_name: str = "",
) -> dict:
    """Insert a component into the active assembly."""
    try:
        valid, msg = validate_path(file_path, must_exist=True)
        if not valid:
            return error_response(msg)
        valid, msg = validate_extension(file_path, {".sldprt", ".sldasm"})
        if not valid:
            return error_response(msg, code="INVALID_PARAMETER")

        x = finite_number("x", x)
        y = finite_number("y", y)
        z = finite_number("z", z)
        model = _get_or_create_assembly(sw_app)
        # AddComponent4(path, configName, x, y, z)
        component = model.AddComponent4(file_path, config_name, x / 1000.0, y / 1000.0, z / 1000.0)
        if component is None:
            return error_response(f"Failed to add component: {file_path}")

        return success_response(
            data={
                "component_name": component.Name2,
                "file_path": file_path,
                "position": [x, y, z],
            },
            message=f"Added component: {os.path.basename(file_path)}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to add component")
        return error_response(f"Failed to add component: {exc}")


def add_mate(
    sw_app: SolidWorksApp,
    mate_type: str,
    entity1: str,
    entity2: str,
    distance: Optional[float] = None,
    entity1_type: str = "AUTO",
    entity2_type: str = "AUTO",
) -> dict:
    """Add a mate between two named entities in the active assembly.

    Args:
        mate_type: One of "coincident", "concentric", "distance".
        entity1: Name of the first face/plane/axis (e.g. "Front Plane@Part1-1").
        entity2: Name of the second face/plane/axis.
        distance: Distance in mm (only used for "distance" mate).
    """
    try:
        model = sw_app.get_active_document()
        if model is None or call_or_value(model, "GetType") != swDocASSEMBLY:
            return error_response("No active assembly document")

        mate_type_map = {
            "coincident": swMateCOINCIDENT,
            "concentric": swMateCONCENTRIC,
            "distance": swMateDISTANCE,
        }
        mate_type_val = mate_type_map.get(mate_type.lower())
        if mate_type_val is None:
            return error_response(
                f"Unsupported mate type: {mate_type}. "
                "Use: coincident, concentric, distance"
            )
        if mate_type_val == swMateDISTANCE:
            if distance is None:
                return error_response(
                    "distance is required for a distance mate",
                    code="INVALID_PARAMETER",
                )
            distance = finite_number("distance", distance)
            if distance < 0:
                return error_response(
                    "distance must be zero or greater",
                    code="INVALID_PARAMETER",
                )

        assembly_title = os.path.splitext(call_or_value(model, "GetTitle"))[0]

        def select_entity(name: str, requested_type: str, append: bool) -> Optional[str]:
            candidates = (
                ENTITY_TYPES
                if requested_type.upper() == "AUTO"
                else (requested_type.upper(),)
            )
            base_names = [name]
            plane_name, separator, component_name = name.partition("@")
            alias = REFERENCE_PLANE_ALIASES.get(plane_name)
            if alias:
                base_names.append(
                    f"{alias}@{component_name}" if separator else alias
                )
            names = []
            for base_name in base_names:
                if base_name.count("@") == 1:
                    names.append(f"{base_name}@{assembly_title}")
                names.append(base_name)
            for selection_name in names:
                for entity_type in candidates:
                    if entity_type not in ENTITY_TYPES:
                        continue
                    if model.Extension.SelectByID2(
                        selection_name,
                        entity_type,
                        0,
                        0,
                        0,
                        append,
                        1,
                        pythoncom.Nothing,
                        0,
                    ):
                        return entity_type
            return None

        model.ClearSelection2(True)
        selected_type1 = select_entity(entity1, entity1_type, False)
        selected_type2 = select_entity(entity2, entity2_type, True)
        if selected_type1 is None or selected_type2 is None:
            model.ClearSelection2(True)
            return error_response(
                f"Could not select both entities: {entity1}, {entity2}"
            )

        dist_m = (distance / 1000.0) if distance is not None else 0.0
        mate_error = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0
        )
        mate = model.AddMate5(
            mate_type_val,
            0,  # align
            False,  # flip
            dist_m,
            dist_m,
            dist_m,
            0,
            0,
            0,
            0,
            0,
            False,
            False,
            0,
            mate_error,
        )
        model.ClearSelection2(True)

        if mate is None:
            return error_response(
                f"Failed to create mate (SolidWorks error {mate_error.value})",
                code="SW_API_ERROR",
            )

        return success_response(
            data={
                "mate_name": mate.Name,
                "type": mate_type,
                "entity_types": [selected_type1, selected_type2],
                "error_status": mate_error.value,
            },
            message=f"Created {mate_type} mate between '{entity1}' and '{entity2}'",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to add mate")
        return error_response(f"Failed to add mate: {exc}")


def get_components(sw_app: SolidWorksApp) -> dict:
    """List components in the active assembly."""
    try:
        model = sw_app.get_active_document()
        if model is None or call_or_value(model, "GetType") != swDocASSEMBLY:
            return error_response("No active assembly document")

        components = model.GetComponents(False)
        names = [comp.Name2 for comp in components] if components else []

        return success_response(
            data={"components": names, "count": len(names)},
            message=f"Found {len(names)} components",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get components")
        return error_response(f"Failed to get components: {exc}")
