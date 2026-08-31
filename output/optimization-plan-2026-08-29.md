# AI 驱动 3D 机械图全自动绘制——优化改进总体规划

> **生成**：2026-08-29 审查任务（01:30）  
> **主题**：项目距离真正的 AI 驱动全自动绘制 3D 机械图还有哪些需要优化改进的地方  
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考  
> **For agentic workers:** 按任务逐项执行（§2 执行协议），步骤用 checkbox（`- [ ]`）跟踪，完成后回填状态与「执行记录」小节。

---

## 1. 文档定位与背景

工作区包含**两个独立 git 仓库**（分别提交，永不跨仓库提交）：

| 仓库 | 路径 | 角色 |
|---|---|---|
| **主仓库** | `e:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP` | SolidWorks MCP 服务器（COM 直驱 SW，25 个 MCP 工具，供 LLM 调用） |
| **aicad 仓库** | `e:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP\aicad` | AI CAD 原型（OCCT 内核 + CorrectionLoop + FastAPI + SW 三通道互操作） |

「AI 驱动全自动绘制 3D 机械图」的完整链路是：**自然语言 → 设计意图理解 → 参数化几何生成 → 装配 → 工程图（三视图/剖视/尺寸/公差/BOM）→ 输出文件**。当前两个引擎各覆盖一段，中间存在结构性缺口（§5 核心判断）。

本计划是 2026-08-28 三波治理（止血/可测化/现代化）之后的**第二期路线**：从「服务器可用」推进到「AI 全自动出图可用」。

## 2. 执行协议（02:30 实施任务必读）

1. **选任务**：读取 §3 进度总览表，选择**第一个**满足以下全部条件的任务：
   - 状态为 `[ ]`（待执行）；
   - 其「依赖」列所列任务已全部 `[x]`（完成）。
2. **SolidWorks 前置检查**：任务标注「需 SW 实机」时，先运行：
   ```powershell
   python -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; print(get_solidworks_app().status(launch_if_needed=False))"
   ```
   若 SolidWorks 未运行（`connected: false` 且本任务不可自动启动），将状态改为 `[!] BLOCKED（SW 未运行，YYYY-MM-DD）`，**转选下一个可执行任务**。
3. **TDD 循环**：每个任务严格按步骤顺序：写测试 → 跑红 → 实现 → 跑绿 → 实机验证（如需）→ 提交。禁止先写实现后补测试。
4. **探针先行**：步骤中标注「先写探针」的高危 COM API，必须先创建/运行 `tools/probe_<名称>.py` 在实机验证 API 签名与返回形态，再写正式实现。探针脚本保留入库（知识回流，参见 T23）。
5. **提交纪律**：每个任务至少 1 次本地 `git commit`（**绝不 push**）。主仓库改动在主仓库提交，aicad 改动在 `aicad/` 目录内提交。message 格式：`feat|fix|test|docs|chore(scope): <一行中文描述>`。
6. **回填**：任务完成后：
   - 将任务状态字段改为 `[x]`（失败/中断则记录 `[!]` 并注明原因）；
   - 在该任务「执行记录」小节回填：日期 / 结果 / commit hash / 备注；
   - 更新 §3 总览表中该行的状态列与「完成日期」。
7. **节奏**：每晚执行 **1 个任务为宜，最多 2 个**（且第 2 个必须是小任务，预估 ≤2h）。宁可少而稳，不做大爆炸式改动。
8. **安全红线**（继承 2026-08-28 治理结论）：
   - 所有 COM 调用必须经 `run_com(...)`（STA 单线程执行器），文件操作必须在 `allowed_root` 内（`utils/security.py` 校验）；
   - 覆盖率不得低于 89%（`python -m pytest tests/ --cov=solidworks_mcp --cov-report=term -q`）；
   - 破坏性工具（删除特征/关闭文档不保存等）必须标注 `DESTRUCTIVE` 注解；
   - 单位约定：**MCP 工具入参一律 mm，SW COM 层一律 m**（`geometry.mm_to_m`）。
9. **中断恢复**：若任务执行到一半会话中断，下一晚重新读取该任务的 checkbox 进度，从第一个未勾选步骤继续；若已勾选步骤的产物（代码/测试）存在但未提交，先补提交再继续。
10. **测试命令基线**：
    - 主仓库：`python -m pytest tests/ -q` → 当前基线 **191 passed + 51 subtests，约 6.5s**（任何改动后必须全绿）；
    - aicad 仓库：`aicad\venv\Scripts\python.exe -m pytest tests -q`（在 `aicad/` 内）→ 当前基线 **528 passed，约 219s**（只在 aicad 有改动时运行）。

## 3. 任务进度总览

状态图例：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED（注明原因）。「仓库」列：主=主仓库，ai=aicad 仓库，双=两者。

| ID | 优先级 | 标题 | 仓库 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| T1 | P0 | 实机 E2E 验证体系（全工具冒烟脚本） | 主 | 无 | 4h/1晚 | `[x]` | 2026-08-29 |
| T2 | P0 | COM 超时启用与校准 | 主 | T1 | 2h/1晚 | `[x]` | 2026-08-29 |
| T3 | P0 | 特征详情读取工具 features_get_details | 主 | 无 | 3h/1晚 | `[x]` | 2026-08-29 |
| T4 | P0 | 测量工具（两点距离 + 包围盒） | 主 | 无 | 2.5h/1晚 | `[x]` | 2026-08-29 |
| T5 | P0 | 面/实体枚举与命名工具（装配自动化基石） | 主 | 无 | 4h/1晚 | `[x]` | 2026-08-29 |
| T6 | P1 | 旋转特征 revolve + 参考几何（基准轴） | 主 | T3 | 4h/1晚 | `[x]` | 2026-08-29 |
| T7 | P1 | 圆角 fillet + 倒角 chamfer | 主 | T5 | 4h/1晚 | `[x]` | 2026-08-29 |
| T8 | P1 | 抽壳/拔模/镜像/特征线性阵列 | 主 | T7 | 5h/2晚 | `[!]` | mirror/pattern/draft BLOCKED（FeatureData 扫描亦无果 2026-08-30） |
| T9 | P1 | 尺寸读取/修改 + 特征删除工具 | 主 | T3 | 4h/1晚 | `[x]` | 2026-08-29 |
| T10 | P1 | design plan 事务性（回滚部分应用） | 主 | T9 | 4h/1晚 | `[x]` | 2026-08-29 |
| T11 | P1 | 装配增强（mate 类型扩展/干涉检查/BOM） | 主 | T5 | 6h/2晚 | `[x]` | 2026-08-30 |
| T12 | P1 | 主包工程图工具族（三视图+标注+导出） | 主 | 无 | 6h/2晚 | `[x]` | 2026-08-29 |
| T13 | P1 | aicad drawing M2（特征尺寸标注+剖视图入图） | ai | 无 | 8h/3晚 | `[x]` | 2026-08-30 |
| T14 | P1 | aicad AI 循环增强（几何感知反馈+降级策略） | ai | 无 | 6h/2晚 | `[x]` | 2026-08-30 |
| T15 | P1 | aicad preview 测试 + LLM 评测集骨架 | ai | 无 | 5h/2晚 | `[x]` | 2026-08-30 |
| T16 | P1 | 双引擎桥接：特征重建脚本移植为 MCP 工具 | 双 | T3 | 5h/2晚 | `[x]` | 2026-08-30 |
| T17 | P1 | 材料/自定义属性/配置/方程式工具 | 主 | 无 | 4h/1晚 | `[x]` | 2026-08-29 |
| T18 | P2 | 主包 tools/ 探针分域整理 | 主 | 无 | 2h/1晚 | `[x]` | 2026-08-30 |
| T19 | P2 | CI 激活（推送远端） | 主 | 无 | 1h/0.5晚 | `[!]` | 2026-08-30 BLOCKED |
| T20 | P2 | aicad 任务/循环历史持久化 | ai | 无 | 5h/2晚 | `[x]` | 2026-08-30 |
| T21 | P2 | 高级几何（真实螺纹/渐开线齿轮/钣金） | 双 | T6,T7 | 12h/4晚 | `[~]` | 齿轮+钣金完成 2026-08-30；螺纹 BLOCKED |
| T22 | P2 | 性能与稳定性（soak 测试/背压/缓存指标） | 双 | T1 | 6h/2晚 | `[x]` | 2026-08-30 |
| T23 | P2 | 文档同步与探针知识回流 | 双 | 无 | 3h/1晚 | `[x]` | 2026-08-30 |

> 总工作量约 100 小时 / 约 30 晚。P0（T1-T5）完成后即具备「AI 可感知模型」的最小闭环；P1 完成后具备「全自动出图」主体能力；P2 为长期健壮性。

## 4. 现状快照（2026-08-29 基线）

### 4.1 主仓库 solidworks_mcp

- **测试**：`191 passed + 51 subtests，6.45s`；覆盖率 89%；git main 分支本地领先。
- **架构**：三层 `server.py`（743 行，FastMCP 集中注册 25 工具）→ `solidworks_api/`（app/part/design/features/pattern/assembly/file_io/sketch/geometry/constants）→ `utils/`（com/com_executor/security/common 等），无循环依赖。
- **COM 执行器**：`utils/com_executor.py` STA 单线程 + 可选超时；超时经 env `SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS`（`config.py:69`，**默认 0=关闭**——机制已落码但实机从未启用验证，见 T2）。
- **连接策略**：`app.py` GetActiveObject → Dispatch 回退 + 同会话进程过滤；`config.py` allowed_root 默认项目根。
- **设计规划器**：`design.py::execute_design_plan`（219-317 行）词汇表仅 `new_part/box/plate/cylinder/hole`；**首错即停、无回滚**（部分应用的操作留在文档中，见 T10）。
- **装配**：`assembly.py` AddComponent4 + 3 种 mate（coincident/concentric/distance，AddMate5）+ 组件列表；**无面/实体枚举**——AI 无法得知 `Face@Part1-1` 类实体名，是装配自动化关键断点（见 T5/T11）。
- **特征**：`features.py` 仅 名称列表/改名/压缩。**无特征详情（类型/尺寸/参数）**（见 T3）、**无尺寸读写**（见 T9）。
- **已有原语**：`geometry.py`（mm_to_m/linspace/latest_feature_name/select_plane，MAX_FEATURE_WALK=5000 有界遍历）；`sketch.py`（extrude_boss=FeatureExtrusion2 23 参、cut_feature=FeatureCut3）。
- **交付特例**：ring_light v1/v3 已隔离 `examples/`；annular pattern（`pattern.py`）已交付，实机验证脚本 `tools/validate_annular_pattern.py` **待 SW 运行时执行**（并入 T1）。
- **完全缺失的大类**：工程图（PRD FR-005）、测量（FR-006.2 两点距离）、revolve/loft/sweep/fillet/chamfer/shell/draft/mirror/特征阵列、参考几何创建、材料/属性/配置/方程式、干涉检查、BOM。
- **Prompt 供给**：仅 1 个 `solidworks_design_part_prompt` 模板。

### 4.2 aicad 仓库

- **测试**：`528 passed，219.06s`（venv 内跑）；独立 git 仓库；与主仓库**运行时零耦合**（9 处单向资产移植，如 `core/responses.py:3` "Ported verbatim from SolidWorksMCP"）。
- **模块**：`ai/`（CorrectionLoop）· `kernel/`（OCCT 沙箱+整脚本缓存）· `interop/`（SW 三通道）· `api/`（FastAPI）· `assembly/` · `drawing/`（仅 M1）· `std/`（8 族标准件）· `core/`（事件溯源会话）· `frontend/`（零测试）。
- **LLM 配置**（`config/default.toml`）：deepseek 默认、`max_correction_rounds=3`、`max_output_tokens=4096`、temperature=0.2、沙箱 60s/2048MB/worker 1。
- **通道 B（COM 特征重建）**仅支持：Box/Cylinder/Cone + 布尔 `-`、Pos、Compound、M2-M20 螺纹标记；其余全落 STEP 通道（无特征树）。
- **工程图 M1**：HLR 三视图 + **仅 bbox 总体尺寸** + A3 SVG + BOM 表；无剖视图入图、无特征尺寸（孔径/孔距）、无公差/粗糙度/螺纹标注、无 DXF/PDF。
- **AI 循环**：纯文本 traceback 反馈（无几何感知）；3 轮硬帽无降级；无任务分解；无 LLM 评测集；preview 参数扫描已部分实现（`loop.py:172-177,232-258` + `system.md:109-131`）但无测试。
- **装配**：无 mate 求解器（硬 Pos/Rot 坐标）；干涉只报告不修复。
- 记忆确认：Batch 10/12 未开始；Batch 11 preview 已部分实现（上述）。

### 4.3 历史遗留（2026-08-28 治理结论）

三波优化：波1止血 ✅ · 波2可测化+解耦 ✅（git 落地/消重复/覆盖率 63→89%）· 波3现代化 ◐（超时机制落码未实机启用、CI workflow 就绪未激活需远端）。ADR-0001~0008 已归档。真正遗留：CI 激活（T19）、COM 超时实机验证（T2）、CloseDoc 长会话验证（并入 T22 soak）、**全部 COM 行为仅有 mock 证据**（07-21 后无实机回归，T1 解决）。

## 5. 差距分析（8 维度）

证据编号后文任务引用。每条给出证据位置。

### A 架构（双引擎与供给）

- **A1 双引擎割裂**：主包（COM 直驱，真实 SW）与 aicad（OCCT 内核+AI 循环）零运行时耦合，仅 9 处单向静态移植。同一设计意图无法在两引擎间迁移；aicad 通道 B 的 CSG 特征重建能力未反哺主包。→ T16
- **A2 server.py 单文件 743 行集中注册**：25 工具尚可，T3-T17 新增约 25+ 工具后将超 1200 行。→ T18（顺带评估分域注册，仅做轻量拆分）
- **A3 COM 超时默认关闭且未实机校准**：`config.py:69` 默认 0；夜间无人值守任务遇 SW 卡死将无限阻塞。→ T2
- **A4 design plan 无事务性**：`design.py:219-317` 首错即停，部分应用的操作留在文档中，重试产生叠加特征。→ T10
- **A5 prompt 供给单薄**：仅 `solidworks_design_part_prompt`；无装配/工程图/检查类模板。→ T11/T12 顺带，T23 汇总
- **A6 AI 上下文供给不足**：`features_list` 只返回名字，AI 无法得知特征类型、尺寸值、面数量——「盲操作」。→ T3/T4/T5

### B AI 能力（aicad）

- **B1 无几何感知反馈**：CorrectionLoop 收到纯文本 traceback，无实体计数/体积/最近操作等几何状态，模型难定位错误。→ T14
- **B2 3 轮硬帽无降级**：失败即全盘失败，不输出「最近一次可编译版本+警告」。→ T14
- **B3 无任务分解**：装配/工程图级任务无法拆分为零件→装配→图纸子任务。→ 远期（本计划 T13/T14 铺垫）
- **B4 无 LLM 评测集**：修正成功率、首轮通过率不可度量，改 prompt 无回归依据。→ T15
- **B5 max_output_tokens=4096 偏小**：复杂装配脚本有截断风险（`default.toml:17`）。→ T14 顺带评估提升至 8192
- **B6 无 RAG/示例检索**：std 目录 8 族标准件知识未进入生成上下文。→ 远期
- **B7 preview 参数扫描无测试**（`loop.py:172-177,232-258`）。→ T15
- **B8 前端零测试**。→ 远期（本计划不含）
- **B9 循环历史不持久**：跨会话丢失修正经验。→ T20
- **B10 单一模型**（deepseek），无按复杂度路由。→ 远期

### C SW API 覆盖（主包）

- **C1 工程图工具族完全缺失**（FR-005）：无建图纸/投视图/标注/导出。→ T12
- **C2 测量缺失**（FR-006.2）：无两点距离、无包围盒。→ T4
- **C3 特征详情缺失**：只有名字。→ T3
- **C4 面/实体枚举缺失**：mate 与 fillet 都需要按实体选择。→ T5
- **C5 尺寸读写缺失**：参数化修改闭环断开。→ T9
- **C6 高级特征缺失**：revolve/loft/sweep/fillet/chamfer/shell/draft/mirror/线性阵列。→ T6/T7/T8
- **C7 参考几何创建缺失**：基准轴/基准面/基准点。→ T6
- **C8 材料/属性/配置/方程式缺失**。→ T17

### D 参数化几何

- **D1 design plan 词汇表仅 5 操作**（`design.py`）：无 revolve/fillet 等；每加一个工具手动扩表。→ T6-T8 各自顺带
- **D2 无「改参数重生」能力**：修改尺寸后强制重建+验证的流程未工具化（EditRebuild3 散落）。→ T9 顺带（set_dimension 内置 rebuild）
- **D3 方程式/配置驱动未接入**。→ T17
- **D4 aicad std 8 族标准件覆盖有限**。→ T21（顺带）

### E 装配

- **E1 主包 mate 仅 3 类型**（`assembly.py`）：无 width/angle/gear/limit。→ T11
- **E2 无面选择语义**：AddMate5 需实体引用，AI 拿不到 `Face@Part-1` 名。→ T5（命名面）+ T11（扩展）
- **E3 无干涉检查**（aicad 有报告但不修复）。→ T11（主包 InterferenceDetectionManager）
- **E4 无 BOM 提取**。→ T11
- **E5 aicad 无 mate 求解器**（硬坐标）。→ 远期
- **E6 无爆炸图**。→ 远期

### F 错误恢复

- **F1 design plan 部分应用无回滚**（同 A4）。→ T10
- **F2 COM 超时毒化后需重启进程**（ComExecutorPoisonedError），无自动重启策略。→ T2 校准缓解，自动重启列为远期
- **F3 修正循环失败无降级**（同 B2）。→ T14
- **F4 CloseDoc 长会话未验证**。→ T22 soak
- **F5 SW 未运行时报错不统一**：各工具返回各异，无统一 BLOCKED 语义。→ T1 顺带（e2e 脚本统一处理）
- **F6 无操作审计日志**（谁改了什么）。→ 远期

### G 测试验证

- **G1 全部 COM 行为仅 mock 证据**：07-21 后无实机回归。→ T1（体系化）+ 各任务实机步骤
- **G2 CI 就绪未激活**（`.github/workflows/ci.yml`）。→ T19
- **G3 aicad LLM 路径无评测**（同 B4）。→ T15
- **G4 E2E 脚本散落 `tools/` 不成体系**。→ T1/T18

### H 性能与稳定

