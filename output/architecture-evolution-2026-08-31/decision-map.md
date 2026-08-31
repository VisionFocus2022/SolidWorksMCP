# 决策图谱（decision-map）— SolidWorksMCP 架构演进审查 2026-08-31

> 产出技能：architecture-visualization:evolution-planner。证据见 `current-vs-target.evidence.md`。

## 1. 已冻结决策（ADR 时间线，全部 current / high confidence）

| ADR | 决策 | 关键取舍 | 后续开口 |
|---|---|---|---|
| 0001 | 所有 SW COM 调用收束单 STA 线程 | 极简并发模型 vs 单调用挂死瘫痪全服 | → 已由 0006.1 超时+毒化闭环 |
| 0002 | COM 晚绑定 + constants.py 手工镜像常量 | 零部署依赖 vs 运行期才暴露参数错 | FakeModel 双打测试兜底 |
| 0003 | 产品工具（ring_light）物理隔离 examples/ + env 门控 | 行为零变化 vs 保留 22 个一次性工具 | 需要时可两行注销 |
| 0004 | 路径校验逐组件解析，禁词法折叠 | 防 junction 穿越丢单 | 残余 TOCTOU 微秒窗（6.3 收窄） |
| 0005 | capabilities 从注册表派生 + 契约测试锁相等 | 消灭三重漂移 | 超时/探测/close 三遗留 → 均已落地 |
| 0006.1-6.6 | 超时+毒化 / 会话过滤 / sink 复查 / allowed_root 收敛 / 显式 close / ring_light 通用化 | 一批安全默认值收紧 | — |
| 0007 | 通用环阵双工具契约（预览 READ_ONLY + 执行 DESTRUCTIVE 分离） | 放弃原生 FeatureCircularPattern4（风险高） | 升级路径留探针 → G7 |
| 0009 | AI 可感知模型：面命名 SetEntityName / 尺寸 mm 契约 | 面序号漂移由「只命名未命名面」缓解 | 角度维度 v1 不支持（v 語义未定） |
| 0010 | 装配修复闭环：干涉体 AABB+质心 / MathTransform 16 元素 / mate 删除树复检下钻 MateGroup | SetTransformAndSolve3 替换式非叠加，调用方累计位姿 | — |
| 0011 | 特征解锁方法论（类型库枚举+PS 反射，不盲试）+ 数学替代如实声明 + COM 释放约定 | 数学替代件非参数联动 | 线性阵列原生 API 缺失实证 → G7 |
| 0012 | CSG 契约 v1（4-op）跨引擎互证 + server 分域注册（1494→206 行） | v1 仅 4 op | 装饰/阵列扩契约 → G6 |

**决策密度观察**：12 个 ADR 家族覆盖了全部高风险面（并发/绑定/安全/契约/分层），方法论沉淀（0011「先取证后编码」）已被四期任务复用。决策记录质量高，无相互冲突。

## 2. 开放决策点（本审查提出，待用户/计划裁决）

| ID | 决策 | 选项与推荐 | 状态 |
|---|---|---|---|
| **D1** | **主仓 15 提交推送**（N8-N14 + 四期全部成果，origin 停在 04bf21f） | A. 用户手动 `git push`（推荐，分钟级保险）/ B. 继续单机存放 | 🔴 新发现，未在四期计划内 |
| **D2** | aicad 远端选型（N22，BLOCKED 中） | gitee（与主仓同平台，推荐）/ github（CI 兼容性好） | ⏳ 等用户提供 URL |
| **D3** | 主仓 CI 激活路径 | A. 加 github 第二远端跑 GH Actions（推荐）/ B. ci.yml 迁 Gitee Go / C. 维持休眠 | 🔴 新发现：ci.yml 是 GitHub Actions 语法但远端在 gitee，CI 从未跑过 |
| **D4** | N23 perf 预算策略 | A. 空闲机复验关单（计划既定，推荐）/ B. 机器状态感知测量（负载 >50% 自动 skip 并标注）——注意红线「禁放室断言」，B 属换测量条件非放宽容差 | ⏳ 待空闲机 |
| **D5** | CSG 契约 v2 范围 | 下一批 op：装饰（fillet/chamfer）→ 阵列 → 螺纹？按评测集失败样本驱动 | 远期 |
| **D6** | 智能自治层排序（S5 内部） | 评测数据先行的 plan-then-execute（>10 件装配 token 瓶颈，B7）优先于 RAG/mate 求解器 | 远期 |
| **D7** | 命名澄清（低优先级） | 主仓远端 URL 名为 `AICAD.git` 与子仓 `aicad/` 同名异体——确认是否历史误设 | 问询 |

## 3. 约束（不可协商，来自 AGENTS.md / 计划红线）

- COM 调用必须经 `run_com(...)`；文件操作限 `allowed_root`；破坏性工具标 DESTRUCTIVE。
- MCP 入参 mm、COM 层 m，换算在实现层。
- 绝不自动 push；双仓分别提交、绝不跨仓。
- 主仓覆盖率红线 ≥89%（CI 硬门 80%）。
- 主仓测试基线 485 passed + 95 subtests；工具计数 4 处断言钉死。
