"""Shared two-phase part save helpers (N37, review M-1).

The create_* primitives validate the output path before any geometry is
built (fail fast) and persist the model after the feature tree is grown.
Both halves used to be copy-pasted per function (>=8 sites); they live
here now. Error codes: path validation and sink re-check failures are
INVALID_OUTPUT_PATH; a SaveAs3 refusal is SW_API_ERROR (unified by N37 —
it used to carry no code).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from solidworks_mcp.solidworks_api.constants import (
    swFileSaveErrorNone,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.utils.security import ensure_sink_path, validate_output_file

PART_EXTENSION = {".sldprt"}


def prepare_part_save(
    save_path: Optional[str], overwrite_confirm: bool
) -> Optional[str]:
    """Front gate: validate the output path before mutating anything.

    Returns the error message, or None when saving may proceed (which
    includes "no save_path requested").
    """
    if not save_path:
        return None
    allowed, message = validate_output_file(
        save_path, PART_EXTENSION, overwrite_confirm
    )
    return None if allowed else message


def persist_part_save(
    model: Any, save_path: Optional[str], result: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    """Tail step: re-check containment at save time and persist.

    Returns ``(error_code, error_message)`` — both None on success, when
    ``result["saved_to"]`` is filled. No-op without a save_path.
    """
    if not save_path:
        return None, None
    ok, message, sink_path = ensure_sink_path(save_path)
    if not ok:
        return "INVALID_OUTPUT_PATH", message
    save_result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
    if save_result != swFileSaveErrorNone:
        return "SW_API_ERROR", f"SaveAs3 failed with code {save_result}"
    result["saved_to"] = save_path
    return None, None