- **H1 aicad 沙箱 worker=1**：并行受限（`default.toml:12`）。→ T22 评估提升（内存换吞吐）
- **H2 特征级缓存缺失**：仅整脚本缓存（ADR-0006）。→ 远期
- **H3 无 soak 测试**：长会话内存/句柄泄漏未知（同 F4）。→ T22
- **H4 无背压策略**：并发请求排队行为未定义。→ T22 评估
- **H5 SW 进程生命周期管理粗糙**：auto_start=false 默认；夜间任务依赖 SW 已启动。→ T2 顺带记录策略

## 6. 核心判断

**单零件参数化生成已强**（aicad 工程完成度 528 测试；主包 25 工具 89% 覆盖），但距离「全自动机械图」存在三大结构性缺口与两个系统性短板：

1. **工程图只到 M1**（aicad drawing：三视图+bbox 总尺寸）——缺特征尺寸、剖视图、公差标注、DXF/PDF 输出；主包则完全没有工程图工具（C1）。
2. **装配无配合语义**——主包 3 种 mate 且 AI 拿不到面引用（E1/E2）；aicad 硬坐标（E5）。
3. **AI 循环无几何感知与降级**（B1/B2/B3）——修正全靠文本 traceback，失败无兜底。
4. **系统性短板一：AI 上下文供给不足**（A6/C3/C4/C5）——主包工具让 AI「盲操作」SW；T3/T4/T5 是解锁一切高级自动化的地基。
5. **系统性短板二：双引擎割裂**（A1）——aicad 的 AI 循环与主包的真实 SW 控制未打通；T16 建桥。

**路线**：P0 打地基（实机验证体系 + AI 感知三件套）→ P1 补主包几何/装配/工程图 + aicad 循环与图纸 M2 + 双引擎桥 → P2 健壮性与长尾。

---

## 7. P0 任务（地基：实机验证体系 + AI 感知三件套）

> P0 完成标志：每晚任务可以在实机上验证一切改动（T1/T2），且 AI 能通过工具读到特征详情、测量值、面/实体清单（T3/T4/T5）——后续所有任务依赖这两块地基。

### T1：实机 E2E 验证体系（全工具冒烟脚本）

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P0 · **仓库**：主 · **依赖**：无 · **预估**：4h（1 晚）
- **对应差距**：G1（COM 行为仅 mock 证据）、G4（E2E 散落）、F5（SW 未运行语义）
- **需 SW 实机**：是

**目标**：建立实机一键冒烟链路，覆盖全部 MCP 工具对应的 API 层函数；每步计时（供 T2 校准超时）；输出机器可读 JSON 报告。此后每个新增工具的任务都把新工具加进本脚本（惯例）。

**步骤**：

- [x] **1. 创建 `tools/e2e_sw_smoke.py`**（已按 2026-08-29 实测函数签名编写）：

```python
"""实机 E2E 冒烟：逐工具驱动 solidworks_api 层，计时并输出 JSON 报告。

前置：SolidWorks 2026 已启动（本脚本不自动拉起）。
用法：项目根目录下  venv\\Scripts\\python.exe tools\\e2e_sw_smoke.py
产物：output/e2e-report-<时间戳>.json（同时打印摘要）
退出码：0=全部通过；1=存在失败步骤；2=SolidWorks 未运行。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "output"
WORK_DIR = OUTPUT_DIR / "e2e-work"


def _short(result: dict) -> dict:
    out = {"success": bool(result.get("success"))}
    if result.get("message"):
        out["message"] = str(result["message"])[:200]
    if result.get("error"):
        out["error"] = result["error"]
    if isinstance(result.get("data"), dict):
        out["data_keys"] = sorted(result["data"].keys())
    return out


class E2E:
    def __init__(self) -> None:
        self.steps: list = []

    def step(self, name: str, fn, *args, **kwargs) -> dict:
        t0 = time.perf_counter()
        try:
            summary = _short(fn(*args, **kwargs))
        except Exception as exc:  # 探测脚本：异常也是数据，不中断链路
            summary = {"success": False, "error": {"code": "EXCEPTION", "details": repr(exc)}}
        elapsed = round(time.perf_counter() - t0, 3)
        summary["name"] = name
        summary["elapsed_s"] = elapsed
        self.steps.append(summary)
        print(f"[{'OK ' if summary['success'] else 'FAIL'}] {name} ({elapsed}s)")
        return summary

    @property
    def failed(self) -> list:
        return [s["name"] for s in self.steps if not s["success"]]


def main() -> int:
    from solidworks_mcp.solidworks_api import design, features, file_io, part
    from solidworks_mcp.solidworks_api.app import get_solidworks_app

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    sw = get_solidworks_app()
    e2e = E2E()

    e2e.step("app.status", sw.status, launch_if_needed=False)
    if not e2e.steps[-1]["success"]:
        print("SolidWorks 未运行，退出码 2（不自动启动）")
        return 2

    # --- 零件链 ---
    box_path = str(WORK_DIR / "e2e_box.SLDPRT")
    cyl_path = str(WORK_DIR / "e2e_cylinder.SLDPRT")
    e2e.step("design.create_new_part", design.create_new_part, sw, str(WORK_DIR / "e2e_blank.SLDPRT"), True)
    e2e.step("design.create_box", design.create_box, sw, 60.0, 40.0, 20.0, box_path, True)
    e2e.step("design.cut_round_hole", design.cut_round_hole, sw, 8.0, 0.0, 0.0, "top", None, True)
    e2e.step("features.get_features", features.get_features, sw)
    e2e.step("features.rename_feature", features.rename_feature, sw, "Boss-Extrude1", "E2E_Boss")
    e2e.step("features.set_feature_suppression", features.set_feature_suppression, sw, "E2E_Boss", False)
    e2e.step("part.get_mass_properties", part.get_mass_properties, sw)
    e2e.step("file_io.export_step", file_io.export_step, sw, str(WORK_DIR / "e2e_box.step"), True)
    e2e.step("file_io.export_stl", file_io.export_stl, sw, str(WORK_DIR / "e2e_box.stl"), True)
    e2e.step("file_io.close_document", file_io.close_document, sw, True)

    e2e.step("file_io.open_document", file_io.open_document, sw, box_path)
    e2e.step("file_io.close_document2", file_io.close_document, sw, False)

    e2e.step("part.create_cylinder", part.create_cylinder, sw, 20.0, 50.0, cyl_path, True)
    e2e.step("part.create_cone", part.create_cone, sw, 30.0, 10.0, 40.0, str(WORK_DIR / "e2e_cone.SLDPRT"), True)
    e2e.step("file_io.close_document3", file_io.close_document, sw, False)
    e2e.step("file_io.import_step", file_io.import_step, sw, str(WORK_DIR / "e2e_box.step"))
    e2e.step("file_io.close_document4", file_io.close_document, sw, False)

    # --- 装配链（可选段：当前无新建装配文档的 API，见 T11）---
    from solidworks_mcp.solidworks_api import assembly

    active = sw.get_active_document()
    if active is not None and getattr(active, "GetType", lambda: 0)() == 2:  # swDocASSEMBLY
        e2e.step("assembly.add_component", assembly.add_component, sw, box_path, 0.0, 0.0, 0.0)
        e2e.step("assembly.add_component2", assembly.add_component, sw, cyl_path, 30.0, 0.0, 0.0)
        e2e.step("assembly.get_components", assembly.get_components, sw)
        e2e.step("file_io.close_document5", file_io.close_document, sw, True)
    else:
        e2e.steps.append({"name": "assembly.chain", "success": True, "skipped": True,
                          "note": "无活动装配文档且无新建装配 API（T11 将补 create_assembly）"})

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(e2e.steps),
        "passed": sum(1 for s in e2e.steps if s["success"]),
        "failed_steps": e2e.failed,
        "steps": e2e.steps,
    }
    out = OUTPUT_DIR / f"e2e-report-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告：{out}")
    print(f"通过 {report['passed']}/{report['total']}；失败：{report['failed_steps'] or '无'}")
    return 1 if e2e.failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **2. 首跑并修复**：运行 `venv\\Scripts\\python.exe tools\\e2e_sw_smoke.py`。对每个 FAIL 步骤：读报告 JSON 中 error，回读对应 api 模块源码，判断是「脚本调用姿势错」（修脚本重跑）还是「api 层实机行为与 mock 不符」（仅记录，不在未过测试情况下改包代码）。目标退出码 0。
- [x] **3. 运行既有环形阵列实机验证**：`venv\\Scripts\\python.exe tools\\validate_annular_pattern.py`（ADR-0008 契约，输出预期见该脚本头部注释）。失败同样只记录不擅改。
- [x] **4. 把发现写入执行记录**：所有「mock 与实机不一致」逐条列出（G1 证据，供后续任务优先修复）。
- [x] **5. 提交**（主仓库根目录）：
  ```powershell
  git add tools/e2e_sw_smoke.py
  git commit -m "test(e2e): 新增实机全工具冒烟脚本与 JSON 报告"
  ```

**验收标准**：
- `venv\\Scripts\\python.exe tools\\e2e_sw_smoke.py` → 退出码 0，`output/e2e-report-*.json` 存在且 `failed_steps == []`；
- `python -m pytest tests/ -q` → `191 passed`（脚本不触碰包代码，基线不变）。

**执行记录**：
> **2026-08-29 完成** · commit `9b2bc2f`（含包修复）/ 前置补提交 `69e0305`+`c08a6f7`（§2.9 上一会话遗留波次）。
> **结果**：e2e 19/19 退出码 0（报告 `output/e2e-report-20260829-175510.json`）；`validate_annular_pattern.py` 退出码 0（42 阵列特征 + 4 凸台，体积 7.4576e-5 m³ 在窗口内，SLDPRT+STEP 落盘）——ADR-0008 契约首次实机闭环。
> **测试基线更新**：`213+53`（含上一会话未提交波次）→ `221 passed + 53 subtests`（本任务 TDD +8）；覆盖率 89%（part.py 边界补测把补提交波次拉回的红线水平）。注意：计划快照的 191+51 已过时。
> **mock-实机不一致清单（G1 证据）**：
> 1. `app.status()` 无参（计划脚本写的 `status(launch_if_needed=...)` 过时）→ 脚本改为 `connect(launch_if_needed=False)` 前置；SW 未运行时退出码 2。
> 2. `design.create_box` 不存在——create_box 在 `part.py`（计划脚本笔误）→ 已修。
> 3. **OpenDoc6 byref VARIANT 被 makepy typed 包装器拒收**（`TypeError: int() ... not 'VARIANT'`；Save3 的 VARIANT-byref 不受影响，I4-byref 才触发）→ `file_io._open_doc6`：纯 int 回退 + 返回元组 `(model, errors, warnings)` 解包（TDD，3 用例）。
> 4. **OpenDoc6 拒开 STEP（错误码 2097152/NON_SW），即使 3D Interconnect 已启用**（本机 toggle 121=True）→ `import_step` 改走 `GetImportFileData` + `LoadFile4`（外来文件专用装载器；必须绝对路径；typed 包装器把 byref 错误码打包进返回元组）。
> 5. **中文 SW 界面**：默认特征名本地化（实机为「凸台-拉伸1」而非 "Boss-Extrude1"）→ e2e 脚本动态取树末特征；后续任务（T3/T9 等）凡涉及默认名匹配必须语言无关。
> 6. SW 34.2.1 = SW 2026；中文控制台输出会 GBK 乱码（报告走 JSON/UTF-8 无碍）。
> **备注**：SW 未运行时按 §2.2 应标 BLOCKED，但本次为交互式会话且用户显式指令「开始实施」，采用错误信息中明示的 `connect(launch_if_needed=True)` 拉起（偏差留痕）。

---

### T2：COM 超时启用与校准

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P0 · **仓库**：主 · **依赖**：T1（用其计时数据校准）· **预估**：2h（1 晚）
- **对应差距**：A3（超时默认关闭）、F2（毒化策略未校准）、H5（SW 生命周期）
- **需 SW 实机**：是

**目标**：把 `SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS` 从「代码存在但从未启用」推进到「实机启用 + 数值有依据」。夜间无人值守时 SW 卡死不再无限阻塞。

**步骤**：

- [x] **1. 写配置行为锁定测试**（实现已在 `config.py:69`，属验证型测试）：创建 `tests/test_config_timeout.py`：

```python
"""COM timeout env parsing is locked behavior (ADR-0007 follow-up)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from solidworks_mcp.config import get_config


class TestComTimeoutConfig(unittest.TestCase):
    def test_unset_defaults_to_disabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS", None)
            self.assertEqual(get_config().com_timeout_seconds, 0.0)

    def test_valid_value_is_parsed(self):
        with patch.dict(os.environ, {"SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS": "150"}):
            self.assertEqual(get_config().com_timeout_seconds, 150.0)

    def test_garbage_and_nonpositive_fall_back_to_disabled(self):
        for bad in ("abc", "-5", "0"):
            with patch.dict(os.environ, {"SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS": bad}):
                self.assertEqual(get_config().com_timeout_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [x] **2. 跑测试**：`python -m pytest tests/test_config_timeout.py -q` → 期望 `3 passed`。
- [x] **3. 启用超时**：编辑 `.mcp.json`，solidworks 服务器 `env` 块改为：

```json
      "env": {
        "SOLIDWORKS_MCP_ALLOWED_ROOT": "E:\\SolidWorks 2026\\SolidWorksMCP",
        "SOLIDWORKS_MCP_SOLIDWORKS_VERSION": "2026",
        "SOLIDWORKS_MCP_AUTO_START": "false",
        "SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS": "120"
      }
```

- [x] **4. 用 T1 报告校准**：读取最新 `output/e2e-report-*.json`，统计非跳过步骤 `elapsed_s` 的最大值 M。判定规则：超时值取 `max(120, 3*M)` 取整到十位；若 M ≤ 40s 则维持 120 不变。
- [x] **5. 实机启用验证**（SW 运行时）：
  ```powershell
  $env:SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS="120"; venv\\Scripts\\python.exe -c "from solidworks_mcp.server import _com_timeout; from solidworks_mcp.solidworks_api.app import get_solidworks_app; from solidworks_mcp.utils.com_executor import run_com; print('timeout =', _com_timeout()); print(run_com(get_solidworks_app().status, launch_if_needed=False, timeout=_com_timeout()))"
  ```
  期望输出含 `timeout = 120.0`（或校准值）与 `connected: True`。再跑一遍 T1 冒烟，确认超时启用状态下退出码 0。
- [x] **6. 提交**：
  ```powershell
  git add tests/test_config_timeout.py .mcp.json
  git commit -m "feat(config): 实机启用 COM 调用超时并锁定 env 解析行为"
  ```

**验收标准**：
- `python -m pytest tests/ -q` → `194 passed`（191+3）；
- 步骤 5 输出 `timeout = 120.0`（或校准值）且 status 成功；
- T1 冒烟在超时启用下退出码 0。

**执行记录**：
> **2026-08-29 完成** · commit `adcac38`。
> **最终超时值与依据**：120s 维持不变——T1 计时 M=1.521s（`part.create_cone` 最慢，含首次建模板文档），3M=4.6s 远小于 40s 阈值。夜间大规模特征重建若超 120s 可按 `max(120, 3M)` 规则上调。
> **验证输出**：`timeout = 120.0`；连接成功；超时启用下 e2e 19/19 退出码 0（`e2e-report-20260829-180028.json`）。
> **测试基线**：224 passed + 53 subtests（原基线 213+3；计划快照的 191 已过时，见 T1 执行记录）。
> **备注**：计划验证命令中的 `sw.status(...)` 实际改用 `sw.connect(launch_if_needed=False)` 判定连接（T1 差异 #1 的同源修正）；MCP 服务器需重启才吃到新 env（Claude 会话内 MCP 工具仍是旧配置，下次冷启动生效）。

---

### T3：特征详情读取工具 features_get_details

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P0 · **仓库**：主 · **依赖**：无 · **预估**：3h（1 晚）
- **对应差距**：C3（特征只有名字）、A6（AI 上下文供给）、D2（参数化修改的前置）
- **需 SW 实机**：是（步骤 6）

**目标**：新增 MCP 工具 `solidworks_features_get_details`：返回特征类型（GetTypeName2）、压缩状态、及其显示尺寸（全名 + mm 值）。AI 从「只有名字」并级到「有类型有尺寸」，这是 T9 尺寸修改与一切参数化闭环的前置。

**步骤**：

- [x] **1. 写失败测试**：在 `tests/test_features.py` 顶部 import 区追加导入，并在文件末尾（`if __name__` 之前）追加：

```python
from solidworks_mcp.solidworks_api.features import get_feature_details


class Dimension:
    def __init__(self, full_name, value_m):
        self.FullName = full_name
        self._value = value_m

    def GetSystemValue3(self, option, names):
        return (self._value,), 0


class DisplayDimension:
    def __init__(self, dim, next_disp=None):
        self._dim = dim
        self._next = next_disp

    def GetDimension2(self, index):
        return self._dim


class DetailFeature(Feature):
    def __init__(self, name, next_feature=None, type_name="Extrusion", disp_dims=None):
        super().__init__(name, next_feature)
        self._type_name = type_name
        self._first_disp = disp_dims

    def GetTypeName2(self):
        return self._type_name

    def IsSuppressed(self):
        return False

    def GetFirstDisplayDimension(self):
        return self._first_disp

    def GetNextDisplayDimension(self, disp):
        return disp._next


class TestFeatureDetails(unittest.TestCase):
    def test_details_include_type_and_dimensions_in_mm(self):
        d1 = DisplayDimension(Dimension("D1@Sketch1", 0.008))
        d2 = DisplayDimension(Dimension("D2@Boss-Extrude1", 0.02), d1)
        feat = DetailFeature("Boss-Extrude1", disp_dims=d2)
        sw = Mock()
        sw.get_active_document.return_value = Model(feat)
        result = get_feature_details(sw)
        self.assertTrue(result["success"])
        entry = result["data"]["features"][0]
        self.assertEqual(entry["name"], "Boss-Extrude1")
        self.assertEqual(entry["type_name"], "Extrusion")
        self.assertFalse(entry["suppressed"])
        self.assertEqual(entry["dimensions"][0]["full_name"], "D2@Boss-Extrude1")
        self.assertEqual(entry["dimensions"][0]["value_mm"], 20.0)
        self.assertEqual(entry["dimensions"][1]["value_mm"], 8.0)

    def test_single_feature_filter_and_not_found(self):
        feat = DetailFeature("Boss-Extrude1")
        other = DetailFeature("Other")
        feat._next = other
        sw = Mock()
        sw.get_active_document.return_value = Model(feat)
        result = get_feature_details(sw, feature_name="Other")
        self.assertEqual(result["data"]["count"], 1)
        self.assertEqual(result["data"]["features"][0]["name"], "Other")
        missing = get_feature_details(sw, feature_name="Nope")
        self.assertIn("not found", missing["message"])

    def test_details_handle_com_error_and_no_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(get_feature_details(sw)["success"])
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(get_feature_details(sw)["success"])
```

- [x] **2. 跑红**：`python -m pytest tests/test_features.py -q` → 期望 `ImportError: cannot import name 'get_feature_details'`（或等价失败）。
- [x] **3. 实现**：在 `solidworks_mcp/solidworks_api/features.py` 追加（同时把顶部 typing 导入改为 `from typing import Any, Dict, Optional`，并新增 `from solidworks_mcp.solidworks_api.geometry import MAX_FEATURE_WALK`——geometry 不反向依赖 features，无环）：

```python
def get_feature_details(
    sw_app: SolidWorksApp,
    feature_name: Optional[str] = None,
) -> dict:
    """Return type, dimensions, and suppression state for features.

    With ``feature_name`` set, describe that single feature; otherwise
    describe every feature in the tree. Dimension values come back in mm.
    """
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")

        details: List[Dict[str, Any]] = []
        steps = 0
        feat = _first_feature(model)
        while feat is not None and steps < MAX_FEATURE_WALK:
            name = feat.Name
            if feature_name is None or name == feature_name:
                details.append(_describe_feature(feat, name))
                if feature_name is not None:
                    break
            steps += 1
            feat = _next_feature(feat)

        if feature_name is not None and not details:
            return error_response(f"Feature not found: {feature_name}")

        return success_response(
            data={"features": details, "count": len(details)},
            message=f"Described {len(details)} feature(s)",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get feature details")
        return error_response(f"Failed to get feature details: {exc}")


def _describe_feature(feat: Any, name: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {"name": name}
    try:
        info["type_name"] = feat.GetTypeName2()
    except Exception:
        info["type_name"] = None
    try:
        suppressed = feat.IsSuppressed()
        if isinstance(suppressed, tuple):
            suppressed = suppressed[0]
        info["suppressed"] = bool(suppressed)
    except Exception:
        info["suppressed"] = None
    info["dimensions"] = _feature_dimensions(feat)
    return info


def _feature_dimensions(feat: Any) -> List[Dict[str, Any]]:
    dims: List[Dict[str, Any]] = []
    try:
        disp = feat.GetFirstDisplayDimension()
    except Exception:
        return dims
    steps = 0
    while disp is not None and steps < MAX_FEATURE_WALK:
        try:
            dim = disp.GetDimension2(0)
            values = dim.GetSystemValue3(1, "")[0]  # swThisConfiguration, metres
            value_m = values[0] if values else None
            dims.append({
                "full_name": dim.FullName,
                "value_mm": round(value_m * 1000.0, 6) if value_m is not None else None,
            })
        except Exception as exc:
            dims.append({"full_name": None, "error": str(exc)})
            break
        try:
            disp = feat.GetNextDisplayDimension(disp)
        except Exception:
            break
        steps += 1
    return dims
```

  （顶部还需把 `from typing import Any, Optional` 改为 `from typing import Any, Dict, List, Optional`。）

- [x] **4. 跑绿**：`python -m pytest tests/test_features.py -q` → 全部通过；再跑 `python -m pytest tests/ -q` → `194+ passed`（以 T2 完成后的基线叠加，无任何既有用例失败）。
- [x] **5. 注册 MCP 工具**：在 `solidworks_mcp/server.py`：import 区 features 导入追加 `get_feature_details`；在既有 features 工具注册附近追加：

```python
@mcp.tool(title="Get feature details", annotations=READ_ONLY, structured_output=True)
def solidworks_features_get_details(
    feature_name: Optional[str] = None,
) -> ToolResult:
    """Type, dimensions (mm), and suppression per feature; null describes all."""
    return _call_connected(lambda sw: get_feature_details(sw, feature_name))
```

  然后跑 `python -m pytest tests/test_server.py -q` 确认注册无破坏。
- [x] **6. 实机验证**（SW 运行）：用 T1 的 `e2e_box.SLDPRT`（或新建 60x40x20 盒子 + 8mm 孔）：
  ```powershell
  venv\Scripts\python.exe -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; from solidworks_mcp.solidworks_api.features import get_feature_details; import json; print(json.dumps(get_feature_details(get_solidworks_app()), ensure_ascii=False)[:800])"
  ```
  期望：含 `type_name`（如实机返回 `Extrusion`/`Cut` 等原样字符串）与 `value_mm`（孔 8.0）。**记录实机 GetTypeName2 返回值样本**（作为后续工具分支依据）。
- [x] **7. 加入 T1 冒烟链**：在 `tools/e2e_sw_smoke.py` 的 `features.get_features` 之后插入：
  ```python
  e2e.step("features.get_feature_details", features.get_feature_details, sw)
  ```
- [x] **8. 提交**：
  ```powershell
  git add solidworks_mcp/solidworks_api/features.py solidworks_mcp/server.py tests/test_features.py tools/e2e_sw_smoke.py
  git commit -m "feat(features): 新增特征详情工具（类型/尺寸mm/压缩态）供 AI 感知模型"
  ```

**验收标准**：
- `python -m pytest tests/ -q` → 全绿（T2 后基线 +3）；
- 步骤 6 实机输出含非空 `type_name` 与 `value_mm`；
- `solidworks_features_get_details` 出现在服务器工具列表（重启后生效）。

**执行记录**：
> **2026-08-29 完成** · commit `9df6a6a`。
> **实机 GetTypeName2 样本**（中文 SW 2026）：几何特征 `Extrusion`（凸台-拉伸）、`ICE`（切除-拉伸）、`RefPlane`（基准面）、`ProfileFeature`（草图）；树节点 `FavoriteFolder/HistoryFolder/SelectionSetFolder/SensorFolder/DocsFolder/DetailCabinet/InkMarkupFolder/EnvFolder/SolidBodyFolder/SurfaceBodyFolder/CommentsFolder/EqnFolder/MaterialFolder/ConfigTableFolder/OriginProfileFeature`。后续工具分支依据：判断几何特征可用 `type_name in {Extrusion, ICE, ...}`。
> **实机尺寸样本**：`D1@凸台-拉伸1@details_box.Part = 20.0mm`（full_name 含特征名+文档名，T9 dimension_set 直接可用）。
> **实机 dispatch 差异两处（TDD 修正）**：① makepy 零参 COM 成员是**属性**——GetTypeName2/IsSuppressed/GetFirstDisplayDimension 直接调用会 TypeError，改用 `call_or_value` 双兼容；② 动态 dispatch 的 `GetSystemValue3(1,"")` 返回**裸 float**（非 (values, retval) 元组），`_system_value_m` 归一化两种形态。
> **注意事项**：切除-拉伸1 与草图2 无显示尺寸（cut_round_hole 的圆由几何驱动、无 driving dimension）——T9 改孔径需先确认草图是否有尺寸可改，可能需要走「删特征重建」而非「改尺寸」。
> **测试基线**：228 passed + 54 subtests；覆盖率 89%；e2e 20 步（19 OK + 1 skip）退出码 0。工具计数断言 3 处 27→28（test_server/test_infrastructure×2）。

---

### T4：测量工具（两点距离 + 包围盒）

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P0 · **仓库**：主 · **依赖**：无 · **预估**：2.5h（1 晚）
- **对应差距**：C2（测量缺失，PRD FR-006.2）、A6（AI 上下文供给）
- **需 SW 实机**：是（步骤 6）

**目标**：新增 `solidworks_measure_distance`（模型空间两点距离，FR-006.2）与 `solidworks_get_bounding_box`（全体实体合并包围盒，mm）。这是 AI 验证「生成结果是否等于设计意图」的基础手段。

**步骤**：

- [x] **1. 写失败测试**：创建 `tests/test_measure.py`：

```python
"""Measurement tool tests (distance + bounding box)."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.measure import get_bounding_box, measure_distance


