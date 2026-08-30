"""N12 实机探针：方程式增删改 / 配置激活 / 按配置设尺寸（2026-08-30）。

用法：venv\\Scripts\\python.exe -X utf8 tools\\probe_properties\\probe_equation_cfg_edit.py

待定契约（供 N12 实现）：
  1. EquationMgr 删改成员形态：动态代理下 propput 带参不可用；强类型
     (gencache IEquationMgr) dir() 反射确认 Delete(i)/SetEquation(i, text)
     还是 put_Equation —— 增删改实现的调用形态以此为准。
  2. model.ShowConfiguration(name) 激活配置；判据 =
     model.ConfigurationManager.ActiveConfiguration.Name 回读。
  3. dim.SetSystemValue3(value_m, 3, names) 按配置设值（3 =
     swSpecifyConfiguration）：names 形态 tuple("CFG_B",) / 逗号字符串 /
     裸字符串逐一试，判据 = 切回默认配置后两配置尺寸不同。

退出码：0 = 全部契约拿到 · 1 = 有未定项 · 2 = SW 未运行 · 3 = 建模失败。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solidworks_mcp.solidworks_api import design, file_io, part
from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.utils.com import call_or_value

EQ_DELETE_FORM: list[str] = []
EQ_PUT_FORM: list[str] = []


def _typed(obj, cls_name: str):
    """Wrap a dynamic COM object in its makepy class (drawing.py pattern)."""
    from win32com.client import gencache

    mods = gencache.GetModuleForProgID("SldWorks.Application")
    raw = getattr(obj, "_oleobj_", None)
    if mods is None or raw is None:
        return None
    return getattr(mods, cls_name)(raw)


def _try(label: str, fn):
    try:
        value = fn()
        print(f"[try] {label}: OK -> {value!r}")
        return True, value
    except Exception as exc:  # noqa: BLE001 - probe reports every form
        print(f"[try] {label}: {type(exc).__name__}: {exc}")
        return False, None


def _first_extrusion_name(model) -> str:
    feat = call_or_value(model, "FirstFeature")
    steps = 0
    while feat is not None and steps < 5000:
        name = call_or_value(feat, "Name")
        if "拉伸" in str(name) or "Extrus" in str(name):
            return str(name)
        feat = call_or_value(feat, "GetNextFeature")
        steps += 1
    raise RuntimeError("no extrusion feature found")


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

    # ---- 1. EquationMgr 删改形态 ---------------------------------------
    mgr = call_or_value(model, "GetEquationMgr")
    for eq in ('"x" = 50', '"y" = 60', '"z" = 70'):
        mgr.Add2(-1, eq, True)
    before = call_or_value(mgr, "GetCount")

    typed = _typed(mgr, "IEquationMgr")
    if typed is None:
        print("[eq-typed] gencache wrap failed")
    else:
        members = [a for a in dir(typed) if "quat" in a.lower() or "elete" in a.lower()]
        print(f"[eq-typed] IEquationMgr members: {members}")

    ok_put, _ = _try(
        "typed.SetEquation(1, '\"y\" = 99')",
        lambda: typed.SetEquation(1, '"y" = 99'),
    )
    if ok_put:
        EQ_PUT_FORM.append("SetEquation")
        print(f"[eq-put] read-back: {mgr.Equation(1)!r}")
    else:
        ok_dyn, _ = _try(
            "dyn.put_Equation(1, '\"y\" = 99')",
            lambda: mgr.put_Equation(1, '"y" = 99'),
        )
        if ok_dyn:
            EQ_PUT_FORM.append("put_Equation")
            print(f"[eq-put] read-back: {mgr.Equation(1)!r}")

    ok_del, _ = _try("typed.Delete(0)", lambda: typed.Delete(0))
    if ok_del:
        EQ_DELETE_FORM.append("typed.Delete")
        after = call_or_value(mgr, "GetCount")
        texts = [mgr.Equation(i) for i in range(after)]
        print(f"[eq-del] count {before}->{after}, texts={texts}")

    # ---- 2. ShowConfiguration / ActiveConfiguration ---------------------
    model.AddConfiguration("CFG_B", "", "", False, False, False, True, 0)
    cfg_mgr = call_or_value(model, "ConfigurationManager")
    ok_show, _ = _try("model.ShowConfiguration('CFG_B')",
                      lambda: model.ShowConfiguration("CFG_B"))
    active = None
    if ok_show:
        active = call_or_value(cfg_mgr, "ActiveConfiguration").Name
        print(f"[cfg] active after show: {active!r}")

    # ---- 3. SetSystemValue3 按配置（names 形态） ------------------------
    # 动态分发对 VARIANT 数组封送不可靠（assembly.py CreateTransform 先例）
    # ——第二轮改用 makepy 强类型 IDimension 包装。
    dim_name = f"D1@{_first_extrusion_name(model)}"
    dim = model.Parameter(dim_name)
    print(f"[dim] {dim_name} -> {dim!r}")
    ok_cfg_set = False
    if dim is not None:
        typed_dim = _typed(dim, "IDimension")
        if typed_dim is None:
            print("[dim-typed] IDimension wrap failed")
        else:
            ok, _ = _try(
                "typed SetSystemValue3(0.05, 3, ('CFG_B',))",
                lambda: typed_dim.SetSystemValue3(0.05, 3, ("CFG_B",)),
            )
            if ok and call_or_value(model, "EditRebuild3"):
                ok_cfg_set = True
                print("[dim-cfg] typed accepted names form: tuple")
        if ok_cfg_set:
            back_default = _try(
                "switch back ShowConfiguration('默认')",
                lambda: model.ShowConfiguration("默认"),
            )[0]
            if back_default:
                val_default = model.Parameter(dim_name).GetSystemValue3(1, "")
                model.ShowConfiguration("CFG_B")
                val_b = model.Parameter(dim_name).GetSystemValue3(1, "")
                print(f"[dim-cfg] default={val_default!r} CFG_B={val_b!r}")
                ok_cfg_set = val_default != val_b

    # ---- 4. 组合通道：激活配置 -> which=1 设值 -> 切回验证 ----------------
    # （SW 官方系列件工作流：ShowConfiguration 后在激活配置上设配置特定值）
    ok_combo = False
    model.ShowConfiguration("CFG_B")
    ok_set1, _ = _try(
        "combo SetSystemValue3(0.05, 1, '') on active CFG_B",
        lambda: model.Parameter(dim_name).SetSystemValue3(0.05, 1, ""),
    )
    if ok_set1 and call_or_value(model, "EditRebuild3"):
        model.ShowConfiguration("默认")
        val_default2 = model.Parameter(dim_name).GetSystemValue3(1, "")
        model.ShowConfiguration("CFG_B")
        val_b2 = model.Parameter(dim_name).GetSystemValue3(1, "")
        print(f"[dim-combo] default={val_default2!r} CFG_B={val_b2!r}")
        ok_combo = val_default2 != val_b2

    file_io.close_document(sw, save_changes=False)
    settled = (
        len(EQ_PUT_FORM) == 1
        and len(EQ_DELETE_FORM) == 1
        and ok_show
        and active == "CFG_B"
        and (ok_cfg_set or ok_combo)
    )
    print(
        f"SUMMARY: {'OK' if settled else 'PARTIAL'} "
        f"put={EQ_PUT_FORM} delete={EQ_DELETE_FORM} "
        f"show_cfg={ok_show}/{active!r} cfg_dim_names={ok_cfg_set} "
        f"cfg_dim_combo={ok_combo}"
    )
    return 0 if settled else 1


if __name__ == "__main__":
    sys.exit(main())
