"""Small helpers for pywin32 COM late-binding differences."""

from __future__ import annotations

from typing import Any, Optional

import pythoncom
import win32com.client


def call_or_value(obj: Any, attr_name: str) -> Any:
    """Return a COM attribute value, calling it when pywin32 exposes a method."""
    value = getattr(obj, attr_name)
    if value.__class__.__name__ == "CDispatch":
        return value
    return value() if callable(value) else value


def make_error_variants() -> tuple:
    """Create BYREF VARIANTs for OpenDoc6/Save3 error and warning outputs."""
    return (
        win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0),
        win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0),
    )


def _is_pyidispatch(raw: Any) -> bool:
    """Mock doubles auto-attribute ``_oleobj_``; only the real type passes."""
    return type(raw).__name__ == "PyIDispatch"


def static_wrap(obj: Any, interface: str) -> Optional[Any]:
    """Wrap a dynamic dispatch in its makepy static class (N5 pattern).

    Variant-array parameters and long positional lists marshal
    unreliably through dynamic dispatch (real-machine evidence:
    CreateTransform raises RPC_E_SERVERFAULT — N8; IModelDoc2
    blends/domes raise DISP_E_PARAMNOTFOUND — quirks 28-3/31); the
    makepy generated classes accept the raw PyIDispatch and restore the
    typed vtable signatures. Returns ``None`` when the makepy cache is
    missing, the object is not a real COM dispatch (Mock doubles
    auto-attribute ``_oleobj_``), or the wrap raises. Single home so
    per-module copies cannot drift again (review M-2/SE-3, N35).
    """
    try:
        from win32com.client import gencache

        mods = gencache.GetModuleForProgID("SldWorks.Application")
        raw = getattr(obj, "_oleobj_", None)
        # Only a real PyIDispatch can be handed to the generated class.
        if mods is None or not _is_pyidispatch(raw):
            return None
        return getattr(mods, interface)(raw)
    except Exception:  # noqa: BLE001 —— wrap failure is a fallback, not an error
        return None


def typed_or_dynamic(obj: Any, interface: str) -> Any:
    """``static_wrap`` with the dynamic object as fallback (typed_doc2 semantics)."""
    return static_wrap(obj, interface) or obj
