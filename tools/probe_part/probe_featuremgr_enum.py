"""N9 步骤 1：类型库枚举——mirror/draft/线性阵列/真实螺纹候选成员真实签名。

T8/T21 BLOCKED 根因 = 盲试签名（InsertMirrorFeature 9 组合零产出、
FeatureLinearPattern×DName 零产出、DraftBody 数组编组失败、InsertCutSwept4
三形态零产出）。本轮先纯类型库枚举（不连 SW、不盲试）：

  gencache.GetModuleForProgID("SldWorks.Application")
    A. IFeatureManager/IModelDoc2/IBody2/IModelDocExtension 上含
       Mirror/Pattern/Draft/Sweep/Helix/Thread 的成员 → 描述文字
    B. swTn* 常量（CreateDefinition 特征类型名，FeatureData 路线入口）
    C. sw*Draft*/sw*Thread* 常量（枚举值佐证）
    D. makepy 生成源码 def 行（真实参数名——docstring 只有描述）
    E. IModelDoc2.InsertCut* 全枚举（真实螺纹扫掠切除候选）

结论回填本文件头与 tools/INDEX.md；实机最小调用由步骤 2 探针（针对性）验证。
纯 makepy 缓存操作，不依赖 SW 运行（缓存由既往 typed 工具生成）。

结论（2026-08-30，log：output/probe_n9_enum.log + 完整签名见探针运行记录）：
1. **draft 特征级 API 存在**（T8 判断有误）：
   `IFeatureManager.InsertMultiFaceDraft(Angle, FlipDir, EdgeDraft, PropType,
   IsStepDraft, IsBodyDraft)` 返 IFeature；另有 ModelDoc2.InsertMfDraft2
   (同前 4 参+StepDraft, 返 void)——优先 FM 版（返回值可判成败）。
2. **FeatureLinearPattern4 = 20 参 / 5 = 22 参**（T8 按 8 参形态调用 FM 版
   必然参数错位）：(Num1, Spacing1, Num2, Spacing2, FlipDir1, FlipDir2,
   DName1, DName2, GeometryPattern, VaryInstance, HasOffset1/2, CtrlByNum1/2,
   FromCentroid1/2, RevOffset1/2, Offset1/2[, D2PatternSeedOnly, SyncSubAssemblies])。
3. **mirror 新线索**：`InsertMirrorFeature2(BMirrorBody, BGeometryPattern,
   BMerge, BKnit, ScopeOptions:int)` 第 5 参 T8 未试（只试 4 参版 9 组合）。
4. **真实螺纹新路径**：`IFeatureManager.InsertCutSwept5` 22 参，尾部
   `CircularProfile:bool, CircularProfileDiameter:double, Direction:int`——
   圆形轮廓扫掠可免 profile 草图，只需 helix 路径选中；T21 的 4 参版无此参。
   helix 契约（T21 已验）：InsertHelix def=0 可建，树名「螺旋线/涡状线1」，
   SelectByID2(名, "REFERENCECURVES", mark=1) 可选。
5. swTn*/枚举常量不在 makepy vars()（枚举不生成），ScopeOptions/PropType
   合法值只能实机收敛（步骤 2）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from win32com.client import gencache

OUT_LOG = Path(__file__).resolve().parents[2] / "output" / "probe_n9_enum.log"
KEYWORDS = ("Mirror", "Pattern", "Draft", "Sweep", "Helix", "Thread")
CLASSES = ("IFeatureManager", "IModelDoc2", "IBody2", "IModelDocExtension")


def main() -> int:
    mods = gencache.GetModuleForProgID("SldWorks.Application")
    if mods is None:
        print("!! makepy 缓存不存在（需先运行任一 typed 工具或 EnsureDispatch 生成）")
        return 2

    lines: list[str] = []

    lines.append("== A. 接口成员（含关键词者，附 __doc__ 签名）==")
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
    lines.append("== C. 其他 Draft/Thread 相关常量 ==")
    hits = 0
    for name in sorted(vars(mods)):
        if not name.startswith("sw"):
            continue
        low = name.lower()
        if ("draft" in low or "thread" in low) and not name.startswith("swTn"):
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
            "InsertMirrorFeature", "InsertMultiFaceDraft", "InsertMfDraft",
            "FeatureLinearPattern", "FeatureCircularPattern4",
            "InsertCutSwept", "InsertHelix", "InsertCosmeticThread3",
            "DraftBody2", "InsertProtrusionSwept",
        )
        for line in text_src.splitlines():
            stripped = line.strip()
            if stripped.startswith("def ") and any(
                t in stripped for t in targets
            ):
                lines.append(f"  {stripped}")

    # E. 扫掠切除候选：IModelDoc2 全部 InsertCut* 成员（真实螺纹路径）
    lines.append("")
    lines.append("== E. IModelDoc2.InsertCut* 成员 ==")
    doc2 = getattr(mods, "IModelDoc2", None)
    if doc2 is not None:
        for name in sorted(m for m in dir(doc2) if m.startswith("InsertCut")):
            lines.append(f"  IModelDoc2.{name}")

    text = "\n".join(lines)
    print(text)
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOG.write_text(text + "\n", encoding="utf-8")
    print(f"\nSUMMARY: enum written to {OUT_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
