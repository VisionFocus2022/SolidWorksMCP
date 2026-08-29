"""Assembly-level SolidWorks operations."""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional

import pythoncom
import win32com.client

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swDocASSEMBLY,
    swMateANGLE,
    swMateCOINCIDENT,
    swMateCONCENTRIC,
    swMateDISTANCE,
    swMateTANGENT,
    swMateWIDTH,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.solidworks_api import file_io
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import (
    ensure_sink_path,
    validate_extension,
    validate_output_file,
    validate_path,
)
from solidworks_mcp.utils.templates import get_assembly_template
from solidworks_mcp.utils.validation import finite_number

logger = logging.getLogger(__name__)

MAX_INTERFERENCES = 50
MAX_COMPONENTS = 500

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


def new_assembly(
    sw_app: SolidWorksApp,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a new empty assembly document (GB template).

    Real machine (T11 probe): ``AddComponent4`` silently returns None unless
    the component's document is already open in the session — the component
    tools below pre-open parts via OpenDoc6.
    """
    try:
        template = get_assembly_template()
        if not template:
            return error_response(
                "No assembly template found; set SOLIDWORKS_MCP_ASSEMBLY_TEMPLATE "
                "to a .asmdot file",
                code="TEMPLATE_NOT_FOUND",
            )
        model = sw_app.app.NewDocument(template, 0, 0, 0)
        if model is None:
            return error_response(
                "SolidWorks rejected creating the assembly document",
                code="SW_API_ERROR",
            )

        saved_path = None
        if save_path:
            valid, msg = validate_output_file(
                save_path, {".sldasm"}, overwrite_confirm
            )
            if not valid:
                return error_response(msg, code="INVALID_OUTPUT_PATH")
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if result != 0:
                return error_response(f"Saving assembly failed with code {result}")
            saved_path = save_path

        return success_response(
            data={
                "title": call_or_value(model, "GetTitle"),
                "template": template,
                "type": swDocASSEMBLY,
                "saved_path": saved_path,
            },
            message="Created new assembly document",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to create assembly")
        return error_response(f"Failed to create assembly: {exc}")


def _preopen_component_document(sw_app: SolidWorksApp, file_path: str) -> Optional[str]:
    """Open the component document before AddComponent4 (real-machine rule).

    Returns None on success or an error message.
    """
    try:
        doc_type = file_io._guess_document_type(file_path)
        model, error_code, _ = file_io._open_doc6(sw_app.app, file_path, doc_type)
    except Exception as exc:
        return f"could not open component document ({exc})"
    if model is None:
        return (
            "SolidWorks would not open the component document "
            f"(load error {error_code}); AddComponent4 requires the part to "
            "be open in the session"
        )
    return None


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
        preopen_error = _preopen_component_document(sw_app, file_path)
        if preopen_error:
            return error_response(preopen_error, code="SW_API_ERROR")
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
        mate_type: One of "coincident", "concentric", "distance", "tangent",
            "angle", "width". Real machine (T11 probe): coincident/distance/
            angle verified — angle mates must pass the value through the
            ``Angle`` slot (parameter 10) in radians; tangent/width are
            mapped but need face/4-selection fixtures and remain unverified
            on this machine.
        entity1: Name of the first face/plane/axis (e.g. "Front Plane@Part1-1").
        entity2: Name of the second face/plane/axis.
        distance: Distance in mm (distance mate) or angle in degrees
            (angle mate). Entity names must be component-qualified and are
            selected as "<name>@<assembly title>" first — bare names can
            mis-select on the real machine.
    """
    try:
        model = sw_app.get_active_document()
        if model is None or call_or_value(model, "GetType") != swDocASSEMBLY:
            return error_response("No active assembly document")

        mate_type_map = {
            "coincident": swMateCOINCIDENT,
            "concentric": swMateCONCENTRIC,
            "distance": swMateDISTANCE,
            "tangent": swMateTANGENT,
            "angle": swMateANGLE,
            "width": swMateWIDTH,
        }
        mate_type_val = mate_type_map.get(mate_type.lower())
        if mate_type_val is None:
            return error_response(
                f"Unsupported mate type: {mate_type}. "
                "Use: coincident, concentric, distance, tangent, angle, width"
            )
        if mate_type_val in (swMateDISTANCE, swMateANGLE):
            if distance is None:
                return error_response(
                    f"distance is required for a {mate_type} mate "
                    "(mm for distance, degrees for angle)",
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

        # Angle mates carry their value in the Angle slot (parameter 10,
        # radians); distance mates in the Distance slot (metres).
        if mate_type_val == swMateANGLE:
            dist_m = 0.0
            angle_val = math.radians(distance)
        else:
            dist_m = (distance / 1000.0) if distance is not None else 0.0
            angle_val = 0.0
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
            0,  # gear ratio numerator
            0,  # gear ratio denominator
            angle_val,
            angle_val,
            angle_val,
            False,  # for positioning only
            False,  # lock rotation
            0,  # width mate option
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


def check_interference(sw_app: SolidWorksApp) -> dict:
    """Check pairwise interference between components in the active assembly.

    Real machine (T11 probe): overlapping boxes → one interference with
    ``Volume`` in m³ and ``Components`` as a component array; separated
    parts → empty. ``TreatCoincidenceAsInterference`` is settable;
    ``TreatSubBodiesAsInterference`` is rejected on this machine and is
    skipped.
    """
    try:
        model = sw_app.get_active_document()
        if model is None or call_or_value(model, "GetType") != swDocASSEMBLY:
            return error_response("No active assembly document")

        mgr = call_or_value(model, "InterferenceDetectionManager")
        if mgr is None:
            return error_response(
                "SolidWorks refused to provide the interference detector",
                code="SW_API_ERROR",
            )
        try:
            mgr.TreatCoincidenceAsInterference = False
        except Exception:
            logger.debug("TreatCoincidenceAsInterference not settable", exc_info=True)

        interferences = call_or_value(mgr, "GetInterferences") or []
        rows: List[Dict[str, Any]] = []
        for inter in list(interferences)[:MAX_INTERFERENCES]:
            volume = call_or_value(inter, "Volume")
            comps = call_or_value(inter, "Components") or []
            names = [
                n
                for c in list(comps)[:MAX_COMPONENTS]
                if isinstance((n := call_or_value(c, "Name2")), str)
            ]
            rows.append(
                {
                    "volume_mm3": round(volume * 1e9, 3)
                    if isinstance(volume, (int, float))
                    else None,
                    "components": names,
                }
            )

        return success_response(
            data={
                "interference_count": len(rows),
                "has_interference": bool(rows),
                "interferences": rows,
            },
            message=(
                f"Found {len(rows)} interference(s)"
                if rows
                else "No interferences detected"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to check interference")
        return error_response(f"Failed to check interference: {exc}")


def get_bom(sw_app: SolidWorksApp) -> dict:
    """Aggregate a bill of materials from the active assembly's components.

    Instances of the same file+configuration are merged with a count.
    """
    try:
        model = sw_app.get_active_document()
        if model is None or call_or_value(model, "GetType") != swDocASSEMBLY:
            return error_response("No active assembly document")

        comps = model.GetComponents(False) or []
        items: Dict[tuple, Dict[str, Any]] = {}
        total = 0
        for comp in list(comps)[:MAX_COMPONENTS]:
            name2 = call_or_value(comp, "Name2")
            if not isinstance(name2, str):  # degenerate proxy — skip
                continue
            path = call_or_value(comp, "GetPathName")
            if not isinstance(path, str):
                path = ""
            config = call_or_value(comp, "ReferencedConfiguration")
            if not isinstance(config, str):
                config = ""
            total += 1
            key = (path.lower(), config)
            if key not in items:
                items[key] = {
                    "name": os.path.splitext(os.path.basename(path))[0],
                    "path": path,
                    "configuration": config,
                    "count": 0,
                }
            items[key]["count"] += 1

        return success_response(
            data={
                "items": list(items.values()),
                "total_components": total,
                "unique_parts": len(items),
            },
            message=(
                f"BOM: {len(items)} unique part(s), {total} component instance(s)"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get BOM")
        return error_response(f"Failed to get BOM: {exc}")
