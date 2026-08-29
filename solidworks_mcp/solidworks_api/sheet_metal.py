"""Sheet-metal base-flange tool (T21-3).

Real-machine contract (probe ``tools/probe_part/probe_sheet_metal_thread.py``,
2026-08-30): a centred rectangle on the top reference plane +
``FeatureManager.InsertSheetMetalBaseFlange`` produces the full sheet-metal
feature set (钣金N / 基体-法兰N / 平展型式N). The ``PCBA`` parameter is a
dispatch slot — plain ``0`` raises a type-mismatch com_error, it must be
``pythoncom.Nothing``. The plate's bounding box reads
``[width, thickness, depth]`` (thickness grows along model -Y).
"""

from __future__ import annotations

import logging
from typing import Optional

import pythoncom

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.constants import (
    swFileSaveErrorNone,
    swSaveAsOptions_Silent,
)
from solidworks_mcp.solidworks_api.geometry import mm_to_m, select_plane
from solidworks_mcp.utils.common import error_response, success_response
from solidworks_mcp.utils.com import call_or_value
from solidworks_mcp.utils.security import ensure_sink_path, validate_output_file
from solidworks_mcp.utils.validation import positive_number

logger = logging.getLogger(__name__)

TOP_PLANE_CANDIDATES = ("Top Plane", "上视基准面")


def create_base_flange(
    sw_app: SolidWorksApp,
    width: float,
    depth: float,
    thickness: float,
    radius: float = 0.0,
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> dict:
    """Create a sheet-metal part from a centred rectangular base flange.

    v1 scope: flat plate (radius 0 default = no bend in the base sketch);
    the feature tree carries the sheet-metal/fold/flat-pattern set so bends
    and flat export can build on it later.
    """
    try:
        width = positive_number("width", width)
        depth = positive_number("depth", depth)
        thickness = positive_number("thickness", thickness)
        radius = positive_number("radius", radius) if radius else 0.0

        if save_path:
            valid, message = validate_output_file(
                save_path, {".sldprt"}, overwrite_confirm
            )
            if not valid:
                return error_response(message, code="INVALID_OUTPUT_PATH")

        from solidworks_mcp.solidworks_api import part as part_api

        model, _created = part_api._get_or_create_part(sw_app)
        if select_plane(model, TOP_PLANE_CANDIDATES,
                        use_extension_fallback=False) is None:
            return error_response(
                "Could not select the top reference plane "
                "(tried: Top Plane, 上视基准面)",
                code="SW_API_ERROR",
            )

        sketch = model.SketchManager
        sketch.InsertSketch(True)
        sketch.CreateCornerRectangle(
            mm_to_m(-width / 2.0), mm_to_m(-depth / 2.0), 0.0,
            mm_to_m(width / 2.0), mm_to_m(depth / 2.0), 0.0,
        )
        sketch.InsertSketch(True)

        feature_manager = call_or_value(model, "FeatureManager")
        feature = feature_manager.InsertSheetMetalBaseFlange(
            mm_to_m(thickness),  # Thickness
            False,               # ThickenDir
            mm_to_m(radius),     # Radius
            0.0,                 # ExtrudeDist1 (closed outline)
            0.0,                 # ExtrudeDist2
            False,               # FlipExtruDir
            0, 8,                # EndCondition1/2
            0,                   # DirToUse
            pythoncom.Nothing,   # PCBA（dispatch 型；0 报类型不匹配）
            True, 0, 0.0, 0.0, 0.0, True,  # relief defaults
        )
        if feature is None:
            return error_response(
                "SolidWorks rejected the base flange "
                "(check thickness vs sketch size)",
                code="SW_API_ERROR",
            )
        feature_name = call_or_value(feature, "Name")

        data = {
            "feature_name": feature_name,
            "width_mm": width,
            "depth_mm": depth,
            "thickness_mm": thickness,
            "radius_mm": radius,
        }
        if save_path:
            ok, message, sink_path = ensure_sink_path(save_path)
            if not ok:
                return error_response(message, code="INVALID_OUTPUT_PATH")
            saved = model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)
            if saved != swFileSaveErrorNone:
                return error_response(f"SaveAs3 failed with code {saved}")
            data["saved_to"] = save_path

        return success_response(
            data=data,
            message=(
                f"Created sheet-metal base flange {width}x{depth}mm, "
                f"t={thickness}mm"
            ),
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAMETER")
    except Exception as exc:
        logger.exception("Failed to create base flange")
        return error_response(f"Failed to create base flange: {exc}")
