"""Standard MCP server for SolidWorks 2026 COM automation."""

from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Annotated, Any, Callable, Dict, List, Literal, Optional, TypedDict

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from solidworks_mcp import __version__
from solidworks_mcp.config import get_config
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.assembly import (
    add_component,
    add_mate,
    check_interference,
    delete_mate,
    get_bom,
    get_components,
    move_component,
    new_assembly,
    rotate_component,
)
from solidworks_mcp.solidworks_api.design import (
    DESIGN_PLAN_OPERATIONS,
    create_new_part,
    create_plate,
    cut_round_hole,
    cut_threaded_hole,
    execute_design_plan,
    rebuild_csg_plan,
)
from solidworks_mcp.solidworks_api.features import (
    delete_feature,
    get_feature_details,
    get_features,
    rename_feature,
    set_dimension,
    set_feature_suppression,
)
from solidworks_mcp.solidworks_api.file_io import (
    close_document,
    export_dxf,
    export_step,
    export_stl,
    import_step,
    open_document,
)
from solidworks_mcp.solidworks_api.topology import list_bodies, list_faces
from solidworks_mcp.solidworks_api.sheet_metal import create_base_flange
from solidworks_mcp.solidworks_api.decorations import (
    apply_chamfer,
    apply_fillet,
    apply_shell,
)
from solidworks_mcp.solidworks_api.drawing import (
    create_drawing_from_part,
    export_drawing_pdf,
    export_drawing_png,
    insert_model_dimensions,
    insert_note,
    insert_section_view,
    insert_surface_finish,
    organize_dimensions,
    set_tolerance,
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
from solidworks_mcp.solidworks_api.properties import (
    add_configuration,
    add_equation,
    get_custom_properties,
    get_material,
    list_equations,
    set_custom_property,
    set_material,
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
FiniteAngle = Annotated[
    float,
    Field(allow_inf_nan=False, description="Finite angle in degrees"),
]
NonNegativeMM = Annotated[
    float,
    Field(ge=0, allow_inf_nan=False, description="Non-negative length in millimeters"),
]
NonEmptyString = Annotated[str, Field(min_length=1)]
MateType = Literal[
    "coincident", "concentric", "distance", "tangent", "angle", "width"
]
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


def _poisoned_response() -> dict:
    """Structured result for a poisoned COM executor with a recovery path.

    N3: a poisoned executor cannot recover in-process; every later tool
    call would fail. Return an actionable result, or exit outright when
    SOLIDWORKS_MCP_POISONED_EXIT=1 so the stdio host's supervisor can
    restart this server process.
    """
    if get_config().poisoned_exit:
        sys.exit(1)
    return error_response(
        "COM 执行器已毒化（超时线程未返回），所有工具将失败。"
        "恢复方法：重启 MCP 会话/服务器进程。",
        data={"recovery": "restart-mcp-session"},
        code="SW_EXECUTOR_POISONED",
    )


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
    except ComExecutorPoisonedError:
        return _poisoned_response()
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
            "Loft/sweep/complex surfaces, GD&T feature-control frames, simulation, and PDM are not yet exposed.",
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
        "mass-property tools before export.\n"
        "Perception workflow for refinement rounds: "
        "solidworks_features_get_details lists every feature with its dimensions in "
        "mm; solidworks_dimension_set edits one (angles unsupported), "
        "solidworks_feature_delete removes one; solidworks_get_bounding_box and "
        "solidworks_measure_distance verify extents; solidworks_part_list_faces "
        "gives named faces for solidworks_part_apply_fillet/_chamfer/_shell; "
        "solidworks_part_set_material attaches a material (Chinese library names, "
        "e.g. 合金钢) and add_equation links dimensions parametrically.\n\n"
        f"Design requirements:\n{requirements}"
    )


@mcp.prompt(title="Assemble parts with mates")
def solidworks_assembly_prompt(requirements: str) -> str:
    """Guide mating components in an assembly via named entities."""
    return (
        "You are assembling components in SolidWorks through solidworks-mcp.\n"
        "Workflow: solidworks_assembly_new creates the assembly (optionally saving "
        "it), then solidworks_assembly_add_component inserts each saved part "
        "(millimetre coordinates). Before mating, run solidworks_part_list_faces "
        "on the referenced parts to obtain stable face names (Face0, Face1, ...). "
        "solidworks_assembly_add_mate then mates two component-qualified entities "
        "(e.g. \"Face2@box-1\" and \"Face0@cyl-1\") — entity names must carry the "
        "component instance and are matched as \"<name>@<assembly title>\" first. "
        "Verify with solidworks_assembly_check_interference (empty means no "
        "collisions; each hit carries volume_mm3 plus center_mm/bbox_mm for "
        "locating the overlap) and solidworks_assembly_get_bom for the part "
        "list (per-part volume_mm3/mass_g/material). Repair loop: "
        "solidworks_assembly_move_component / _rotate_component transform "
        "the offending component, then re-check interference; "
        "solidworks_assembly_delete_mate removes one mate by exact name. "
        "All lengths are millimetres.\n\n"
        f"Assembly requirements:\n{requirements}"
    )


@mcp.prompt(title="Create a drawing from a part")
def solidworks_drawing_prompt(requirements: str) -> str:
    """Guide producing a dimensioned drawing sheet from a saved part."""
    return (
        "You are producing an engineering drawing through solidworks-mcp.\n"
        "Workflow: solidworks_drawing_create_from_part takes a SAVED .sldprt path "
        "and creates a GB A3 sheet with three projected views (the referenced "
        "part is opened automatically). Then solidworks_drawing_insert_dimensions "
        "pulls the model's dimensions into the views. Export with "
        "solidworks_drawing_export_pdf and solidworks_drawing_export_png (paths "
        "under allowed_root; overwrite needs confirmation). The drawing holds the "
        "part open afterwards — close documents when done.\n\n"
        f"Drawing requirements:\n{requirements}"
    )


@mcp.prompt(title="Rebuild an aicad CSG plan")
def solidworks_csg_rebuild_prompt(requirements: str) -> str:
    """Rebuild a cross-engine CSG scene as an SW feature tree."""
    return (
        "You are rebuilding an aicad CSG scene in SolidWorks through "
        "solidworks-mcp.\n"
        "Call solidworks_features_rebuild_csg with one plan (version 1, "
        "units mm; ops: box, cylinder, cone, cut_cylinder). Contract: the "
        "first op must be box (it creates the part and its stock at the "
        "origin); solid ops stack on the axis -- at.z must equal the current "
        "stack top (heights add up); cut_cylinder keeps its x/y offset and "
        "cuts down from the top; a failed plan rolls back atomically, so fix "
        "only the offending op and re-run. Feature names must be unique.\n"
        "Example 4-op plan:\n"
        '{"version": 1, "units": "mm", "operations": [\n'
        '  {"op": "box", "name": "base", "size": [80, 60, 10], "at": [0, 0, 0]},\n'
        '  {"op": "cylinder", "name": "boss", "diameter": 24, "height": 14, '
        '"at": [0, 0, 10]},\n'
        '  {"op": "cut_cylinder", "name": "hole1", "diameter": 8, '
        '"at": [20, 0, 24], "through": true},\n'
        '  {"op": "cut_cylinder", "name": "hole2", "diameter": 8, '
        '"at": [-20, 0, 24], "depth": 12}]}\n'
        "Verify the result with solidworks_features_list and "
        "solidworks_part_get_mass_properties before saving.\n\n"
        f"CSG scene to rebuild:\n{requirements}"
    )


@mcp.prompt(title="Drive a part family parametrically")
def solidworks_parametric_prompt(requirements: str) -> str:
    """Drive a part family via material, equations, dimensions, configurations."""
    return (
        "You are driving a parametric part family through solidworks-mcp.\n"
        "Workflow: open or build the base part, then solidworks_part_set_material "
        "(Chinese library names, e.g. 合金钢), solidworks_part_add_equation to "
        "link dimensions parametrically (e.g. Height = 2 * Thickness), "
        "solidworks_dimension_set to drive one driving dimension per variant, "
        "and solidworks_part_add_configuration to snapshot each family member; "
        "activate the next configuration and repeat the dimension edits. "
        "Verify every variant with solidworks_part_get_mass_properties and "
        "export with solidworks_file_export_step. All lengths are "
        "millimeters.\n\n"
        f"Part family requirements:\n{requirements}"
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
    except ComExecutorPoisonedError:
        return _poisoned_response()
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


@mcp.tool(title="Set material", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_set_material(
    material_name: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Assign a material from the SOLIDWORKS MATERIALS library (Chinese names, e.g. 合金钢)."""
    return _call_connected(
        lambda sw: set_material(sw, material_name),
        launch_if_needed,
    )


@mcp.tool(title="Get material", annotations=READ_ONLY, structured_output=True)
def solidworks_part_get_material(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Read the active part's material (name, database, configuration)."""
    return _call_connected(get_material, launch_if_needed)


@mcp.tool(title="Set custom property", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_set_custom_property(
    name: NonEmptyString,
    value: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Set a document-level custom property (text type, overwrite)."""
    return _call_connected(
        lambda sw: set_custom_property(sw, name, value),
        launch_if_needed,
    )


@mcp.tool(title="Get custom properties", annotations=READ_ONLY, structured_output=True)
def solidworks_part_get_custom_properties(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """List document-level custom properties with resolved values."""
    return _call_connected(get_custom_properties, launch_if_needed)


@mcp.tool(title="Add equation", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_add_equation(
    equation: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Append an equation or global variable, e.g. '\"x\" = 50'."""
    return _call_connected(
        lambda sw: add_equation(sw, equation),
        launch_if_needed,
    )


@mcp.tool(title="List equations", annotations=READ_ONLY, structured_output=True)
def solidworks_part_list_equations(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """List all equations and global variables with solved values."""
    return _call_connected(list_equations, launch_if_needed)


@mcp.tool(title="Add configuration", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_add_configuration(
    name: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Add a derived configuration to the active document."""
    return _call_connected(
        lambda sw: add_configuration(sw, name),
        launch_if_needed,
    )


@mcp.tool(title="Sheet-metal base flange", annotations=STATE_CHANGE, structured_output=True)
def solidworks_sheet_metal_base_flange(
    width: PositiveMM,
    depth: PositiveMM,
    thickness: PositiveMM,
    radius: float = 0.0,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Create a sheet-metal part from a centred rectangular base flange (GB, flat v1)."""
    return _call_connected(
        lambda sw: create_base_flange(
            sw, width, depth, thickness, radius, save_path, overwrite_confirm
        ),
        launch_if_needed,
    )


@mcp.tool(title="Rebuild CSG plan", annotations=STATE_CHANGE, structured_output=True)
def solidworks_features_rebuild_csg(
    plan: Dict[str, Any],
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Rebuild a cross-engine CSG plan (v1: box/cylinder/cone/cut_cylinder, stacking semantics) as an SW feature tree."""
    return _call_connected(
        lambda sw: rebuild_csg_plan(sw, plan),
        launch_if_needed,
    )


@mcp.tool(title="New assembly", annotations=STATE_CHANGE, structured_output=True)
def solidworks_assembly_new(
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Create a new empty assembly document (GB template), optionally saving it."""
    return _call_connected(
        lambda sw: new_assembly(sw, save_path, overwrite_confirm),
        launch_if_needed,
    )


@mcp.tool(title="Check interference", annotations=READ_ONLY, structured_output=True)
def solidworks_assembly_check_interference(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Report volume and components of every interference in the active assembly."""
    return _call_connected(check_interference, launch_if_needed)


@mcp.tool(title="Get BOM", annotations=READ_ONLY, structured_output=True)
def solidworks_assembly_get_bom(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Aggregate a bill of materials (part, configuration, instance count)."""
    return _call_connected(get_bom, launch_if_needed)


@mcp.tool(title="Create drawing from part", annotations=STATE_CHANGE, structured_output=True)
def solidworks_drawing_create_from_part(
    part_path: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Create a drawing (GB A3 template) from a saved part and project three views. The part must be saved before creating the drawing; close the drawing (solidworks_file_close) when done to release file locks."""
    return _call_connected(
        lambda sw: create_drawing_from_part(sw, part_path),
        launch_if_needed,
    )


@mcp.tool(title="Insert model dimensions", annotations=STATE_CHANGE, structured_output=True)
def solidworks_drawing_insert_dimensions(
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Insert the model's dimensions into the active drawing's views."""
    return _call_connected(insert_model_dimensions, launch_if_needed)


@mcp.tool(title="Export drawing PDF", annotations=IDEMPOTENT_WRITE, structured_output=True)
def solidworks_drawing_export_pdf(
    file_path: NonEmptyString,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Export the active drawing to PDF under allowed_root."""
    return _call_connected(
        lambda sw: export_drawing_pdf(sw, file_path, overwrite_confirm),
        launch_if_needed,
    )


@mcp.tool(title="Export drawing PNG", annotations=IDEMPOTENT_WRITE, structured_output=True)
def solidworks_drawing_export_png(
    file_path: NonEmptyString,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Export the active drawing sheet to PNG (raster) under allowed_root."""
    return _call_connected(
        lambda sw: export_drawing_png(sw, file_path, overwrite_confirm),
        launch_if_needed,
    )


@mcp.tool(title="Organize drawing dimensions", annotations=STATE_CHANGE, structured_output=True)
def solidworks_drawing_organize_dimensions(
    view_name: str = "",
    mode: str = "dedupe_shift",
    shift_step_mm: float = 8.0,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Tidy overlapping dimensions in the active drawing: delete same-feature duplicates within each view, then stagger annotations closer than 2 mm apart by shift_step_mm (sheet mm). Run after solidworks_drawing_insert_dimensions; empty view_name processes every view."""
    return _call_connected(
        lambda sw: organize_dimensions(
            sw, view_name or None, mode, shift_step_mm
        ),
        launch_if_needed,
    )


@mcp.tool(title="Insert section view", annotations=STATE_CHANGE, structured_output=True)
def solidworks_drawing_insert_section_view(
    source_view_name: NonEmptyString,
    cut_position_mm: float = 0.0,
    direction: str = "vertical",
    position_xy_mm: Optional[List[float]] = None,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Create a section view of source_view_name with a straight cut line (vertical/horizontal, offset cut_position_mm in sheet mm from the view anchor; the line is drawn in the blank strip below/left of the view — lines on top of a view never produce a section view). The section view lands 120 mm to the right unless position_xy_mm (sheet mm) is given; SolidWorks assigns the A/B/C label automatically."""
    return _call_connected(
        lambda sw: insert_section_view(
            sw, source_view_name, cut_position_mm, direction, position_xy_mm
        ),
        launch_if_needed,
    )


@mcp.tool(title="Set dimension tolerance", annotations=STATE_CHANGE, structured_output=True)
def solidworks_drawing_set_tolerance(
    dimension_name: NonEmptyString,
    upper_mm: float,
    lower_mm: float,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Set +/- tolerances (PlusMinus type) on a drawing display dimension. dimension_name matches the FullName exactly or without its trailing part segment (e.g. 'D1@SketchName'); bounds are sheet millimetres and keep their sign (lower_mm=-0.05 renders as -0.05). Readback values are returned."""
    return _call_connected(
        lambda sw: set_tolerance(sw, dimension_name, upper_mm, lower_mm),
        launch_if_needed,
    )


@mcp.tool(title="Insert surface finish symbol", annotations=STATE_CHANGE, structured_output=True)
def solidworks_drawing_insert_surface_finish(
    value_um: float = 1.6,
    x_mm: float = 100.0,
    y_mm: float = 50.0,
    symbol: str = "remove_material",
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Insert a surface-finish symbol on the active drawing (default: remove-material Ra symbol). value_um is the Ra value in micrometres (0.008-100); x_mm/y_mm place the symbol in sheet millimetres; symbol picks the shape: basic / remove_material / no_remove_material."""
    return _call_connected(
        lambda sw: insert_surface_finish(sw, value_um, x_mm, y_mm, symbol),
        launch_if_needed,
    )


@mcp.tool(title="Insert drawing note", annotations=STATE_CHANGE, structured_output=True)
def solidworks_drawing_insert_note(
    text: NonEmptyString,
    x_mm: float = 100.0,
    y_mm: float = 50.0,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Insert a plain text note (e.g. technical requirements) on the active drawing at x_mm/y_mm in sheet millimetres."""
    return _call_connected(
        lambda sw: insert_note(sw, text, x_mm, y_mm),
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
    """Execute ordered design operations: new_part, box, plate, cylinder, cone, hole, threaded_hole, annular_pattern."""
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


@mcp.tool(title="Export DXF", annotations=IDEMPOTENT_WRITE, structured_output=True)
def solidworks_file_export_dxf(
    file_path: NonEmptyString,
    overwrite_confirm: bool = False,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Export the active drawing to ASCII .dxf (AC1015) under allowed_root. SolidWorks returns a warning code for DXF saves; success is judged by a valid SECTION header in the written file."""
    return _call_connected(
        lambda sw: export_dxf(sw, file_path, overwrite_confirm),
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
    """Type, dimensions (mm), and suppression per feature; null describes all. Large models require one COM round-trip per feature; expect slower responses on 1000+ feature parts."""
    return _call_connected(
        lambda sw: get_feature_details(sw, feature_name),
        launch_if_needed,
    )


@mcp.tool(title="Set dimension value", annotations=STATE_CHANGE, structured_output=True)
def solidworks_dimension_set(
    dimension_full_name: NonEmptyString,
    value_mm: PositiveMM,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Set a length dimension (full name from features_get_details) in mm and rebuild."""
    return _call_connected(
        lambda sw: set_dimension(sw, dimension_full_name, value_mm),
        launch_if_needed,
    )


@mcp.tool(title="Delete feature", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_feature_delete(
    feature_name: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Delete one exactly matched feature from the tree (destructive, no undo guarantee)."""
    return _call_connected(
        lambda sw: delete_feature(sw, feature_name),
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
    """Enumerate solid faces (type/area mm2); unnamed faces get stable entity names for mating. Large models require one COM round-trip per face; expect slower responses on 1000+ face parts."""
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
    """Add a basic mate; AUTO tries face, plane, axis, edge, then vertex. distance is millimeters for distance mates and degrees for angle mates; entities are component-qualified names from list_components/list_faces."""
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


@mcp.tool(title="Delete assembly mate", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_assembly_delete_mate(
    mate_name: NonEmptyString,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Delete one exactly matched mate from the active assembly (destructive; success is judged by the mate leaving the tree, so verify with list_features afterwards if critical)."""
    return _call_connected(
        lambda sw: delete_mate(sw, mate_name),
        launch_if_needed,
    )


@mcp.tool(title="Move component", annotations=STATE_CHANGE, structured_output=True)
def solidworks_assembly_move_component(
    component_name: NonEmptyString,
    dx: FiniteMM,
    dy: FiniteMM,
    dz: FiniteMM,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Translate one component by (dx, dy, dz) millimetres, composed onto its current transform; the assembly is rebuilt so an immediate check_interference reflects the new position."""
    return _call_connected(
        lambda sw: move_component(sw, component_name, dx, dy, dz),
        launch_if_needed,
    )


@mcp.tool(title="Rotate component", annotations=STATE_CHANGE, structured_output=True)
def solidworks_assembly_rotate_component(
    component_name: NonEmptyString,
    axis: Literal["x", "y", "z"],
    angle_deg: FiniteAngle,
    launch_if_needed: Optional[bool] = None,
) -> ToolResult:
    """Rotate one component by angle_deg degrees about an assembly axis (x/y/z) through the origin; follow up with check_interference to verify the new pose."""
    return _call_connected(
        lambda sw: rotate_component(sw, component_name, axis, angle_deg),
        launch_if_needed,
    )


def main() -> None:
    """Run the local MCP server over stdio."""
    _configure_logging()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


