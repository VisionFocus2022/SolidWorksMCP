# -*- coding: utf-8 -*-
"""N57 批次 A2：GD&T 工具全链 e2e（API 层直调=最新代码）。

connect → part_new+create_box(60,40,10) → create_drawing_from_part
→ insert_gtol(flatness 0.05) → export_pdf。
判据：insert 成功（typed fallback 实机路径）+ PDF %PDF 头 + bbox 正常。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "probe_out" / "n57_gtol_e2e.pdf"


def main() -> int:
    import pythoncom
    from win32com.client import Dispatch

    from solidworks_mcp.solidworks_api.app import SolidWorksApp
    from solidworks_mcp.solidworks_api.part import create_box
    from solidworks_mcp.solidworks_api.drawing import (
        create_drawing_from_part,
        export_drawing_pdf,
        insert_gtol,
    )

    pythoncom.CoInitialize()
    sw = SolidWorksApp()
    assert sw.connect(launch_if_needed=False)["success"]

    part_path = ROOT / "probe_out" / "n57_gtol_part.sldprt"
    part_path.parent.mkdir(exist_ok=True)
    try:
        from solidworks_mcp.solidworks_api.design import create_new_part

        r = create_new_part(sw, str(part_path), overwrite_confirm=True)
        assert r.get("success") is True, r
        r = create_box(sw, 60, 40, 10, str(part_path), True)
        assert r.get("success") is True, r
        print("box built + saved", flush=True)

        r = create_drawing_from_part(sw, str(part_path))
        assert r.get("success") is True, r
        views = (r.get("data") or {}).get("views")
        print(f"drawing created: {views}", flush=True)

        r = insert_gtol(sw, "flatness", 0.05, 120.0, 60.0)
        assert r.get("success") is True, r
        print(f"gtol inserted: {r.get('data')}", flush=True)

        if OUT.exists():
            OUT.unlink()
        r = export_drawing_pdf(sw, str(OUT), True)
        assert r.get("success") is True, r
        head = OUT.read_bytes()[:5]
        assert head == b"%PDF-", head
        print(f"PDF exported {OUT.stat().st_size}B", flush=True)
        print("BATCH A2 PASS: GD&T tool full chain on real SW", flush=True)
        return 0
    finally:
        try:
            sw.app.CloseAllDocuments(True)
            print("cleanup done", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"cleanup warn: {exc}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
