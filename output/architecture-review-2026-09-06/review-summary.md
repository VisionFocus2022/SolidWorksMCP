# SolidWorksMCP 专家团全面审查总结（2026-09-06）

> 方法：Qoder 专家团方法论落地（详见 §1）——五角色并行子智能体审查 + 主循环机械证据交叉验证。
> 审查范围：第五期 N27-N34 增量代码 + CI 时代交付面；基线对照 `output/architecture-evolution-2026-08-31/`。
> 原始产出：同目录 `{factual,engineer,security,consistency,redundancy}.json`（每条 finding 附实读行号证据）。
> 环境 Note：五位审查者均无 Bash/Read 原生工具，仅 CodeGraph 只读索引（覆盖 .py；markdown 与测试执行由主循环补跑）。

## 一句话结论

**第五期交付质量总体扎实（安全 0 CRITICAL/HIGH、计数五方对齐、双 CI 全绿、实测 542+105/712+18 绿），但 part.py 已击穿治理红线（1243 行，HIGH×1），四条 MEDIUM 结构债（save 样板×6、makepy 包装×3~6 漂移、CSG 哨兵脆弱、基线数字漂移）应在下一期初收口，LOW×8 可顺手批。**

## 0. 主循环机械证据（与审查者交叉验证）

| 项 | 实测 | 文档声明 | 判定 |
|---|---|---|---|
| 主仓全套 | **542 passed + 105 subtests**（9.4s） | AGENTS.md 537/538 | 漂移（多会话并行加测未回填基线） |
| aicad 全套 | **712 passed + 18 perf deselected**（178s） | 计划 637/719 | 漂移（同上） |
| 工具注册 | registry 合计 81 处 `mcp.tool(`（products 2 个 env 门控→默认 79） | README/断言 79/81 | ✅ 一致 |
| part.py | **1242 行**（wc -l） | 08-31 基线 1011、<1100 线 | ❌ 击穿（+232，+23%） |
| design.py | 1087 行 | 08-31 基线 1011 | 逼近线 |
| decorations→part 依赖 | 单向无环（grep import 全集） | — | ✅ 无循环 |

## 1. Qoder 专家团学习方法论（本审查的"学习"交付物）

1. **探查结论**：`~/.qoder/` 无「专家团」独立定义资产（settings.json 仅插件开关；42 个 skills 无相关；plans/ 为普通计划文档）——专家团是 Qoder IDE **内置 GUI 多智能体面板**，配置不可文件化复用。
2. **方法论内核可迁移**：多角色分工（事实核查/资深工程/安全/一致性/冗余五视角）+ 并行取证 + 证据纪律（每 finding 必附实读行号）+ 宁缺勿滥——与 SDW L3 深度并行规划、用户全局 agents.md 的五视角编排同构。
3. **落地配方（本仓可复用）**：Workflow 派 5 角色并行（每角色自带 CANNOT_READ 兜底声明）→ 主循环补跑机械验证（测试/计数/行数——subagent 无 shell 时这是必要补位）→ 汇总去重成报告。本节即为复用模板。
4. **环境教训**：本会话 subagent 无文件工具是常态而非异常（两次审查皆如此）——**审查类 Workflow 必须配主循环机械验证层**，否则文档/测试执行面全部失明。

## 2. 发现汇总（去重合并后 1H/4M/8L）

### HIGH（下一期初必须处置）

| ID | 标题 | 来源 | 证据锚点 |
|---|---|---|---|
| H-1 | **part.py 1243 行击穿 <1100 治理红线**（E-12 基线 1011，N28-N30 注入约 +590 行毛增/净 +232） | engineer SE-1 | L563-1243 逐函数行号清单；主循环 wc=1242 ✓ 互证 |

处置：按域拆分 primitives / sweep_loft / refgeom 三模块 + `_typed_doc2` 上提 utils/com.py（联动 M-2）。

### MEDIUM（进 backlog，下期收口）

