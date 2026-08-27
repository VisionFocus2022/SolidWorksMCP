"""Validation helpers shared by MCP tools and SolidWorks operations."""

from __future__ import annotations

import math
from typing import Any


def finite_number(name: str, value: Any) -> float:
    """Return a finite float or raise a user-facing ValueError."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def positive_number(name: str, value: Any) -> float:
    """Return a positive finite float or raise a user-facing ValueError."""
    number = finite_number(name, value)
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def parse_bool(name: str, value: Any) -> bool:
    """Parse strict JSON-like boolean values without Python truthiness surprises."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"{name} must be a boolean")
