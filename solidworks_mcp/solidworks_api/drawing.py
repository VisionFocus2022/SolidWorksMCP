"""Engineering drawing tools: create from part / project views / insert
model dimensions / export PDF + PNG.

Real-machine contract (probe ``tools/probe_drawing.py``, SW 2026 Chinese,
2026-08-29):

- Template discovery: ``GetUserPreferenceStringValue(10)`` returns the user's
  default ``.drwdot``; the GB template directory beside it holds ``gb_a0`` …
  ``gb_a4p``. A3 is preferred; ``SOLIDWORKS_MCP_DRAWING_TEMPLATE`` overrides.
- ``app.NewDocument(template, 0, 0.0, 0.0)`` — paper arguments are ignored
  when a template path is given. Returns a dynamic dispatch whose member
  surface is IModelDoc + IDrawingDoc: **``SelectByID2`` is NOT resolvable on
  it** (that lives on ModelDoc2) — view selection must go through
  ``model.Extension.SelectByID2`` (9 params, Callout=``pythoncom.Nothing``).
- ``Create1stAngleViews2`` always returns False on this machine (two
  templates, after ActivateDoc3). The manual route works deterministically:
  ``CreateDrawViewFromModelView3(path, "", x, y, 0)`` for the front view,
  select it as ``DRAWINGVIEW``, then ``CreateUnfoldedViewAt3`` for the
  projected views. Sheet coordinates are metres.
- Dimensions: ``drawing.InsertModelAnnotations2(0, True, 0, True, True,
  False)`` inserts every display dimension. InsertModelAnnotations3/4 return
  None and insert nothing here; the plan's ``Extension.InsertModelAnnotations3``
  host is wrong (it is a DrawingDoc member, and the Extension object rejects
  the name outright).
- View/dimension judgment: zero-arg properties ``GetFirstView`` /
  ``GetNextView`` / ``GetDisplayDimensionCount`` / ``GetAnnotationCount``
  (sheet view '图纸1' carries ~82 template annotations — the GB title block).
- Export: ``SaveAs3(path, 0, swSaveAsOptions_Silent)`` returns 0 on success;
  PDF ≈ 45 KB, PNG is a valid raster (line art compresses well — judge by
  the IHDR resolution, not file size).
- A drawing holds its referenced part open (file lock); cleanup needs
  ``app.CloseAllDocuments(True)``.
"""

from __future__ import annotations

import logging
import os
import struct
from typing import Any, Dict, List, Optional, Tuple

import pythoncom

from solidworks_mcp.config import get_config
from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swDocDRAWING,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import (
    ensure_sink_path,
    validate_output_file,
    validate_path,
)

logger = logging.getLogger(__name__)

# A3 first-angle-ish layout in sheet metres (probe-verified on gb_a3.drwdot)
FRONT_XY = (0.15, 0.10)
TOP_XY = (0.15, 0.19)
SIDE_XY = (0.27, 0.10)

# Preference order when falling back from the user default (usually gb_a0)
PREFERRED_TEMPLATES = ("gb_a3.drwdot", "gb_a4.drwdot", "gb_a0.drwdot")

PAPER_SIZE_DEFAULT = 0  # ignored when a template path is supplied
MAX_VIEW_WALK = 50

SUPPORTED_PART_EXTENSIONS = (".sldprt", ".prt")
DRAWING_VIEW_TYPE = "DRAWINGVIEW"


def _resolve_template(app: Any) -> Optional[str]:
    """Pick a drawing template: env override → A3/A4 beside the user default."""
    env_template = get_config().drawing_template
    if env_template and os.path.isfile(env_template):
        return env_template

    try:
        preferred = app.GetUserPreferenceStringValue(10)  # swDefaultTemplateDrawing
    except Exception:
        return None
    if not isinstance(preferred, str) or not preferred:
        return None
    # The preference can go stale (uninstalled version dir); the GB set
    # beside it is still usable.
    template_dir = os.path.dirname(preferred)
    for name in PREFERRED_TEMPLATES:
        candidate = os.path.join(template_dir, name)
        if os.path.isfile(candidate):
            return candidate
    return preferred if os.path.isfile(preferred) else None


