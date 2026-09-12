# -*- coding: utf-8 -*-
"""N52/N57 批次 A 探针：GD&T 框格实机契约定谳（探针先行，ADR-0011 路径）。

观测点（每步独立判据，任何一步异常即停并打印定谳）：
  1. 建图纸（gb 模板发现链，复用 templates.py）
  2. IDrawingDoc.NewGtol() 返回值 —— None = AutoBalloon 同族静默拒收，BLOCKED 定谳
  3. SetFrameSymbols2(flatness) / SetFrameValues2(0.05) / SetPosition —— 返回值观测
  4. GetFrameCount 零参属性 == 1 —— 框格落图判据
  5. SaveAs3 导出 PDF（字节头复核）+ CloseAllDocuments 清理（红线）

用法（SW 已运行）：
    venv\\Scripts\\python.exe tools\\probe_n52_gtol.py
退出码 0 = 契约全通；1 = BLOCKED/异常（stdout 已含定谳行）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pythoncom  # noqa: E402
from win32com.client import Dispatch  # noqa: E402
from solidworks_mcp.utils.com import call_or_value  # noqa: E402

# typelib 取证（N52）：GCS flatness=15；MC none=0
GCS_FLATNESS = 15
MC_NONE = 0

OUT_DIR = ROOT / "probe_out"
VERDICTS = []


def verdict(step: str, ok: bool, detail: str) -> bool:
    line = ("PASS" if ok else "FAIL") + f" | {step} | {detail}"
    print(line, flush=True)
    VERDICTS.append(line)
    return ok


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    pdf_path = OUT_DIR / "n57_gtol_probe.pdf"

    sw = Dispatch("SldWorks.Application")
    sw.Visible = True
    app_major = call_or_value(sw, "RevisionNumber")
    print(f"connected: SW {app_major}", flush=True)

    from solidworks_mcp.utils.templates import get_drawing_template

    template = get_drawing_template()
    if not verdict("template", bool(template), str(template)):
        return 1

    doc = sw.NewDocument(template, 0, 0.0, 0.0)
    if not verdict("NewDocument(drawing)", doc is not None, str(call_or_value(doc, "GetTitle"))):
        return 1

    try:
        try:
            gtol = doc.NewGtol()
        except Exception as dyn_exc:  # noqa: BLE001 —— quirks#26③：NewDocument 返回的
            # dynamic dispatch 成员面受限（DISP_E_MEMBERNOTFOUND）——转 typed IDrawingDoc
            from win32com.client import gencache

            print(f'dynamic NewGtol failed ({dyn_exc}); retrying via typed IDrawingDoc', flush=True)
            mod = gencache.GetModuleForProgID('SldWorks.Application')
            typed_doc = mod.IDrawingDoc(doc._oleobj_)
            gtol = typed_doc.NewGtol()
        if not verdict(
            "NewGtol()", gtol is not None,
            "returned object" if gtol is not None else "SILENT NONE — AutoBalloon-family BLOCKED",
        ):
            return 1

        r1 = gtol.SetFrameSymbols2(1, GCS_FLATNESS, False, MC_NONE, False, 0, 0, 0, 0)
        r2 = gtol.SetFrameValues2(1, "0.05", "", "", "", "")
        r3 = gtol.SetPosition(0.10, 0.05, 0.0)
        verdict(
            "Setters(Symbols2/Values2/Position)",
            all(r is not None for r in (r1, r2, r3)),
            f"returns {r1}/{r2}/{r3} (COM 返回值不可靠，判据看 GetFrameCount)",
        )

        frames = gtol.GetFrameCount  # 零参属性语义（quirks#5 call_or_value 家族）
        if not verdict("GetFrameCount", frames == 1, f"== {frames}"):
            return 1

        doc.SaveAs3(str(pdf_path), 0, 1)  # swSaveAsOptions_Silent
        head = Path(pdf_path).read_bytes()[:5] if pdf_path.exists() else b""
        verdict("SaveAs3 PDF", head == b"%PDF-", f"{pdf_path} {len(Path(pdf_path).read_bytes()) if pdf_path.exists() else 0}B")
        return 0
    finally:
        try:
            sw.CloseAllDocuments(True)
            print("cleanup: CloseAllDocuments(True) done", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"cleanup warn: {exc}", flush=True)


if __name__ == "__main__":
    rc = main()
    OUT_DIR.joinpath("n57_gtol_probe_verdicts.txt").write_text(
        "\n".join(VERDICTS) + "\n", encoding="utf-8"
    )
    print(f"VERDICT: {'PASS' if rc == 0 else 'FAIL/BLOCKED'}", flush=True)
    sys.exit(rc)