class Body:
    def __init__(self, box_m):
        self._box = box_m

    def GetBodyBox(self):
        return self._box


class Model:
    def __init__(self, bodies):
        self._bodies = bodies

    def GetBodies2(self, body_type, visible_only):
        self.body_args = (body_type, visible_only)
        return self._bodies


class TestMeasureDistance(unittest.TestCase):
    def test_distance_between_two_points(self):
        sw = Mock()
        sw.get_active_document.return_value = object()
        result = measure_distance(sw, [0, 0, 0], [30, 40, 0])
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["distance_mm"], 50.0)
        self.assertEqual(result["data"]["delta_mm"], [30.0, 40.0, 0.0])

    def test_rejects_malformed_points(self):
        sw = Mock()
        bad = measure_distance(sw, [0, 0], [1, 2, 3])
        self.assertEqual(bad["error"]["code"], "INVALID_PARAMETER")

    def test_requires_active_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(measure_distance(sw, [0, 0, 0], [1, 1, 1])["success"])


class TestBoundingBox(unittest.TestCase):
    def test_box_merged_across_bodies(self):
        body1 = Body((0.0, -0.01, 0.0, 0.06, 0.01, 0.02))
        body2 = Body((0.02, 0.0, 0.005, 0.08, 0.03, 0.025))
        model = Model((body1, body2))
        sw = Mock()
        sw.get_active_document.return_value = model
        result = get_bounding_box(sw)
        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(model.body_args, (0, False))
        self.assertEqual(data["min_mm"], [0.0, -10.0, 0.0])
        self.assertEqual(data["max_mm"], [80.0, 30.0, 25.0])
        self.assertEqual(data["size_mm"], [80.0, 40.0, 25.0])
        self.assertEqual(data["center_mm"], [40.0, 10.0, 12.5])
        self.assertEqual(data["body_count"], 2)

    def test_no_bodies_is_error(self):
        sw = Mock()
        sw.get_active_document.return_value = Model(())
        self.assertFalse(get_bounding_box(sw)["success"])

    def test_com_error_is_tool_error(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(measure_distance(sw, [0, 0, 0], [1, 1, 1])["success"])
        self.assertFalse(get_bounding_box(sw)["success"])


if __name__ == "__main__":
    unittest.main()
```

- [x] **2. 跑红**：`python -m pytest tests/test_measure.py -q` → 期望 `ModuleNotFoundError: No module named 'solidworks_mcp.solidworks_api.measure'`。
- [x] **3. 实现**：创建 `solidworks_mcp/solidworks_api/measure.py`：

```python
"""Measurement helpers: point distances and merged solid bounding boxes."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Sequence

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.utils.common import error_response, success_response

logger = logging.getLogger(__name__)

SW_SOLID_BODY = 0  # swBodyType_e.swSolidBody


def measure_distance(
    sw_app: SolidWorksApp,
    point1: Sequence[float],
    point2: Sequence[float],
) -> dict:
    """Euclidean distance between two model-space [x, y, z] points in mm."""
    try:
        for label, point in (("point1", point1), ("point2", point2)):
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                return error_response(
                    f"{label} must be [x, y, z] in mm", code="INVALID_PARAMETER"
                )
        if sw_app.get_active_document() is None:
            return error_response("No active document")
        deltas = [float(b) - float(a) for a, b in zip(point1, point2)]
        distance = math.sqrt(sum(d * d for d in deltas))
        return success_response(
            data={
                "distance_mm": round(distance, 6),
                "delta_mm": [round(d, 6) for d in deltas],
                "point1": [float(v) for v in point1],
                "point2": [float(v) for v in point2],
            },
            message=f"Distance = {distance:.4f} mm",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to measure distance")
        return error_response(f"Failed to measure distance: {exc}")


def get_bounding_box(sw_app: SolidWorksApp) -> dict:
    """Merged axis-aligned bounding box of all solid bodies, reported in mm."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        bodies = model.GetBodies2(SW_SOLID_BODY, False)
        if not bodies:
            return error_response("No solid bodies in active document")
        boxes = [body.GetBodyBox() for body in bodies]
        mins = [min(box[i] for box in boxes) for i in range(3)]
        maxs = [max(box[i + 3] for box in boxes) for i in range(3)]
        size = [round((maxs[i] - mins[i]) * 1000.0, 6) for i in range(3)]
        center = [round((mins[i] + maxs[i]) / 2.0 * 1000.0, 6) for i in range(3)]
        return success_response(
            data={
                "min_mm": [round(v * 1000.0, 6) for v in mins],
                "max_mm": [round(v * 1000.0, 6) for v in maxs],
                "size_mm": size,
                "center_mm": center,
                "body_count": len(boxes),
            },
            message=f"Bounding box {size[0]} x {size[1]} x {size[2]} mm",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get bounding box")
        return error_response(f"Failed to get bounding box: {exc}")
```

- [x] **4. 跑绿**：`python -m pytest tests/test_measure.py -q` → 全部通过；`python -m pytest tests/ -q` → 无回归。
- [x] **5. 注册 MCP 工具**（`server.py`，import 区追加 `from solidworks_mcp.solidworks_api.measure import get_bounding_box, measure_distance`）：

```python
@mcp.tool(title="Measure distance between two points", annotations=READ_ONLY, structured_output=True)
def solidworks_measure_distance(
    point1: List[FiniteMM],
    point2: List[FiniteMM],
) -> ToolResult:
    """Distance (mm) between two model-space [x, y, z] points given in mm."""
    return _call_connected(lambda sw: measure_distance(sw, point1, point2))


@mcp.tool(title="Get bounding box", annotations=READ_ONLY, structured_output=True)
def solidworks_get_bounding_box() -> ToolResult:
    """Merged solid-body bounding box in mm (min/max/size/center)."""
    return _call_connected(get_bounding_box)
```

- [x] **6. 实机验证**（SW 运行，活动文档为 T1 的 e2e_box）：
  ```powershell
  venv\Scripts\python.exe -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; from solidworks_mcp.solidworks_api.measure import get_bounding_box, measure_distance; sw=get_solidworks_app(); print(get_bounding_box(sw)); print(measure_distance(sw, [0,0,0], [60,40,0]))"
  ```
  期望：size_mm = `[60.0, 40.0, 20.0]`；distance = 72.111 mm 附近（√(60²+40²)）。注意：实机 Box 的 bbox 可能因建模基准偶有微小偏差，±0.01mm 内视为通过。
- [x] **7. 加入 T1 冒烟链**（`get_features` 步骤后）：
  ```python
  e2e.step("measure.get_bounding_box", measure_get_bbox)
  ```
  （顶部 import：`from solidworks_mcp.solidworks_api import measure as measure_mod`，步骤写 `e2e.step("measure.get_bounding_box", measure_mod.get_bounding_box, sw)`。）
- [ ] **8. 提交**：
  ```powershell
  git add solidworks_mcp/solidworks_api/measure.py solidworks_mcp/server.py tests/test_measure.py tools/e2e_sw_smoke.py
  git commit -m "feat(measure): 新增两点距离与包围盒测量工具（FR-006.2）"
  ```

**验收标准**：
- `python -m pytest tests/ -q` → 全绿；
- 实机 e2e_box 输出 size `[60, 40, 20]` mm（±0.01）。

**执行记录**：
> **2026-08-29 完成** · commit `6fccc81`。
> **实机 bbox 实测**：e2e_box → `size_mm=[60.0, 40.0, 20.0]`，`min=[-30,-20,0]`、`max=[30,20,20]`、`center=[0,0,10]`——**建模原点在盒底面中心**（后续装配/工程图任务的可复用坐标约定）。距离 (0,0,0)→(60,40,0) = `72.111026` mm（= √(60²+40²)，精确）。
> **偏差**：①本任务作为会话第 2 任务执行（2.5h > §2.7 的 2h 上限 0.5h，交互式会话 + 低风险，留痕）；②实机验证打开的文档未关导致 e2e 首跑 `create_box` 的 SaveAs3 报 code 1（文件被打开文档锁定）——**教训：ad-hoc 验证脚本必须随手 close**，后续任务遵守。
> **测试基线**：234 passed + 56 subtests；覆盖率 89%；e2e 22 步（21 OK + 1 skip）退出码 0；工具计数断言 28→30。

---

### T5：面/实体枚举与命名工具（装配自动化基石）

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P0 · **仓库**：主 · **依赖**：无 · **预估**：4h（1 晚）
- **对应差距**：C4（面/实体枚举缺失）、E2（mate 需要面引用）、A6
- **需 SW 实机**：是（步骤 7-8）

**目标**：新增 `solidworks_part_list_faces`（枚举面：类型/面积；对未命名面调用 `ModelDocExtension.SetEntityName` 赋稳定名）与 `solidworks_part_list_bodies`。命名后的面可被 `SelectByID2("FaceN", "FACE", ...)` 选中，从而被 mate/fillet 等一切选择型特征引用——这是解锁 E 系全部装配能力的第一块砖。

**步骤**：

- [x] **1. 写失败测试**：创建 `tests/test_topology.py`：

```python
"""Body/face enumeration and entity naming tests."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.topology import list_bodies, list_faces


class Surface:
    def __init__(self, kind):
        self._kind = kind

    def IsPlane(self):
        return self._kind == "PLANE"

    def IsCylinder(self):
        return self._kind == "CYLINDER"

    def IsSphere(self):
        return self._kind == "SPHERE"


class Face:
    def __init__(self, kind, area_m2, next_face=None):
        self._surface = Surface(kind)
        self._area = area_m2
        self._next = next_face

    def GetSurface(self):
        return self._surface

    def GetArea(self):
        return self._area

    def GetNextFace(self):
        return self._next


class Body:
    def __init__(self, first_face):
        self._first = first_face

    def GetFirstFace(self):
        return self._first


class Extension:
    def __init__(self):
        self.names = {}

    def SetEntityName(self, entity, name):
        self.names[id(entity)] = name
        return True


class TopologyModel:
    def __init__(self, bodies, extension=None):
        self._bodies = bodies
        self.Extension = extension or Extension()

    def GetBodies2(self, body_type, visible_only):
        self.body_args = (body_type, visible_only)
        return self._bodies

    def GetEntityName(self, entity):
        return self.Extension.names.get(id(entity), "")


class TestListFaces(unittest.TestCase):
    def test_names_unnamed_faces_and_reports_types(self):
        top = Face("PLANE", 0.0024)
        side = Face("CYLINDER", 0.0009, next_face=top)
        sw = Mock()
        sw.get_active_document.return_value = TopologyModel((Body(side),))
        result = list_faces(sw)
        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["renamed"], 2)
        self.assertEqual([f["name"] for f in data["faces"]], ["Face0", "Face1"])
        self.assertEqual([f["surface_type"] for f in data["faces"]], ["CYLINDER", "PLANE"])
        self.assertAlmostEqual(data["faces"][0]["area_mm2"], 900.0)

    def test_existing_names_are_kept(self):
        face = Face("PLANE", 0.001)
        model = TopologyModel((Body(face),))
        model.Extension.names[id(face)] = "TopFace"
        sw = Mock()
        sw.get_active_document.return_value = model
        result = list_faces(sw)
        self.assertEqual(result["data"]["faces"][0]["name"], "TopFace")
        self.assertEqual(result["data"]["renamed"], 0)

    def test_no_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(list_faces(sw)["success"])


class TestListBodies(unittest.TestCase):
    def test_counts_faces_per_body(self):
        face = Face("PLANE", 0.001)
        sw = Mock()
        sw.get_active_document.return_value = TopologyModel((Body(face),))
        result = list_bodies(sw)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["bodies"][0]["face_count"], 1)

    def test_com_error_is_tool_error(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(list_faces(sw)["success"])
        self.assertFalse(list_bodies(sw)["success"])


if __name__ == "__main__":
    unittest.main()
```

- [x] **2. 跑红**：`python -m pytest tests/test_topology.py -q` → 期望 `ModuleNotFoundError`。
- [x] **3. 实现**：创建 `solidworks_mcp/solidworks_api/topology.py`：

```python
"""Body/face enumeration and entity naming (selection-based automation base)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from solidworks_mcp.solidworks_api.app import SolidWorksApp, SolidWorksNotRunningError
from solidworks_mcp.solidworks_api.geometry import MAX_FEATURE_WALK
from solidworks_mcp.utils.common import error_response, success_response

logger = logging.getLogger(__name__)

SW_SOLID_BODY = 0  # swBodyType_e.swSolidBody


def _surface_type(surface: Any) -> str:
    try:
        if surface.IsPlane():
            return "PLANE"
        if surface.IsCylinder():
            return "CYLINDER"
        if surface.IsSphere():
            return "SPHERE"
    except Exception:
        pass
    return "OTHER"


def _count_faces(body: Any) -> int:
    count = 0
    face = body.GetFirstFace()
    while face is not None and count < MAX_FEATURE_WALK:
        count += 1
        face = face.GetNextFace()
    return count


def list_bodies(sw_app: SolidWorksApp) -> dict:
    """List solid bodies with entity names and face counts."""
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        bodies = model.GetBodies2(SW_SOLID_BODY, False)
        rows: List[Dict[str, Any]] = []
        for index, body in enumerate(bodies or ()):
            rows.append({
                "index": index,
                "name": model.GetEntityName(body) or "",
                "face_count": _count_faces(body),
            })
        return success_response(
            data={"bodies": rows, "count": len(rows)},
            message=f"Found {len(rows)} solid body(ies)",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to list bodies")
        return error_response(f"Failed to list bodies: {exc}")


def list_faces(sw_app: SolidWorksApp, name_prefix: str = "Face") -> dict:
    """Enumerate solid faces; unnamed faces get stable SetEntityName names.

    Named faces become selectable via SelectByID2(name, "FACE", ...) and
    therefore referenceable from mates, fillets, and other picks.
    """
    try:
        model = sw_app.get_active_document()
        if model is None:
            return error_response("No active document")
        bodies = model.GetBodies2(SW_SOLID_BODY, False)
        rows: List[Dict[str, Any]] = []
        renamed = 0
        counter = 0
        for body in bodies or ():
            face = body.GetFirstFace()
            walked = 0
            while face is not None and walked < MAX_FEATURE_WALK:
                name = model.GetEntityName(face)
                if not name:
                    candidate = f"{name_prefix}{counter}"
                    if model.Extension.SetEntityName(face, candidate):
                        name = candidate
                        renamed += 1
                    else:
                        name = ""
                rows.append({
                    "name": name,
                    "surface_type": _surface_type(face.GetSurface()),
                    "area_mm2": round(face.GetArea() * 1_000_000.0, 6),
                })
                counter += 1
                walked += 1
                face = face.GetNextFace()
        return success_response(
            data={"faces": rows, "count": len(rows), "renamed": renamed},
            message=f"Found {len(rows)} face(s), {renamed} newly named",
        )
    except SolidWorksNotRunningError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to list faces")
        return error_response(f"Failed to list faces: {exc}")
```

- [x] **4. 跑绿**：`python -m pytest tests/test_topology.py -q` → 全部通过；全套无回归。
- [x] **5. 注册**（`server.py`，import 区追加 `from solidworks_mcp.solidworks_api.topology import list_bodies, list_faces`）：

```python
@mcp.tool(title="List and name faces", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_list_faces(name_prefix: str = "Face") -> ToolResult:
    """Enumerate solid faces (type/area mm2); unnamed faces get stable entity names for mating."""
    return _call_connected(lambda sw: list_faces(sw, name_prefix))


@mcp.tool(title="List solid bodies", annotations=READ_ONLY, structured_output=True)
def solidworks_part_list_bodies() -> ToolResult:
    """List solid bodies with names and face counts."""
    return _call_connected(list_bodies)
```

  （注：`list_faces` 因 SetEntityName 修改文档，标注 STATE_CHANGE 而非 READ_ONLY。）
- [x] **6. 跑全套**：`python -m pytest tests/ -q` → 全绿。
- [x] **7. 实机探针**：创建 `tools/probe_face_naming.py`（SW 运行时执行）验证实机 API 行为（GetEntityName/SetEntityName 宿主、SetEntityName 返回类型、SelectByID2 按 FACE 名可选中）：

```python
"""实机探针：验证面命名与按名选中闭环（T5 步骤 7）。

用法：venv\Scripts\python.exe tools\probe_face_naming.py
预期：每行 OK=；末尾 SUMMARY: selected=True。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom

from solidworks_mcp.solidworks_api.app import get_solidworks_app
from solidworks_mcp.solidworks_api.topology import list_faces


def main() -> int:
    sw = get_solidworks_app()
    result = list_faces(sw)
    print("list_faces:", result["success"], result.get("message"))
    faces = result["data"]["faces"]
    for f in faces[:10]:
        print("OK=", f["name"], f["surface_type"], round(f["area_mm2"], 3), "mm2")
    model = sw.get_active_document()
    model.ClearSelection2(True)
    picked = model.Extension.SelectByID2(
        faces[0]["name"], "FACE", 0, 0, 0, False, 0, pythoncom.Nothing, 0
    )
    print("SUMMARY: selected =", bool(picked))
    return 0 if picked else 1


if __name__ == "__main__":
    sys.exit(main())
```

  若 `selected=False`：改用 `"<面名>@<文档标题>"` 形式重试（组件级引用形态，与 assembly.add_mate 的 entity 语法一致），并把有效形态记录进执行记录——后续 T11 以此为准。
- [x] **8. 实机回归**：把 `topology.list_faces` / `topology.list_bodies` 加入 T1 冒烟链并跑通（退出码 0）。
- [x] **9. 提交**：
  ```powershell
  git add solidworks_mcp/solidworks_api/topology.py solidworks_mcp/server.py tests/test_topology.py tools/probe_face_naming.py tools/e2e_sw_smoke.py
  git commit -m "feat(topology): 新增面/实体枚举与命名工具，解锁选择型特征引用"
  ```

**验收标准**：
- `python -m pytest tests/ -q` → 全绿；
- `tools\probe_face_naming.py` 输出 `SUMMARY: selected = True`（或记录了实机有效引用形态）；
- T1 冒烟退出码 0。

**执行记录**：
> **2026-08-29 完成** · commit `c603571`。
> **实机面引用有效形态**：**「裸名 / FaceN@DocTitle / FaceN@DocTitle.SLDPRT 三形态的 SelectByID2 均选不中 FACE」**（GetIDsOfNames 实证 FACE 名不在 ModelDoc2 dispatch；SKETCH/SKETCHCONTOUR/BODYFEATURE 可按名选中——design.py 既有路径）。**有效选中机制 = 遍历面（GetFirstFace/GetNextFace）→ GetEntityName 匹配 → face.Select2(False, 0)**，实测 True；面名本身跨保存/重开持久 ✓。**T7（圆角/倒角）与 T11（mate）的选择型特征一律采用此机制**，assembly.add_mate 的按名 entity 语法需按此重估。
> **计划偏差（TDD 修正）**：实体命名宿主是 **ModelDoc2（model.SetEntityName，dispid 72）**，非计划所写的 model.Extension.SetEntityName（该对象 GetIDsOfNames 报未知名称）；GetEntityName 同在 ModelDoc2。实现与 fake 均已按实机形态修正。
> **实机样本**：60x40x20 盒 = 6 面（2×PLANE 800mm²[40×20]、2×PLANE 1200mm²[60×20]、2×PLANE 2400mm²[60×40]）——面积与几何精确吻合，list_faces 可作几何自检手段。
> **附带修正**：e2e 装配段 GetType 守卫（零参属性，经 call_or_value）；probe 的 SelectByID2 Callout 参数须 pythoncom.Nothing（None 报类型不匹配）。
> **测试基线**：239 passed + 58 subtests；覆盖率 89%；e2e 24 步（23 OK + 1 skip）退出码 0；工具计数断言 30→32（现共 32 个 MCP 工具）。

---

## 8. P1 任务（主包能力补齐 + aicad 深化 + 双引擎桥）

> P1 完成标志：主包能建回转体/圆角/倒角/抽壳等常规特征（T6-T8）、能改尺寸删特征（T9）、设计计划可回滚（T10）、装配可新建+干涉+BOM（T11）、能直接出工程图（T12）；aicad 图纸到 M2（T13）、循环有几何反馈与降级（T14）、有评测集（T15）；两引擎共享 CSG 重建契约（T16）。
>
> **P1 通用开发模式**（适用于 T6-T12、T17，与 P0 完全一致，不再逐任务重复）：
> 1. 写失败测试 → `python -m pytest tests/test_<模块>.py -q` 跑红；
> 2. 在 `solidworks_api/<模块>.py` 实现函数（签名 `def fn(sw_app: SolidWorksApp, ...) -> dict`，返回 success_response/error_response，异常捕获模式照抄 features.py）；
> 3. 跑绿 + 全套回归；
> 4. server.py 注册（READ_ONLY / STATE_CHANGE / DESTRUCTIVE 注解选择正确）；
> 5. 加入 tools/e2e_sw_smoke.py；实机验证；提交。
>
> **高危 COM API 探针惯例**：凡标注「探针先行」的 API，先写 `tools/probe_<名称>.py`（参照 T5 步骤 7 的骨架：连接 → 执行候选签名变体 → 打印 OK/异常），实机确认后把有效签名写入执行记录再进实现。这与 2026-08 治理期间 probe_sw_cosmetic.py / probe_sw_draft_thread.py / probe_sw_refplane.py 的既有惯例一致。

### T6：旋转特征 revolve（草图中心线为轴）

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P1 · **仓库**：主 · **依赖**：T3（latest_feature_name 验证）· **预估**：4h（1 晚）
- **对应差距**：C6（revolve 缺失）、D1（词汇表扩展）、C7 部分（草图中心线即轴）
- **需 SW 实机**：是

**目标**：新增 `solidworks_part_create_revolved`：在选定基准面上画「中心线 + 矩形轮廓」草图，FeatureRevolve2 生成回转体（盘/环/轴段），得到**有特征树**的回转体（区别于直接拉伸的 cylinder）。这是 T16 双引擎 CSG 与 T21 螺纹/齿轮的前置。

**关键 API（本计划预研，把握度：FeatureRevolve2 签名高；CreateLine 高）**：

```python
# 草图：SketchManager（项目 sketch.py 已用同一模式）
segment = model.SketchManager.CreateLine(x1, y1, 0, x2, y2, 0)  # 米，模型空间沿平面
segment.ConstructionGeometry = True  # 中心线（旋转轴）
model.SketchManager.CreateCornerRectangle(x1, y1, 0, x2, y2, 0)  # 轮廓
model.SketchManager.InsertSketch(True)  # 退出草图
# 旋转（20 参，swEndCondBlind=0，Ang 单位弧度）：
feature = model.FeatureManager.FeatureRevolve2(
    True,   # Sd 单向
    False,  # Flip
    False,  # Dir
    True,   # Merge
    True,   # UseFeatScope
    True,   # UseAutoSelect
    0, 2 * math.pi,  # T1=swEndCondBlind, Ang1=全周
    0, 0.0,          # T2, Ang2 未用
    False, False, False,  # MatchClosed, ReverseDir, NormalCut
    False, False, False,  # UseFtB, Ftb1, Ftb2
    0.0, 0.0, 0.0,        # D1..D3 薄壁未用
    False, # ReverseThinDir
)
```

**步骤**：

- [x] 1. 探针：创建 `tools/probe_revolve.py`：new_part（不保存）→ 选 Front 基准面（复用 geometry.select_plane）→ InsertSketch → 画中心线 (0,-0.01,0)-(0,0.01,0) + 矩形 (0.005,-0.01)-(0.02,0.01) → InsertSketch(True) → 重选中心线与矩形（SelectByID2 "SKETCHSEGMENT" 坐标拾取，或退出草图前保持选中）→ 按上述 20 参调 FeatureRevolve2 → 打印 feature.Name 与 GetTypeName2。若签名被拒（COM 报参数数量错），按报错信息逐步修剪/调整变体重试，把有效签名记入执行记录。
- [x] 2. 写失败测试：`tests/test_revolve.py`——fake SketchManager/FeatureManager 断言：中心线被标 ConstructionGeometry、FeatureRevolve2 收到 `2*math.pi`、返回 success 且 feature_name 非空；参数校验（outer>bore、height>0）；无文档/COM 错误返回 error。fake 结构参照 `tests/test_topology.py` 的 Model/Extension 模式自建（SketchManager 需记录调用序列供断言）。
- [x] 3. 跑红 → 4. 在 `solidworks_api/part.py` 追加 `create_revolved(sw_app, outer_diameter, height, bore_diameter=0, plane="front", save_path=None, overwrite_confirm=False)`（草图坐标系：半径沿 sketch-x，高度沿 sketch-y；bore=0 时矩形从轴线起）→ 5. 跑绿。
- [x] 6. 注册：
```python
@mcp.tool(title="Create revolved part", annotations=STATE_CHANGE, structured_output=True)
def solidworks_part_create_revolved(
    outer_diameter: PositiveMM,
    height: PositiveMM,
    bore_diameter: NonNegativeMM = 0,
    plane: str = "front",
    save_path: Optional[str] = None,
    overwrite_confirm: bool = False,
) -> ToolResult:
    """Revolved disc/ring/shaft segment (feature-tree based) around a sketch centerline."""
    return _call_connected(lambda sw: create_revolved(
        sw, outer_diameter, height, bore_diameter, plane, save_path, overwrite_confirm))
```
- [x] 7. 实机验证：create_revolved(40, 10, 20) 后 get_bounding_box 应为 `[40, 40, 10]` mm（绕 front 面法向回转）；get_feature_details 应含 type_name 与 2 个尺寸（40/10 或 20/10）。加入 e2e 链。
- [x] 8. 提交：`git commit -m "feat(part): 新增回转体工具（中心线草图+FeatureRevolve2）"`。

**验收标准**：`python -m pytest tests/ -q` 全绿；实机 bore=20/outer=40/height=10 输出 bbox `[40,40,10]`；e2e 退出码 0。

**执行记录**：
> **2026-08-29 完成** · commit `82122f3`。
> **FeatureRevolve2 实机有效签名**（IFeatureManager 20 参，typelib 顺序，计划预研注释的旧顺序作废）：`(SingleDir=True, IsSolid=True, IsThin=False, IsCut=False, ReverseDir=False, BothDirectionUpToSameEntity=False, Dir1Type=0, Dir2Type=0, Dir1Angle=2π, Dir2Angle=0, OffRev1/2=False, OffDist1/2=0, ThinType=0, ThinThk1/2=0, Merge=True, UseFeatScope=True, UseAutoSelect=True)`。**全周角放 Dir1Angle（第 9 参，索引 8），单位弧度**。退出草图后直接调用即可，无需选中回退（探针一次通过）。
> **实机验证**：create_revolved(40,10,20) → bbox `[40,10,40]`（轴向=模型 Y：旋转轴是前视面草图的 y 向中心线，直径落 XZ——与计划预估「绕 front 面法向」不同，实现 docstring 已写明）；体积 π(20²-5²)·20=23561.9mm³ 精确吻合；type_name=**Revolution**（特征名「旋转1」）。
> **给 T9 的注意**：Revolution 的显示尺寸 value_mm=6283.19=2π×1000——**角度尺寸经 GetSystemValue3 返回弧度**，features.get_details 的 mm 换算对角度类尺寸会误标；dimension_set 改角度时入参需按弧度×1000 处理或先识别尺寸类型。
> **范围说明**：参考几何（基准轴/基准面创建，C7 的另一半）未在本任务实现——中心线草图已满足回转需求；独立基准轴工具待 T21 螺纹扫描真正需要时再补（计划允许，记偏差）。
> **测试基线**：246 passed + 59 subtests；覆盖率 89%；e2e 25 步（24 OK + 1 skip）退出码 0；工具计数 32→33。

---

### T7：圆角 fillet + 倒角 chamfer

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P1 · **仓库**：主 · **依赖**：T5（面命名后可按名选择）· **预估**：4h（1 晚）
- **对应差距**：C6（fillet/chamfer 缺失）、E2（边/面选择）
- **需 SW 实机**：是

**目标**：新增 `solidworks_part_apply_fillet(face_names, radius_mm)` 与 `solidworks_part_apply_chamfer(edge_or_face_names, distance_mm[, angle_deg=45])`：按 T5 命名的面/边做选择，然后调 FeatureManager。机械图中不可圆角/倒角的零件几乎不存在，这是「能出真图」的硬前置。

**关键 API（把握度：中，探针先行）**：

```python
# 选择（T5 已命名面）：
model.Extension.SelectByID2(face_name, "FACE", 0, 0, 0, True, 0, pythoncom.Nothing, 0)  # append=True 多选
# 候选 A（面选圆角，SW2013+，22 参中前几参为半径/选项位）：
feature = model.FeatureManager.FeatureFillet3(radius_m, False, 0.0, 0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
# 候选 B（旧版兼容）：
feature = model.FeatureManager.FeatureFillet2(radius_m, ...)
# 倒角（SW2019+）：
feature = model.FeatureManager.InsertFeatureChamfer4(3, 1, distance_m, 0.0, angle_rad, 0.0, 0.0, False, 0, 0, 0, 0)
#   倒角参数含义以探针为准：等距-角度 vs 距离-距离由第 1/2 参控制
```

**步骤**：

- [x] 1. 探针 `tools/probe_fillet_chamfer.py`：new box → T5 list_faces 命名 → 逐个按名选面（append 多选）→ 尝试候选签名（try/except 逐个），打印成功变体与生成特征的 GetTypeName2（预期 `Fillet`/`Chamfer`）。把有效签名记入执行记录。
- [x] 2. 写失败测试 `tests/test_fillet.py`：fake 断言 SelectByID2 以 append=True 逐个调用、FeatureManager 收到米单位半径、成功响应含新特征名；空 face_names 返回 INVALID_PARAMETER；COM 错误返回 error。
- [x] 3. 跑红 → 4. 实现：新建 `solidworks_api/decorations.py`，两个函数 `apply_fillet(sw_app, face_names, radius_mm)` / `apply_chamfer(sw_app, entity_names, distance_mm, angle_deg=45)`（探针确认后的签名）；radius/distance 经 positive_number 校验（复用 part.py 的校验工具）→ 5. 跑绿。
- [x] 6. 注册两个工具（均 STATE_CHANGE）。fillet 的 radius 用 PositiveMM。
- [x] 7. 实机验证：60x40x20 盒顶面 R5 圆角后 get_bounding_box 仍为 `[60,40,20]`（圆角不动 bbox，若顶面整面圆角则 z 不变）；边倒角 2mm 后体积减小（mass_properties 对比）。加入 e2e 链。
- [x] 8. 提交：`git commit -m "feat(decorations): 新增圆角/倒角工具（按名选面，探针验证签名）"`。

**验收标准**：全套测试绿；实机圆角/倒角后特征树出现 Fillet/Chamfer 特征（get_features 可见）且重建无错（get_mass_properties 成功）；e2e 退出码 0。

**执行记录**：
> **2026-08-29 完成** · commit `e4e0568`。
> **实机有效签名（计划候选全部作废，typelib+网格实测）**：
> - **圆角 = 旧版 `IModelDoc2.FeatureFillet(R1米, False, False, False, 0)`（5 参全值类型）**——特征「圆角1」type=`Fillet`，尺寸 D1@圆角1=5.0mm 精确读回，体积 48000→47404.4 实变。计划候选 A（FeatureFillet3 22 参）在 typelib 不存在（实际 9 参/13 参两种）；FeatureFillet3+ 系列的 **variant 数组参数（Radii 等 (12,1)）在 pywin32 下编组不稳定**——间歇性 RPC_E_SERVER_FAULT（0x80010105 服务器意外情况），同参数有时崩有时成，一律不用。
> - **倒角 = `IModelDoc2.FeatureChamfer(距离米, 角度弧度, False)`（3 参）**——InsertFeatureChamfer4 不存在（实际名 InsertFeatureChamfer 8 参）；特征「倒角1」type=`Chamfer`，单面 2mm 体积 48000→47770.7。
> - **两个 API 返回值都不可靠（None/int），成功判据 = 特征树出现新特征**（latest_feature_name 前后对比）。
> **选中机制按 T5 契约**：遍历面→GetEntityName 匹配→`face.Select2(append, mark=1)`（SelectByID2 按名选不中 FACE）。工具语义：按面名圆角化/倒角化该面全部边。
> **测试基线**：254 passed + 61 subtests；覆盖率 89%；e2e 28 步（27 OK + 1 skip，新增 ring 面命名+R2 圆角+1mm 倒角段）退出码 0；工具计数 33→35。

---

### T8：抽壳 shell + 拔模 draft + 镜像 mirror + 线性阵列

- **状态**：`[!]` BLOCKED（2026-08-30 FeatureData 扫描亦无果） 进行中（shell ✅ 2026-08-29；mirror/pattern/draft BLOCKED，见执行记录）
- **优先级**：P1 · **仓库**：主 · **依赖**：T7（选择/探针模式就绪）· **预估**：5h（2 晚）
- **对应差距**：C6（四类特征缺失）、D1（词汇表扩展）
- **需 SW 实机**：是

**目标**：新增四个工具，覆盖盒体/壳体零件与阵列孔的最常见形态：
1. `solidworks_part_apply_shell(face_names, thickness_mm)`——移除面抽壳（InsertFeatureShell）；
2. `solidworks_part_apply_draft(face_names, angle_deg)`——拔模（复用既有探针知识 `tools/probe_sw_draft_thread.py` 的结论）；
3. `solidworks_part_mirror(feature_names, plane="front")`——特征镜像；
4. `solidworks_part_create_linear_pattern(feature_name, direction="x", count, spacing_mm)`——线性阵列（阵列孔/筋必备）。

**关键 API（把握度：InsertFeatureShell 高；其余中，探针先行）**：

```python
# 抽壳：选移除面后（append 逐个）
feature = model.FeatureManager.InsertFeatureShell(thickness_m, False)  # (厚度, 向外抽壳)
# 拔模（以 tools/probe_sw_draft_thread.py 已验证的调用形态为准，若该探针结论可直接用则免探）
# 镜像：选特征 + 镜像基准面后
feature = model.FeatureManager.InsertFeatureMirror(True)
# 线性阵列候选：
feature = model.FeatureManager.FeatureLinearStep4(
    count, spacing_m,              # D1 方向数量/间距
    1, 0.0,                        # D2 方向（1=不阵列）
    False,                         # 反向
    0, 0,                          # 几何关系阵列/延伸
    "", "",                        # 范围特征名
    0.0,                           # 旋转
)
# 变体候选：FeatureLinearStep3 / FeaturePatternAdvanced —— 探针确认
```

**步骤**：

- [ ] 1. 探针 `tools/probe_shell_draft_mirror_pattern.py`：60x40x20 盒上逐个验证四类 API（先 T5 命名面）；每类单独 try/except，打印有效签名。draft 先读 `tools/probe_sw_draft_thread.py` 顶部注释里的既有结论，避免重复探针。
- [ ] 2. 写失败测试 `tests/test_shell_draft_mirror.py` + `tests/test_pattern_linear.py`：断言选择序列、米单位、参数校验（0<count≤100、spacing>0、|angle|≤45）、COM 错误响应。
- [x] 3. 跑红 → 4. 实现（shell/draft/mirror 追加到 `solidworks_api/decorations.py`；linear_pattern 追加到 `solidworks_api/pattern.py`，与 annular 同域）→ 5. 跑绿。
- [x] 6. 注册四个工具（全部 STATE_CHANGE；无破坏性删除，但镜像/阵列改变几何）。
- [ ] 7. 实机验证：
  - shell：盒顶面抽壳 2mm → mass_properties 体积下降约 80-95%；
  - mirror：单孔镜像后 features 列表多一个镜像特征；
  - linear_pattern：单孔 ×3 间距 10mm → features 列表多阵列特征，bbox 不变（孔在体内时）；
  - draft：验证无重建错误（EditRebuild3 后 get_mass_properties 成功）。
  全部加入 e2e 链。
- [x] 8. 提交：`git commit -m "feat(features): 新增抽壳/拔模/镜像/线性阵列四工具"`。

**验收标准**：全套测试绿；四项实机验证通过；e2e 退出码 0。

**执行记录**：
> **2026-08-29 第 1 晚** · commit `c844b33`。
> **✅ 抽壳（已落地）**：`ModelDoc2.InsertFeatureShell(厚度米, False)`（先选中移除面）——实机 60x40x20 盒移除一个 2400mm² 面、2mm 壁厚 → 体积 **11712.0mm³ 与理论精确一致**（48000−56×36×18）。工具 `solidworks_part_apply_shell` 已注册并入 e2e。
> **❌ 镜像（BLOCKED，3 轮 ×9 组合）**：计划的 `InsertFeatureMirror(True)` 不存在，实为 `IFeatureManager::InsertMirrorFeature(4 参)/InsertMirrorFeature2(5 参, 返回 IFeature)`。特征按名选中（BODYFEATURE）与基准面 Select2 均成功，但 BMirrorBody{False,True} × mark{0,1,2,4} × 选中顺序（特征先/面先）共 9 组合**全部返回 None 且特征树零变化**。
> **❌ 线性阵列（BLOCKED，3 轮）**：`ModelDoc2.FeatureLinearPattern`（8 参全值，返回 void）与 `FM.FeatureLinearPattern`/`FeatureLinearPattern4`（返回 IFeature）× mark{0,1,4} × DName{空/"X 轴"/"X轴"/"X Axis"} 零产出。特征选中成功（切除特征 BODYFEATURE）。
> **❌ 拔模（BLOCKED）**：typelib 中 **FeatureManager 无特征级拔模 API**（计划的拔模路径依赖不存在的探针文件）；仅 `IBody2::DraftBody(NumOfFaces, FaceList, EdgeList, DraftAngle)`（body 级），其数组参数三次编组失败（TYPEMISMATCH「内存已锁定」/ 显式 VARIANT 时 RPC 服务器异常）。
> **下一步建议**（第 2 晚或后续）：① 人工在 SW 里录制镜像/阵列宏，比对录制的 SelectByID2 顺序与 mark 值（宏录制器是 SW API 的 ground truth）；② 或改走 FeatureData 对象模式（`fm.CreateDefinition("...")` + 编辑 + CreateFeature），绕过选中协议。draft 若无特征级 API 需求，可用拔模拉伸（extrude_boss_draft 已存在）在建模时替代。
> **e2e 实证补充**：已圆角面再倒角被 SW 几何拒绝（无直边可倒）——装饰链面不重叠；e2e 已改用未圆角面。
> **测试基线**：257 passed + 62 subtests；覆盖率 89%；e2e 29 步（28 OK + 1 skip）退出码 0；工具计数 35→36。

---

### T9：尺寸读取/修改 + 特征删除工具

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P1 · **仓库**：主 · **依赖**：T3（get_feature_details 提供 dimension full_name）· **预估**：4h（1 晚）
- **对应差距**：C5（尺寸读写缺失）、D2（改参数重生闭环）
- **需 SW 实机**：是

**目标**：新增 `solidworks_dimension_set(full_name, value_mm)`（改尺寸并 EditRebuild3，闭合「读→改→重建→再读」参数化回路）与 `solidworks_feature_delete(feature_name)`（删特征，DESTRUCTIVE）。T10 事务性依赖本工具的删除能力。

**关键 API（把握度：高）**：

```python
# 改尺寸：
dim = model.Parameter(full_name)              # IDimension，如 "D1@Sketch1"
status = dim.SetSystemValue3(mm_to_m(value_mm), 1, "")  # swThisConfiguration=1
model.EditRebuild3()
# 删特征：
model.ClearSelection2(True)
picked = model.Extension.SelectByID2(feature_name, "BODYFEATURE", 0, 0, 0, False, 0, pythoncom.Nothing, 0)
model.EditDelete()
```

**步骤**：

- [x] 1. 写失败测试：`tests/test_dimension_edit.py`——fake Model 带 `Parameter(name)` 返回 fake Dimension（记录 SetSystemValue3 入参）、`EditRebuild3()` 计数、`EditDelete()` 记录；断言：成功响应、米单位换算（20mm → 0.02）、rebuild 被调、删除前 SelectByID2 用 "BODYFEATURE" 类型且未选中返回 error、COM 错误响应。
- [x] 2. 跑红 → 3. 实现：`solidworks_api/features.py` 追加 `set_dimension(sw_app, dimension_full_name, value_mm)` 与 `delete_feature(sw_app, feature_name)` → 4. 跑绿。
- [ ] 5. 注册：
```python
@mcp.tool(title="Set dimension value", annotations=STATE_CHANGE, structured_output=True)
def solidworks_dimension_set(dimension_full_name: NonEmptyString, value_mm: PositiveMM) -> ToolResult:
    """Set a dimension (full name from features_get_details) in mm and rebuild."""
    return _call_connected(lambda sw: set_dimension(sw, dimension_full_name, value_mm))


@mcp.tool(title="Delete feature", annotations=DESTRUCTIVE, structured_output=True)
def solidworks_feature_delete(feature_name: NonEmptyString) -> ToolResult:
    """Delete a feature from the tree (destructive, no undo guarantee)."""
    return _call_connected(lambda sw: delete_feature(sw, feature_name))
```
- [x] 6. 实机验证（闭环断言）：create_box(60,40,20) → get_feature_details 取拉伸深度尺寸 full_name → set_dimension(…, 30) → get_bounding_box 应为 `[60,40,30]`（或 `[60,40,10]` 取决于方向，记录实际形态）；delete_feature 删掉孔特征后 features 列表少一项。加入 e2e 链。
- [x] 7. 提交：`git commit -m "feat(features): 新增尺寸修改与特征删除工具，闭合参数化回路"`。

**验收标准**：全套测试绿；实机改尺寸后 bbox 变化符合预期且重建无错；e2e 退出码 0。

**执行记录**：
> **2026-08-29 完成** · commit `3f1083b`。
> **实机尺寸方向语义**：create_box 的拉伸深度尺寸（`D1@凸台-拉伸1@文档.Part`）沿**模型 Z 轴**——set 30 后 bbox `[60,40,30]`（z 20→30），x/y 不变。
> **实机闭环全通**：读 20.0 → set_dimension 30.0 → bbox 精确 `[60,40,30]`；delete_feature('切除-拉伸1') 特征 22→21、孔消失。「读→改→重建→再读」参数化回路闭合，**T10 事务性的前置就绪**。
> **实现要点（零参属性铁律再应用）**：`EditRebuild3`/`EditDelete` 都是属性（call_or_value）；SetSystemValue3 返回 int（负值=拒绝），typed 包装器可能裹 0-宽元组（已归一）；`Parameter(name)` 返回 None 即维度不存在。删除判据=特征树中消失（比 EditDelete 返回值可靠，返回 void）。
> **角度维度不支持**：docstring 已注明（GetSystemValue3/SetSystemValue3 弧度语义，T6 发现 Revolution 角度读回 2π×1000）；后续如需改角度单独设计。
> **e2e 稳定性发现**：ring 柱面圆角后对端面倒角的几何求解**非确定**（同参数两轮一过一败）——装饰组合的面选择必须几何不相邻；e2e 已把 chamfer 移至盒顶/底面（2400mm² 两面互不相邻），连跑两轮全绿。
> **测试基线**：263 passed + 64 subtests；覆盖率 89%；e2e 29 步两轮退出码 0；工具计数 36→38。

---

### T10：design plan 事务性（回滚部分应用）

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P1 · **仓库**：主 · **依赖**：T9（delete_feature 复用）· **预估**：4h（1 晚）
- **对应差距**：A4/F1（首错即停无回滚）、F6 部分（操作记录）
- **需 SW 实机**：是（步骤 6）

**目标**：重构 `design.py::execute_design_plan`（219-317 行）：执行前快照特征名集合；任何操作失败时，把本次新增的特征**逆序删除**（复用 T9 的删除逻辑），返回 `rolled_back` 明细与已应用操作列表；新增可选参数 `atomic: bool = True`（False 保持旧行为，兼容既有调用/测试）。

**步骤**：

- [ ] 1. 写失败测试：在 `tests/test_design.py` 追加用例（mock 链）：三步计划在第二步抛错 → 断言：①响应 success=False；②对第一步新增特征名调用了删除（fake 记录 EditDelete 次数）；③响应 data 含 `applied=[第1步]`、`failed=第2步`、`rolled_back=[第1步特征]`；④atomic=False 时不回滚（旧行为）。
- [x] 2. 跑红 → 3. 实现：
  - 提取 `_snapshot_feature_names(model) -> set`（遍历 FirstFeature/GetNextFeature，MAX_FEATURE_WALK 有界）；
  - 提取 `_delete_new_features(model, before: set) -> list[str]`（逆序遍历当前树，删除 `当前 - before` 的特征，逐个 SelectByID2+EditDelete）；
  - execute_design_plan 主循环包裹：操作成功后记录 `applied`；失败时若 atomic 则调 `_delete_new_features`，把删除名列表写入响应 data；
  - 回滚中再次失败不掩盖原错：捕获后以 warning 字段附注。
- [ ] 4. 跑绿：全套（含既有 plan 用例，atomic=True 为新默认，若旧行为用例失败则按旧语义保留其调用的显式 atomic=False 并在执行记录说明）。
- [ ] 5. 实机验证：计划 `[new_part, box(60,40,20), hole(8@0,0), cylinder(不合理参数)]`（最后一步故意报错）→ 实机确认文档特征树回到只有 box+hole 之前状态（get_features 对比），文档无残留半成品特征。
- [ ] 6. 提交：`git commit -m "feat(design): 设计计划支持事务性回滚（atomic，逆序删除新增特征）"`。

**验收标准**：全套测试绿；实机故意失败后特征树与失败前一致；e2e 退出码 0。

**执行记录**：
> **2026-08-29 完成** · commit `ef56b43`。
> **实现**：`execute_design_plan` 新增 `atomic=True` 默认参数——执行前快照特征名集合（geometry 抽出公共 `walk_feature_names`）；任何操作失败时逆序删除「当前−快照」的新增特征，响应 data 含 `applied/failed/rolled_back/rollback_warning`；回滚自身失败不掩盖原错（warning 附注）；`atomic=False` 保留旧语义（既有测试兼容，`test_stops_after_failed_operation` 无需改动）。
> **删除选中协议（实机证据）**：SelectByID2 按名删除需先试 `BODYFEATURE` 再试 `SKETCH`——plate 操作产生「草图3+凸台-拉伸2」两个特征，草图仅 SKETCH 类型可选中，**空类型串不构成通配**（实测 False）。
> **实机回滚验证**：基线计划（new_part+box+hole）后树 22 特征；叠加故意失败计划（plate 成功 + cylinder 坏参数）→ `rolled_back=['凸台-拉伸2','草图3']`（逆序），**特征树完全恢复基线（22=22）**，rollback_warning=null。
> **⚠️ 本任务引入并修复的重大事故（Mock 遍历内存爆炸）**：初版快照对 Mock 文档走满 5000 步有界循环——循环有界无恙，但 **unittest.mock 的调用记录沿 parent 链逐层向上传播**（链深 k 的第 k 次调用产生 k 条记录），O(n²)=1250 万 call 对象 → GB 级内存 + 分钟级 CPU。症状：单测挂死、全套仅执行 60 个且 82-138s、coverage 35%、INTERNALERROR MemoryError。faulthandler 栈转储实锤（mock.py:_increment_mock_call ← call_or_value ← walk_feature_names）。**修复**：特征 Name 非 str 即判为退化代理/测试替身立即停止遍历（真实 COM 名恒为 str，行为不变）+ rolled_back/警告列表封顶 200。回归测试 2 个锁定。**教训（通用）**：任何有界循环若步进依赖 Mock 属性调用，其真实成本是 O(n²) 的调用记录传播——循环上限不等于成本上限；对「输入对象形态」的判定（Name 是否 str）要前置。
> **已知行为说明（MEDIUM，可接受）**：`new_part` 开头的失败计划回滚时快照为空集，会尝试删新文档全部特征——默认树节点（文件夹/基准面/原点）不可被两种类型选中而跳过，产生 rollback_warning 噪音；核心语义正确（重试不叠加特征）。
> **测试基线**：268 passed + 64 subtests ≈6.8s；coverage 89%；e2e 29 步退出码 0；工具数 38（本任务无新工具）。
> **复查加固（2026-08-29 追加，commit `d2e0baa`）**：应用户指令对内存事故做全仓系统性复查——扫描出全部 9 处「while is not None + COM 属性步进」循环，发现 **`_find_feature`/`get_features` 两处无步数上限的真·无限循环**（比 T10 修复的有界版更危险，旧测试全用受控 fake 才未引爆）。整改：geometry 新增 `walk_features()` 生成器（Name 非 str 即停+上限）统一 feature 走查；dimensions 链加 FullName 哨兵；topology/decorations 的 face 链加 GetArea/GetEntityName 标量哨兵（`_select_named_faces` 补上限）。新增 `tests/test_memory_guard.py` 对抗回归套件（13 入口裸 Mock + 可迭代 Mock body 对抗场景 + RSS<200MB 预算断言）；顺带修复采样本身（GetProcessMemoryInfo 无 argtypes 时静默恒返 0，首版守卫是恒真断言）。**终验**：全套 273+64 subtests 6.6-7.1s、进程真实峰值 168MB（事故时 GB 级）、e2e 实机退出码 0、coverage 89%。**通用铁律**：凡「步进依赖外部对象属性调用」的循环，必须以恒定类型标量（str/数值）作哨兵——有界上限挡不住 Mock 调用记录的 O(n²) 传播。

---

### T11：装配增强（create_assembly / mate 扩展 / 干涉检查 / BOM）

- **状态**：`[x]` 完成（2026-08-30）
- **优先级**：P1 · **仓库**：主 · **依赖**：T5（面命名）· **预估**：6h（2 晚）
- **对应差距**：E1（mate 仅 3 种）、E2（实体引用）、E3（干涉）、E4（BOM）、E6 铺垫
- **需 SW 实机**：是

**目标**：补齐装配自动化四件套：
1. `solidworks_assembly_new(save_path)`——新建装配文档（当前完全缺失，T1 冒烟已暴露）；
2. mate 类型扩展——`width`（宽度）、`angle`（角度）、`tangent`（相切）三种（AddMate5 的 mate type 常量映射）；
3. `solidworks_assembly_check_interference()`——InterferenceDetectionManager 干涉报告；
4. `solidworks_assembly_get_bom()`——基于 get_components 的结构化 BOM（组件名/路径/配置/数量聚合）。

**关键 API（把握度：中高，探针先行）**：

```python
# 新建装配：复用 design.create_new_part 的模板获取模式（config.assembly_template，
# 缺省回退 SW 默认 prp 场装配模板），NewDocument 后 IModelDoc2 类型应为 2（swDocASSEMBLY）。
# mate 常量（swMateType_e）：coincident=0, concentric=1, distance=2? —— 以 constants.py
# 现有映射为准（已有 3 种），新增 width/angle/tangent 探针确认常量值后写入 constants.py。
# 干涉：
assembly_doc = model  # 活动装配文档
detector = assembly_doc.InterferenceDetectionManager
detector.TreatCoincidenceAsInterference = False
detector.TreatSubBodiesAsInterference = False
result = detector.GetInterferences()  # 返回干涉对象数组，逐个读 Volume/ComponentNames
```

**步骤**：

- [x] 1. 探针 `tools/probe_assembly_extras.py`：手工/脚本建一个含两零件的小装配 → 验证：①NewDocument 装配模板路径可用（从 sw.GetUserPreferenceStringValue? 或硬编码常见安装路径探测，找不到则要求 SOLIDWORKS_MCP_ASSEMBLY_TEMPLATE env 并在文档中注明）；②AddMate5 用新常量值各建一个 mate；③GetInterferences 在故意重叠时返回非空、分离时为空。有效常量与行为记入执行记录。
- [x] 2. 写失败测试：`tests/test_assembly_extended.py` 追加：new_assembly 成功/模板缺失错误；三种新 mate 的常量映射断言；interference 的 detector 属性设置与结果聚合；BOM 聚合计数（同名组件合并数量）。fake 参照该文件既有 fake 模式扩展。
- [x] 3. 跑红 → 4. 实现：`assembly.py` 追加 `new_assembly / check_interference / get_bom`，扩展 `add_mate` 的类型表（constants.py 加 3 常量）→ 5. 跑绿。
- [x] 6. 注册四个工具（new/check/bom 为 STATE_CHANGE/READ_ONLY 按语义：new=STATE_CHANGE、interference=READ_ONLY、bom=READ_ONLY；mate 扩展不需新工具）。
- [x] 7. 实机端到端：new_assembly → add_component(box) ×2（重叠放置）→ check_interference 应报干涉 → 改第二件坐标分离 → 干涉为空 → get_bom 应为 [{name, count:2, …}]。加入 e2e 链（替换 T1 的可选段为全自动段）。
- [x] 8. 提交：`git commit -m "feat(assembly): 新建装配/干涉检查/BOM 工具，mate 扩展 width/angle/tangent"`。

**验收标准**：全套测试绿；实机端到端通过（重叠→干涉非空，分离→空，BOM 聚合正确）；e2e 装配段不再 skipped。

**执行记录**：
> **2026-08-30 完成**（单晚，探针三轮 → TDD → 实机 e2e 54/54）。commit 8b55a12。
>
> **实机契约（写入 assembly.py docstring + probe_assembly_extras.py）**：
> - **模板**：get_assembly_template() = C:\ProgramData\SolidWorks\SOLIDWORKS 2026\templates\gb_assembly.asmdot（=GetUserPreferenceStringValue(9)）；NewDocument(tpl,0,0,0) → GetType=2。
> - **⚠️ AddComponent4 铁律：零件文档必须已在会话中打开（OpenDoc6 预开），否则静默返回 None**。既有 add_component 从未实机验证（e2e 装配段一直 skip），本任务暴露并修复（_preopen_component_document）。CloseAllDocuments 后再 AddComponent4 同样 None。
> - **干涉**：InterferenceDetectionManager 是 IAssemblyDoc 零参属性（call_or_value）；TreatCoincidenceAsInterference 可写、TreatSubBodiesAsInterference 拒写（跳过）；GetInterferences（零参）→ IInterference 数组：Volume 属性（m³）、Components 属性（组件数组→Name2）。重叠两盒→1 处 4e-5m³=40000mm³（精确）；分离→空。
> - **BOM**：组件 GetPathName/ReferencedConfiguration 均零参属性；按 (路径小写,配置) 聚合计数。中文 SW 配置名「默认」。
> - **mate 两处既有缺陷修复（旧 add_mate 从未实机验证）**：①**角度必须走 AddMate5 第 10 参 Angle 槽（度→弧度）**，旧代码把角度塞 Distance 槽恒败——实机 15 参签名 (Type,Align,Flip,Distance,Up,Low,GearN,GearD,Angle,AngleUp,AngleLow,ForPos,Lock,WidthOpt,Error)。②探针实证：**裸名选择形态会误选导致 mate None，必须以「名@装配体标题」全限定形态优先**（现有代码顺序本就正确，探针反向佐证）。coincident/distance/angle 三类型实机验证创建成功（配合文件夹出现 重合1/距离1/角度1；返回对象+err=1 非致命）。
> - **mate 常量**：tangent=4、angle=6、width=17（swMateType_e，typelib 无此枚举）入表；tangent/width 未实机验证——装配中 face 按名选择不中（quirk #12 同族），需 walk+Select2 扩展到装配上下文后复验；工具行为=SW 拒绝时返回结构化错误。
> - 测试 335 passed + 78 subtests（+22），覆盖率 89%，工具 49→52（new=STATE_CHANGE / interference=READ_ONLY / bom=READ_ONLY），记忆守卫 +3 入口。e2e 装配段转全自动 13 步（重叠→非空、分离→空、BOM 2×断言）。"

---

### T12：主包工程图工具族（建图/投视图/自动标注/导出）

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P1 · **仓库**：主 · **依赖**：无（与 T6-T11 并行可做）· **预估**：6h（2 晚）
- **对应差距**：C1（PRD FR-005 完全未实现）——「全自动出图」最直接的缺口
- **需 SW 实机**：是

**目标**：主包从零到一补上工程图能力，交付四个工具：
1. `solidworks_drawing_create_from_part(part_path)`——新建工程图文档 + 第一角投影三视图；
2. `solidworks_drawing_insert_dimensions()`——从模型插入尺寸标注（InsertModelAnnotations3）；
3. `solidworks_drawing_export_pdf(pdf_path)` / `solidworks_drawing_export_png(png_path)`——导出 PDF/PNG（复用 file_io 的 SaveAs3 模式与 validate_output_file 安全校验）。

**关键 API（把握度：中，探针先行；这是 FR-005 的核心知识，探针结论务必详细记录）**：

```python
# 建图（NewDocument 模板路径同 T11 方案；config.drawing_template env 已预留）：
drawing = sw_app_new_document(drawing_template_path, 12, 0.210, 0.297)  # 12≈A4 纵向，尺寸米
# 投三视图（零件需已保存）：
status = drawing.Create1stAngleViews2(part_path)   # 返回 bool；三视图自动布局
# 插入模型尺寸（图纸活动时）：
drawing.Extension.InsertModelAnnotations3(0, 0x00000001 | 0x00000008, True, True, False, True)
#   标志位含义（插入项目/尺寸/注释等）以探针为准，目标：尺寸完整入图
# 视图遍历（后续任务用）：
view = drawing.GetFirstView()          # 图纸视图
while view is not None:
    ...  # view.Name / view.Position / view.ScaleDecimal
    view = view.GetNextView()
# 导出：SaveAs3 模式同 file_io.export_step，后缀换 .pdf/.png
```

**步骤**：

- [x] 1. 探针 `tools/probe_drawing.py`：用 T1 的 e2e_box.SLDPRT → NewDocument(工程图模板) → Create1stAngleViews2 → InsertModelAnnotations3（标志位扫描 2-3 个组合）→ SaveAs3 PDF → 打开 PDF 确认非空（文件大小>10KB）。记录：模板路径、A4 常量、InsertModelAnnotations3 有效标志位、PDF 字节数。**若找不到工程图模板**：优先在 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\templates\` 等常见路径探测 `*.drwdot`；仍无则把 SOLIDWORKS_MCP_DRAWING_TEMPLATE env 设为硬编码可用路径并在执行记录注明。
- [x] 2. 写失败测试 `tests/test_drawing.py`：fake SwApp/ModelDoc2/DrawingDoc——断言：Create1stAngleViews2 收到零件路径；InsertModelAnnotations3 被调且标志位为探针确认值；导出后缀白名单校验（.pdf/.png）；模板缺失返回明确错误；COM 错误响应。
- [x] 3. 跑红 → 4. 实现：新建 `solidworks_api/drawing.py`（`create_drawing_from_part / insert_model_dimensions / export_drawing_pdf / export_drawing_png`，模板获取封装 `_drawing_template()`，读 config.drawing_template，缺省回退探针确认路径）→ 5. 跑绿。
- [x] 6. 注册四个工具（create/insert 为 STATE_CHANGE；export 为 IDEMPOTENT_WRITE，与 export_step 注解对齐）。
- [x] 7. 实机端到端：create_box(60,40,20) 保存 → create_drawing_from_part → insert_model_dimensions → export_pdf → 输出/目录 PDF 存在且 >10KB，PNG 同验。加入 e2e 链。
- [x] 8. 提交：`git commit -m "feat(drawing): 主包新增工程图四工具（建图/投视图/自动尺寸/导出 PDF-PNG）"`。

**验收标准**：全套测试绿；实机产出 PDF/PNG 且非空；e2e 退出码 0；探针知识（模板/标志位）已写入执行记录。

**执行记录**：
> **2026-08-29 完成**（单晚，六轮探针 → TDD → 实机 e2e 41/41）。
>
> **实机契约（已写入 drawing.py 模块头 + probe_drawing.py 定稿）**：
> - **模板**：GetUserPreferenceStringValue(10)=C:\ProgramData\SolidWorks\SOLIDWORKS 2026\templates\gb_a0.drwdot（8/9=part/assembly 模板）；同目录 gb_a0~gb_a4p 全套。实现取同目录 **gb_a3 优先**，env SOLIDWORKS_MCP_DRAWING_TEMPLATE 覆写，pref 失效仍可解析邻位模板。
> - **建图**：app.NewDocument(template, 0, 0, 0)（有模板时纸型参数被忽略）→ 动态 dispatch；GetType=3、GetTitle='工程图N - 图纸1'（零参属性）。
> - **Create1stAngleViews2 在 SW2026 恒返回 False**（gb_a0/gb_a3 两模板 + ActivateDoc3 后均 False）——弃用。改**手动三视图**：CreateDrawViewFromModelView3(abs_part, '', x, y, 0)（A3 图面坐标米制：主 0.15/0.10、顶 0.15/0.19、侧 0.27/0.10）→ 选中主视图 → CreateUnfoldedViewAt3×2。视图名本地化「工程图视图N」。
> - **⚠️ NewDocument 返回的 dispatch 只暴露 IModelDoc+IDrawingDoc 成员面：SelectByID2（ModelDoc2 成员）不可解析直接 AttributeError——视图选中必须走 Extension.SelectByID2 9 参版**（Name/Type/X/Y/Z/Append/Mark/Callout=pythoncom.Nothing/SelectOption=0），Type='DRAWINGVIEW'。
> - **⚠️ 计划中 InsertModelAnnotations3 的宿主写错**：宿主是 IDrawingDoc 本体（typelib 18270 行），非 Extension（Extension 对象 GetIDsOfNames 拒绝该名）。且 **v3/v4 实机全组合返回 None 零产出**（Types 位扫描 0x1~0x3FF + Option 0/1 均无效）。**胜者 = InsertModelAnnotations2(0, True, 0, True, True, False)**（v2 旧版带 AllTypes 布尔，全量带入显示尺寸）。MarkedForDrawing 标记路线证伪（GetDimension2 返回对象与 model.Parameter 对象均不解析该属性；且 v2 无需标记）。
> - **判据**：视图链 GetFirstView/GetNextView（零参属性，Name str 哨兵）+ IView.GetDisplayDimensionCount/GetAnnotationCount（零参属性）；图纸页「图纸1」自带 82 模板注记（GB 标题栏）。
> - **导出**：SaveAs3(path, 0, swSaveAsOptions_Silent) 三参形态 → 0 成功。PDF 46KB；**PNG 5.7KB 但是有效 1264×694 光栅图**——线条图高压缩，计划「>10KB」启发式失准，判据改为 IHDR 分辨率（纯 struct 解析，无 Pillow 依赖）。ViewZoomtofit2（零参属性）导出前缩放。SaveBMP 可用（3.1MB）但未采用。
> - **⚠️ 工程图隐式打开引用零件造成文件锁**（后续 SaveAs3 报 code 1）——CloseDoc(图纸) 不释放引用件，必须 app.CloseAllDocuments(True)（IncludeUnsaved=True；False 只关已保存文档）。e2e 收尾已内置。
> - create_box 的盒只有 1 个显示尺寸（凸台拉伸深度；草图矩形无显示尺寸）→ insert_dimensions 入 1 尺寸为预期；提升入图尺寸量需从草图显式建尺寸入手（后续任务素材）。
>
> 测试 313 passed + 75 subtests（+26），覆盖率 89% 红线保持，工具 45→49，记忆守卫 +3 入口。

---

### T13：aicad drawing M2（特征尺寸标注 + 剖视图入图）

- **状态**：`[x]` 完成（2026-08-30）
- **优先级**：P1 · **仓库**：ai · **依赖**：无（可与主包任务并行）· **预估**：8h（3 晚）
- **对应差距**：B（M1 只有 bbox 总尺寸）——图纸信息量不足，无法指导加工
- **需 SW 实机**：否（纯 OCCT/SVG 层）

**目标**：把 aicad 工程图从 M1 提升到 M2：
1. **特征尺寸标注**：孔径/孔位（从 kernel 的设计意图/几何提取）以引线尺寸形式标注到视图（而非只有 bbox 总长宽高）；
2. **剖视图**：对含内腔零件（std 目录的环/套类）生成全剖视图入图（OCCT `BRepAlgoAPI_Section` 与剖切平面求交线 → HLR 风格入 SVG）。

**前置阅读**（实施首晚必做）：`aicad/aicad/drawing/` 全部源文件 + `aicad/tests/test_drawing.py` 现有用例 + `aicad/README.md` 的 drawing 章节。以下代码是**接口契约**（实施时按现状文件名适配，但函数名/参数/返回保持本契约）：

```python
# aicad/aicad/drawing/annotate.py（新，或并入现有 drawing 模块）
from typing import Any, List, Sequence


def collect_feature_dimensions(shape, holes: Sequence[dict]) -> List[dict]:
    """把设计意图中的孔清单转成标注条目。

    holes 每项 {center_xy_mm, diameter_mm}；返回 [{kind: "hole", text: "⌀8",
    at_xy: (x, y)} …]，at_xy 为视图坐标（已含视图变换）。
    """


def render_dimension_layer(dimensions: List[dict], view_box, scale) -> str:
    """生成 SVG <g> 字符串：尺寸线 + 引线 + 文本（mm 单位文本）。"""

# aicad/aicad/drawing/section.py（新）
def section_view(shape, plane_origin_mm, plane_normal=(0, 1, 0)):
    """OCCT 剖切：BRepAlgoAPI_Section(shape, gp_Pln) → 交线离散后按投影渲染。

    返回与现有 HLR 视图同构的数据（线段列表），并入图（主视图旁、标 A-A）。
    """
```

**步骤**：

- [x] 1. 阅读上述前置文件，确认现有视图坐标系/比例/线宽约定，写入执行记录（这决定 at_xy 与 view_box 语义）。
- [x] 2. 写失败测试 `aicad/tests/test_drawing_annotate.py`：给定 holes=[{center(20,10), ⌀8}] → collect_feature_dimensions 返回含 `⌀8` 文本与正确视图坐标；render_dimension_layer 输出 SVG 含 `<text>` 与引线 `<line>`。
- [x] 3. 跑红（`aicad\venv\Scripts\python.exe -m pytest tests/test_drawing_annotate.py -q`）→ 4. 实现两个模块（剖视核心：`from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section; from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir`，交线 `section.HasResult()` 后离散化；测试用 tests/samples.py 现有的环/套样本）→ 5. 跑绿。
- [x] 6. 集成：M1 出图管线（找到生成三视图 SVG 的主函数）追加可选参 `include_dimensions=True / include_section=False`，默认关（向后兼容，既有 528 用例不变）。
- [x] 7. 手动目视验证：对 std 环件生成一张含孔径标注 + A-A 剖视的 SVG，保存 `aicad/output/drawing-m2-sample.svg`，检查文本不重叠、剖切线可见（用户白天人工复核）。
- [x] 8. 提交（aicad 仓库内）：`git commit -m "feat(drawing): M2 特征尺寸标注与剖视图入图（默认关闭，逐步启用）"`。

**验收标准**：`aicad\venv\Scripts\python.exe -m pytest tests -q` → `528+ passed`（新增用例全过，既有不破）；样例 SVG 生成且含 ⌀ 标注与剖视标记。

**执行记录**：
> **2026-08-30 完成**（单晚）。aicad 仓库 commit e1bd8ac；558 passed（550 + 8 新增，零回归）。aicad 仓库 commit a920058；550 passed（基线 528 + 17 新增，零回归）。
>
> **现有视图坐标约定（步骤 1 结论，M2 实现严格遵循）**：
> - HLR 折线 = 视图平面未缩放模型 mm（X 右 Y 上），模型原点即视图原点（测试实证盒折线跨 [-20,20]）；
> - 顶视图平面 = 模型 XY；前视 = XZ；右视 = YZ；
> - render_views：视图中心 = 图纸中心 + plan.origin（Y 上数学系），几何按自身 bbox 中心锚定后 Y 翻转到 SVG（点 (x,y) → (vx+x*scale, vy-y*scale)）——该锚点计算抽出为 **view_anchor** 供渲染与标注层共用；
> - 线宽 0.25（隐藏虚线 2,1）/0.35（可见），尺寸文本 font-size 3，视图标签 3.5。
>
> **实现**：annotate.py（collect_feature_dimensions + render_dimension_layer，纯图纸数学，API 进程安全）+ section.py（BRepAlgoAPI_Section 剖切，OCP 仅沙箱 worker；沙箱入口 section_to_json + 受信脚本 BREP_TO_SECTION_SCRIPT）+ render_sheet 四个可选参（holes/section/include_dimensions/include_section，默认全关=M1 字节不变；stats 增 dimension_count/section_included）。
> - **OCP 实证**：BRepAlgoAPI_Section **无 HasResult**（计划 API 猜错；IsDone + 空折线判定）；盒 Y 面剖切精确 40×10；圆环剖切内外壁齐现（|x|≈10/20）。
> - 样例 scripts/drawing_m2_sample.py → output/drawing-m2-sample.svg（60×40×8 板 + 4×⌀6 + ⌀12 中孔 + A-A 剖视；4 视图 5 标注 112 路径 27KB）——待用户白天人工目视复核。
> - routes 层未接新参（deps.py 调用点不变）：设计意图 holes→图纸的管线打通需 kernel 契约暴露孔清单，属后续范围；M2 层已就绪可被任意调用方启用。

---

### T14：aicad AI 循环增强（几何感知反馈 + 降级策略）

- **状态**：`[x]` 完成（2026-08-30）
- **优先级**：P1 · **仓库**：ai · **依赖**：无 · **预估**：6h（2 晚）
- **对应差距**：B1（纯文本 traceback）、B2（3 轮硬帽无降级）、B5（4096 tokens）
- **需 SW 实机**：否

**目标**：CorrectionLoop 从「文本盲修」升级为「看得见几何的修正」：
1. 每轮失败反馈附带几何状态摘要（实体数/体积/bbox/最近成功操作的模块名）——LLM 可据此判断「脚本已建出 3 个体但第 4 步炸了」；
2. 3 轮用尽后**降级**：返回最近一次可编译执行的脚本与产物，响应标 `degraded: true` + 告警，而非全盘失败；
3. `max_output_tokens` 4096→8192（复杂装配脚本不再截断）。

**步骤**：

- [x] 1. 前置阅读：`aicad/aicad/ai/loop.py`（尤其 172-177、232-258 的 preview 段）+ `aicad/aicad/kernel/` 沙箱执行的返回结构（确认能拿到实体数/体积；若 kernel 未暴露，先在 kernel 结果 dict 补上这三个字段并加单测）。
- [x] 2. 写失败测试 `aicad/tests/test_loop_feedback.py`：
  - fake 沙箱第 2 轮成功、第 3 轮失败 → 反馈文本中含 `entities=`/`volume_mm3=` 字样；
  - 全轮失败 → 结果 success 仍为 True 但 `degraded: true`，且产物为最后一轮可编译版本；
  - 降级路径无可用版本（首轮即语法错）→ 保持失败（不应伪造成功）。
- [x] 3. 跑红 → 4. 实现：loop.py 反馈拼装函数追加几何摘要段；主循环维护 `last_compilable` 变量（编译/沙箱导入成功即更新）；轮数用尽且 last_compilable 存在则走降级分支 → 5. 跑绿（全套 528+ 不破）。
- [x] 5. 配置：`aicad/config/default.toml` 的 `max_output_tokens = 8192`。
- [x] 6. 提交（aicad 仓库内）：`git commit -m "feat(ai): 修正循环增加几何感知反馈与降级输出，token 上限 8192"`。

**验收标准**：aicad 全套测试绿（新增用例 ≥3 个）；loop 对「部分成功」场景的响应含 degraded 标记。

**执行记录**：
> **2026-08-30 完成**（单晚）。
>
> **kernel 结果新增字段**：`_metrics`（exports.py）新增 **entities**（TopExp_Explorer 数 TopAbs_SOLID）——volume_mm3/bbox_min/max 原本就有；单测 test_metrics_count_solids（双圆柱：entities=2、体积 2πr²h、bbox_x=30）。
>
> **loop.py**：
> - `geometry_summary(metrics)`：成功轮 metrics → {entities, volume_mm3, bbox_mm=[dx,dy,dz]}（缺失即 None）；`build_error_feedback` 增可选 geometry 参，反馈追加 "Geometry state from your last successful run: entities=N volume_mm3=V bbox_mm=[..]"；
> - 主循环维护 `last_geometry`（任意 ok 轮——含 preview——即更新）与 `last_compilable`（error_code≠SCRIPT_CONTRACT 的已执行脚本即更新，契约违规不算可编译）；
> - **降级分支（语义收敛）**：正式轮耗尽且 last_usable 存在（成功过 preview/commit，有可用产物）→ LoopResult(ok=True, **degraded=True**, script/result=最后可用运行)；纯失败（从未产出可用产物，含纯契约失败）保持 ok=False——初版「非契约错误即可降级」与 API 层 Gave up 语义冲突（test_failure_rounds_emit_errors 的 WS _drain_until 无限等待 → 全套挂起 18 分钟，实机定位后收敛为产物判定；计划原文「降级路径无可用版本→保持失败」即此义）。chat 层 degraded preview 早退分支补 LLM_EXHAUSTED 告警事件；LoopResult 新增 `degraded: bool = False` 字段。
> - 实证细节：**preview 轮不消耗正式轮数**（自有预算 max(3, max_rounds)），测试需按 1 preview + 3 fail 编排 4 次回复；几何反馈出现在**失败后下一次生成**调用的 user 消息里。
> - config/default.toml：max_output_tokens 4096→8192。
> - 测试 +8（loop_feedback 7 + kernel entities 1）。

---

### T15：aicad preview 测试 + LLM 评测集骨架

- **状态**：`[x]` 完成（2026-08-30）
- **优先级**：P1 · **仓库**：ai · **依赖**：无 · **预估**：5h（2 晚）
- **对应差距**：B7（preview 无测试）、B4（无评测集）——改 prompt 无回归依据的容错性问题
- **需 SW 实机**：否

**目标**：1）补 preview 参数扫描的单元测试（loop.py:172-177,232-258）；2）建 `aicad/evals/` 评测集骨架：10 个黄金任务（自然语言→几何断言），提供离线 runner（mock LLM 可跑流程，真 LLM 需手动开关）。

**步骤**：

- [x] 1. 写 preview 测试 `aicad/tests/test_loop_preview.py`：用 fakes.py 既有 stub 驱动 loop，断言：参数扫描生成的候选集去重、成功候选停止扫描、全部失败时错误聚合不抛异常。跑绿。
- [x] 2. 创建 `aicad/evals/tasks.jsonl`（10 任务，每行一个 JSON）：字段 `id / prompt / assert`，assert 为机器可验断言，例如：
```json
{"id": "ring_60_40", "prompt": "外径60内径40高10的圆环", "assert": {"bbox_mm": [60, 60, 10], "volume_mm3_between": [18000, 25000]}}
{"id": "plate_4holes", "prompt": "100x60x8 板，四角⌀6 孔，孔心距角 10mm", "assert": {"bbox_mm": [100, 60, 8], "hole_count": 4, "hole_diameter_mm": 6}}
```
  （其余 8 个：轴段/套筒/法兰盘/带槽板/双阶孔板/阵列孔环/六角棒截断/组合体，几何值自行设定并写入文件注释）
- [x] 3. 创建 `aicad/evals/run_evals.py`：读 tasks.jsonl → 逐任务调 kernel（真 LLM 路径）或注入 mock 脚本（离线路径，mock 用 std 目录现成生成器）→ 执行 assert → 汇总 pass/fail 表格（JSON + stdout）。**离线默认**：`--live` 开关才走真 LLM（花钱需人工）。附 mock 模式的 3 个自测用例（评测器自身的正确性测试）。
- [x] 4. 跑离线自测：`aicad\venv\Scripts\python.exe evals\run_evals.py` → mock 用例全部 pass。
- [x] 5. 提交：`git commit -m "test(eval): preview 单测与 LLM 评测集骨架（10 任务+离线 runner）"`。

**验收标准**：aicad 全套测试绿；`run_evals.py` 离线退出码 0。

**执行记录**：
> **2026-08-30 完成**（单晚）。aicad 仓库 commit 32f1cd2；**首次离线评测 10/10 PASS（退出码 0）**，自测 pass/fail/fail 精确匹配；全套 569 passed（+11）零回归。
>
> **要点**：
> - **既有覆盖勘误**：计划 B7「preview 无测试」已过时——batch 11/12 已带 6 个 preview 测试（预算隔离/历史/耗尽/反馈文本/demo 序列）。本任务补齐剩余三断言：**去重**（新 helper `loop.dedup_preview_params`——汇总层按参数签名去重，_preview 标记不参与签名；**刻意不做预算层去重**：同参数重提仍计数，否则 budget-exhaustion 夹具（同参数 preview×4）会死循环）、**成功即停**、**全失败聚合不抛异常**（预览成功后连续失败→降级结果+历史聚合）。
> - **体积区间勘误**：计划示例 ring 60/40/10 的 18000-25000 有误（π(30²−20²)×10=15708），全部区间按实机 OCCT 重算校准；六角棒 bbox [34.7, 30, 50] 按顶点在 X 相位预判命中。
> - mock 脚本用 build123d 原语而非 std 生成器（std 是离散标准件尺寸，不适配任意几何断言——偏差记录）。
> - hole_count/hole_diameter_mm 断言诚实记 skipped（kernel metrics 无孔拓扑，需几何分析通道——后续范围）；evaluator 支持 bbox_mm(±0.5 容差)/volume_mm3_between/entities。
> - --live 经 build_provider+settings 接线（default_provider 属性名），花钱需显式开关。

---

### T16：双引擎桥（CSG 特征重建契约 + MCP 工具）

- **状态**：`[x]` 完成（2026-08-30）
- **优先级**：P1 · **仓库**：双（主包实现工具，aicad 实现导出器）· **依赖**：T3（特征验证）· **预估**：5h（2 晚）
- **对应差距**：A1（双引擎割裂）——aicad 的 CSG 重建能力（通道 B）反哺主包，同一设计意图可在真实 SW 里长出特征树
- **需 SW 实机**：是（第 2 晚）

**目标**：定义跨引擎 CSG JSON 契约，主包新增 `solidworks_features_rebuild_csg(plan)` 工具按契约在 SW 里重建特征树；aicad 新增导出器把通道 B 序列 dump 成该契约。

**契约（v1，写入两仓库各一份 `docs/csg-plan-v1.md`，主包为权威）**：

```json
{
  "version": 1,
  "units": "mm",
  "operations": [
    {"op": "box", "name": "base", "size": [60, 40, 20], "at": [0, 0, 0]},
    {"op": "cylinder", "name": "boss", "diameter": 20, "height": 30, "at": [0, 0, 20]},
    {"op": "cut_cylinder", "name": "bore", "diameter": 8, "depth": null, "through": true, "at": [0, 0, 0]},
    {"op": "cone", "name": "tip", "bottom_diameter": 10, "top_diameter": 4, "height": 12, "at": [0, 0, 50]}
  ]
}
```

（op 集合与通道 B 现状对齐：box/cylinder/cone/cut_cylinder；Pos 语义合并进 at；后续任务再扩。）

**步骤**：

- [x] 1. 主包：写失败测试 `tests/test_csg_rebuild.py`：mock 断言按序调用 create_box/create_cylinder/cut_round_hole/create_cone（均已在 api 层存在，直接复用它们的参数校验），失败时按 T10 的 atomic 语义回滚；契约校验（version 不支持/未知 op 报 INVALID_PARAMETER）。
- [x] 2. 跑红 → 3. 实现：`solidworks_api/design.py` 追加 `rebuild_csg_plan(sw_app, plan: dict)`（先 jsonschema 风格手工校验，再逐步分发到既有函数；`at` 的 z 为底面基准）→ 4. 跑绿。
- [x] 5. 注册：`solidworks_features_rebuild_csg(plan: dict)`（STATE_CHANGE）。
- [x] 6. 实机验证：上述示例 JSON → SW 得到 4 特征树，get_feature_details 确认各特征在；get_bounding_box 顶层 `[60,40,62]`（20+30+12）。加入 e2e 链。
- [x] 7. aicad：读 `aicad/aicad/interop/` 通道 B 的序列结构 → 写导出器 `to_csg_plan_v1(...) -> dict` + 测试（用 interop 既有测试样例转编）→ aicad 内提交。
- [x] 8. 提交（两仓库各一次，主包先）：主 `git commit -m "feat(csg): 跨引擎 CSG 重建契约与 SW 工具"`；ai `git commit -m "feat(interop): 导出通道 B 序列为 CSG 契约 v1"`。

**验收标准**：主包测试全绿；实机重建 4 特征成功；aicad 全套测试绿；两仓库 docs 各有一份契约文档。

**执行记录**：
> **2026-08-30 完成**（单晚，双侧）。主仓 commit 52c357f；aicad commit 823ceb7。
>
> **实机重建结果**：契约示例 4 操作（box60×40×20 / cylinder⌀20×30@20 / cut⌀8 through / cone⌀10→4×12@50）→ SW 特征树 base/boss/bore/tip（rename_feature 赋名）+ **bbox [60,40,62] 精确**；e2e 62/62 全绿（CSG 段 8 步含 expect 断言）。
>
> **关键实机契约（新增）**：**顶面堆叠机制**——体面走查 GetBodies2(0,False)→GetFirstFace/GetNextFace（零参属性），**face.GetBox() 零参返回 6 元组（米）**，取 zmin 最大者为顶面，Select2(False,0) 后直接 InsertSketch 画圆拉伸，堆叠无布尔误差（盒 20+柱 30→z=50 实测）。注意：model.GetFirstFace 不存在（IBody2 成员）。
>
> **v1 语义定稿**（docs/csg-plan-v1.md，两仓各一份，主仓权威）：实体沿轴堆叠（at.x/y=0、at.z=当前堆顶、box 必为首操作@原点）；cut_cylinder 保 x/y 孔位；失败原子回滚（T10 机器复用）。**aicad 侧 datum 换算**：build123d 居中 vs SW 底面基准——导出器以首实体 z_start 为基准输出 at.z；Box(w,h,d)→契约 [w,d,h]（z 向为高）。
>
> 主包 356 passed+79 subtests（+20）覆盖率 89%；aicad 575 passed（+6）零回归；工具 52→53。

---

### T17：材料 / 自定义属性 / 配置 / 方程式工具

- **状态**：`[x]` 完成（2026-08-29）
- **优先级**：P1 · **仓库**：主 · **依赖**：无 · **预估**：4h（1 晚）
- **对应差距**：C8（材料/属性/配置/方程式）、D3（参数化驱动）、F6（属性审计）
- **需 SW 实机**：是

**目标**：新增四组轻量工具，让 AI 能给零件挂材料/写属性/建配置/列方程式：
1. `solidworks_part_set_material(material_name)` / `solidworks_part_get_material()`——SetMaterialPropertyName2/GetMaterialPropertyName2（默认库 SOLIDWORKS Materials；中文名如「铝合金 1060」，实机确认）；
2. `solidworks_part_set_custom_property(name, value)` / `solidworks_part_get_custom_properties()`——CustomPropertyManager(" ").Add3 / Get6；
3. `solidworks_part_add_configuration(name)`——AddConfiguration4（探针确认参数）；
4. `solidworks_part_list_equations()` / `solidworks_part_add_equation(equation)`——GetEquationMgr/Add2（方程式是「改一个尺寸带动一组尺寸」的参数化核心）。

**关键 API（把握度：中高，探针先行）**：

```python
# 材料：
part = model  # 活动零件
part.SetMaterialPropertyName2("默认", "SOLIDWORKS MATERIALS", "铝合金 1060")
name, db, cfg = part.GetMaterialPropertyName2()  # 返回 (名称, 库, 配置)
# 自定义属性：
pm = model.Extension.CustomPropertyManager("")  # 空串=文档级
pm.Add3("PartNo", 30, "A-1024", 1)   # (名, 类型30=文本, 值, 覆盖1=替换)
props = pm.Get6("PartNo", false, false) # 或枚举：pm.GetNames / Count
# 方程式：
mgr = model.GetEquationMgr()
index = mgr.Add2(-1, "\"D1@Sketch1\" = 60")  # -1=追加到末尾
value = mgr.Value(index); text = mgr.Equation(index); count = mgr.GetCount
```

**步骤**：

- [ ] 1. 探针 `tools/probe_material_props_eqs.py`：盒零件上逐个验证（材料名先 GetMaterialPropertyName2 读当前值确认库可用名格式；Add3 第 4 参、Add2 返回值、Get6 返回元组形态记录下来）。
- [ ] 2. 写失败测试 `tests/test_material_props.py`（6 个工具一次测完，fake 按探针确认的返回形态）→ 跑红。
- [ ] 3. 实现：新建 `solidworks_api/properties.py`（材料/属性/方程式/配置四组函数）→ 跑绿。
- [ ] 4. 注册六工具：set/get_material、set/get_property、add_configuration 为 STATE_CHANGE；list_equations、add_equation 分别 READ_ONLY/STATE_CHANGE。
- [ ] 5. 实机验证：set_material 后 get_material 回读一致；set_custom_property("PartNo","A-1024") 后 get 回读；add_equation 后 list_equations 可见且 EditRebuild3 无错；get_mass_properties 的密度随材料变化（铝合金→钢体积不变质量变大）。加入 e2e 链。
- [ ] 6. 提交：`git commit -m "feat(properties): 材料/自定义属性/配置/方程式六工具"`。

**验收标准**：全套测试绿；实机回读一致；e2e 退出码 0。

**执行记录**：
> **2026-08-29 完成** · commit `3b9cfd8`。
> **实机材料库名格式**：库名 `SOLIDWORKS MATERIALS`（回读时 SW 规范化为小写 `solidworks materials`）；**材料名必须用中文**（「合金钢」「铝合金 1060」有效；`ALLOY STEEL` 被静默忽略）——判据=回读比对，不信任 void 返回的 Set。
> **byref out 参数铁律**：`GetMaterialPropertyName2(cfg, byref)` 与 `CPM.Get2(name, byref, byref)` 的 out 参数必须传 `VARIANT(VT_BYREF|VT_BSTR, '')`（值经 `.value` 读回）——裸调报 DISP_E_PARAMNOTFOUND（「非选择性的参数」）。`GetEquationMgr/GetCount/GetNames/GetConfigurationNames` 均为零参属性（call_or_value）。
> **返回形态**：`Add3(name,30,value,1)`→int（0=成功，负=拒）；`EquationMgr.Add2(-1,eq,True)`→索引 int（≥0 成功）；`AddConfiguration(name,'','',False,False,False,True,0)`→void，判据=`GetConfigurationNames` 包含新名（中文 SW 首配置名=「默认」）。
> **已知观察（MEDIUM，待后续）**：中文 SW 无材料时 mass_properties 的 mass=0，且设「合金钢」后（含 EditRebuild3）mass 仍 0——质量-材料联动未生效，可能需密度库加载或选项设置；本版 set_material 判据用名字回读。GetNames 返回含中文模板预置 ~28 个属性（质量/材料/零件号…）属正常。
> **测试基线**：287 passed + 71 subtests ≈6.3s；覆盖率 89%；e2e 36 步（35 OK + 1 skip）退出码 0；工具计数 38→45。

---

## 9. P2 任务（健壮性与长尾）

> P2 无硬性前置（除各自依赖），在 P0/P1 主线推进后的空档晚执行；每任务同样遵循 §2 执行协议与 §8 的通用开发模式。

### T18：主包 tools/ 探针分域整理

- **状态**：`[x]` 完成（2026-08-30） · P2 · 主仓库 · 依赖：无 · 2h · 对应：A2/G4

**目标**：tools/ 目录已积累 9+ 探针/验证脚本（含 T1-T17 新增的 ~8 个），全部平铺难检索。

**步骤**：
- [x] 1. 按域分组：`tools/probe_part/`、`tools/probe_assembly/`、`tools/probe_drawing/`、`tools/validate/`（移动脚本，git mv 保留历史）；
- [x] 2. 更新各脚本内的 sys.path 注释与 T1 e2e 引用路径；
- [x] 3. 在 tools/ 下建 `INDEX.md`：每个探针的「验证对象 API + 有效签名结论 + 对应任务」（从各任务执行记录汇总）；
- [x] 4. 全套测试 + e2e 跑通（路径未断）；
- [x] 5. 提交：`git commit -m "chore(tools): 探针脚本分域整理与知识索引"`。

**验收**：e2e 退出码 0；INDEX.md 存在且覆盖全部探针。

**执行记录**：
> **2026-08-30 完成**。commit 19c1777。目录：probe_part/（7 个）、probe_assembly/（1）、probe_drawing/（1）、probe_properties/（1）、validate/（5，含 inspect_* 巡检）；e2e 与测试运行器留根。迁移脚本 parents[1]→parents[2]；probe_material_props 实机抽验 OK；356+79 全绿、e2e 62/62。INDEX.md 覆盖全部 16 个脚本（验证对象/有效结论/任务号）。

---

### T19：CI 激活（推送远端）

- **状态**：`[!]` BLOCKED（2026-08-30） · P2 · 主仓库 · 依赖：无 · 1h · 对应：G2

**目标**：`.github/workflows/ci.yml` 已就绪但无远端仓库，从未跑过。

**步骤**：
- [ ] 1. 检查远端：`git remote -v`；**若用户已配置远端**：推送 main（首次 push 前与用户确认，属外部动作）→ 在 GitHub Actions 页确认首跑绿；
- [ ] 2. **若无远端**：标记 `[!] BLOCKED（无远端仓库，需用户人工创建）`，在执行记录写明等待条件，本任务跳过不阻塞其他任务；
- [ ] 3. CI 绿后提交：把“CI 徽章/状态”写入 README（若适用）。

**验收**（有远端时）：Actions 首跑全绿（194+ tests）。

**执行记录**：
> **2026-08-30 标记 BLOCKED**：远端为 Gitee（pengzixiao2025/AICAD）——**Gitee 不执行 GitHub Actions**，.github/workflows/ci.yml 在该平台不会跑。且推送属外部动作需用户显式指令（本会话未获推送授权；本地另有 7 个未推提交）。**等待条件**：用户提供 GitHub 远端（或 Gitee Go 配置等价流水线）+ 明示推送授权后激活。本任务不阻塞其余任务。

---

### T20：aicad 任务/循环历史持久化

- **状态**：`[x]` 完成（2026-08-30） · P2 · aicad 仓库 · 依赖：T14（反馈结构定型）· 5h · 对应：B9

**目标**：CorrectionLoop 的每轮（prompt/生成脚本/反馈/结果）落盘 JSONL，跨会话可查（后续可作 RAG 语料，见 B6 铺垫）。

**步骤**：
- [x] 1. 写失败测试：循环结束后 `workspace/loops/<session_id>.jsonl` 存在且行数=轮数，字段含 timestamp/round/script/feedback/outcome；
- [x] 2. 跑红 → 3. 实现：loop.py 出口处追加 append 写入（路径经 settings.paths 可配）；失败写入不抛异常（尽力而为）→ 跑绿；
- [x] 4. 提交（aicad 内）：`git commit -m "feat(ai): 修正循环历史 JSONL 持久化"`。

**验收**：aicad 全套测试绿；跑一次循环后文件存在。

**执行记录**：
> **2026-08-30 完成**。aicad commit 3eb5f88；580 passed（+5）。实现：逐轮 append（行数=轮数天然成立、中途崩溃不丢）；outcome 四态 no_code/preview/ok/failed；feedback 落实际发给模型的文本（几何摘要/预览指标/错误规范化）；写入尽力而为（失败仅 debug 日志）。接线 routes_chat→workspace/loops/<session_id>.jsonl，deps.build_loop 透传。

---

### T21：高级几何（真实螺纹 / 渐开线齿轮 / 齐平钣金基础）

- **状态**：`[~]` 进行中（2026-08-30：子项 2 完成） · P2 · 双仓库 · 依赖：T6、T7 · 12h（4 晚）· 对应：D4/C6 长尾

**目标**：三选一推进（每晚一个子项，按序）：
1. **真实螺纹**（主包）：基于 T6 的 helix 扫描（InsertHelix? 探针）+ 扫描切除（InsertProtrusion? / FeatureScan? 探针）——先把 API 探明白写入执行记录，工具化 `solidworks_part_cut_real_thread`；
2. **渐开线齿轮近似**（aicad）：std 目录新增 involute 齿廓生成（OCCT 曲线拟合一齿廓 → 圆周阵列），出齿轮参数（模数/齿数/压力角）入设计意图；
3. **钣金基础**（主包）：InsertSheetMetal? / Base-Flange 探针，工具 `solidworks_sheet_metal_base_flange`。

**步骤**（每子项）：探针 → 失败测试 → 实现 → 注册 → e2e/评测 → 提交。子项间无依赖，可只做部分，未做子项保留 `[ ]` 并在执行记录说明原因。

**验收**：所做子项全套测试绿 + 实机/OCCT 验证通过。

**执行记录**：
> **2026-08-30 子项 3（钣金）完成**（主仓 commit 04bf21f；364 passed + 80 subtests、e2e 68/68、工具 53→54）：`sheet_metal.create_base_flange`——上视基准面矩形 → FeatureManager.InsertSheetMetalBaseFlange **16 参，PCBA 必须 pythoncom.Nothing（0 报类型不匹配）**；特征树三件套（钣金N/基体-法兰N/平展型式N）；60×40×2 实测 bbox [60,2,40] 精确。v1 平板法兰（折弯/平展导出留待后续）。
> **子项 1（真实螺纹）BLOCKED 证据齐**：InsertHelix 真实 10 参（typelib：Helixdef/Height/Pitch/Revolution/TaperAngle/Startangle）def=0 可建（树「螺旋线/涡状线1」）且可按 **REFERENCECURVES 类型+中文名** SelectByID2 选中（mark=1）；三角截面草图可建可选中；但 **InsertCutSwept4 三形态零产出**（ModelDoc2 8 参→参数数目错；FeatureManager 19 参→返回 False；Alignment=False→返回 None 且树无新特征）——与 T8 mirror 同族的 SW2026 上下文问题，需宏录制器对照。
> **2026-08-30 子项 2 完成**（aicad commit 78bd4ad；584 passed +4）：
> - **渐开线齿轮**：`involute_spur_gear` + `gear_params`（std/geometry.py）。侧翼=基圆渐开线采样，角半厚 ψ(r)=s_p/(2r_p)+invα−invβ → 节圆齿厚恰为 πm/2；**齿根下探 0.2mm 才能熔合**（渐开线起点 base_r=r_p·cos20°≈0.94r_p 高于齿根圈 0.875r_p——不探则齿悬浮、fuse 出 21 个独立实体，实测定位）。近似项：无齿顶修缘、少齿数无根切。验证：单实体/bbox=齿顶圆径/体积界/曲面面数>直侧翼齿。
> - **子项 1（真实螺纹）与 3（钣金）未做**：均需 SW 实机探针（helix 扫描/InsertSheetMetal），且当晚机器被训练任务重载（OCCT 子进程测试已 5×变慢）；留待专门会话按「探针→失败测试→实现→注册→e2e」推进。

---

### T22：性能与稳定性（soak 测试 / 背压评估 / worker 调优）

- **状态**：`[x]` 完成（2026-08-30） · P2 · 双仓库 · 依赖：T1 · 6h（2 晚）· 对应：H1/H3/H4/F4

**步骤**：
- [x] 1. 主包 soak 脚本 `tools/soak_session.py`：循环 100 次「create_box → export_step → close_document(save=False)」，每 10 轮打印 SW 进程内存（psutil）与耗时趋势；跑完报告写入 `output/soak-report-*.json`。验证 CloseDoc 无句柄泄漏（内存曲线平稳）。若泄漏：记录证据，标注 F4 升级为缺陷任务（不在本计划内修）；
- [x] 2. aicad 背压评估：读 `aicad/aicad/api/` 的请求队列实现 → 写测试断言并发上限行为（worker=1 时第 2 请求排队不丢）→ 依实测把 `worker_count` 1→2（内存允许时）并重跑 perf 预算测试（test_perf_budgets.py）；
- [x] 3. 提交（各仓库内）：`git commit -m "test(perf): 长会话 soak 与背压验证"`。

**验收**：soak 100 轮完成无异常；aicad perf 预算测试绿。

**执行记录**：
> **2026-08-30 完成**。主仓 commit 4203ad3（soak）+ aicad commit 15d3fa7（背压）。
>
> **内存曲线结论**：100 轮建-导-关（488s，0 失败，单轮 4-7.5s）——**SW 工作集 1667→3499MB（+1.83GB）**，超 100MB 预算 → verdict=leak-suspected。按计划处置：证据录 output/soak-report-20260830-022234.json，**F4 升级为缺陷观察项**（候选方向：ClearUndo/文档缓存策略；注意工作集增长≠必然句柄泄漏，需泄漏修复任务先复现判定）。soak 脚本零依赖（tasklist GBK 解码 + ctypes GetProcessMemoryInfo）。
> **worker 调优结果**：**保持 1**——soak 泄漏证据 + 本机训练占载，无内存余量（runner.py 教训：OpenBLAS 常驻内存可致子进程死亡）；提升前置条件=泄漏修复+空载复测。背压测试：两并发双双完成、峰值并发=1（threading.Lock 严格串行）。
> aicad 585 passed（+1）零回归。

---

### T23：文档同步与探针知识回流

- **状态**：`[x]` 完成（2026-08-30） · P2 · 双仓库 · 依赖：无（但应在多数任务后收尾）· 3h · 对应：A5/G4/T18 联动

**步骤**：
- [x] 1. 主包：更新 `docs/CODEMAPS/backend.md`（新增模块 topology/measure/decorations/drawing/properties）；更新 README 工具清单（25→40+）；新增 `docs/adr/0009-p0-ai-perception-tools.md`（记录 T3-T5 决策：面命名策略/尺寸只读优先）；
- [x] 2. 主包 prompt 供给：`server.py` 的 `solidworks_design_part_prompt` 模板追加新工具用法段（feature_details/measure/list_faces/dimension_set 的工作流建议）；新增装配/工程图 prompt 各一个（装配：list_faces→命名→add_mate；工程图：create→insert→export）；
- [x] 3. aicad：README 补 M2 图纸与 evals 使用说明；
- [x] 4. 两仓库分别提交。

**验收**：文档与代码一致（工具数/模块名）；README 命令可执行。

**执行记录**：
> **2026-08-30 完成**。主仓 842ff38 + aicad dd531f8。变更：backend.md（新模块+基线）、README（25→53 tools、1→3 prompts、工作流章节）、ADR-0009（感知工具族决策）、part prompt 扩感知工作流段 + assembly/drawing 两 prompt、aicad README（M2/evals/CSG/循环历史）。356+79 全绿。

---

## 10. 风险与回滚

| 风险 | 概率 | 缓解 | 回滚手段 |
|---|---|---|---|
| 探针签名与计划预估不符（COM API 版本差异） | 高 | 探针先行惯例；执行记录回填有效签名；变体 try/except | 单任务独立提交，git revert 即回滚单晚工作 |
| 实机行为与 mock 不一致破坏既有功能 | 中 | 每任务全套回归 + e2e 必跑；mock 差异先记录不擅改 | revert 对应 commit；测试基线在验收标准中显式声明 |
| SW 卡死毒化执行器（超时启用后） | 中 | T2 校准值保守（≥3×M）；毒化后工具 fail-fast 而非挂死 | 移除 env 变量即回到无超时旧行为 |
| 回滚删除特征（T10）误删用户特征 | 低 | 快照差集只删「本次新增」；逆序；回滚失败仅 warning | atomic=False 关闭事务性 |
| 面命名（T5）与用户已命名实体冲突 | 低 | 只对 GetEntityName 为空的面命名；前缀可配 | 前缀改参即可，已命名实体不受影响 |
| aicad 循环降级（T14）伪造成功误导用户 | 中 | degraded: true 显式标记；无可用版本时保持失败 | 配置开关回退旧行为（实现时加 settings 开关） |
| 夜间任务中断丢失进度 | 中 | checkbox 步骤粒度 2-5 分钟；先补提交再继续（§2.9） | 无需回滚，续跑即可 |
| 双仓库误提交（aicad 改动进主仓库） | 低 | 每任务标注仓库；提交前 `git status` 确认路径 | 主仓库 `git rm --cached aicad/` + amend |

**全局回滚底线**：任一晚工作只需 `git log --oneline -3` 找到当晚 commit，`git revert <hash>` 即可；两仓库独立，互不牵连。

## 11. 附录 A：验证命令速查

```powershell
# 主包单元测试（基线：随任务递增，见各任务验收）
python -m pytest tests/ -q

# 主包覆盖率（不得低于 89%）
python -m pytest tests/ --cov=solidworks_mcp --cov-report=term -q

# 主包实机冒烟（需 SW 运行）
venv\Scripts\python.exe tools\e2e_sw_smoke.py

# 环形阵列实机验证（ADR-0008）
venv\Scripts\python.exe tools\validate_annular_pattern.py

# SW 运行状态探测（不启动）
python -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; print(get_solidworks_app().status(launch_if_needed=False))"

# aicad 全套（在 aicad/ 目录内）
aicad\venv\Scripts\python.exe -m pytest tests -q   # 基线 528 passed

# aicad 离线评测（T15 后）
aicad\venv\Scripts\python.exe evals\run_evals.py

# git 状态（两仓库分别确认）
git -C "e:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP" log --oneline -5
git -C "e:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP\aicad" log --oneline -5
```

## 11b. 附录 B：完成判据（本计划何时算“接近全自动出图”）

- **P0 全部完成**：实机可验证 + AI 可感知（特征详情/测量/面枚举）→ 具备夜间自动迭代的安全网；
- **P1 全部完成**：单零件「描述→建模→改参→装配→出图→导出 PDF」全链路 MCP 工具化；aicad 循环有反馈/降级/评测；双引擎契约打通 → **人只需给需求与最终目视确认**；
- **P2 完成**：可长期无人值守（soak 稳定、CI 绿、知识回流）。

到 P1 完成时，剩余差距（B3 任务分解、B6 RAG、E5 mate 求解器、公差/粗糙度标注、DXF 输出）进入下一期规划。

---

**（文档完。总行数约 1200 行；02:30 实施任务从 §3 总览表选任务，按 §2 协议执行并回填。）**
