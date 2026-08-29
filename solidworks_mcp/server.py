"""Standard MCP server for SolidWorks 2026 COM automation."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Annotated, Any, Callable, Dict, List, Literal, Optional, TypedDict

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from solidworks_mcp import __version__
from solidworks_mcp.config import get_config
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.assembly import add_component, add_mate, get_components
from solidworks_mcp.solidworks_api.design import (
    create_new_part,
    create_plate,
    cut_round_hole,
    cut_threaded_hole,
    execute_design_plan,
)
from solidworks_mcp.solidworks_api.features import (
    get_feature_details,
    get_features,
    rename_feature,
    set_feature_suppression,
)
from solidworks_mcp.solidworks_api.file_io import (
    close_document,
    export_step,
    export_stl,
    import_step,
    open_document,
)
from solidworks_mcp.solidworks_api.topology import list_bodies, list_faces
from solidworks_mcp.solidworks_api.decorations import (
    apply_chamfer,
    apply_fillet,
    apply_shell,
)
from solidworks_mcp.solidworks_api.measure import get_bounding_box, measure_distance
from solidworks_mcp.solidworks_api.part import (
    create_box,
    create_cone,
    create_cylinder,
    create_revolved,
    get_mass_properties,
)
from solidworks_mcp.solidworks_api.pattern import (
    AnnularRing,
    build_annular_layout,
    create_annular_pattern,
)
from solidworks_mcp.examples.ring_light import create_ring_light
from solidworks_mcp.examples.ring_light_v3 import create_ring_light_v3
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.com_executor import (
    ComCallTimeoutError,
    ComExecutorPoisonedError,
    run_com,
)
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.security import DEFAULT_ALLOWED_ROOT

PositiveMM = Annotated[
    float,
    Field(gt=0, allow_inf_nan=False, description="Positive length in millimeters"),
]
FiniteMM = Annotated[
    float,
    Field(allow_inf_nan=False, description="Finite coordinate in millimeters"),
]
NonNegativeMM = Annotated[
    float,
    Field(ge=0, allow_inf_nan=False, description="Non-negative length in millimeters"),
]
NonEmptyString = Annotated[str, Field(min_length=1)]
MateType = Literal["coincident", "concentric", "distance"]
EntityType = Literal["AUTO", "FACE", "PLANE", "AXIS", "EDGE", "VERTEX"]


class ToolError(TypedDict):
    code: str
    details: Any


class ToolResult(TypedDict):
    success: bool
    data: Any
    message: str
    warning: Optional[str]
    error: Optional[ToolError]

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
STATE_CHANGE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)
IDEMPOTENT_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=False,
)


def _configure_logging() -> None:
    config = get_config()
    try:
        log_path = Path(config.log_path)
        handler: logging.Handler = RotatingFileHandler(
            log_path,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[handler],
    )


mcp = FastMCP(
    "solidworks-mcp",
    instructions=(
        "Design and inspect SolidWorks documents. All lengths are millimeters. "
        "Call solidworks_design_capabilities before planning geometry, keep file "
        "paths under allowed_root, and require explicit confirmation to overwrite."
    ),
)

# FastMCP 1.x does not expose version in its constructor.
mcp._mcp_server.version = __version__

DOC_TYPES = {1: "part", 2: "assembly", 3: "drawing"}


def _sw():
    return get_solidworks_app()


def _com_timeout() -> Optional[float]:
    """COM call timeout in seconds; None keeps the historic no-timeout mode."""
    timeout = get_config().com_timeout_seconds
    return timeout if timeout > 0 else None


def _call_connected(
    operation: Callable[[Any], dict],
    launch_if_needed: Optional[bool] = None,
) -> dict:
    """Connect and execute one operation in the dedicated COM apartment."""

    def invoke() -> dict:
        sw = _sw()
        connection = sw.connect(launch_if_needed=launch_if_needed)
        if not connection["success"]:
            return connection
        return operation(sw)

    try:
        return run_com(invoke, timeout=_com_timeout())
    except ComCallTimeoutError as exc:
        return error_response(str(exc), code="SW_TIMEOUT")
    except ComExecutorPoisonedError as exc:
        return error_response(str(exc), code="SW_EXECUTOR_POISONED")
    except Exception as exc:
        logging.getLogger(__name__).exception("Unhandled SolidWorks tool error")
        return error_response(
            "SolidWorks operation failed unexpectedly",
            code="SW_API_ERROR",
            details={"exception_type": type(exc).__name__},
        )


def _active_document_data(sw: Any) -> dict:
    model = sw.get_active_document()
    if model is None:
        return success_response(data=None, message="No active document")
    doc_type = int(call_or_value(model, "GetType"))
    path = call_or_value(model, "GetPathName")
    return success_response(
        data={
            "title": call_or_value(model, "GetTitle"),
            "type": doc_type,
            "type_name": DOC_TYPES.get(doc_type, "unknown"),
            "path": path or None,
        },
        message="Active document retrieved",
    )


def _capabilities() -> Dict[str, Any]:
    config = get_config()
    return {
        "name": "solidworks-mcp",
        "version": __version__,
        "solidworks_version": config.solidworks_version,
        "transport": "stdio",
        "units": {
            "tool_length": "millimeter",
            "solidworks_internal_length": "meter",
            "angle": "radian unless a tool says otherwise",
        },
        "allowed_root": DEFAULT_ALLOWED_ROOT,
        "auto_start": config.auto_start,
        "tools": [tool.name for tool in mcp._tool_manager.list_tools()],
        "design_plan_operations": [
            {"type": "new_part"},
            {"type": "box", "width": 100, "depth": 60, "height": 10},
            {"type": "plate", "width": 100, "depth": 60, "thickness": 6},
            {"type": "cylinder", "diameter": 20, "height": 40},
            {"type": "cone", "bottom_diameter": 30, "top_diameter": 10, "height": 40},
            {
                "type": "hole",
                "diameter": 6,
                "x": 15,
                "y": 10,
                "plane": "top",
                "through_all": True,
            },
            {
                "type": "threaded_hole",
                "spec": "M6",
                "x": 15,
                "y": 10,
                "plane": "top",
                "through_all": True,
            },
            {
                "type": "annular_pattern",
                "rings": [{"radius_mm": 30, "count": 6, "diameter_mm": 6}],
                "plane": "top",
                "feature_kind": "cut",
                "through_all": True,
            },
        ],
        "safety": [
            "All file paths must stay under allowed_root.",
            "Outputs require an existing parent directory and the correct extension.",
            "Overwriting an existing file requires overwrite_confirm=true.",
            "SolidWorks auto-start follows configuration unless a tool overrides it.",
            "SolidWorks COM calls are serialized on one STA thread.",
        ],
        "limitations": [
            "Design plans currently support primitive bosses (box/plate/cylinder/cone), round cut holes, ISO threaded holes, and annular patterns.",
            "solidworks_part_create_ring_light generates a validated spherical-dome LED layout (row_counts is free-form, defaulting to the confirmed 9-row product layout); the native SLDPRT uses 24 annular bands when FeatureRevolve2 is unavailable.",
            "Assembly mates use the compatibility AddMate5 API for basic mate types.",
            "Complex surfaces, drawings, simulation, and PDM are not yet exposed.",
        ],
    }


@mcp.resource(
    "solidworks://capabilities",
    title="SolidWorks MCP capabilities",
    mime_type="application/json",
)
def solidworks_capabilities_resource() -> str:
    """Read supported operations, units, safety rules, and limitations."""
    return json.dumps(_capabilities(), ensure_ascii=False, indent=2)


@mcp.resource(
    "solidworks://status",
    title="SolidWorks connection status",
    mime_type="application/json",
)
def solidworks_status_resource() -> str:
    """Probe the cached SolidWorks connection without launching the application."""
    status = run_com(_sw().status, timeout=_com_timeout())
    status["allowed_root"] = DEFAULT_ALLOWED_ROOT
    return json.dumps(status, ensure_ascii=False, indent=2)


@mcp.resource(
    "solidworks://active-document",
    title="Active SolidWorks document",
    mime_type="application/json",
)
def solidworks_active_document_resource() -> str:
    """Read the active document, attaching only to an already running SolidWorks."""
    result = _call_connected(_active_document_data, launch_if_needed=False)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.prompt(title="Design a SolidWorks part")
def solidworks_design_part_prompt(requirements: str) -> str:
    """Convert part requirements into conservative, executable MCP calls."""
    return (
        "You are designing a SolidWorks part through solidworks-mcp.\n"
        "Use millimeters for all tool length parameters. First call "
        "solidworks_design_capabilities and inspect the active document. Prefer one "
        "solidworks_design_execute_plan call for supported geometry. Do not invent "
        "dimensions, planes, feature names, or overwrite approval. If required "
        "geometry is unsupported, explain the exact missing operation and ask only "
        "for the parameter needed to continue. Verify the result with feature and "
        "mass-property tools before export.\n\n"
        f"Design requirements:\n{requirements}"
    )


@mcp.tool(
    title="Connect to SolidWorks",
    annotations=STATE_CHANGE,
    structured_output=True,
)
def solidworks_connect(launch_if_needed: Optional[bool] = None) -> ToolResult:
    """Connect to SolidWorks; null uses SOLIDWORKS_MCP_AUTO_START."""
    try:
        return run_com(_sw().connect, launch_if_needed, timeout=_com_timeout())
    except ComCallTimeoutError as exc:
        return error_response(str(exc), code="SW_TIMEOUT")
    except ComExecutorPoisonedError as exc:
        return error_response(str(exc), code="SW_EXECUTOR_POISONED")
    except Exception as exc:
        logging.getLogger(__name__).exception("SolidWorks connection request failed")
        return error_response(
            "Could not execute the SolidWorks connection request",
            code="SW_API_ERROR",
            details={"exception_type": type(exc).__name__},
        )


@mcp.tool(title="Get active document", annotations=READ_ONLY, structured_output=True)
def solidworks_get_active_document(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Return the active document title, path, numeric type, and type name."""
    return _call_connected(_active_document_data, launch_if_needed)


