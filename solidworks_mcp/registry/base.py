"""Shared plumbing for the per-domain tool registry (N14).

Everything a domain module needs to define one tool lives here: the
pydantic type aliases, the structured ToolResult contract, the tool
annotation presets, and the COM execution helpers. ``mcp`` itself stays
on the :mod:`solidworks_mcp.server` facade — ``_capabilities`` imports
it lazily so importing this package never cycles.
"""

from __future__ import annotations

import logging
import sys
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
)

from mcp.types import ToolAnnotations
from pydantic import Field

from solidworks_mcp import __version__
from solidworks_mcp.config import get_config
from solidworks_mcp.solidworks_api.app import get_solidworks_app
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
SignedMM = Annotated[
    float,
    Field(allow_inf_nan=False, description="Signed finite length in millimeters (non-zero)"),
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
    from solidworks_mcp.server import mcp  # late: the facade owns the instance

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
            "Complex surfaces, GD&T feature-control frames, simulation, and PDM are not yet exposed.",
            "Drawing BOM balloons (AutoBalloon family) are blocked by the SolidWorks API on this machine; use drawing_insert_bom_table instead.",
            "Exploded-state drawing projection is an open observation item; project from the saved model configuration.",
        ],
    }
