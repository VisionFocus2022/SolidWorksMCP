"""实机探针定稿：材料/自定义属性/方程式/配置（T17，2026-08-29 实测契约）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_material_props_eqs.py
实机契约（供 properties.py 实现）：
  - 配置名经 GetConfigurationNames（零参属性，call_or_value）取首个：中文 SW 为「默认」
  - GetMaterialPropertyName2(cfg, VARIANT(VT_BYREF|VT_BSTR,''))：Database 为 byref out，
    裸调报 DISP_E_PARAMNOTFOUND；返回材料名（可为空），db.value=库名（小写规范化）
  - SetMaterialPropertyName2(cfg, 'SOLIDWORKS MATERIALS', '合金钢')：中文材料名有效，
    英文 'ALLOY STEEL' 无效（静默）；void 返回，判据=回读
  - CPM = Extension.CustomPropertyManager('')；Add3(name, 30, value, 1)→int；
    Get2(name, byref, byref)→None，值在 byref.value；GetNames（零参属性）→tuple
  - GetEquationMgr（零参属性）；EquationMgr.Add2(-1, eq, True)→index；
    GetCount（零参属性）；Equation(i)/Value(i) 带参方法
  - AddConfiguration(name,'','',False,False,False,True,0)→void，判据=GetConfigurationNames
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom
from win32com.client import VARIANT

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.utils.com import call_or_value


def _bstr_ref():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")


def main() -> int:
    sw = get_solidworks_app()
    if not sw.connect(launch_if_needed=False)["success"]:
        print("SolidWorks 未运行，退出码 2")
        return 2
    if not design.create_new_part(sw)["success"]:
        return 3
    if not part.create_box(sw, 60, 40, 20)["success"]:
        return 3
    model = sw.get_active_document()
    cfg = list(call_or_value(model, "GetConfigurationNames"))[0]

    model.SetMaterialPropertyName2(cfg, "SOLIDWORKS MATERIALS", "合金钢")
    db = _bstr_ref()
    name = model.GetMaterialPropertyName2(cfg, db)
    call_or_value(model, "EditRebuild3")
    mass = part.get_mass_properties(sw)["data"]["mass"]
    print(f"[mat] name={name!r} lib={db.value!r} mass_after_rebuild={mass:.4f}kg")

    cpm = model.Extension.CustomPropertyManager("")
    add_ret = cpm.Add3("PartNo", 30, "A-1024", 1)
    v1, v2 = _bstr_ref(), _bstr_ref()
    cpm.Get2("PartNo", v1, v2)
    names = call_or_value(cpm, "GetNames")
    print(f"[prop] Add3ret={add_ret!r} read={v1.value!r} total_names={len(names)}")

    mgr = call_or_value(model, "GetEquationMgr")
    idx = mgr.Add2(-1, '"x" = 50', True)
    count = call_or_value(mgr, "GetCount")
    print(f"[eq] idx={idx} count={count} text={mgr.Equation(idx)!r} value={mgr.Value(idx)!r}")

    model.AddConfiguration("E2E_CFG", "", "", False, False, False, True, 0)
    cfgs = list(call_or_value(model, "GetConfigurationNames"))
    print(f"[cfg] names={cfgs}")
    file_io.close_document(sw, save_changes=False)
    ok = name == "合金钢" and v1.value == "A-1024" and idx >= 0 and "E2E_CFG" in cfgs
    print("SUMMARY:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
