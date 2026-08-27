"""Runtime configuration for the SolidWorks MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _workspace_root() -> str:
    """Return the parent workspace that contains the SolidWorksMCP project."""
    return str(Path(__file__).resolve().parents[2])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_positive_float(name: str) -> float:
    value = os.getenv(name)
    if value is None:
        return 0.0
    try:
        parsed = float(value)
    except ValueError:
        return 0.0
    return parsed if parsed > 0 else 0.0


@dataclass(frozen=True)
class ServerConfig:
    """Configuration values shared by tools and API helpers."""

    allowed_root: str
    auto_start: bool
    solidworks_version: str
    part_template: str | None
    assembly_template: str | None
    drawing_template: str | None
    log_path: str
    com_timeout_seconds: float


def get_config() -> ServerConfig:
    """Return the current server configuration."""
    return ServerConfig(
        allowed_root=os.getenv("SOLIDWORKS_MCP_ALLOWED_ROOT", _workspace_root()),
        auto_start=_env_bool("SOLIDWORKS_MCP_AUTO_START", False),
        solidworks_version=os.getenv("SOLIDWORKS_MCP_SOLIDWORKS_VERSION", "2026"),
        part_template=os.getenv("SOLIDWORKS_MCP_PART_TEMPLATE"),
        assembly_template=os.getenv("SOLIDWORKS_MCP_ASSEMBLY_TEMPLATE"),
        drawing_template=os.getenv("SOLIDWORKS_MCP_DRAWING_TEMPLATE"),
        log_path=os.getenv(
            "SOLIDWORKS_MCP_LOG_PATH",
            str(_project_root() / "solidworks_mcp.log"),
        ),
        com_timeout_seconds=_env_positive_float(
            "SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS"
        ),
    )