@mcp.tool(title="Get design capabilities", annotations=READ_ONLY, structured_output=True)
def solidworks_design_capabilities() -> ToolResult:
    """Return supported design operations, units, safety rules, and limitations."""
    return success_response(
        data=_capabilities(),
        message="SolidWorks MCP capabilities retrieved",
    )


@mcp.tool(title="Create new part", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_new(
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Create a blank part; save_path must end in .sldprt."""
    return _call_connected(
        lambda sw: create_new_part(sw, save_path, overwrite_confirm),
        launch_if_needed,
    )


@mcp.tool(title="Create rectangular plate", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_plate(
    width: PositiveMM,
    depth: PositiveMM,
    thickness: PositiveMM,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Add a centered rectangular plate boss to the active part, or create a part."""
    return _call_connected(
        lambda sw: create_plate(
            sw, width, depth, thickness, save_path, overwrite_confirm
        ),
        launch_if_needed,
    )


@mcp.tool(title="Create box", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_box(
    width: PositiveMM,
    depth: PositiveMM,
    height: PositiveMM,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Add a centered rectangular boss to the active part, or create a part."""
    return _call_connected(
        lambda sw: create_box(sw, width, depth, height, save_path, overwrite_confirm),
        launch_if_needed,
    )


@mcp.tool(title="Create cylinder", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_cylinder(
    diameter: PositiveMM,
    height: PositiveMM,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Add a centered cylindrical boss to the active part, or create a part."""
    return _call_connected(
        lambda sw: create_cylinder(
            sw, diameter, height, save_path, overwrite_confirm
        ),
        launch_if_needed,
    )


@mcp.tool(title="Cut round hole", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_part_cut_round_hole(
    diameter: PositiveMM,
    x: FiniteMM = 0.0,
    y: FiniteMM = 0.0,
    plane: NonEmptyString = "top",
    depth: Optional[PositiveMM] = None,
    through_all: bool = True,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Cut a round hole from top/front/right or an exact named plane."""
    return _call_connected(
        lambda sw: cut_round_hole(
            sw, diameter, x, y, plane, depth, through_all
        ),
        launch_if_needed,
    )


@mcp.tool(title="Create cone", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_cone(
    bottom_diameter: PositiveMM,
    height: PositiveMM,
    top_diameter: NonNegativeMM = 0.0,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Add a centered conical/frustum boss (drafted extrusion) to the active part."""
    return _call_connected(
        lambda sw: create_cone(
            sw, bottom_diameter, top_diameter, height, save_path, overwrite_confirm
        ),
        launch_if_needed,
    )


@mcp.tool(title="Create revolved part", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_revolved(
    outer_diameter: PositiveMM,
    height: PositiveMM,
    bore_diameter: NonNegativeMM = 0.0,
    plane: str = "front",
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Revolved disc/ring/shaft segment (feature-tree based) around a sketch centerline."""
    return _call_connected(
        lambda sw: create_revolved(
            sw, outer_diameter, height, bore_diameter, plane, save_path,
            overwrite_confirm,
        ),
        launch_if_needed,
    )


@mcp.tool(title="Apply fillet to faces", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_apply_fillet(
    face_names: List[NonEmptyString],
    radius_mm: PositiveMM,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Fillet all edges of the named faces (names from list_faces) with a constant radius."""
    return _call_connected(
        lambda sw: apply_fillet(sw, face_names, radius_mm),
        launch_if_needed,
    )


@mcp.tool(title="Apply chamfer to faces", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_apply_chamfer(
    face_names: List[NonEmptyString],
    distance_mm: PositiveMM,
    angle_deg: float = 45.0,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Chamfer all edges of the named faces by distance and angle (0<angle<90)."""
    return _call_connected(
        lambda sw: apply_chamfer(sw, face_names, distance_mm, angle_deg),
        launch_if_needed,
    )


@mcp.tool(title="Shell part", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_apply_shell(
    face_names: List[NonEmptyString],
    thickness_mm: PositiveMM,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Hollow the part keeping thickness_mm walls; the named faces are removed."""
    return _call_connected(
        lambda sw: apply_shell(sw, face_names, thickness_mm),
        launch_if_needed,
    )


@mcp.tool(title="Cut threaded hole", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_part_cut_threaded_hole(
    spec: NonEmptyString,
    x: FiniteMM = 0.0,
    y: FiniteMM = 0.0,
    plane: NonEmptyString = "top",
    depth: Optional[PositiveMM] = None,
    through_all: bool = True,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Cut an ISO coarse-thread hole (M2-M20) at its tap-drill diameter with a cosmetic thread."""
    return _call_connected(
        lambda sw: cut_threaded_hole(
            sw, spec, x, y, plane, depth, through_all
        ),
        launch_if_needed,
    )


@mcp.tool(title="Preview annular pattern layout", annotations=READ_ONLY, structured_output=True)
def solidworks_pattern_annular_layout(
    rings: List[AnnularRing],
    avoid_angles_degrees: Optional[List[float]] = None,
) -> ToolResult:
    """Compute ring positions, optimized phases, and overlap warnings without touching SolidWorks."""
    try:
        layout = build_annular_layout(rings, avoid_angles_degrees)
    except (ValueError, ValidationError) as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    return success_response(
        data=layout,
        message=(
            f"Annular layout: {layout['total_feature_count']} features "
            f"on {len(layout['rings'])} rings"
        ),
    )


@mcp.tool(title="Create annular feature pattern", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_part_create_annular_pattern(
    rings: List[AnnularRing],
    plane: NonEmptyString = "top",
    feature_kind: Literal["cut", "boss"] = "cut",
    depth: Optional[PositiveMM] = None,
    through_all: bool = True,
    avoid_angles_degrees: Optional[List[float]] = None,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Cut or extrude concentric rings of circular features on a named plane (bosses always blind)."""
    return _call_connected(
        lambda sw: create_annular_pattern(
            sw,
            rings,
            plane=plane,
            feature_kind=feature_kind,
            depth=depth,
            through_all=through_all,
            avoid_angles_degrees=avoid_angles_degrees,
            save_path=save_path,
            overwrite_confirm=overwrite_confirm,
        ),
        launch_if_needed,
    )


@mcp.tool(title="Create 9-row ring light", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_ring_light(
    save_path: NonEmptyString,
    outer_diameter: PositiveMM = 80.0,
    center_hole_diameter: PositiveMM = 40.0,
    carrier_thickness: PositiveMM = 60.0,
    led_diameter: PositiveMM = 2.6,
    row_counts: Optional[List[int]] = None,
    start_angle_degrees: float = 30.0,
    end_angle_degrees: float = 60.0,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Create a dome ring-light part (defaults to the confirmed 9-row layout) and save it as .sldprt."""
    return _call_connected(
        lambda sw: create_ring_light(
            sw,
            save_path=save_path,
            overwrite_confirm=overwrite_confirm,
            outer_diameter=outer_diameter,
            center_hole_diameter=center_hole_diameter,
            carrier_thickness=carrier_thickness,
            led_diameter=led_diameter,
            row_counts=row_counts,
            start_angle_degrees=start_angle_degrees,
            end_angle_degrees=end_angle_degrees,
        ),
        launch_if_needed,
    )

@mcp.tool(title="Create STEP-based concave 9-row ring light", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_ring_light_v3(
    source_path: NonEmptyString,
    save_path: NonEmptyString,
    row_counts: Optional[List[int]] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Preserve a STEP-derived housing and replace its front annulus with a concave dish (defaults to the confirmed 9-row layout)."""
    return _call_connected(
        lambda sw: create_ring_light_v3(
            sw,
            source_path=source_path,
            save_path=save_path,
            overwrite_confirm=overwrite_confirm,
            row_counts=row_counts,
        ),
        launch_if_needed,
    )

@mcp.tool(title="Execute design plan", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_design_execute_plan(
    operations: List[Dict[str, Any]],
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Execute ordered new_part, box, plate, cylinder, and hole operations."""
    return _call_connected(
        lambda sw: execute_design_plan(
            sw, operations, save_path, overwrite_confirm
        ),
        launch_if_needed,
    )


@mcp.tool(title="Get mass properties", annotations=READ_ONLY, structured_output=True)
def solidworks_part_get_mass_properties(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Read volume, area, mass, center of mass, and their SI units."""
    return _call_connected(get_mass_properties, launch_if_needed)


@mcp.tool(title="Open document", annotations=STATE_CHANGE, structured_output=True)
def solidworks_file_open(
    file_path: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Open an existing document under allowed_root."""
    return _call_connected(lambda sw: open_document(sw, file_path), launch_if_needed)


@mcp.tool(title="Close document", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_file_close(
    save_changes: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Close the active document; unsaved edits are discarded unless save_changes=true."""
    return _call_connected(
        lambda sw: close_document(sw, save_changes),
        launch_if_needed,
    )


@mcp.tool(title="Import STEP", annotations=STATE_CHANGE, structured_output=True)
def solidworks_file_import_step(
    file_path: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Import an existing .step or .stp file under allowed_root."""
    return _call_connected(lambda sw: import_step(sw, file_path), launch_if_needed)


@mcp.tool(title="Export STEP", annotations=IDEMPOTENT_WRITE, structured_output=True)
def solidworks_file_export_step(
    file_path: NonEmptyString,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Export the active document to .step or .stp under allowed_root."""
    return _call_connected(
        lambda sw: export_step(sw, file_path, overwrite_confirm),
        launch_if_needed,
    )


@mcp.tool(title="Export STL", annotations=IDEMPOTENT_WRITE, structured_output=True)
def solidworks_file_export_stl(
    file_path: NonEmptyString,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Export the active part to .stl under allowed_root."""
    return _call_connected(
        lambda sw: export_stl(sw, file_path, overwrite_confirm),
        launch_if_needed,
    )


@mcp.tool(title="List features", annotations=READ_ONLY, structured_output=True)
def solidworks_features_list(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """List feature names in the active document."""
    return _call_connected(get_features, launch_if_needed)


@mcp.tool(title="Get feature details", annotations=READ_ONLY, structured_output=True)
def solidworks_features_get_details(
    feature_name: Optional[str] = None,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Type, dimensions (mm), and suppression per feature; null describes all."""
    return _call_connected(
        lambda sw: get_feature_details(sw, feature_name),
        launch_if_needed,
    )


@mcp.tool(title="Measure distance between two points", annotations=READ_ONLY, structured_output=True)
def solidworks_measure_distance(
    point1: List[FiniteMM],
    point2: List[FiniteMM],
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Distance (mm) between two model-space [x, y, z] points given in mm."""
    return _call_connected(
        lambda sw: measure_distance(sw, point1, point2),
        launch_if_needed,
    )


@mcp.tool(title="Get bounding box", annotations=READ_ONLY, structured_output=True)
def solidworks_get_bounding_box(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Merged solid-body bounding box in mm (min/max/size/center)."""
    return _call_connected(get_bounding_box, launch_if_needed)


@mcp.tool(title="List and name faces", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_list_faces(
    name_prefix: str = "Face",
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Enumerate solid faces (type/area mm2); unnamed faces get stable entity names for mating."""
    return _call_connected(
        lambda sw: list_faces(sw, name_prefix),
        launch_if_needed,
    )


@mcp.tool(title="List solid bodies", annotations=READ_ONLY, structured_output=True)
def solidworks_part_list_bodies(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """List solid bodies with names and face counts."""
    return _call_connected(list_bodies, launch_if_needed)


@mcp.tool(title="Rename feature", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_feature_rename(
    old_name: NonEmptyString,
    new_name: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Rename one exactly matched feature in the active document."""
    return _call_connected(
        lambda sw: rename_feature(sw, old_name, new_name),
        launch_if_needed,
    )


@mcp.tool(title="Set feature suppression", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_feature_set_suppression(
    feature_name: NonEmptyString,
    suppressed: bool,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Suppress or unsuppress one exactly matched feature."""
    return _call_connected(
        lambda sw: set_feature_suppression(sw, feature_name, suppressed),
        launch_if_needed,
    )


@mcp.tool(title="Add assembly component", annotations=STATE_CHANGE, structured_output=True)
def solidworks_assembly_add_component(
    file_path: NonEmptyString,
    x: FiniteMM = 0.0,
    y: FiniteMM = 0.0,
    z: FiniteMM = 0.0,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Insert a .sldprt or .sldasm component at an approximate millimeter position."""
    return _call_connected(
        lambda sw: add_component(sw, file_path, x, y, z),
        launch_if_needed,
    )


@mcp.tool(title="List assembly components", annotations=READ_ONLY, structured_output=True)
def solidworks_assembly_list_components(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """List component names in the active assembly."""
    return _call_connected(get_components, launch_if_needed)


@mcp.tool(title="Add assembly mate", annotations=STATE_CHANGE, structured_output=True)
def solidworks_assembly_add_mate(
    mate_type: MateType,
    entity1: NonEmptyString,
    entity2: NonEmptyString,
    distance: Optional[FiniteMM] = None,
    entity1_type: EntityType = "AUTO",
    entity2_type: EntityType = "AUTO",
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Add a basic mate; AUTO tries face, plane, axis, edge, then vertex."""
    return _call_connected(
        lambda sw: add_mate(
            sw,
            mate_type,
            entity1,
            entity2,
            distance,
            entity1_type,
            entity2_type,
        ),
        launch_if_needed,
    )


def main() -> None:
    """Run the local MCP server over stdio."""
    _configure_logging()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