| ID | 标题 | 来源 |
|---|---|---|
| M-1 | save_path 双块样板 part.py ≥6 处逐字复制（design._save_active_model L102-122 已有现成抽象）；附带 feature 失败响应 code 缺失不一致（swept/polygon/slot 无 code vs ref_plane/ref_axis 有） | engineer SE-2 |
| M-2 | makepy typed 包装逻辑全仓 3 处生产重复 + 3 处探针拷贝，且已**语义漂移**（assembly._wrap_static 最完善含 PyIDispatch 防误判；part/decorations/features 各自简化版）；decorations 跨模块取 part 私有符号 | engineer SE-3 + redundancy R-1 合并 |
| M-3 | CSG v2 `stack_top=None` 哨兵对未来 op 扩展脆弱（漏检→TypeError 退化报错且不触发回滚；else 兜底把未知 op 当 cut_cylinder，依赖前置校验）；rebuild_csg_plan 180+ 行 6 分支长链 | engineer SE-4 |
| M-4 | **基线数字多会话漂移**：AGENTS.md 537/538 vs 实测 542；计划 637/719 vs 实测 712+18——08-31 审查 G3「文档计数漂移」同源问题的重演（多会话并行加测未回填权威基线） | 主循环实测（两审查者因无 markdown 读取权失明，正好证明该盲区） |

### LOW（顺手批）

| ID | 标题 | 来源 |
|---|---|---|
| L-1 | `test_default_subprocess_registers_71_tools` 方法名残留旧计数 71（断言实为 79）——N14 时代命名未随计数演进 | factual + consistency（同源互证） |
| L-2 | registry plane/path_type 注解三风格混用（NonEmptyString/裸 str），未用 Literal 在 schema 层 fail-fast（base.py MateType 已有先例） | engineer SE-5 |
| L-3 | `_validate_csg_plan` 数值检查未排 NaN/+inf/bool（绕开 finite_number 纪律，isinstance(x,(int,float)) 放行 NaN/True） | security |
| L-4 | 注解不一致：rebuild_csg=STATE_CHANGE 而 execute_design_plan=DESTRUCTIVE（两者含同等减材能力） | security |
| L-5 | `_expand_long_path` 缓冲区不足时静默放弃（fail-closed 正确但未按返回所需大小重试） | security |
| L-6 | csg_rebuild 内置 prompt 未宣发 v2 契约（in-code 文档滞后 N31） | consistency |
| L-7 | CSG_VERSION=1 常量成无消费者死值（版本合法集硬编码在校验器） | consistency |
| L-8 | 已完成探针（n9/n28/n29/n30）缺「已完成」标注；探针脚手架 helper 六脚本重复；N28-N30 三个测试文件重复实现同一套 FakeModel（~150 行）且两处文件名与内容错位 | redundancy |

### 明确不处置（审查者判断合理样板）

- registry 层 launch_if_needed/_call_connected 样板：框架要求，不建议抽象（redundancy）。
- 探针留档：实机契约已转录生产 docstring，脚本保留作历史证据（redundancy）。

## 3. 与 08-31 审查对照（增量视角）

| 08-31 差距 | 本次状态 |
|---|---|
| G1 交付可靠 | ✅ 已闭环（双仓双远端+双 CI 全绿）且经受住第五期 30+ 提交的持续验证 |
| G2/G3 质量观测 | ✅ 大体闭环；**新表现**：基线数字漂移重演（M-4）——多会话并行的治理新课题 |
| G4/G5 能力长尾 | ✅ 8 个新工具落地；代价=part.py 破线（H-1，长尾扩能的熵账单） |
| G6 CSG v2 | ✅ 落地；哨兵设计留 v3 重构债（M-3） |
| 宏录制器队列 | 不变（mirror/pattern/rib/combine/AutoBalloon 五族，路径已留） |
| **新观察** | 第五期四波次「加函数不改结构」模式把治理债集中到单文件——**下期第一动作应是还结构债再扩能**（与 08-31「先交付后扩能」同一哲学的结构版） |

## 4. 处置建议（优先级序）

1. **下期首个任务批**：H-1 拆分（含 M-2 的 utils/com.py 上提，二者联动）+ M-4 基线权威化（AGENTS.md 改「基线=实测命令输出，文档不存死数」或建立回填纪律）。
2. **第二批**：M-1 save helper 上提、M-3 CSG handler 字典化（v3 前）、L-1/L-6/L-7 顺手批。
3. **触碰时顺手**：L-2 Literal 收紧、L-3 NaN 排除、L-4 注解统一、L-5 缓冲重试、L-8 探针标注+FakeModel 合并。
4. 全部 LOW+MEDIUM 建议入下一期计划任务清单（本报告为取材蓝本，同 08-31 五件套之于第五期）。

---
*审查执行：Claude Code 专家团 Workflow（5 agents，515K tokens，129 tool uses，10.7 分钟）+ 主循环机械验证（pytest×2、wc、grep 计数、import 环检查）。*
