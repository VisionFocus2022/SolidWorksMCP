# ADR-0010：装配修复闭环——干涉定位、mate 删除、组件变换（N8）

日期：2026-08-30 · 状态：已接受（实机验证，探针七轮）

## 背景

第三期差距 E1/E2/E5：干涉检测只报体积与组件名（AI 知道谁撞不知撞在哪），
无 delete_mate / 组件移动——AI 检测到干涉后的唯一路径是推倒重来。修复
闭环 = 定位 → 改 mate/挪件 → 复检，三者缺一环闭环即断。

## 决策

### 1. 干涉空间定位：干涉体取包围盒与质心

- **决策**：`IInterference.GetInterferenceBody()` → `IBody2`，再
  `GetBodyBox()`（6 值，米）取 AABB、`GetMassProperties(1000.0)` 取
  质心（[0:3]）与体积（[3]，m³），统一换算 mm/mm³ 输出。
- **依据**：干涉结果对象上直接可用，无需二次几何求交；60×40×20 盒
  干涉体实机数值精确。
- **代价**：AABB 对斜干涉体偏大——定位语义（撞在哪）够用，精确形状
  不承诺。

### 2. 组件变换：MathTransform 16 元素 + SetTransformAndSolve3

- **决策**：IAssemblyDoc 的 Translate/RotateComponent 为零参交互式、
  `TransformComponent2` 已被 2026 移除。正路 = `GetMathUtility` →
  `CreateTransform(16 元素 VARIANT)`（13 元素不生效）→
  `IComponent2.SetTransformAndSolve3(xform, True)`，随后**必须
  `EditRebuild3()`** 干涉检测才更新（否则读旧几何）。
- **依据**：探针逐项实跑排除法（typed/gen_py 签名 grep + 逐成员验证）。
- **代价**：SetTransformAndSolve3 是**替换式**非叠加——连续挪件须由
  调用方累计位姿；换算与坐标系契约在工具 docstring 声明。

### 3. mate 删除：按名选 "MATE" + 树复检含 MateGroup

- **决策**：`SelectByID2(mate_name, "MATE")` → `EditDelete`
  （BODYFEATURE/FEATURE 形态均 False）；删除后特征树复检遍历**必须
  下钻 MateGroup 一层子特征**——顶层 walk 看不到 mate，coincident/
  distance 两轮重复验证。
- **代价**：无；复检遗漏会让"删除成功"假绿。

## 后果

装配修复闭环（检测→定位→修 mate/挪件→复检）成立；BOM 扩列（质量/
材料）同批落地。证据：`e5afd1d`、探针 `output/probe_n8_interference.log`。
