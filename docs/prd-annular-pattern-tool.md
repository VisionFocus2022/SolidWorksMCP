# PRD-lite：通用环形阵列工具（annular pattern）

**版本**: 1.0
**日期**: 2026-08-28
**档位**: 🟡 L2（高确定 × 中影响，纯加法）
**关联**: ADR-0006.6（独立立项边界）、ADR-0007（契约决策）
**授权留痕**: 用户指令"『通用环形阵列工具』要做，按 ADR-0006.6 应独立立项" + AskUserQuestion 两项裁决（契约=双工具+模型校验；实机验证=留一键脚本）

## 1. 背景与目标

ring_light 的行数已通用化（1-64 行），但安装孔/线缆盒仍是产品常量，且模块位于 `examples/`。机械设计中"同心环上排布圆特征"（螺栓孔圆、散热孔阵、LED 阵）是高频通用需求。本项把该能力提炼为**通用层**（`solidworks_api/`）独立工具，不膨胀 examples。

## 2. 功能需求（FR）

- **FR-1 布局预览工具** `solidworks_pattern_annular_layout`（READ_ONLY，纯几何、不触碰 SolidWorks）：输入环列表 + 可选避让角，输出逐环位置/相位/总数/重叠警告。
- **FR-2 执行工具** `solidworks_part_create_annular_pattern`（DESTRUCTIVE）：在命名平面上按布局逐环建草图并 cut/boss；cut 支持 through_all/blind，boss 恒为 blind；可选 save_path 保存。
- **FR-3 逐项 schema 校验**：环参数用 pydantic `AnnularRing` 模型（radius_mm>0 / count 1-1000 / diameter_mm>0 / phase 0-360），补上审查 P2-7 指出的"聚合参数无逐项校验"短板。
- **FR-4 相位优化**：环未显式给 phase 且提供避让角时，用 ring_light 已实机验证的 72 步最大间隙算法自动选相位。
- **FR-5 重叠警告**：环内弦距<孔径、环间径向间距<半径和时在 warning 中提示（SolidWorks 会合并特征，需告知用户）。
- **FR-6 实机验证脚本** `tools/validate_annular_pattern.py`：建板→三环 cut（一环避让角优化）+一环 boss→特征树/质量属性核验（含体积区间断言）→存档 SLDPRT/STEP→关闭文档；一键可重跑。

## 3. 验收标准（AC）

- AC-1 pytest 全绿且新增测试 ≥18 条（布局数学 11 + COM 双打 8 + 注册/schema 2）；工具数 23→25，三处计数断言同步。
- AC-2 `rings` 参数的 inputSchema 具备 items.properties 逐项约束（exclusiveMinimum 等），feature_kind 为枚举。
- AC-3 布局输出确定性：同输入同输出；避让角优化结果可解析断言（如 8 环避让 [0,90,180,270] → 相位 22.5°）。
- AC-4 COM 路径复用 geometry/sketch 原语，特征命名 `ANNULAR_{CUT|BOSS}_RING_{ii}_R{半径}_N{数量}`。
- AC-5 模式与既有工具一致：错误码 INVALID_PARAMETER/SW_API_ERROR、五段响应、mm→m 换算、save 走 ensure_sink_path 链。
- AC-6 验证脚本在 SW 运行时一键出报告（退出码语义明确），SW 未运行时给出结构化提示。

## 4. 范围

Out of Scope：SW 原生 FeatureCircularPattern4 阵列既有特征（参数序无文档佐证，若需要另行立项）；非圆特征；3D 曲线阵列；把 ring_light 产品常量搬进通用层。

## 5. 风险与假设（含三栏账）

- **已知**：几何/COM 原语全部现成且有 89% 覆盖率测试网；"逐环单草图 + 单特征"路线在 ring_light LED 标记上已被实机验证。
- **假设**：FeatureCut3/FeatureExtrusion2 在多环场景的行为与 ring_light 一致（同一调用形态）——实机脚本核销。
- **未知→已裁决**：契约形态（用户选双工具+模型校验）；实机验证时机（用户选留脚本）。