def _view_reports(model: Any) -> List[Dict[str, Any]]:
    views: List[Dict[str, Any]] = []
    view = call_or_value(model, "GetFirstView")
    for _ in range(MAX_VIEW_WALK):
        if view is None:
            break
        name = call_or_value(view, "Name")
        if not isinstance(name, str):  # degenerate proxy — stop immediately
            break
        try:
            dims = call_or_value(view, "GetDisplayDimensionCount")
        except Exception:
            dims = None
        try:
            anns = call_or_value(view, "GetAnnotationCount")
        except Exception:
            anns = None
        views.append(
            {
                "name": name,
                "dimensions": dims if isinstance(dims, int) else None,
                "annotations": anns if isinstance(anns, int) else None,
            }
        )
        view = call_or_value(view, "GetNextView")
    return views


def _total_dimensions(views: List[Dict[str, Any]]) -> int:
    return sum(v["dimensions"] or 0 for v in views)


def _select_view(model: Any, view_name: str) -> bool:
    """Select a drawing view by name (9-param Extension form, ModelDoc2's
    SelectByID2 is not resolvable on the NewDocument dispatch)."""
    extension = call_or_value(model, "Extension")
    try:
        return bool(
            extension.SelectByID2(
                view_name, DRAWING_VIEW_TYPE, 0, 0, 0, False, 0,
                pythoncom.Nothing, 0,
            )
        )
    except Exception:
        logger.exception("Failed to select drawing view %s", view_name)
        return False


