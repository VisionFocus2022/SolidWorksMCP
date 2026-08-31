"""N28 步骤 1：类型库枚举——loft/sweep（放样/扫描）候选成员真实签名。

0011 方法论（先取证后编码）：N9 probe_featuremgr_enum 同模式纯缓存
枚举（不连 SW、不盲试——T8/T21 的教训是盲试签名零产出）：

  gencache.GetModuleForProgID("SldWorks.Application")
    A. IFeatureManager/IModelDoc2/IModelDocExtension 上含 Loft/Swept 的成员 → 描述
    B. swTn* 常量（CreateDefinition 特征类型名：Loft/Sweep 系）
    C. sw*Loft*/sw*Sweep* 常量（枚举值佐证）
    D. makepy 源码 def 行（真实参数名——Loft/Swept 全代次）
    E. *Loft*/*Sweep* 数据类（CreateDefinition 路线的 FeatureData 对象）

结论回填本文件头与 tools/INDEX.md；实机最小调用由步骤 2 探针验证。
纯 makepy 缓存操作，不依赖 SW 运行（缓存由既往 typed 工具生成）。

结论（2026-08-31，log：output/probe_n28_enum.log，完整签名见 D 段）：
1. **sweep 首选路线锁定**：`IFeatureManager.InsertProtrusionSwept4` 20 参
   `(Propagate, Alignment, TwistCtrlOption, KeepTangency, BAdvancedSmoothing,
   StartMatchingType, EndMatchingType, IsThinBody, Thickness1, Thickness2,
   ThinType, PathAlign, Merge, UseFeatScope, UseAutoSelect, TwistAngle,
   BMergeSmoothFaces, CircularProfile, CircularProfileDiameter, Direction)`
   ——尾部三参与 N9 记录的 InsertCutSwept5 同款：**CircularProfile=True 时
   免轮廓草图，只需路径草图选中**（最简扫描形态：圆截面沿路径）。
   注意 IModelDoc2.InsertProtrusionSwept4 是另一形态（12 参，无 Merge/
   CircularProfile 尾参）——务必走 IFeatureManager 版。
2. **凸台放样无直接 API**（2026 类型库双接口实证）：IFeatureManager 与
   IModelDoc2 均无 InsertProtrusionLoft 系；仅有 InsertLoftRefSurface(2)
   （放样**曲面**）与 IModelDoc2.AddLoftSection（老式 blend 序列入口）。
   loft 候选路线（步骤 2 实机收敛）：
   A. CreateDefinition(swTnLoft*) + LoftFeatureData + CreateFeature（现代路线，
      LoftFeatureData/ILoftFeatureData 类存在）
   B. AddLoftSection 老式序列
3. swTn*/sw*Loft* 枚举常量不在 makepy vars()（N9 结论 5 再次证实）——
   路线 A 所需 swTnLoft 常量值须 PowerShell 反射 swconst.dll（先例
   swFmSweepThread=87）。
4. SweepFeatureData/SweptFlangeFeatureData 数据类存在——sweep 亦有
   CreateDefinition 备选路线（若 InsertProtrusionSwept4 直调失败再启用）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from win32com.client import gencache

OUT_LOG = Path(__file__).resolve().parents[2] / "output" / "probe_n28_enum.log"
KEYWORDS = ("Loft", "Swept", "Sweep")
CLASSES = ("IFeatureManager", "IModelDoc2", "IModelDocExtension")


def main() -> int:
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    if mods is None:
        print("!! makepy 缓存不存在（需先运行任一 typed 工具或 EnsureDispatch 生成）")
        return 2

    lines: list[str] = []

    lines.append("== A. 接口成员（含 Loft/Swept 关键词者，附 __doc__ 签名）==")
    for cls_name in CLASSES:
        cls = getattr(mods, cls_name, None)
        if cls is None:
            lines.append(f"-- {cls_name}: 模块中不存在")
            continue
        members = sorted(
            m for m in dir(cls) if any(kw.lower() in m.lower() for kw in KEYWORDS)
        )
        lines.append(f"-- {cls_name}: {len(members)} 个成员命中关键词")
        for name in members:
            doc = getattr(cls, name).__doc__ or ""
            doc_one = " ".join(doc.split())
            lines.append(f"  {cls_name}.{name}: {doc_one}")

    lines.append("")
    lines.append("== B. swTn* 常量（CreateDefinition 特征类型名）==")
    for name in sorted(vars(mods)):
        if not name.startswith("swTn"):
            continue
        if any(kw.lower() in name.lower() for kw in KEYWORDS):
            lines.append(f"  {name} = {getattr(mods, name)!r}")

    lines.append("")
    lines.append("== C. sw*Loft*/sw*Sweep* 常量 ==")
    hits = 0
    for name in sorted(vars(mods)):
        if not name.startswith("sw"):
            continue
        low = name.lower()
        if ("loft" in low or "sweep" in low or "swept" in low) and not name.startswith(
            "swTn"
        ):
            lines.append(f"  {name} = {getattr(mods, name)!r}")
            hits += 1
    lines.append(f"  （共 {hits} 项）")

    # D. makepy 源码 def 行：docstring 只有描述，真实参数名在生成源码里
    lines.append("")
    lines.append("== D. makepy 源码 def 行（真实参数名）==")
    src = Path(mods.__file__)
    lines.append(f"  源码: {src}")
    if src.exists():
        text_src = src.read_text(encoding="utf-8", errors="replace")
        targets = (
            "InsertProtrusionLoft", "InsertLoft", "FeatureLoft",
            "InsertProtrusionSwept", "InsertSwept", "FeatureSweep",
            "InsertCutSwept", "CreateSweep", "CreateLoft",
        )
        src_lines = text_src.splitlines()
        for i, line in enumerate(src_lines):
            stripped = line.strip()
            if not (
                stripped.startswith("def ")
                and any(t in stripped for t in targets)
            ):
                continue
            # makepy 的 def 跨多物理行（参数续行缩进），拼到闭合括号为止
            block = [stripped]
            for cont in src_lines[i + 1 : i + 12]:
                s2 = cont.strip()
                if not s2 or s2.startswith("def ") or s2.startswith('"""'):
                    break
                block.append(s2)
                if s2.rstrip().endswith("):"):
                    break
            lines.append("  " + " ".join(block))

    # E. CreateDefinition 路线的数据类（LoftFeatureData/SweepFeatureData 等）
    lines.append("")
    lines.append("== E. *Loft*/*Sweep* 数据类 ==")
    for name in sorted(vars(mods)):
        if "Loft" not in name and "Sweep" not in name and "Swept" not in name:
            continue
        if isinstance(getattr(mods, name), type):
            lines.append(f"  class {name}")

    text = "\n".join(lines)
    print(text)
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOG.write_text(text + "\n", encoding="utf-8")
    print(f"\nSUMMARY: enum written to {OUT_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
