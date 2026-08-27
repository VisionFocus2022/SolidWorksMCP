"""Common response helpers."""

from __future__ import annotations

from typing import Any, Optional


def success_response(
    data: Any,
    message: str = "Success",
    warning: Optional[str] = None,
) -> dict:
    """Build a successful tool response."""
    return {
        "success": True,
        "data": data,
        "message": message,
        "warning": warning,
        "error": None,
    }


def error_response(
    message: str,
    data: Any = None,
    warning: Optional[str] = None,
    code: str = "OPERATION_FAILED",
    details: Any = None,
) -> dict:
    """Build an error tool response."""
    return {
        "success": False,
        "data": data,
        "message": message,
        "warning": warning,
        "error": {"code": code, "details": details},
    }