def create_drawing_from_part(sw_app: SolidWorksApp, part_path: str) -> dict:
    """Create a new drawing from a saved part and project three views."""
    try:
        valid, msg = validate_path(part_path, must_exist=True)
        if not valid:
            return error_response(msg, code="INVALID_PARAMETER")

        ext = os.path.splitext(part_path)[1].lower()
        if ext not in SUPPORTED_PART_EXTENSIONS:
            return error_response(
                f"Expected a part file (.sldprt), got: {ext or '<none>'}",
                code="INVALID_PARAMETER",
            )

        template = _resolve_template(sw_app.app)
        if template is None:
            return error_response(
                "No drawing template found; set SOLIDWORKS_MCP_DRAWING_TEMPLATE "
                "to a .drwdot file",
                code="TEMPLATE_NOT_FOUND",
            )

        drawing = sw_app.app.NewDocument(
            template, PAPER_SIZE_DEFAULT, 0.0, 0.0
        )
        if drawing is None:
            return error_response(
                "SolidWorks rejected creating the drawing document",
                code="SW_API_ERROR",
            )

        abs_part = os.path.abspath(part_path)
        front = drawing.CreateDrawViewFromModelView3(
            abs_part, "", FRONT_XY[0], FRONT_XY[1], 0.0
        )
        if front is None:
            return error_response(
                "SolidWorks refused to create the front view "
                f"(part must be a valid saved model: {abs_part})",
                code="SW_API_ERROR",
            )
        front_name = call_or_value(front, "Name")

        for target_xy in (TOP_XY, SIDE_XY):
            if not _select_view(drawing, front_name):
                return error_response(
                    f"Failed to select the front view {front_name!r} before "
                    "projecting",
                    code="SW_API_ERROR",
                )
            projected = drawing.CreateUnfoldedViewAt3(
                target_xy[0], target_xy[1], 0.0, False
            )
            if projected is None:
                return error_response(
                    f"SolidWorks refused to create the projected view at "
                    f"({target_xy[0]}, {target_xy[1]})",
                    code="SW_API_ERROR",
                )

        views = _view_reports(drawing)
        if len(views) < 4:  # sheet + front + two projections
            return error_response(
                f"Only {len(views)} views present after projection "
                "(expected 4: sheet + three views)",
                code="SW_API_ERROR",
            )

        return success_response(
            data={
                "title": call_or_value(drawing, "GetTitle"),
                "template": template,
                "part": part_path,
                "view_count": len(views),
                "views": views,
            },
            message="Created drawing with three projected views "
            "(drawing stays open; the referenced part is opened by SolidWorks)",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to create drawing")
        return error_response(f"Failed to create drawing: {exc}")


def insert_model_dimensions(sw_app: SolidWorksApp) -> dict:
    """Insert all model dimensions of the drawing's views.

    ``InsertModelAnnotations2(0, True, 0, True, True, False)`` is the only
    call verified to insert anything on this machine (SW 2026).
    """
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        doc_type = call_or_value(model, "GetType")
        if doc_type != swDocDRAWING:
            return error_response(
                f"Active document is not a drawing (type={doc_type})"
            )

        before = _total_dimensions(_view_reports(model))
        inserted = model.InsertModelAnnotations2(
            0, True, 0, True, True, False
        )
        call_or_value(model, "EditRebuild3")
        views = _view_reports(model)
        after = _total_dimensions(views)

        if after <= before:
            return error_response(
                "SolidWorks inserted no dimensions "
                f"(call returned {inserted!r}; the part may expose no display "
                "dimensions — create sketch/extrude features with dimensions)",
                code="SW_NO_EFFECT",
            )

        return success_response(
            data={
                "dimensions_inserted": after - before,
                "total_dimensions": after,
                "views": views,
            },
            message=f"Inserted {after - before} model dimensions into the drawing",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to insert model dimensions")
        return error_response(f"Failed to insert model dimensions: {exc}")


def _png_resolution(path: str) -> Optional[Dict[str, int]]:
    """Read the IHDR chunk (no imaging dependency needed for line art)."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(24)
        if len(head) < 24 or head[12:16] != b"IHDR":
            return None
        return {
            "width": struct.unpack(">I", head[16:20])[0],
            "height": struct.unpack(">I", head[20:24])[0],
        }
    except OSError:
        return None


def _export_drawing(
    sw_app: SolidWorksApp,
    file_path: str,
    extensions: Tuple[str, ...],
    overwrite_confirm: bool,
    label: str,
) -> dict:
    try:
        valid, msg = validate_output_file(file_path, set(extensions), overwrite_confirm)
        if not valid:
            return error_response(msg, code="INVALID_OUTPUT_PATH")

        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document to export")

        ok, message, sink_path = ensure_sink_path(file_path)
        if not ok:
            return error_response(message, code="INVALID_OUTPUT_PATH")

        call_or_value(model, "ViewZoomtofit2")
        result = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
        if result != 0:
            return error_response(f"{label} export failed with code {result}")

        try:
            size = os.path.getsize(sink_path)
        except OSError:
            return error_response(f"{label} export reported success but no "
                                  f"file was written: {sink_path}")
        data: Dict[str, Any] = {"path": file_path, "size_bytes": size}
        if sink_path.lower().endswith(".png"):
            data["resolution"] = _png_resolution(sink_path)
        return success_response(
            data=data,
            message=f"Exported {label} to: {file_path}",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to export %s", label)
        return error_response(f"Failed to export {label}: {exc}")


def export_drawing_pdf(
    sw_app: SolidWorksApp,
    file_path: str,
    overwrite_confirm: bool = False,
) -> dict:
    """Export the active drawing to PDF."""
    return _export_drawing(
        sw_app, file_path, (".pdf",), overwrite_confirm, "PDF"
    )


def export_drawing_png(
    sw_app: SolidWorksApp,
    file_path: str,
    overwrite_confirm: bool = False,
) -> dict:
    """Export the active drawing to PNG (raster of the sheet)."""
    return _export_drawing(
        sw_app, file_path, (".png",), overwrite_confirm, "PNG"
    )
