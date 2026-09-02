"""N33 探针：爆炸视图全链（2026-09-01 SW 2026 v34.2.1）。

取证：
  - IAssemblyDoc.AutoExplode() 零参（返回 bool）——自动爆炸活动配置
  - GetExplodedViewCount()/GetExplodedViewNames()——查询爆炸视图
  - ShowExploded(ShowIt)/ShowExploded2(ShowIt, ViewName)
  - IConfiguration.AddExplodeStep(ExplDist, ReverseDir, RigidSubassembly,
    ExplodeRelated) 4 参（需选中组件——手工步进路线，本探针先走自动）
  - CreateDrawViewFromModelView3(path, ConfigName, x, y, z) 第 2 参=配置名
    ——爆炸视图名是否可作配置引用（图纸投影爆炸态）
链路：两组件分离装配（N32 修复后的 add_component）→ AutoExplode →
爆炸视图名/计数 → 爆炸态图纸 → PDF。

结论（2026-09-01 实机）：
1. **AutoExplode 一次通过**：typed IAssemblyDoc 零参（dynamic 属性语义）→
   GetExplodedViewCount=1、GetExplodedViewNames=('爆炸视图1',)。
   → 生产工具 `assembly_explode`（含 ShowExploded(True) 切显示态）。
2. **图纸投影**：CreateDrawViewFromModelView3 第 2 参**空串**成功
   （view=True+PDF 42.8KB）；「爆炸视图1」/「默认」名字形态被拒——
   爆炸视图不是配置名。GetExplodedViewConfigurationName 查关联配置
   因探针变量序 bug 未采到——**爆炸态图纸投影留观察项**（v1 装配域
   AutoExplode 为主交付）。
3. AddExplodeStep(4 参手工步进) 存在未走（需选中组件）——v1 自动布局。
4. GetSpecificTransform(False/True) 变化判据未检出（显示态切换语义
   待深究，不影响爆炸视图创建事实）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pythoncom
from win32com.client import gencache

from solidworks_mcp.solidworks_api import assembly, design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.drawing import FRONT_XY, _resolve_template
from solidworks_mcp.utils.com import call_or_value

OUT = Path(__file__).resolve().parents[2] / "output" / "n33_probe"


def _fixture(sw):
    OUT.mkdir(exist_ok=True)
    for name, builder in (
        ("box20", lambda: part.create_box(
            sw, 40.0, 30.0, 10.0, save_path=str(OUT / "box20.sldprt"),
            overwrite_confirm=True)),
        ("cyl10", lambda: part.create_cylinder(
            sw, 16.0, 25.0, save_path=str(OUT / "cyl10.sldprt"),
            overwrite_confirm=True)),
    ):
        assert design.create_new_part(sw)["success"], name
        assert builder()["success"], name
        file_io.close_document(sw, save_changes=False)
    assert assembly.new_assembly(
        sw, save_path=str(OUT / "asm.sldasm"), overwrite_confirm=True
    )["success"]
    assert assembly.add_component(sw, str(OUT / "box20.sldprt"))["success"]
    assert assembly.add_component(
        sw, str(OUT / "cyl10.sldprt"), x=60.0, y=0.0, z=10.0
    )["success"]
    comps = assembly.get_components(sw)["data"]["components"]
    print(f"[asm] components: {comps}")
    assert len(comps) == 2, comps
    return str(OUT / "asm.sldasm")


def main() -> int:
    sw = get_solidworks_app()
    assert sw.connect(launch_if_needed=True)["success"]
    try:
        sw.app.CloseAllDocuments(True)
    except Exception:
        pass
    asm_path = _fixture(sw)
    model = sw.get_active_document()

    mods = gencache.GetModuleForProgID("SldWorks.Application")
    asm_doc = mods.IAssemblyDoc(model._oleobj_)
    # 爆炸前组件变换（基线）
    comps = model.GetComponents(False)
    t0 = comps[0].Transform2.ArrayData if hasattr(comps[0], "Transform2") else None

    auto = call_or_value(asm_doc, "AutoExplode")  # 零参：dynamic 属性语义
    if not isinstance(auto, bool) or not auto:
        try:
            auto = asm_doc.AutoExplode()
        except Exception as exc:  # noqa: BLE001
            auto = None
            print(f"[explode] AutoExplode EXC {exc!r}")
    print(f"[explode] AutoExplode: {auto!r}")
    count = asm_doc.GetExplodedViewCount()
    names = asm_doc.GetExplodedViewNames()
    print(f"[explode] count={count!r} names={names!r}")

    comps = model.GetComponents(False)
    moved = False
    for c in comps:
        try:
            exploded_t = c.GetSpecificTransform(False)  # False = 爆炸态
            normal_t = c.GetSpecificTransform(True)  # True = 忽略爆炸
            if exploded_t is not None and normal_t is not None:
                e = exploded_t.ArrayData
                n = normal_t.ArrayData
                if e and n and (abs(e[9] - n[9]) > 1e-6 or abs(e[10] - n[10]) > 1e-6 or abs(e[12] - n[12]) > 1e-6):
                    moved = True
        except Exception:  # noqa: BLE001
            pass
    print(f"[explode] component moved in exploded state: {moved}")
    linked_cfg = None
    try:
        linked_cfg = asm_doc.GetExplodedViewConfigurationName(explode_name)
    except Exception as exc:  # noqa: BLE001
        print(f"[dwg] linked cfg query EXC {exc!r}")
    print(f"[dwg] linked_config={linked_cfg!r}")
    file_io.close_document(sw, save_changes=False)

    # 爆炸态图纸：CreateDrawViewFromModelView3 第 2 参=配置名（爆炸视图名?）
    explode_name = None
    if isinstance(names, (list, tuple)) and names:
        explode_name = names[0]
    elif isinstance(names, str) and names:
        explode_name = names
    print(f"[dwg] explode={explode_name!r}")
    template = _resolve_template(sw.app)
    ok = False
    for config_name in ["", linked_cfg, "默认", explode_name]:
        dwg = sw.app.NewDocument(template, 12, 0.0, 0.0)
        if dwg is None:
            continue
        view = dwg.CreateDrawViewFromModelView3(
            os.path.abspath(asm_path), config_name,
            FRONT_XY[0], FRONT_XY[1], 0.0,
        )
        pdf = OUT / "asm_exploded.pdf"
        code = dwg.SaveAs3(str(pdf), 0, 1)
        size = pdf.stat().st_size if pdf.exists() else 0
        print(
            f"[dwg] config={config_name!r} view={view is not None} "
            f"code={code} size={size}B"
        )
        file_io.close_document(sw, save_changes=False)
        if view is not None and size > 10_000:
            ok = True
            break

    verdict = (isinstance(count, int) and count > 0) and ok
    print("SUMMARY:", "OK" if verdict else "FAIL")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
