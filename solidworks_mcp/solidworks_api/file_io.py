"""File import/export operations for SolidWorks."""

from __future__ import annotations

import logging
import os
from typing import Optional

import pythoncom
import win32com.client

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import validate_output_file, validate_path

logger = logging.getLogger(__name__)

# SolidWorks API constants
swDocPART = 1
swDocASSEMBLY = 2
swDocDRAWING = 3
swOpenDocOptions_Silent = 1
swSaveAsOptions_Silent = 1
swFileSaveErrorNone = 0

# Common SolidWorks file load error codes
FILE_LOAD_ERROR_NON_SW = 2097152
SUPPORTED_OPEN_EXTENSIONS = {
    ".sldprt",
    ".prt",
    ".sldasm",
    ".asm",
    ".slddrw",
    ".drw",
    ".step",
    ".stp",
    ".iges",
    ".igs",
    ".x_t",
    ".x_b",
    ".sat",
    ".stl",
}


def _guess_document_type(file_path: str) -> int:
    """Guess SolidWorks document type from extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".sldprt", ".prt"):
        return swDocPART
    if ext in (".sldasm", ".asm"):
        return swDocASSEMBLY
    if ext in (".slddrw", ".drw"):
        return swDocDRAWING
    # Treat generic CAD formats as parts by default.
    return swDocPART


def _make_error_variants() -> tuple:
    """Create BYREF VARIANTs for OpenDoc6 error/warning outputs."""
    errs = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warns = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    return errs, warns


def _format_load_error(error_code: int) -> str:
    """Provide a human-readable hint for common load error codes."""
    if error_code == FILE_LOAD_ERROR_NON_SW:
        return (
            "SolidWorks could not open the file as a native document. "
            "For STEP/IGES files, ensure 3DInterconnect is enabled: "
            "Tools > Options > System Options > Import > Enable 3D Interconnect"
        )
    return f"load error code {error_code}"


def _model_title(model) -> str:
    return call_or_value(model, "GetTitle")


def open_document(
    sw_app: SolidWorksApp,
    file_path: str,
    doc_type: Optional[int] = None,
) -> dict:
    """Open an existing SolidWorks document."""
    try:
        valid, msg = validate_path(file_path, must_exist=True)
        if not valid:
            return error_response(msg)

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_OPEN_EXTENSIONS:
            return error_response(
                f"Unsupported document extension: {ext or '<none>'}",
                code="INVALID_PARAMETER",
            )

        target_type = doc_type if doc_type is not None else _guess_document_type(file_path)
        errs, warns = _make_error_variants()
        model = sw_app.app.OpenDoc6(
            file_path,
            target_type,
            swOpenDocOptions_Silent,
            "",
            errs,
            warns,
        )
        if model is None:
            detail = _format_load_error(errs.value)
            return error_response(f"Failed to open document: {file_path}. {detail}")

        return success_response(
            data={
                "path": file_path,
                "type": target_type,
                "title": _model_title(model),
                "errors": errs.value,
                "warnings": warns.value,
            },
            message=f"Opened document: {os.path.basename(file_path)}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to open document")
        return error_response(f"Failed to open document: {exc}")


def import_step(
    sw_app: SolidWorksApp,
    file_path: str,
) -> dict:
    """Import a STEP (.step/.stp) file into SolidWorks."""
    try:
        valid, msg = validate_path(file_path, must_exist=True)
        if not valid:
            return error_response(msg)

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".step", ".stp"):
            return error_response(f"Expected .step or .stp file, got: {ext}")

        errs, warns = _make_error_variants()
        model = sw_app.app.OpenDoc6(
            file_path,
            swDocPART,
            swOpenDocOptions_Silent,
            "",
            errs,
            warns,
        )
        if model is None:
            detail = _format_load_error(errs.value)
            return error_response(f"Failed to import STEP: {file_path}. {detail}")

        return success_response(
            data={
                "path": file_path,
                "title": _model_title(model),
                "errors": errs.value,
                "warnings": warns.value,
            },
            message=f"Imported STEP: {os.path.basename(file_path)}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to import STEP")
        return error_response(f"Failed to import STEP: {exc}")


def export_step(
    sw_app: SolidWorksApp,
    file_path: str,
    overwrite_confirm: bool = False,
) -> dict:
    """Export the active document to STEP format."""
    try:
        valid, msg = validate_output_file(
            file_path, {".step", ".stp"}, overwrite_confirm
        )
        if not valid:
            return error_response(msg, code="INVALID_OUTPUT_PATH")

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document to export")

        result = model.SaveAs3(file_path, 0, swSaveAsOptions_Silent)
        if result != swFileSaveErrorNone:
            return error_response(f"Export failed with code {result}")

        return success_response(
            data={"path": file_path},
            message=f"Exported STEP to: {file_path}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to export STEP")
        return error_response(f"Failed to export STEP: {exc}")


def export_stl(
    sw_app: SolidWorksApp,
    file_path: str,
    overwrite_confirm: bool = False,
) -> dict:
    """Export the active part to STL format."""
    try:
        valid, msg = validate_output_file(file_path, {".stl"}, overwrite_confirm)
        if not valid:
            return error_response(msg, code="INVALID_OUTPUT_PATH")

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document to export")

        result = model.SaveAs3(file_path, 0, swSaveAsOptions_Silent)
        if result != swFileSaveErrorNone:
            return error_response(f"STL export failed with code {result}")

        return success_response(
            data={"path": file_path},
            message=f"Exported STL to: {file_path}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to export STL")
        return error_response(f"Failed to export STL: {exc}")
