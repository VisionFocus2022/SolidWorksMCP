# 迁移路线图（migration-roadmap）— SolidWorksMCP 2026-08-31

> 产出技能：architecture-visualization:evolution-planner。
> 依赖图见 `architecture-evolution.dot`；差距图谱见 `current-vs-target.dot`；开放决策见 `decision-map.md`。
> 每片必含验证信号（VS）。状态=proposed（本文档为审查产物，供下一期 optimization-plan 取材）。

## S0 灾备保险（P0，用户动作，分钟级）→ 决策 D1

**保护的业务路径**：全部已交付能力（69 工具 + aicad 12 批次 + N18-N21 治理成果）。

- 步骤：用户对主仓执行 `git push origin main`（15 提交：N8-N14 六特性 + N18-N21）。
- 无代码改动，无需 TDD。
- **VS**：`git rev-parse origin/main == HEAD`；gitee 网页可见 00db3e7。
- 依据：单机存放两周成果 = 当前系统最高severity、最低修复成本的风险。

## S1 交付闭环（P1）→ 决策 D2/D3（N22 扩容）

**保护的业务路径**：夜间 02:30 自动任务产出的每一晚增量不再裸奔。

- 步骤：
  1. aicad 远端接入（用户提供 URL，gitee 优先与主仓同平台）+ 首推 69 提交。
  2. 主仓 CI 激活裁决（D3）：推荐加 github 第二远端跑现成 ci.yml（pytest + coverage≥80 + pip-audit）；或迁 Gitee Go。
  3. aicad CI 绑定（pytest + npm build 两 job，主仓模板复刻）。
- **VS**：push 后 CI 首跑绿；aicad 远端 SHA == 本地 HEAD；两仓 `git status -sb` 无 ahead。
- 风险：aicad 两个 untracked 脚本（tools/e2e_four_ring.py / golden_flange_sample.py）归属裁决——入库或删除后远端才干净。

## S2 质量收口（P2）→ 决策 D4

- 步骤：
  1. N23 空闲机复验（SW 关 + CPU<20%）：`pytest tests/test_perf_budgets.py -q` 绿→关单；红→开提取循环微优化批（预算线不动）。
  2. H2 缓存命中率报表（aicad /api/health 数据已有，补导出面）。
  3. CodeRabbit `auth login` 后补跑外审（J3）。
- **VS**：perf 用例在受控环境确定性绿；报表可导出 CSV/JSON；CodeRabbit 首份报告落地。

## S3 零件能力长尾（P2，可分波，每波一晚）→ 决策 D5

**解锁的业务路径**：AI 覆盖非箱体/回转体类零件（覆盖面从 90% 型材件扩到自由曲面件）。

- 步骤（建议顺序，全部走 0011 方法论：先类型库取证→探针→TDD）：
  1. loft / sweep（放样/扫描——多草图特征族，解锁曲面件）
  2. 筋 / 圆顶 / 参考几何创建（geared toward 支撑类件）
  3. 多实体 combine；通用草图原语（多边形/槽/样条）
  4. CSG 契约 v2 扩 op（跟随已落地特征逐步纳入跨引擎可迁移集）
- **VS**：每特征 TDD（FakeModel 红→绿）+ 实机 e2e（探针数值窗口断言）；CSG v2 = 跨引擎往返体积互证（0012 模式）；工具计数 4 处断言同步 +N。

## S4 图纸能力长尾（P2，与 S3 并行——域不相交）

**解锁的业务路径**：制造级交付图纸的最后装饰面（当前 PDF/STEP/STL/DXF 已齐，缺装配表达件）。

- 步骤：
  1. BOM 气泡引线（drawing 域，挂 BOM 表已有）
  2. 爆炸图（assembly 域 ExplodedView + drawing 投影）
  3. aicad 前端冒烟测试（React/three.js 当前零测试——最终交付物的视觉正确性无自动防线）
- **VS**：e2e 产物断言（PDF 内实体存在/图层正确）；前端 npm test 绿 + 关键交互冒烟。

## S5 智能自治层（远期，按评测数据驱动立项）→ 决策 D6

**解锁的业务路径**：从「AI 可调用全工具链」到「AI 无人值守自主完成整机图纸」。

- 候选（优先级待评测集失败样本定夺）：
  1. plan-then-execute 任务分解（B7：>10 件装配超 8192 tokens 无法生成——token 瓶颈）
  2. RAG 示例检索（历史成功件检索增强生成）
  3. mate 约束求解器（装配意图→约束组合自动求解）
  4. 多模型路由（规划用强模型/执行用快模型）
  5. 原生 FeatureCircularPattern4 升级（G7——数学替代件改一处不驱动全阵；探针升级路径已留）
- **VS**：评测集任务通过率提升可量化（aicad 评测框架已有 10 任务离线 10/10 基线）。

## 排序原则（为什么 S0/S1 在能力扩展前）

1. **可逆性**：S0/S1 是纯交付面动作，零代码风险；S3-S5 每晚新增代码都受益于前置灾备。
2. **价值**：能力面（三期 17/17）已覆盖目标场景主路径；剩余差距按四期核心判断是「治理与可靠」而非「能力缺失」。
3. **验证成本**：S0 的 VS 几乎免费；S5 的 VS 需要评测基线对比，最贵。
