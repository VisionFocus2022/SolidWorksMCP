"""Small helpers for pywin32 COM late-binding differences."""

from __future__ import annotations

from typing import Any


def call_or_value(obj: Any, attr_name: str) -> Any:
    """Return a COM attribute value, calling it when pywin32 exposes a method."""
    value = getattr(obj, attr_name)
    if value.__class__.__name__ == "CDispatch":
        return value
    return value() if callable(value) else value
