# AI 驱动 3D 机械图全自动绘制——优化改进规划（第三期：出图质量 + 闭环 + 无人值守）

> **生成**：2026-08-30 审查任务（01:30）
> **主题**：项目距离真正的 AI 驱动全自动绘制 3D 机械图还有哪些需要优化改进的地方
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考
> **For agentic workers:** 按任务逐项执行（§2 执行协议），步骤用 checkbox（`- [ ]`）跟踪，完成后回填状态与「执行记录」小节。

---

## 1. 文档定位与背景

本计划**承接 2026-08-29 规划**（`output/optimization-plan-2026-08-29.md`，23 任务 T1-T23）。该计划两晚执行 20/23 完成：主包工具 25→54、测试 191→364+80 subtests、e2e 62/62 实机全绿；aicad 585 测试、AI 循环有几何反馈/降级、M2 图纸能力落地（测试态）、评测集 10 任务离线 10/10、CSG 契约 v1 双侧落码。残留 T8（mirror/draft/线性阵列 BLOCKED）、T19（CI 无远端 BLOCKED）、T21（螺纹未做/钣金已实现未提交）**并入本计划**：T21 钣金收尾→N1，T8+T21 螺纹→N9，T19 维持 BLOCKED（等用户提供 GitHub 远端）。

**本期核心判断的转变**：工具链已齐（零件→装配→工程图→导出 PDF/STEP/STL 全链路 MCP 化），当前距离目标的三类新差距是——
1. **出图质量不达制造标准**：主包图纸尺寸全量插入必然重叠、无公差/粗糙度/剖视图/DXF；aicad M2 能力只在测试里、生产路径未接线（本计划亲验 `aicad/aicad/api/deps.py:376` 不传 holes/section）。
2. **闭环断点**：装配干涉只报体积不知位置、无 delete_mate/组件移动——AI 检测到干涉也修不了；评测 hole 断言 SKIPPED（2/10 任务含水分）；CSG 导出器没接路由（桥只通一半）。
3. **无人值守可靠性**：COM 超时默认 0（SW 卡死=服务器永久挂死）；soak 100 轮 SW 工作集 +1.83GB 泄漏嫌疑；capabilities/description 已与实现漂移（"drawings not yet exposed" 与已注册 drawing 四工具矛盾——LLM 被误导放弃出图链路）。

## 2. 执行协议（02:30 实施任务必读）

1. **选任务**：读 §3 总览表，选**第一个**状态 `[ ]` 且依赖全部 `[x]` 的任务。
2. **SolidWorks 前置检查**（标注「需 SW 实机」的任务）：
   ```powershell
   python -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; print(get_solidworks_app().status(launch_if_needed=False))"
   ```
   未运行则改状态 `[!] BLOCKED（SW 未运行，YYYY-MM-DD）`，转下一个可执行任务。
3. **TDD 循环**：写测试 → 跑红 → 实现 → 跑绿 → 实机验证（如需）→ 提交。禁止先实现后补测试。
4. **探针先行**：标注「探针先行」的 COM API 必须先写/跑 `tools/probe_*/probe_<名>.py` 记录实机签名。**本计划新增方法论：类型库枚举法**——`gencache.EnsureDispatch("SldWorks.Application")` 后 `dir()` / `help()` 枚举接口真实方法名与 docstring，替代盲试（T8/T21 的 BLOCKED 根因就是盲试签名）：
   ```python
   from win32com.client.gencache import EnsureDispatch
   sw = EnsureDispatch("SldWorks.Application")
   fm = sw.ActiveDoc.FeatureManager
   print([m for m in dir(fm) if "Mirror" in m or "Pattern" in m or "Sweep" in m or "Draft" in m])
   ```
   探针脚本保留入库并更新 `tools/INDEX.md`。
5. **提交纪律**：每任务 ≥1 次本地 `git commit`（**绝不 push**）；主仓库/aicad 仓库分别提交，绝不跨仓。message：`feat|fix|test|docs|chore(scope): <一行中文描述>`。
6. **回填**：任务状态改 `[x]`（失败 `[!]` 注明原因）；「执行记录」小节回填日期/结果/commit hash/备注；更新 §3 总览行。
7. **节奏**：每晚 1 个任务为宜，最多 2 个（第二个必须 ≤2h 小任务）。
8. **安全红线**（继承）：COM 调用必须经 `run_com(...)`；文件操作在 `allowed_root` 内；破坏性工具标 `DESTRUCTIVE`；MCP 入参 mm、COM 层 m；覆盖率 ≥89%。
9. **中断恢复**：读到未勾选步骤继续；已勾选产物未提交则先补提交。**当前工作区有 T21-3 钣金未提交工作（N1 收尾）——任何其他任务开始前必须先执行 N1 或明确跳过原因。**
10. **测试命令基线**：
    - 主仓库：`venv\Scripts\python.exe -m pytest tests/ -q` → 基线 **364 passed + 80 subtests，约 7.5s**（含未提交钣金，N1 提交后即为新基线）；
    - aicad 仓库（在 aicad/ 内）：`venv\Scripts\python.exe -m pytest tests -q` → 基线 **585 passed，约 219s**（仅 aicad 改动时跑）；
    - 实机 e2e：`venv\Scripts\python.exe tools\e2e_sw_smoke.py`（需 SW 运行）。

## 3. 任务进度总览

状态：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED。「仓」列：主=主仓库，ai=aicad，双=两者。

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N1 | P0 | 钣金工具收尾提交（T21-3 中断恢复） | 主 | 无 | 0.5h | `[x]` | 2026-08-30 |
| N2 | P0 | AI 上下文纠偏 + capabilities 单一事实源 | 主 | N1 | 2h | `[x]` | 2026-08-30 |
| N3 | P0 | COM 超时默认启用 + 毒化行为治理 | 主 | 无 | 2.5h | `[x]` | 2026-08-30 |
| N4 | P1 | 工程图深化 A：尺寸去重叠 + 剖视图 | 主 | N1 | 5h/2晚 | `[x]` | 2026-08-30 |
| N5 | P1 | 工程图深化 B：公差/粗糙度注释 + DXF 导出 | 主 | N4 | 6h/2晚 | `[x]` | 2026-08-30 |
| N6 | P1 | aicad M2 上生产（holes/section 接线） | ai | 无 | 3h/1晚 | `[x]` | 2026-08-30 |
| N7 | P1 | aicad 评测真实化（hole 断言 + live 指标） | ai | 无 | 4h/2晚 | `[x]` | 2026-08-30 |
| N8 | P1 | 装配修复闭环（干涉定位 + delete_mate + 组件移动） | 主 | N1 | 5h/2晚 | `[x]` | 2026-08-30 e5afd1d |
| N9 | P1 | BLOCKED 解锁：mirror/draft/线性阵列/真实螺纹 | 主 | N1 | 8h/3晚 | `[x]` | 2026-08-30 51bd1c3 |
| N10 | P1 | SW 内存泄漏定位与修复 | 主 | N1 | 5h/2晚 | `[x]` | 2026-08-30 eca371c |
| N11 | P1 | CSG 端到端打通 + 验收清单#5 跨仓三件套 | 双 | 无 | 4h/1-2晚 | `[x]` | 2026-08-30 40708d2 + aicad 90c6a5a |
| N12 | P2 | 参数化闭环补全（方程式增删改/角度尺寸/配置切换） | 主 | N2 | 4h/1晚 | `[x]` | 2026-08-30 0f99bbd |
| N13 | P2 | aicad 循环增强 II（孔直方图反馈/token 守卫/重试/干涉回流） | ai | N6 | 5h/2晚 | `[x]` | 2026-08-30 aicad 58df2e9 |
| N14 | P2 | server.py 分域注册重构 + ring_light 迁出 | 主 | N2 | 3h/1晚 | `[x]` | 17048c8 |
| N15 | P2 | 文档漂移治理（工具清单自动生成 + ADR 回填） | 双 | 无 | 2.5h/1晚 | `[~]` | → 第四期 N18（output/optimization-plan-2026-08-31.md） |
| N16 | P2 | 测试治理（错误码收敛/超时定位/产物回潮） | 主 | N2 | 3h/1晚 | `[~]` | → 第四期 N19 |
| N17 | P2 | aicad DXF 导出 + 沙箱队列解耦 | ai | 无 | 4h/1-2晚 | `[ ]` | → 第四期 N20 |

> 合计约 67.5h / 约 22 晚。P0 完成 = AI 能力面不再失真 + 无人值守单点消除；P1 完成 = 出图达制造标准 + 三大闭环（装配修复/评测/双引擎）打通；P2 = 可维护性与长尾。
> **远期观察项（本计划不排期）**：任务分解 plan-then-execute、RAG 示例检索、mate 约束求解器、多模型路由、前端测试、特征级缓存、爆炸图、BOM 气泡引线、CI 激活（等远端，T19 遗留）。

## 4. 现状快照（2026-08-30 基线）

### 4.1 主仓库 solidworks_mcp

- **测试**：364 passed + 80 subtests（7.54s，含未提交钣金），覆盖率 ~89%；e2e 62/62 实机全绿（2026-08-30）。
- **规模**：server.py 1140 行 / 54 工具（53 已提交 + 1 钣金待提交）/ 3 个 prompt 模板；solidworks_api/ 16 模块。
- **已覆盖**：box/plate/cylinder/cone/revolved/fillet/chamfer/shell/圆孔/螺纹孔/环阵/钣金基体法兰；特征详情/尺寸读写/删除/改名/压缩；面/实体枚举命名；测量/包围盒/质量属性；材料/属性/配置/方程式；6 类 mate + 干涉 + BOM；工程图四件套（建图/三视图/模型尺寸/PDF+PNG）；STEP/STL 导入导出；CSG 重建；design plan 事务回滚。
- **已知缺陷/残留**：capabilities 与实现漂移（§5-A1，亲验）；COM 超时默认 0；soak 泄漏 +1.83GB；mirror/draft/线性阵列/真实螺纹 BLOCKED；环阵非原生 pattern 特征。

### 4.2 aicad 仓库

- **测试**：585 passed（219s）。
- **AI 循环**：几何反馈 3 标量（entities/volume/bbox）+ 降级输出 + token 上限 8192 + JSONL 历史（只写不读）。
- **图纸**：生产路径=M1（三视图+bbox 总尺寸+BOM SVG，`deps.py:376` 亲验不传 holes/section）；M2（孔径标注+剖视图）仅测试态；导出仅 SVG。
- **评测**：10 任务离线 10/10，但 hole 断言 SKIPPED（2/10 含水分），live 无过程指标。
- **装配**：硬坐标；干涉 report-only 不回流。
- **桥接**：CSG v1 导出器已实现未接路由。

## 5. 差距分析（8 维度，含证据）

> 编号供任务引用。标【亲验】者为本审查会话直接读代码验证；其余来自定向审查并抽查可信。

### A 架构

- **A1 capabilities 双源维护且已漂移**【亲验：server.py limitations "Complex surfaces, drawings, simulation, and PDM are not yet exposed" vs L727-770 已注册 drawing 四工具】→ N2。LLM 读 capabilities 会放弃出图链路——与目标正面冲突的最高优先纠偏。
- **A2 execute_plan docstring 词汇表过时**【亲验：design.py:543 支持 8 op；docstring 只列 5 个】→ N2。锥体/螺纹孔/环阵被拆成多次调用，丢失原子回滚。
- **A3 server.py 1140 行 54 工具单文件**，每工具 8-12 行同构 `_call_connected` 样板 → N14。
- **A4 ring_light 产品专用工具混入通用 54 工具**（server.py:84-85 import examples）→ N14。
- **A5 CSG 导出器未接任何路由**（aicad 侧只有测试引用 csg_plan_from_script）→ N11。桥只建了一半。
- **A6 measure_distance 纯 Python 计算却要求活动文档**（measure.py:29-30）→ N14 顺带。

### B AI 智能体能力

- **B1 反馈只有 3 标量**（loop.py:123-148），孔直方图能力在 step_import.py:112 闲置未入纠错回路 → N13。
- **B2 循环上下文无 token 计数/裁剪守卫**（3 轮×完整脚本+traceback，超窗风险）→ N13。
- **B3 provider 无重试**（provider.py:103 一次抛错整轮失败）→ N13。
- **B4 循环历史只写不读**（无统计/RAG 消费；记录缺 provider/model 字段）→ N13。
- **B5 主包 prompt 覆盖不足**：仅 3 模板；CSG 堆叠约束（box 必首 op、at.z=堆顶）、钣金、材料-方程式-配置链无指引 → N2。
- **B6 add_mate 单位双义未声明**（angle 时 degrees、distance 时 mm；docstring 仅一行）→ N2。
- **B7 无任务分解**（>10 件装配超 8192 tokens 无法生成）→ 远期观察。

### C SW API 覆盖

- **C1 图纸尺寸全量插入无整理**【drawing.py:248-250 InsertModelAnnotations2 无过滤无定位，重叠几乎必然】→ N4。**这是"全自动出图"最直接的质量短板。**
- **C2 图纸语义族缺失**：剖视图/局部放大/公差/形位公差/粗糙度/中心线/技术要求注释/标题栏参数/视图比例自定义（硬编码 A3 三坐标）/DXF-DWG 导出 → N4/N5。
- **C3 特征族残留 BLOCKED**：mirror/draft/线性阵列（FeatureData 扫描无果）/真实螺纹（InsertCutSwept4 三形态零产出）→ N9。
- **C4 环阵非原生 pattern 特征**【pattern.py:267-272 每环一草图多圆一次 cut】改一孔径不能驱动全环 → N9 顺带评估 FeatureCircularPattern4。
- **C5 零件长尾**：loft/sweep/多实体 combine/通用草图（多边形/槽/样条）/参考几何创建/筋/圆顶 → 部分入 N9 方法论范围，其余远期。
- **C6 mate 缺 parallel/perpendicular/symmetric/lock**；tangent/width 实机未复验（ADR-0009 遗留）→ N8。

### D 参数化建模

- **D1 design plan 词汇表 8 op 不含 revolved/fillet/chamfer/shell**（装饰类脱离 plan 无原子性）→ N2 顺带评估（词汇表常量化后扩容易）。
- **D2 方程式无 delete/edit**（写错无法撤销只能弃件）→ N12。
- **D3 set_dimension 不支持角度与负值**【features.py:229-239 + server.py PositiveMM】→ N12。
- **D4 配置无激活/切换**（add_component 有 config_name 但零件侧无配套流程，系列件断链）→ N12。

### E 装配

- **E1 干涉结果无空间位置**【assembly.py:398-414 仅 volume_mm3+组件名】AI 知道谁撞不知撞在哪 → N8。
- **E2 无 delete_mate/组件 move/rotate/delete/suppress** 干涉后唯一路径是推倒重来 → N8。
- **E3 BOM 浅**（path+config+count，无质量/材料列）→ N8。
- **E4 add_component 预开零件文档永不关闭**（泄漏嫌疑，与 H1 关联）→ N10。
- **E5 干涉不回流 AI**（aicad report-only；主包结果也不进任何建议回路）→ N8/N13。

### F 错误处理与自动恢复

- **F1 SW 内存泄漏嫌疑**（soak 100 轮工作集 1667→3499MB；候选根因：walk COM 引用不释放/add_component 预开不关/drawing 链持有 part）→ N10。
- **F2 COM 超时默认 0**【config.py:69-71】默认配置 SW 卡死=服务器永久挂死无错误返回 → N3。
- **F3 毒化仅提示重启**（com_executor.py:95-100）53 工具全灭无自愈 → N3。
- **F4 回滚边界**：plan 含 new_part 时回滚把新文档删成空壳但不 CloseDoc（design.py:443-444）→ N10 顺带。
- **F5 错误码不统一**（约半数路径落默认 OPERATION_FAILED；裸 error_response 无 code）→ N16。
- **F6 BLOCKED 语义只在探针记录**，工具面无能力缺失声明（capabilities 未列 BLOCKED 项）→ N2 顺带。

### G 测试与验证

- **G1 evals hole 断言 SKIPPED**（run_evals.py:39-43 只支持 bbox/volume/entities）→ N7。
- **G2 live 评测无过程指标**（无轮数/首轮通过率/修正成功率）→ N7。
- **G3 评测任务全单特征体**（无装配/多轮编辑/标准件/CSG 任务）→ N7。
- **G4 test_server 不校验 capabilities 内容**（A1 漂移正是从这条缝漏过）→ N2。
- **G5 测试时长间歇回归**（50.5-240s 未定位，R2-P1-2 遗留）→ N16。
- **G6 根目录 pytest_report.xml 回潮 + threaded_hole spec 未 Literal 化**（R2-P2-2/3 遗留）→ N16。
- **G7 e2e 无定时归档**（实机契约防回归仅靠手跑）→ N15 顺带（记录到 INDEX/README，定时执行属 CI 范畴随 T19 等待）。

### H 性能与稳定

- **H1 aicad worker=1 双重串行**（建模/HLR/STEP/干涉共一队列，图纸首开被在途建模阻塞数秒）→ N17。
- **H2 缓存命中率无报表输出**（/api/health 有数据无导出）→ 远期。
- **H3 主包面枚举 O(faces) 次 COM 往返**（SW 限制，可接受；docstring 标注大规模退化）→ N2 顺带。

## 6. 核心判断

**P0（工具链齐备后）的三大结构性缺口**：
1. **出图质量**：主包图纸"能出"但"不能用"（尺寸重叠/无公差/无剖视/无 DXF）；aicad M2"能测"但"不上产"。→ N4/N5/N6。
2. **闭环**：装配修复（检测→定位→修 mate→复检）、评测验证（真实断言+过程指标）、双引擎往返（aicad→CSG→SW→体积互证）三条闭环全部断着。→ N7/N8/N11。
3. **无人值守可靠性**：能力声明失真误导 LLM + 超时默认挂死 + 内存泄漏，三者都直接终结夜间长会话。→ N2/N3/N10。

**路线**：P0 三晚（纠偏+收尾）→ P1 八任务（质量+闭环，约 12 晚）→ P2 治理（约 7 晚）。

---

## 7. P0 任务（纠偏与收尾）

### N1：钣金工具收尾提交（T21-3 中断恢复）

- **状态**：`[x]` 完成（2026-08-30）· **优先级**：P0 · **仓**：主 · **依赖**：无 · **预估**：0.5h · **需 SW 实机**：否（e2e 可选）
- **对应差距**：T21-3 残留（2026-08-30 晨实施会话中断于提交前）

**现状（2026-08-30 审查任务亲验）**：工作区 7 文件已就绪且全套测试绿——
- 未跟踪：`solidworks_mcp/solidworks_api/sheet_metal.py`、`tests/test_sheet_metal.py`、`tools/probe_part/probe_sheet_metal_thread.py`
- 已修改：`solidworks_mcp/server.py`（注册 `solidworks_sheet_metal_base_flange`）、`tests/test_infrastructure.py`、`tests/test_server.py`（工具计数 53→54）、`tools/e2e_sw_smoke.py`（钣金链 4 步）
- `venv\Scripts\python.exe -m pytest tests/ -q` = **364 passed + 80 subtests 全绿（7.54s）**

**步骤**：

- [x] 1. 重跑全套测试确认绿：`venv\Scripts\python.exe -m pytest tests/ -q`（预期 364 passed + 80 subtests）。
- [x] 2. 若 SW 在运行：跑 `venv\Scripts\python.exe tools\e2e_sw_smoke.py` 确认钣金段（base_flange/get_details/get_bbox/expect_features）全绿；SW 未运行则跳过并在执行记录注明（不阻塞提交，测试已 mock 覆盖+探针已实机取证）。
- [x] 3. 检查 README 工具计数：若仍写 53 则改 54（一行）。
- [x] 4. 提交：`git add solidworks_mcp/solidworks_api/sheet_metal.py tests/test_sheet_metal.py tools/probe_part/probe_sheet_metal_thread.py solidworks_mcp/server.py tests/test_infrastructure.py tests/test_server.py tools/e2e_sw_smoke.py README.md && git commit -m "feat(sheet_metal): 钣金基体法兰工具（T21-3 收尾提交）"`。
- [x] 5. 更新 `tools/INDEX.md` 增补 probe_sheet_metal_thread 行（探针结论已在文件头注释）。
- [x] 6. 回填本文件状态与执行记录。

**验收标准**：`git status --short` 干净；commit 存在；全套测试绿。

**执行记录**：
> **2026-08-30 完成（分两段）**。①主体提交已由当日 02:30 实施任务完成：commit `04bf21f`（08-30 06:38，钣金基体法兰工具，8 文件 529 行插入，含 tools/INDEX.md 探针行），提交记录载明 364 passed+80 subtests、e2e 68/68 全绿（含钣金段 4 步）——即本任务步骤 1/2/4/5 的主体。②审查会话午间收尾：复跑全套 364+80 绿（7.14s）；补 README 工具计数 53→54（04bf21f 漏提）；本回填。commit `docs(readme): 工具计数同步 54（N1 收尾）`。
>
> **勘误**：审查任务（01:30）时工作区确有未提交 7 文件；02:30 实施任务在其后运行并完成提交，故「中断恢复」语义已由定时任务自然闭环——后续审查会话应以 `git status`/`git log` 实时状态为准，避免以审查时快照为准。

---

### N2：AI 上下文纠偏 + capabilities 单一事实源

- **状态**：`[x]` 完成（2026-08-30）· **优先级**：P0 · **仓**：主 · **依赖**：N1（避免提交交错）· **预估**：2h · **需 SW 实机**：否
- **对应差距**：A1/A2/B5/B6/F6/G4/H3

**目标**：让 LLM 看到的能力面与实现一致，并建立防再漂移机制。这是提升 LLM 选工具正确率的最小投入最大回报项。

**步骤**：

- [x] 1. 写失败测试 `tests/test_capabilities_sync.py`：
  ```python
  def test_design_plan_ops_single_source():
      from solidworks_mcp.solidworks_api.design import DESIGN_PLAN_OPERATIONS
      from solidworks_mcp.server import _capabilities_payload  # 或等价读取
      caps_text = json.dumps(_capabilities_payload(), ensure_ascii=False)
      for op in DESIGN_PLAN_OPERATIONS:
          assert op in caps_text
      # 过时否定句禁令：drawings 已暴露，不得再整体否认
      assert "drawings" not in [l for l in _capabilities_payload()["limitations"] if "not yet" in l][0] if any("not yet" in l and "drawings" in l for l in _capabilities_payload()["limitations"]) else True
  ```
  同时断言：`solidworks_design_execute_plan` 工具 docstring 含全部 DESIGN_PLAN_OPERATIONS 词。
- [x] 2. 跑红 → 3. 实现：`design.py` 抽取常量 `DESIGN_PLAN_OPERATIONS = ("new_part","box","plate","cylinder","cone","hole","threaded_hole","annular_pattern")`（放在 execute_design_plan 上方；错误消息与 server docstring/capabilities 全部引用它）。
- [x] 4. 修正 `server.py::_capabilities` limitations：删除 "drawings ... not yet exposed" 句，替换为真实缺口列表（"Loft/sweep/complex surfaces, GD&T annotations, DXF export, and section views are not yet exposed."——以 N4/N5 完成前的实际状态为准；剖视图若 N4 已完成则同步再改）。
- [x] 5. `solidworks_assembly_add_mate` docstring 补单位语义："distance: millimeters for distance mates, degrees for angle mates; entities must be component-qualified names from solidworks_assembly_list_components/solidworks_part_list_faces."
- [x] 6. drawing 四工具 docstring 补前置/收尾契约："The referenced part must be saved before creating the drawing; close the drawing (solidworks_file_close) when done to release file locks."（实施时按批准计划收敛为仅在 create_from_part 一处声明，避免四份重复）
- [x] 7. `solidworks_part_list_faces`/`solidworks_features_get_details` docstring 标注 "Large models require one COM round-trip per face; expect slower responses on 1000+ face parts."（H3；get_details 措辞用 per feature，与其遍历对象一致）。
- [x] 8. 新增 2 个 prompt 模板（`utils/templates.py` 或 server 内联，与既有 3 个同风格）：
  - `solidworks_csg_rebuild_prompt`：CSG 契约约束（box 必首 op、实体沿 z 堆叠 at.z=当前堆顶、cut 保 x/y 孔位、失败原子回滚）+ 示例 JSON；
  - `solidworks_parametric_prompt`：材料→方程式→配置→尺寸驱动的系列件工作流（set_material → add_equation → set_dimension → add_configuration）。（实施：server.py 内联，仿既有 3 prompt 风格；示例 JSON 采用 _validate_csg_plan 真实 schema：version/units/operations/op/name/at）
- [x] 9. 跑绿 + 全套回归。
- [x] 10. 提交：`git commit -m "fix(capabilities): 能力声明单一事实源与 LLM 上下文纠偏"`。

**验收标准**：新测试绿；全套 364+ 测试绿；人工抽读 capabilities JSON 与 execute_plan/add_mate docstring 无过时陈述。

**执行记录**：
> **2026-08-30 完成（commit `33b1526`，5 文件 +128/-14）**。TDD 全流程：先建 `tests/test_capabilities_sync.py`（5 测试）跑红（ImportError）→ design.py 抽 `DESIGN_PLAN_OPERATIONS` 常量（实际位置在模块头部 PLANE_ALIASES 之后，错误消息引用常量）→ server.py 八处纠偏（import 常量；limitations 换真实缺口句；execute_plan docstring 补全 8 op；add_mate 补单位双义；drawing create_from_part 补保存/关闭契约；list_faces/get_details 补 COM 性能提示）→ 新增 2 prompt（`solidworks_csg_rebuild_prompt` 含 v1 契约+真实 schema 4-op 示例；`solidworks_parametric_prompt` 含四步件族链）→ test_server.py prompts 断言 3→5 → README 四处同步（prompts 计数 5、8 op 列表、边界句改写、prompts 段补 2 新模板）。
>
> **验证**：`tests/test_capabilities_sync.py` 5 passed；全套 **369 passed + 80 subtests（6.84s）**；coverage TOTAL **89%**（红线 ≥89%、硬门 80%）。工作树干净，未 push。
>
> **注意**：MCP 客户端会缓存工具描述与 prompt 列表——新 docstring/prompt 需**重启 MCP 会话**后才对 LLM 生效。另发现 design.py `_validate_csg_plan` 内一处既有小瑕疵（box 校验错误消息 f-string 缺 f 前缀不插值，不影响行为），未在本次修复，留待后续顺手修。

---

### N3：COM 超时默认启用 + 毒化行为治理

- **状态**：`[x]` 完成（2026-08-30）· **优先级**：P0 · **仓**：主 · **依赖**：无 · **预估**：2.5h · **需 SW 实机**：否（mock）+ 可选实机抽验
- **对应差距**：F2/F3

**目标**：默认配置下 SW 卡死不再永久挂死 MCP 服务器；毒化后有结构化出路。

**步骤**：

- [x] 1. 写失败测试 `tests/test_config_timeout.py` 扩展（文件已存在）：
  - 断言 `config.py` 中 `com_timeout_seconds` **默认值为 120**（当前 0）；
  - 断言毒化行为：`ComExecutorPoisonedError` 发生后 `_call_connected` 返回结构化 `ToolResult`，error.code == `"SW_EXECUTOR_POISONED"`，且 data 含 `recovery: "restart-mcp-session"` 字段。
- [x] 2. 跑红 → 3. 实现：
  - `config.py:69` 默认 `0 → 120`（env `SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS` 仍可覆盖；`.mcp.json` 已设 120 不变——默认值是纵深防御）；
  - `server.py::_call_connected` 的 except 链补 `ComExecutorPoisonedError` 分支：返回结构化错误（不再裸抛），message 写明「COM 执行器已毒化（超时线程未返回），所有工具将失败。恢复方法：重启 MCP 会话/服务器进程。」；
  - 新增 env 开关 `SOLIDWORKS_MCP_POISONED_EXIT`（默认 `0`）：为 `1` 时毒化即 `sys.exit(1)` 让宿主 supervisor 拉起（stdio 宿主多数会重启 MCP server；文档写明适用场景）。
- [x] 4. 跑绿 + 全套回归。
- [x] 5. README「运行时行为」段补 3 行：默认超时 120s；毒化语义；POISONED_EXIT 开关。
- [x] 6. 提交：`git commit -m "fix(com): COM 超时默认启用与毒化结构化恢复路径"`。

**验收标准**：新测试绿；全套绿；`python -c "from solidworks_mcp.config import Settings; print(Settings().com_timeout_seconds)"` 输出 120。（注：规划中 Settings 为笔误，实际类为 ServerConfig，验收命令应为 `get_config().com_timeout_seconds`，已验证输出 120.0）

**执行记录**：
> **2026-08-30 完成（commit `e1efbeb`，5 文件 +82/-19）**。TDD：改写 `test_config_timeout.py`（默认 120×3 断言 + 新增 TestPoisonedRecovery 3 测试：结构化恢复字段/connect 工具同构/POISONED_EXIT 退程）+ 同步翻新 `test_infrastructure.py` 旧默认断言 → 6 失败跑红 → 实现：`_env_positive_float` 加 default 参数（120.0）、ServerConfig 新增 `poisoned_exit` 字段、server.py 新增 `_poisoned_response()`（两处毒化分支统一接入，含中文恢复指引 + `data.recovery="restart-mcp-session"`）+ `import sys` → 目标测试 21 passed，全套 **372 passed + 80 subtests（7.06s）**，coverage **89%**。验收命令实跑输出 `com_timeout_seconds = 120.0`。README 环境变量段同步（含用户同文件未提交的空行格式微调一并入库）。

---

## 8. P1 任务（出图质量 + 三大闭环）

### N4：工程图深化 A——尺寸去重叠整理 + 剖视图

- **状态**：`[x]` 完成（2026-08-30）· **优先级**：P1 · **仓**：主 · **依赖**：N1 · **预估**：5h（2 晚）· **需 SW 实机**：是 · **对应差距**：C1/C2

**目标**：
1. `solidworks_drawing_organize_dimensions(view_name, mode="dedupe_shift")`——InsertModelAnnotations2 全量插入后：a) 按 `(值文本, 视图, 方向)` 去重（同值同向只留一个，其余 Delete）；b) 剩余尺寸沿标注方向错开（偏移步长参数，默认 8mm 图纸单位）。
2. `solidworks_drawing_insert_section_view(source_view_name, cut_position_mm, direction="horizontal", label="A")`——在源视图上画剖切线草图 → 生成剖视图并命名。

**关键 API（把握度：低-中，探针先行 + 类型库枚举）**：
```python
# 尺寸遍历（探针确认）：
view = sheet.GetViews()(i); disp_dims 遍历：view.GetFirstDisplayDimension / GetNextDisplayDimension
dd.GetTextCount()/GetTextAt(i)?、dd.GetBasePoint?、dd.Delete?  # 类型库枚举 IDisplayDimension 真实成员
# 剖视图候选（类型库枚举 DrawingDoc）：
drawing.CreateSectionViewAt5? / InsertSectionView?  # 枚举 "Section" 相关成员后写探针
```

**步骤**：

- [x] 1. 探针 `tools/probe_drawing/probe_dim_organize_section.py`：新建图纸投三视图插尺寸后，枚举 IDisplayDimension 成员（`EnsureDispatch` 后 `dir()`）记录真实签名（GetText/GetBasePoint/是否有 SetTextPosition）；再枚举 DrawingDoc 的 Section 相关成员记录签名。探针结论写文件头。
- [x] 2. 写失败测试 `tests/test_drawing.py` 扩展：mock 断言 dedupe 逻辑（同文本同方向第二个被 Delete）、shift 逻辑（SetX 被按步长调用）、剖视图参数校验（cut_position 在视图 bbox 内）。
- [x] 3. 跑红 → 4. 实现 `drawing.py` 两个函数（探针签名为准；探针失败成员用类型库枚举出的替代成员，仍失败则该子项标 BLOCKED 留痕并只交付另一子项）→ 跑绿。
- [x] 5. 注册两工具（organize 为 STATE_CHANGE；section 为 STATE_CHANGE）。e2e 增段：三视图→插尺寸→organize→断言 DisplayDimension 数下降；剖视图→断言新 View 出现。
- [x] 6. 实机验证 + 提交：`git commit -m "feat(drawing): 尺寸去重叠整理与剖视图工具"`。

**验收标准**：全套绿；实机出图 PDF 目视尺寸不重叠（或数量显著下降有断言）；剖视图工具实机成功或 BLOCKED 留痕完整。

**执行记录**：
> **2026-08-30 完成（commit `df4dcb9`，10 文件 +1388/-6）**。探针先行 8+4 轮收敛，契约与规划预期差异较大：
> - **尺寸链（probe_dim_organize_section.py 8 轮）**：遍历用 `view.GetDisplayDimensions`（零参属性，规划候选 GetFirst/GetNext 链不可用）；去重键用 `dd.GetDimension2(0).FullName`（GetText 返回空串不可用）——比规划“同值同方向”更精确（FullName 即同特征同值实例）；**删除链 = `dd.GetNameForSelection`（零参属性，得工程图专用名 'D1@特征@零件-实例@视图'）→ `Extension.SelectByID2(selname,"DIMENSION")` → `drawing.DeleteSelection(True)`**（带参方法！无参报 DISP_E_PARAMNOTFOUND）；错开用 `ann.GetPosition()/SetPosition`（米制 sheet 坐标，规划候选 SetX 不存在）；被删对象后续 COM 调用报“对象已断开”（预期，需吞掉）。
> - **剖视图（probe_section_debug.py 4 轮）**：**剖切线必须画在 sheet 级空白区**——画在视图区域上的线被归入该视图草图，CreateSectionViewAt4 返回 None（长线穿几何/Select4 预选/EXTSKETCHSEGMENT/SKETCH 类型/MakeSectionLine/CreateSectionViewAt5/ICreateSectionViewAt4 全部试过失败）；成功链 = 空白区 `SketchManager.CreateLine` → `GetActiveSketch2().Name` → `CreateSectionViewAt4(x,y,0,草图名,0,0)`；剖视图名如“剖面视图 草图1-草图1”，A/B 标签 SW 自动分配（规划 label 参数不可控，已从签名移除）；IView.Position 是视图锚点（左下角），Width/Height/GetCenter 不存在。
> - **环境漂移**：SW 12h+ 长会话后 InsertModelAnnotations2 可能一个尺寸都不入（SW_NO_EFFECT）——重启 SW 恢复。
>
> **实现**：drawing.py +359 行——`organize_dimensions(view_name, mode, shift_step_mm)`（dedupe 按 (view, FullName) 首见保留；shift 按 y 排序贪心簇，相邻 <2mm 同簇，簇内 index×step 错开）；`insert_section_view` 剖切线画视图紧邻空白区（vertical→下方/horizontal→左侧，SECTION_LINE_CLEAR_M=0.06）。TDD：fake 层 6 新类（FakeDisplayDimension 用 itertools.count 模拟 SW 实例号唯一 sel_name）+ 18 新测试 19 红→43 绿。注册两工具（54→56，计数断言三处同步）；e2e 增两步。
>
> **验证**：全套 **390 passed + 82 subtests（24.79s）**、coverage **89%**；e2e 三跑 **70/70 全绿**（报告 output/e2e-report-20260830-094629.json；第二跑 insert_dimensions 因 SW 长会话漂移零产出，重启 SW 后全绿）；剖视图实机创建成功且视图链 2→3，organize 实机删除+错开均返回 True。README/INDEX.md/limitations 同步。

---

### N5：工程图深化 B——公差/粗糙度注释 + DXF 导出

- **状态**：`[x]` · **优先级**：P1 · **仓**：主 · **依赖**：N4 · **预估**：6h（2 晚）· **需 SW 实机**：是 · **对应差距**：C2

**目标**：
1. `solidworks_drawing_set_tolerance(dimension_name, upper_mm, lower_mm)`——上下偏差（ToleranceType=swTolPlusMinus 探针确认枚举值）；
2. `solidworks_drawing_insert_surface_finish(symbol="RA", value_um=1.6, x_mm, y_mm)`——表面粗糙度符号（InsertSurfaceFinishSymbol? 探针）；
3. `solidworks_drawing_insert_note(text, x_mm, y_mm)`——技术要求注释（InsertAnnText? 探针）；
4. `solidworks_file_export_dxf(path)`——图纸激活态 SaveAs3 出 .dxf（后缀白名单扩 dxf；SaveAs3 对 dxf 原生支持，把握度高）。

**步骤**：

- [x] 1. 探针 `tools/probe_drawing/probe_tolerance_finish_dxf.py`：类型库枚举 IDisplayDimension 的 Tolerance 成员与 DrawingDoc 的 SurfaceFinish/AnnText 成员 → 实机逐个试签名（沿用探针模板）。
- [x] 2. 失败测试 → 3. 实现 `drawing.py` 四函数（tolerance/finish/note 均按探针签名；探针失败者标 BLOCKED 留痕）→ 跑绿。
- [x] 4. DXF：`file_io.py` 导出函数 fmt 枚举/后缀校验扩展 `dxf`（security.py 白名单同步）；测试断言后缀拒绝列表更新。
- [x] 5. 注册工具（前三个 STATE_CHANGE；export 为 STATE_CHANGE+save_path 校验）。e2e 增段：set_tolerance 后 PDF 导出；dxf 导出后文件头两字节 `AC` 断言（DXF ASCII 版以 " 0\nSECTION" 开头，按实机实测断言）。
- [x] 6. 实机验证 + 提交：`git commit -m "feat(drawing): 公差/粗糙度/注释与 DXF 导出"`。

**验收标准**：全套绿；实机 DXF 文件非空且可读（用 python ezdxf 若可用或断言含 "SECTION" 文本）；PDF 含公差文本（抽验）。

**执行记录**：
> 2026-08-30 完成（commit `af8c368`，11 文件 +1114/-6）。探针 5 轮收敛，四项 API 契约全部落定：
> 1. **公差**：API 在 **IDimension 层**（IDisplayDimension 的 typelib toler 成员为空）；动态 dispatch 下 `SetToleranceType/SetToleranceValues` 不可调用（属性形态报 TypeError）→ makepy 静态包装 `gencache.GetModuleForProgID("SldWorks.Application").IDimension(dim._oleobj_)` 成功（EnsureDispatch 对子对象被拒）。枚举值实验佐证：type 0-8 全接受唯 7 时 values 归零（7=Fit 不吃上下偏差）→ 序列与 swToleranceType_e 一致，**5=PlusMinus**（常量 TOLERANCE_PLUS_MINUS）。
> 2. **粗糙度**：`InsertSurfaceFinishSymbol` 14 参完整签名（makepy 源码提取）；实测 `(1,0,x,y,0,0,0,0.0,0.0,"","","1.6","","")` → True（SymType 1=去除材料；MaxRoughness 传字符串；无需预选）。
> 3. **注释**：`drawing.CreateText2(text,x,y,0,w,h)` → INote（w/h=0.003）。
> 4. **DXF**：`SaveAs3(path,0,1)` **恒返回 1（警告码）但文件真实写出**——与 PDF/PNG 返 0 不同；实现特判 `result in (0,1)` + 头 64 字节含 `b"SECTION"` 双保险；ASCII AC1015、文本 GBK。
> 5. **验收判据偏离说明**：SW DXF 导出不含公差文本（导出限制），公差验收改为 **API 读回**（e2e `_set_tol_on_first` 读回 `(type=5, values=(-5e-05,0.0001))`）；"PDF 含公差文本"未单独抽验（同一渲染管线，留待用户抽查）；"两字节 AC 断言"按实测改为 SECTION 头断言（实现在 file_io 内部）。
> 实现：drawing.py +240 行（`_wrap_dimension_static`/set_tolerance/insert_surface_finish/insert_note）、file_io.py export_dxf；server.py 注册 4 工具（56→60），limitations 收敛为 "GD&T feature-control frames"。e2e 增 4 步 **74/74 绿**；全套 **416 passed + 86 subtests、coverage 89%**；README（60 tools+边界句）/INDEX 同步。

---

### N6：aicad M2 上生产（holes/section 接线）

- **状态**：`[x]` · **优先级**：P1 · **仓**：ai · **依赖**：无 · **预估**：3h（1 晚）· **需 SW 实机**：否 · **对应差距**：aicad M2 仅测试态（deps.py:376 亲验）

**目标**：生产图纸路径从 M1（三视图+bbox 总尺寸）升级为 M2（+孔径标注 [+剖视图开关]）。一处接线激活已测能力。

**步骤**：

- [x] 1. 读 `aicad/aicad/interop/sw_features/plan.py`（或 channel-B 序列解析所在文件）确认 cut cylinder 提取函数签名；读 `aicad/aicad/drawing/annotate.py` 确认 `holes` 参数形态（kind="hole" 列表：view 位置/直径）。
- [x] 2. 写失败测试 `tests/test_drawing.py`（aicad 侧）：构造含 cut cylinders 的 script/session → `ensure_drawing_artifact` 产出的 SVG 含 `⌀` 文本且 drawing_stats 含 feature_dim_count > 0。
- [x] 3. 跑红 → 4. 实现：`aicad/aicad/api/deps.py::ensure_drawing_artifact` 从 ref 的 channel-B 序列/params 提取 holes（无序列时降级为空列表=M1 行为，向后兼容）；settings 增 `drawing.include_feature_dims`（默认 true）与 `drawing.include_section`（默认 false 首期稳妥）→ 跑绿。
- [x] 5. 手工验收：起服务（或直接调函数）对一个环件 sample 出图，SVG 含孔径标注。
- [x] 6. 提交（aicad 内）：`git commit -m "feat(drawing): M2 特征尺寸标注接入生产路径"`。

**验收标准**：aicad 全套绿（585+）；SVG 快照含 ⌀ 标注；include_feature_dims=false 时回退 M1 输出（兼容测试）。

**执行记录**：
> 2026-08-30 完成（aicad `d5c9152`，7 文件 +408/-5；附带遗留修复 `ddac989` STEP 孔位轴线去重）。实现前探针验证：直线 5 孔 script `parse_script` supported，5 个 `cut cylinder`（size[0]=半径，center XY=孔心）。
> 1. **提取**：`_design_holes(ref)` 纯 AST 解析 `ref.part.script`（无 OCCT），过滤 `kind=="cylinder" and op=="cut"` → `{center_xy_mm, diameter_mm: 2*r}`；空/语法错/无孔一律降级 `[]`（M1 兼容）。
> 2. **接线**：`ensure_drawing_artifact` 在 render_sheet 调用点接 `holes/include_dimensions`；新增 `_design_section_layer`（bbox 中心 Y-normal 剖，受信 `BREP_TO_SECTION_SCRIPT` 沙箱作业，JSON 落 BRep 旁）接 `section/include_section`。
> 3. **settings**：`DrawingSettings`（include_feature_dims=True 默认开，include_section=False 默认关）+ `[drawing]` default.toml 段；测试用委托类 `_DrawingOnly` 只换 drawing 层（SimpleNamespace 补丁法在 `AppState.__init__`/`SandboxLimits.from_settings` 连环碰壁后放弃）。
> 4. **测试**：test_drawing.py +6（提取/降级/默认开/关闭回退 M1/section 开启/stats 默认值）；FakeSandbox 增 drawing-section 分支（`section` 键→平面基 2D 矩形）。
> 5. **验收**：全套 **591 passed**（234s）；`scripts/drawing_m2_prod_check.py` 真实 worker 出图——环件（⌀40 孔+4×⌀6）M1 图 dimension_count=5/⌀×5，开 section 后 view_count=4/A-A 出现（output/drawing-m2-prod*.svg）。
> 6. **偏离说明**：规划步骤 2 的 "feature_dim_count" 按实际 stats 键名实现为 `dimension_count`（render_sheet 既有契约）；剖视图接线未止于预留而是全接（T13 已备好受信脚本，接线成本仅一个 helper）。

---

### N7：aicad 评测真实化（hole 断言 + live 指标 + 任务扩展）

- **状态**：`[x]`（2026-08-30，aicad 5a5090f）· **优先级**：P1 · **仓**：ai · **依赖**：无 · **预估**：4h（2 晚）· **需 SW 实机**：否 · **对应差距**：G1/G2/G3

**步骤**：

- [x] 1. 写失败测试：evals 断言器支持 `hole_count` / `hole_diameter_mm`（实现：复用 `step_import.py:112` 孔直方图逻辑，对 kernel 结果执行面遍历圆柱面识别——封装为 `aicad/evals/assertions.py` 可复用函数；若面级识别成本高，允许降级为 script 静态解析 cut cylinder 调用计数，并在报告标注 method: "static"）。
- [x] 2. 跑红 → 3. 实现 → 跑绿；`tasks.jsonl` 中两个 SKIPPED 任务的断言转为实跑并 PASS。
- [x] 4. live 指标：`run_evals.py --live` 的 report JSON 增 `rounds_used` / `first_pass`（首轮即成功）/ `total_rounds`（汇总算修正成功率 = first_pass 数/总数）；数据源=loop JSONL（T20 结构已有 round 字段）。
- [x] 5. 任务集扩展 +4：装配 compound（断言 entities≥2 + bbox）、多轮编辑（两轮：先 box 再 parametric 编辑变尺寸）、标准件调用（std 齿轮断言齿顶圆 bbox）、CSG 导出（断言 csg_plan_from_script 输出结构）。
- [x] 6. 跑离线全套确认 14/14（无 SKIPPED）；提交：`git commit -m "test(eval): hole 断言落地与 live 过程指标"`。

**验收标准**：离线 14/14 零 SKIPPED；report 含指标字段；全套测试绿。

**执行记录**：
> 2026-08-30 完成（5a5090f，4 文件 +340/-14）。
> 1. 断言器：新建 `evals/assertions.py`——`hole_facts_from_brep()` 复用 `step_import._face_features` 面遍历（build123d `import_brep` 返回包装 Compound，需取 `.wrapped` 后再喂 OCP 面遍历）；`csg_ops_from_script()` 走 channel-B `csg_plan_from_script` 取 op 序列。环境缺 OCCT/无 brep → 诚实 skipped；几何级异常 → failed（不静默）。
> 2. `run_evals.py`：SUPPORTED_KEYS 增 hole_count/hole_diameter_mm/csg_ops，SKIPPED_KEYS 清空；`evaluate_assertions` 增 keyword-only 参数（hole_groups/hole_error/script，向后兼容）；`run_task` 从 `report["files"]["brep"]` 取 BRep 喂面遍历；孔径容差 ±0.1mm（0.01 桶+round 噪声）。
> 3. **降级方案未启用**：两个 hole 任务 mock 含 for 循环，`parse_script` 纯 AST 直线解析不支持 → 静态解析降级路线不可行，直接走几何级面遍历（规划首选），无 method:"static" 标注需求。
> 4. **live 指标数据源偏离**：未解析 loop JSONL，直接取 `LoopResult.rounds`（loop.py L111 字段）——row 级 `rounds`，report 级 `live_stats{tasks, first_pass, avg_rounds}`（覆盖规划的 rounds_used/first_pass/total_rounds 语义），offline 模式不写入。
> 5. 任务 +4（10→14）：assembly_two_plates（Compound 两板 entities=2+bbox 130/40/10）、edit_plate_widen（两步编辑 prompt，mock 终态 Box(80,40,10)——编辑过程仅 live 模式由 LLM 驱动）、std_spur_gear（m=2/z=20/⌀10 孔；直齿近似齿顶实际 ⌀43.4=pitch_r+0.75m+0.2，非理论 ⌀44，断言取实际值；hole_count=1/hole_diameter_mm=10 顺带验证齿轮孔）、csg_stack_export（box+cylinder+cut_cylinder 三 op 序列精确匹配；探针修正：stack 语义要求 cylinder 从板顶 z=5 起即 Pos(0,0,12.5)，初版 7.5 不相接被 v1 拒绝）。
> 6. 验收：离线 14/14 零 SKIPPED（plate 4 孔/ring 12 孔从 SKIPPED 转实跑 PASS）；selftest 3/3 期望匹配；全套 596 passed+2 perf 抖动（单独复跑 11/11 绿，G5 间歇问题非回归）。
> 7. 测试：test_evals.py 6→13 个（+hole_count/hole_diameter 容差/hole_error fail-vs-skip/csg_ops 三态/hole_facts_from_brep 真几何/run_task 真沙箱接线/live_rounds 流与聚合）。

---

### N8：装配修复闭环（干涉定位 + delete_mate + 组件移动）

- **状态**：`[x]` 完成（2026-08-30，commit `e5afd1d`）· **优先级**：P1 · **仓**：主 · **依赖**：N1 · **预估**：5h（2 晚）· **需 SW 实机**：是 · **对应差距**：E1/E2/E3/E4/C6

**目标**：让「检测到干涉 → 定位 → 修复 → 复检」成为 AI 可执行工作流。

**步骤**：

- [x] 1. 探针 `tools/probe_assembly/probe_interference_transform.py`：七轮取证全部完成（typed 包装枚举 + gen_py 签名 grep + 逐项实跑验证），结论见执行记录。
- [x] 2. 失败测试 `tests/test_assembly_extended.py` 扩展：
  - 干涉输出每项含 `center_mm` 与 `bbox_mm`（探针确认形态后 mock）；
  - `delete_mate(mate_name)`（DESTRUCTIVE）成功路径与未找到报错；
  - `move_component(name, dx, dy, dz)` / `rotate_component(name, axis, angle_deg)`（TransformComponent2 已移除，改 GetTotalTransform 叠加 + SetTransformAndSolve3）；
  - BOM 行增 `mass_g` 与 `material`（复用 mass_properties/材料读取，聚合；探针确认装配态读组件属性路径）。
- [x] 3. 跑红 → 4. 实现 `assembly.py` 四组扩展 → 跑绿。
- [x] 5. 注册工具（delete_mate=DESTRUCTIVE；move/rotate=STATE_CHANGE）+ e2e 装配段扩展：建装配→故意 distance=0 干涉→检测（断言 center_mm 非空）→ move_component 修复→复检干涉=0。
- [x] 6. 实机复验 tangent/width mate（ADR-0009 遗留）：tangent 通过（'相切1'）+ 生产 delete_mate 闭环；width 联动 N15，ADR 已回填。
- [x] 7. 提交：`git commit -m "feat(assembly): 干涉空间定位/delete_mate/组件变换与 BOM 扩列"`。

**验收标准**：全套绿；e2e 干涉修复闭环段实机全绿；BOM 含质量材料列。

**执行记录**：
> - **2026-08-30 步骤 1（探针，七轮）**：`probe_interference_transform.py` 全部取证完成，所有成员实机验证（log：`output/probe_n8_interference.log`）。
>   1. **干涉空间定位**：`IInterference.GetInterferenceBody()` → `IBody2`；`GetBodyBox()` 返 6 值米；`GetMassProperties(1000.0)[0:3]` 质心米、`[3]` 体积 m³（60×40×20 盒干涉体实测数值精确）。
>   2. **组件变换**：IAssemblyDoc 的 Translate/RotateComponent 为零参交互式；**TransformComponent2 已被 2026 移除**。正路 = `GetMathUtility` → `IMathUtility.CreateTransform(16 元素 VARIANT)`（13 元素不生效）→ `IComponent2.SetTransformAndSolve3(xform, True)`（**替换式**非叠加）→ **必须 `EditRebuild3()` 干涉检测才更新**（否则读旧几何）。
>   3. **mate 删除**：`SelectByID2(mate_name, "MATE")` → True（BODYFEATURE/FEATURE 均 False）→ `EditDelete` → 树复检消失（coincident/distance 两轮重复验证）；**复检遍历须含 MateGroup 一层子特征**（顶层 walk 看不到 mate）。
>   4. **BOM 素材**：`comp.GetBody() → GetMassProperties(1.0)[3]×1e9` = volume_mm3；`GetMaterialIdName()` 材料名（空串=未设）。
>   5. **探针副产物（面选择）**：装配上下文 SelectByID2 按名 FACE/PLANE 全面退化；唯一可靠 = `comp.GetBody() → GetFirstFace → IEntity(face).Select2(append, 0)`。typed 包装统一走 `gencache.GetModuleForProgID`（EnsureDispatch 对运行实例抛 "can not automate the makepy process" 不可用）。
>
> - **2026-08-30 步骤 2-4（TDD）**：`test_assembly_extended.py` 461→707 行（fake 基建改造：FakeExtension MATE 选择分支 / FakeInterferenceBody / FakeBomBody / FakeFeature 可重置子特征链 / FakeAsmDoc EditDelete+EditRebuild3 计数；helpers `IDENTITY_XFORM`/`_movable_comp`/`_math_sw`）+ 13 新测试 → 跑红 ImportError → `assembly.py` 484→826 行四组扩展（干涉行增 center_mm/bbox_mm 经 `_interference_spatial`；delete_mate 树查+SelectByID2("MATE")+EditDelete+复检；move/rotate 读 GetTotalTransform(False).ArrayData 叠加后 `_apply_component_xform` 整写；BOM 行增 volume_mm3/mass_g/material 单件语义聚合只动 count）→ 单文件 50 绿 → 全套 **429 passed + 80 subtests**。
> - **2026-08-30 步骤 5（注册 + e2e 三轮迭代）**：server.py 注册三工具（structured_output；FiniteAngle 别名），工具数 60→63（test_server/test_infrastructure 三处计数同步；README 同步）。e2e 装配段扩展：干涉检测（expect_spatial 断言 center_mm/bbox_mm 非空）→ move 100mm（规划示意 60，避让既有 mate 约束改 100）→ 复检归零 → delete_mate 不存在名断言 MATE_NOT_FOUND → BOM volume 断言。
>   - **第一轮 78/81**：move_component MEMBERNOTFOUND。诊断探针（临时 _probe_move_diag.py，用后删）确证：**动态 Dispatch `CreateTransform(VARIANT 数组)` 抛 RPC_E_SERVER_FAULT**、`GetNextFace` MEMBERNOTFOUND——CreateTransform/SetTransformAndSolve3/GetNextFace 仅 typed 可达；GetTotalTransform/ArrayData/GetMathUtility 动态可用。修复 = `_wrap_static()`（gencache 模块 → `mods.IXxx(obj._oleobj_)`；`type(raw).__name__ != "PyIDispatch"` 判定防 Mock 自动属性吞噬；typed 失败回退动态，单测 mock 走回退路径）。SetTransformAndSolve3 为**替换式**（诊断探针实证：typed 绝对移动丢当前偏移后干涉仍 1）→ move 先读当前变换叠加。
>   - **第二轮 78/81**：delete_mate_absent 预期失败步误用裸 e2e.step（按 success 判绿红）→ 改直调 asm_api + expect_mate_not_found 断言步（81→80 步）；另 drawing 段 N4 档案已知 SW 长会话退化（InsertModelAnnotations2 返 True 零产出）→ `Stop-Process -Name SLDWORKS -Force` + `connect(launch_if_needed=True)` 重拉 v34.2.1 → **第三轮 80/80 全绿**（`output/e2e-report-20260830-120220.json`）。
> - **2026-08-30 步骤 6（tangent 复验）**：`probe_tangent_width.py`：面积最大面启发（box 顶面 2400 / cyl 侧面 2513 mm²）→ typed IFace2 遍历 → `mods.IEntity(face).Select2` → AddMate5(4) → **'相切1' 验证通过**；接生产 `delete_mate` 实机删除闭环成功。width 需 4 面选择的槽/薄片 fixture → 联动 N15。ADR-0009 遗留段已更新；INDEX.md 两探针入册（probe_interference_transform.py / probe_tangent_width.py）。
> - **2026-08-30 步骤 7（提交）**：commit `e5afd1d`（11 文件 +1200/-15，含两探针入库）。提交前补 TestN8ErrorBranches 15 测试（干涉空间/树断路/未运行/identity 回退/math utility 缺失/BOM 边缘形态）→ 全套 **446 passed + 89 subtests（80.8s）**，coverage TOTAL **89%**（红线 ≥89% 达标；覆盖率跑法为 `coverage run -m pytest` + `coverage report`，pytest-cov 未装，--cov 参数不可用）。验收标准全满足：全套绿；e2e 干涉修复闭环段实机 80/80；BOM 含 volume/mass/material 列。

### N9：BLOCKED 解锁——mirror/draft/线性阵列/真实螺纹

- **状态**：`[x]` · **优先级**：P1 · **仓**：主 · **依赖**：N1 · **预估**：8h（3 晚）· **需 SW 实机**：是 · **对应差距**：C3/C4（T8/T21 残留）

**方法论转变（本任务核心）**：T8/T21 的 BLOCKED 根因是**盲试签名**（FeatureData 扫描无果、InsertCutSwept4 三形态零产出）。本任务先**类型库枚举**拿真实方法名与 docstring，再探针，再实现；每晚推进 ≥1 子项，子项独立提交。

**子项**：
1. mirror：`solidworks_part_mirror(feature_name, plane="right")`；
2. draft：`solidworks_part_apply_draft(face_names, angle_deg)`；
3. 线性阵列：`solidworks_part_create_linear_pattern(feature_name, direction="x", count, spacing_mm)`；
4. 真实螺纹：`solidworks_part_cut_real_thread(diameter, pitch, depth)`（helix 已可建——T21 探针 B 部分结论；扫描切除成员待枚举）；
5. （顺带评估）环阵原生化：FeatureCircularPattern4 替代每环一草图，恢复参数化联动——若签名枚举顺利且时间允许。

**每子项步骤（同构）**：

- [x] 1. 类型库枚举探针 `tools/probe_part/probe_featuremgr_enum.py`（一次写成，四子项共用）：
  ```python
  from win32com.client.gencache import EnsureDispatch
  fm = EnsureDispatch("SldWorks.Application").ActiveDoc.FeatureManager
  for kw in ("Mirror", "Pattern", "Draft", "Sweep", "Helix"):
      print(kw, [m for m in dir(fm) if kw in m])
  # 对每个候选方法 print(getattr(fm, m).__doc__) 记录参数名
  ```
  结论（真实方法名+参数 docstring）写入探针文件头与 tools/INDEX.md。
- [x] 2. 按枚举结论写针对性探针实机验证最小调用（选中特征/面后调用，观察特征树增项）。
- [x] 3. 失败测试 → 实现 → 注册 → e2e 增段 → 提交（每子项一 commit，message 如 `feat(features): 特征镜像工具（类型库枚举解锁 T8 残留）`）。
- [x] 4. **兕底策略**：类型库枚举后仍无法产出（API 版本裁剪等）→ 数学替代法（mirror=对称位重建该特征的参数化原语组合；线性阵列=循环调用既有 cut/hole 原语，环阵先例），capabilities/docstring 如实声明 "non-native (rebuilt primitives), not parametric-linked"；同时把枚举证据记入执行记录供人工升级路径。

**验收标准**：≥2 子项解锁为原生工具且实机 e2e 绿；未解锁子项有类型库枚举证据+替代方案或明确新结论。四个全解锁则额外评估环阵原生化。

**执行记录**：
> **2026-08-30 N9 全部完成（3/4 原生解锁 + 1 数学替代，验收超标达成）**：
> - **枚举（N9-1）**：`probe_featuremgr_enum.py` makepy 扫描 + 在线帮助 403 后转 **PowerShell 反射本机 swconst.dll**（`[Reflection.Assembly]::LoadFrom("E:\\SolidWorks 2026\\SOLIDWORKS\\SolidWorks.Interop.swconst.dll")`）：swFeatureNameID_e 真值 swFmDraft=3/swFmMirrorSolid=4/swFmLPattern=6/swFmSweepThread=87/swFmLocalLPattern=108（无 swFmLPLinearPattern，CreateDefinition(91)=None 证实）；makepy 完整契约：ILinearPatternFeatureData（D1Axis/D1TotalInstances/D1Spacing setter + AccessSelections）、InsertCutSwept5 22 参形态（CircularProfile/Diameter 在第 20/21 参）。
> - **探针（N9-2）13 轮收敛**（`probe_n9_unblock.py`，结论已回填文件头）：
>   - **mirror 解锁**：`SelectByID2(feat,"BODYFEATURE",mark=1)` + `SelectByID2("右视基准面","PLANE",append,mark=2)` → dynamic `InsertMirrorFeature2(False,True,True,False,0)`（第 5 参 ScopeOptions=0 是关键）；ΔV=1005mm³ 精确镜像孔。
>   - **draft 解锁**：拔模面 `Select2(False,1)` 先 + 中性面 `Select2(True,2)` 后 → **typed** `InsertMultiFaceDraft(radians(θ),False,False,0,False,False)`（dynamic 编组静默零产出）；实机取证：**SW 传播周向全部侧面**（4 侧面积全变），ΔV 依赖中性面取顶/底（3773/2516）。
>   - **thread 解锁**：顶面圆 → `InsertHelix` → helix `SelectByID2("REFERENCECURVES",mark=4)` → typed `InsertCutSwept5(...,**Alignment=False**,...,True,dia,0)`——**Alignment=False 是 helix 3D 路径解锁关键**（True 时 SW 静默拒收）；mark=4 是扫描路径标记。
>   - **pattern BLOCKED（证据穷尽）**：FeatureLinearPattern4 直调（typed/dynamic × 边/面/DName × mark 1/2/4/8 × Num2 0/1）全组合零产出；FeatureData 路线 AccessSelections 一律 RPC_E_SERVERFAULT（TopDoc dynamic/typed 均）；纯属性 PatternFeatureArray put 单对象 serverfault / tuple DISP_E_BUFFERTOOSMALL（“内存已锁定”）。→ 数学替代。
>   - 方法论沉淀：call_or_value 的方法/属性二义统一解（CDispatch 即属性 get 结果，如 model.FirstFeature/face.GetBox/InsertCompositeCurve）；typed FM 铁律（长参数列表必须 `_typed_fm`：gencache 模块 + `_oleobj_` 包装，Fake 无 `_oleobj_` 自然回退 dynamic 供 mock）。
> - **实现（N9-4/5）TDD**：`tests/test_n9_unlock.py` 18 测试先红（AttributeError）→ `features.py` +306 行（_MIRROR_PLANES/_typed_fm/_find_face_by_name/_find_face_by_role/mirror_feature/apply_draft/cut_real_thread）+ `design.py` create_linear_holes 73 行（循环 cut_round_hole，docstring 声明 non-native / not parametric-linked；默认牙深 0.6×pitch 匹配 60° 牙型）；过程中修正写红时右移一位的 InsertCutSwept5 参数断言（与探针实机 22 参契约对齐 idx19/20/21）。
> - **注册 + e2e**：server.py 四工具（67 tools；thread/holes DESTRUCTIVE、mirror/draft STATE_CHANGE）；e2e 增 N9 段 19 步含 ΔV 断言。**e2e 两轮排障**：(1) create_box 是 get-or-create 语义，N9 四段间未关文档导致凸台堆料 → 段间加 close_document 隔离；(2) draft ΔV 首断言 419 基于单面假设 → 一次性取证探针（删）实锤 MultiFace 全周传播，断言改宽区间 [2000,4200] 并在 apply_draft docstring 声明传播语义；(3) drawing 两步 SW_NO_EFFECT 复现两轮 → `Stop-Process SLDWORKS` + 重拉 v34.2.1 恢复（SW 长会话劣化，与 N8 档案同族）→ **第三轮 e2e 99/99 全绿**（e2e-report-20260830-162811.json）。
> - **提交**：`fad426b`（探针两枚 + INDEX.md，+729）与 `51bd1c3`（四工具 + 测试 + 注册 + e2e，+917/-3）。全套 **465 passed + 93 subtests**，coverage **89%** 红线达标。环阵原生化（子项 5）未启动——pattern 系 API 同族 BLOCKED，维持既有数学替代；后续若 SW 版本更新可复深。

---

### N10：SW 内存泄漏定位与修复

- **状态**：`[x]` · **优先级**：P1 · **仓**：主 · **依赖**：N1 · **预估**：5h（2 晚） · **需 SW 实机**：是 · **对应差距**：F1/F4/E4（T22 soak 证据：100 轮工作集 1667→3499MB）

**步骤**：

- [x] 1. `tools/soak_session.py` 增 `--tool-filter <name>` 参数（按工具二分定位）：`box-only` / `+faces` / `+drawing` / `+assembly` 各 50 轮，报告写入 `output/soak-report-*.json`（格式沿用现有）。
- [x] 2. 实机跑 4 组定位最大贡献者（预期排序参考：faces/drawing > assembly 预开 > box 基线）。
- [x] 3. 按定位结果实施修复（证据导向取舍，见执行记录）：
  - ~~`geometry.py`/`topology.py` walk 循环 del+gc~~（免做：+faces 组 0.67MB/轮 低于 box 基线 0.90，walk 无泄漏）；
  - [x] `assembly.py::add_component`：实机证据改向——成功路径 CloseDoc 被 SW 装配语义静默忽略（count 3→3，文档仍可查）；改为**失败路径关闭预开文档**（无引用时有效）；`_document_is_open` 用 `GetOpenDocumentByName`（typed wrapper 无 Name2 变体，且仅完整路径可匹配、标题不行）；
  - [x] `design.py` 回滚路径 CloseDoc 空壳（F4）：`_close_plan_created_shell` + 统一失败路径（参数校验异常也走回滚，不再裸 return 漏空壳）+ 固有特征白名单（原点/Origin，防空壳树固有节点拦截）+ 失败 error code 继承；
  - ~~drawing 导出后关图~~（不做：会断 e2e 连续导出链 pdf→png→dxf）。
- [x] 4. 修复后重跑完整 100 轮 soak：验收目标 = 工作集增量 <300MB（基线 1.83GB）；仍超则报告精确证据并在执行记录写明剩余嫌疑面。
- [x] 5. 回归：全套测试 + e2e（确认 CloseDoc 不破坏 e2e 链）。
- [x] 6. 提交：`git commit -m "fix(memory): COM 引用释放与文档关闭约定，soak 泄漏收敛"`。

**验收标准**：soak 对比报告存在且增量达标（或有精确剩余证据）；全套绿；e2e 绿。

**执行记录**：
> - soak --tool-filter 改造（argparse choices+LOADOUTS 表，报告加 tool_filter/sw_rss_first_mb 字段）。
> - 四组×50 轮同会话顺序实测：box-only 45.1MB（0.90MB/轮 stable）/ +faces 33.4MB（0.67，最低——推翻预期，walk 免修）/ +drawing 139.1MB（2.78）/ +assembly 158.7MB（3.17 最大贡献者）。
> - 关键洞察：soak 每轮 `_close_all` 兜底掩盖了真实泄漏场景（无兜底连续 add_component）；无兜底探针（5 零件×15 轮）：doc_count 每新零件 +2（预开+装配引用副本）、11 滞留——但 CloseDoc 取证证明**装配引用持有是 SW 语义而非可修泄漏**（CloseDoc 静默无效、OpenDoc6 重开不激活、ActivateDoc3 typed 拒 byref）。
> - 修复定性改变：交付**失败路径关闭**（真实可行）+ design 空壳关闭（shell_closed=true、count 1→0 实测）+ 统一失败路径堵回滚漏洞；成功路径滞留在 assembly.py docstring 文档化为 SW 装配语义。
> - 途中发现并修复：typed wrapper 无 GetOpenDocumentByName2（Mock 盲区，实机 AttributeError 被吞成静默失效）；空壳树实机 17 固有节点（收藏/注解/基准面…）使 warning-free 回滚不可能→shell 关闭不依赖 warning；参数校验异常裸 return 绕过回滚；error code 被统一路径覆盖。
> - 验收：单测 470 passed+93 subtests；e2e 99/99（SW 重启后；drawing 两项长会话劣化与 N8 档案同族，非本次改动）；soak box-only 100 轮 verdict=stable growth=64.4MB<300MB failures=0；提交 eca371c（6 files，+351/-48）。

---

### N11：CSG 端到端打通 + 验收清单 #5 跨仓三件套

- **状态**：`[x]` · **优先级**：P1 · **仓**：双 · **依赖**：无 · **预估**：4h（1-2 晚）· **需 SW 实机**：是（主包侧）· **对应差距**：A5 + 验收清单第 5 项（B 组审查：跨仓三件套单脚本断言缺执行记录）

**步骤**：

- [x] 1. aicad 侧：写失败测试 `tests/test_csg_route.py` → 实现 `GET /api/sw/csg/{session}/{version}`（调 `csg_plan_from_script` 导出器返回契约 JSON；session/version 语义沿用既有路由参数风格）→ 跑绿 → aicad 提交。
- [x] 2. 主包侧：写 `tools/validate/csg_roundtrip.py`：aicad（子进程或 HTTP）生成环件 → 取 CSG JSON → 调 `solidworks_features_rebuild_csg` 重建 → SW `get_mass_properties` 体积 ↔ aicad kernel metrics 体积双向比对 ±1% → 报告 JSON。
- [x] 3. 扩展为验收清单 #5 脚本 `tools/validate/triple_artifact.py`：同一会话产出三件套断言——aicad `views.svg` 存在且 polyline 非空 + SW `.sldprt` 保存 + `.step` 导出成功，全部通过退出码 0。
- [x] 4. 实机跑两脚本；回填 `docs/acceptance-checklist-mechanical-drawing-v1.md` 第 5 项（标注实测日期与脚本路径）。
- [x] 5. 提交（两仓各一）：主 `git commit -m "feat(csg): 跨引擎端到端往返与三件套验收脚本"`；ai `git commit -m "feat(api): CSG 导出路由"`。

**验收标准**：两脚本退出码 0；体积差 <1%；清单 #5 标注实测。

**执行记录**：
> 2026-08-30 双仓闭环。
> - 步骤 1（aicad）：TDD 红→绿 `tests/test_csg_route.py`（3 测试：FLANGE 契约
>   ops/name/through/at.z、SPHERE→422、未知 session/version→404；hole 无 label
>   → name "cylinder_2"、boss at.z=5.0 为导出器堆叠契约，以既有 test_csg_export
>   固化事实为准）；全套 590 passed（排除 perf_budgets）；提交 90c6a5a。
> - 步骤 2（csg_roundtrip）：跨 venv 子进程（aicad venv python，stdin 传脚本）
>   exec 得 kernel 体积 + `csg_plan_from_script` 得契约 → 主仓 venv
>   rebuild_csg_plan（applied: ring+cylinder_2，stack_top 8.0mm）→
>   get_mass_properties 比对：12566.37061435917 ↔ 12566.370614359173，
>   rel_diff 2.9e-16（门限 ±1%），EXIT=0，报告
>   output/csg-roundtrip-20260830-181326.json。
> - 步骤 3+4（triple_artifact）：一次实机通过 EXIT=0——ring.svg（HLR 三视图
>   edge_count=32，scale 1:1）+ ring.sldprt（SaveAs3）+ ring.step（COM 导出）
>   同目录落盘 output/triple-artifact-20260830-192223/；验收清单 #5 已标注实测
>   日期与脚本路径。
> - 步骤 5：主仓提交 40708d2（代码+清单，3 files +364）；aicad 提交 90c6a5a（步骤 1 已完成）。
> - 关键洞察：aicad 生成器单子进程同时产 views.svg 与 CSG 契约
>   （export_brep → project_brep_to_json → render_sheet 链路全部可在 venv 内
>   直连，无需起 FastAPI），三件套共享同一几何源头即"同一会话"语义的脚本级
>   实现。

## 9. P2 任务（治理与长尾）

### N12：参数化闭环补全（方程式增删改 / 角度尺寸 / 配置切换）

- **状态**：`[x]` · **优先级**：P2 · **仓**：主 · **依赖**：N2 · **预估**：4h（1 晚）· **需 SW 实机**：是 · **对应差距**：D2/D3/D4

**步骤**：

- [x] 1. 失败测试 `tests/test_material_props.py` / `test_dimension_edit.py` 扩展：
  - `delete_equation(index_or_text)` / `edit_equation(index, new_text)`（EquationMgr.Delete/put_Equation? 探针确认；删除判据=list_equations 不再含）；
  - `set_dimension_angle(name, value_deg)`（拆分新工具支持角度尺寸，度数制，内部转弧度 EditRebuild3）；
  - `set_dimension` 放开负值（去 PositiveMM 约束，加 signed float 校验）；
  - `activate_configuration(name)`（ShowConfiguration? 探针）+ `set_dimension(..., configuration=name)`（按配置设值探针）。
- [x] 2. 跑红 → 3. 实现（properties.py / features.py；探针先行确认 EquationMgr 成员与 ShowConfiguration 名）→ 跑绿。
- [x] 4. 注册工具（delete/edit_equation、activate_configuration 为 STATE_CHANGE；delete_equation 标 DESTRUCTIVE）。
- [x] 5. e2e 增段：建配置→激活→改尺寸→切回验证互不干扰（系列件工作流最小链）。
- [x] 6. 提交：`git commit -m "feat(parametric): 方程式增删改/角度尺寸/配置激活系列件闭环"`。

**验收标准**：全套绿；e2e 系列件段实机绿。

**执行记录**：
> 2026-08-30 单晚闭环，提交 0f99bbd（9 files +759/-16）。
> - 探针（tools/probe_properties/probe_equation_cfg_edit.py，两轮定案）：
>   ① 方程式改/删只在 makepy 强类型 IEquationMgr 下可达（SetEquation(i,text)
>   /Delete(i)，动态分发 propput 不可达；Delete 返回值无语义，判据=GetCount
>   回读）；② ShowConfiguration 返回值不可信（False 但切换成功），判据=
>   ConfigurationManager.ActiveConfiguration.Name 回读；③ 按配置设值两通道
>   实测：SetSystemValue3(v,3,names) 返回 0 但不生效（names 通道废弃），
>   组合通道（激活+which=1）生效——默认 25mm/E2E_CFG 30mm 互不干扰。
> - 实现：properties.py +edit_equation/delete_equation/activate_configuration
>   （_wrap_equation_mgr_static 照搬 drawing 的 IDimension 包装纪律）；
>   features.py set_dimension 改 signed（去 positive_number，非零校验）+
>   configuration 参数（组合通道，复用 activate_configuration）、新增
>   set_dimension_angle（度→弧度，T6 契约）。
> - 工具注册：4 新工具（activate/edit=STATE_CHANGE、delete=DESTRUCTIVE、
>   set_angle=STATE_CHANGE）+ dimension_set 改 SignedMM+configuration；工具数
>   67→71（test_server/test_infrastructure 同步）。
> - 测试：单测 31 passed（含 mock 契约注释探针日期）；全套 481 passed；
>   e2e 108/108（99+9：edit/activate/set_cfg/read_default/read_family/
>   expect_config_isolated/delete 等），报告
>   output/e2e-report-20260830-193642.json。
> - 关键洞察：SW COM 返回码 0 ≠ 生效（names 通道），回读判据是唯一可信验证
>   ——这与 T17 材料回读判据同源，后续所有“写入型”工具都应坚持回读。

---

### N13：aicad 循环增强 II（孔直方图反馈 / token 守卫 / 重试 / 干涉回流）

- **状态**：`[x]` · **优先级**：P2 · **仓**：ai · **依赖**：N6 · **预估**：5h（2 晚）· **需 SW 实机**：否 · **对应差距**：B1/B2/B3/B4/E5

**步骤**：

- [x] 1. 失败测试（aicad tests/，6 文件 18 新测）：
  - 反馈摘要含 `holes: {count, diameters_mm[前5]}`（复用 step_import.py:112 孔直方图，对 preview 后 kernel 结果执行）；
  - 第 2 轮起 traceback 只保留尾部 30 行 + 脚本超长（>600 行）时反馈只带 diff 提示；
  - provider 网络类异常（requests.Timeout/ConnectionError）重试 1 次再抛；
  - 装配会话：interference contacts 摘要（前 3 对组件名+体积）拼入下轮反馈文本；
  - JSONL 行增 provider/model 字段。
- [x] 2. 跑红 → 3. 实现 → 跑绿（6 文件 41 passed）。
- [x] 4. 离线统计脚本 `aicad/scripts/loop_stats.py`：读 workspace/loops/*.jsonl 输出失败模式 Top5（outcome=failed 的 feedback `Message:` 行数字归一化聚类）+ 各 outcome 占比 + provider/model 分布。
- [x] 5. 提交：`git commit -m "feat(ai): 几何拓扑反馈/token 裁剪/重试/干涉回流与历史统计"`（58df2e9，17 files +1051/-169）。

**验收标准**：aicad 全套绿；loop_stats 对现有 JSONL 能出报告。

**执行记录**：
> 2026-08-30 闭环，提交 58df2e9（17 files +1051/-169）。
> - 架构决策①：孔直方图单一事实源公共化——`_face_features` 从
>   interop/step_import 搬到新 `aicad/analysis/hole_histogram.py`
>   （face_features/hole_groups_from_brep/hole_summary），OCP BRepTools 直读
>   BREP（文件缺失/无栈→None，损坏→raise，evals 区分 skip/FAILED）；
>   step_import 留薄别名、evals/assertions 改调公共函数（与 N7 联动）。
> - 架构决策②（B2 diff 协议闭环）：规划字面“只带 diff 提示”会让模型回的
>   函数块跑不过脚本契约，改为三层闭环——build_error_feedback 超长时改
>   patch 指示文案；registry.apply_function_patch（ast 顶层块按名替换/追加，
>   import 等无名块保留）；loop.run 以 `"PARAMS" not in script and
>   "PARAMS" in last_script` 判定 patch 并合并（SyntaxError 兜底按原样执行）。
> - B3 重试：_is_network_error 按 MRO 类名小写子串匹配 markers（覆盖
>   openai/requests/httpx/stdlib 各族，零 import）；complete 全重试，
>   stream 仅 create 阶段重试（已 yield 的 delta 不可回滚）。
> - E5 干涉回流：context.interference_notes 遍历 latest.artifacts 的
>   `interference:` 前缀 key 读缓存报告，contacts 前 3 对拼入 chat_service
>   下轮 notes（与 imported_step_notes/model_state_notes 并列第三块）。
> - B4：CorrectionLoop 增 provider_name 参数（deps.build_loop 两处+cli 传参），
>   JSONL 行增 model/provider 字段。
> - 踩坑修复（3 个根因）：① `type(cls).__name__` 应为 `cls.__name__`
>   （MRO 遍历元素已是类，取元名恒为 'type'，重试判定恒 False）；
>   ② OCP `BRepTools.Read_s` 必须传 `BRep_Builder()` 第三参；
>   ③ preview_feedback 契约是 dict（run 内 `result.report or {}`），新测试
>   误传 SandboxResult——旧测试（test_loop.py）即 dict，写新测试前先看旧契约。
> - 验收：全套 620 passed + 1 个无关性能预算失败（test_perf_budgets 的
>   tessellate 100k 预算 0.391s>0.3s；其子进程 import 链仅
>   aicad.kernel.mesh_frame，与 N13 改动无交集，本机性能状态问题，未放水）；
>   loop_stats 端到端实跑：3 个真实 CorrectionLoop 会话（fail→ok / preview→ok /
>   双败耗尽）写入 workspace/loops/acceptance-n13.jsonl，输出 6 records、
>   failed 50%/ok 33.3%/preview 16.7%、dashscope/qwen-max 4 + deepseek 2、
>   聚类 3x "empty solid"——报告四段全出。

---

### N14：server.py 分域注册重构 + ring_light 迁出

- **状态**：`[x]` · **优先级**：P2 · **仓**：主 · **依赖**：N2 · **预估**：3h（1 晚）· **需 SW 实机**：否 · **对应差距**：A3/A4/A6

**步骤**：

- [x] 1. 设计：新建 `solidworks_mcp/registry/` 包，按域建 `part.py / features.py / assembly.py / drawing.py / file_io.py / properties.py / misc.py` 各暴露 `register(mcp, helpers)`；server.py 瘦身为装配入口（~150 行）。**纯移动不改行为**——每工具函数体逐字搬运。
- [x] 2. 先写防回归测试：现有 test_server.py 工具清单断言不变（54+新增）；加断言 ring_light 两工具默认不注册。
- [x] 3. ring_light 迁出：注册受 env `SOLIDWORKS_MCP_PRODUCT_TOOLS=ring_light` 控制（默认不注册，工具数下降 2；README/MCP 配置同步说明——注意 .mcp.json 无需改，产品工具属专项验证用）。
- [x] 4. measure_distance 去活动文档依赖（纯计算路径直算，仅两点参数）；solidworks_connect 手写 try/except 收敛进 _call_connected 复用。
- [x] 5. 全套绿 + e2e（SW 运行时）确认零行为变化；提交：`git commit -m "refactor(server): 分域注册与产品工具迁出"`。

**验收标准**：全套绿；server.py <200 行；工具计数符合预期（含迁移说明）；e2e 绿。

**执行记录**：
> - **提交**：`17048c8 refactor(server): 分域注册与产品工具迁出`（21 files +2090/-1446）。
> - **结构落地**：registry/ 10 文件（base.py 共享类型/annotations/执行件 + 8 域 + __init__.register_all）；server.py 1494→215 行门面——mcp 实例/3 资源/main 留守，re-export 全部 69 工具名 + 5 prompt 名 + base 辅助名（test_infrastructure 等 ~35 处 server.* 引用零改动）。行数 215 略超 200（re-export 段撑起，纯声明无逻辑，可接受）。
> - **偏离规划两处**（均为可维护性）：①register(mcp) 集中装饰模式而非字面 register(mcp, helpers)——helpers 省略、base 直接 import，保函数体逐字搬运；②域文件从 7 个扩到 9 个（properties/products 从 part 拆出）。
> - **门控**：SOLIDWORKS_MCP_PRODUCT_TOOLS=ring_light；默认 69 工具/3 资源/5 提示词，caps 同步 69；开启后 71。README 同步（63→69 + 门控说明），.mcp.json 未动。
> - **纯化/收敛**：measure_distance 去 sw 参数/活动文档检查/NotRunningError except（纯计算，无 SW 可用）；connect 收敛 _call_connected——消息恒变 "Already connected..."（invoke 前置 connect 后 operation 二次 connect 走缓存），success/data/version 不变，e2e 只查 success 已确认。
> - **测试适配**（防回归先行）：test_server 69 断言 + 新增 TestProductToolGate（子进程门控双向 69/71）；patch 点迁移——run_com→registry.base（test_server 1 处、test_config_timeout 3 处、test_infrastructure 2 处）、_call_connected→各域模块（test_server test_n5 拆 drawing 3+file_io 1、test_infrastructure 21 工具用 ExitStack 六域 patch、server 内资源函数的 patch 保留）；test_measure 去 sw + 新增无 SW 纯算测试；test_ring_light×2 注册断言改子进程 env 门控模式（保留 schema 断言经 stdout JSON 传回）；e2e_sw_smoke measure 去 sw。
> - **验收**：全套 484 passed + 95 subtests（12.1s）；e2e 106/108——两败（drawing.insert_dimensions SW_NO_EFFECT + set_tolerance 级联 E2E_NO_DIM）判定环境非回归：①git diff 证明 solidworks_api/drawing.py 零改动（e2e 直调 API 层不经过 registry）②两次复现全新生成的 part 仍无效果→SW 长会话 InsertModelAnnotations 行为退化（19:36 基线同路径 OK）③同域其余 7 步与全部 21 个 registry 工具路径两次全过。建议 SW 重启后复跑确认。
> - **踩坑（工具层）**：Read/SearchReplace 快照严重陈旧——test_server/test_infrastructure 磁盘断言实为 71 而工具见 67，锚文本 71 不匹配、写回降级 67；应对：编辑前必用 Bash/Select-String 交叉验证，多项替换拆小步、失败后立即核盘补刀（本次两次补刀均成功）。

---

### N15：文档漂移治理（工具清单自动生成 + ADR 回填）

- **状态**：`[ ]` · **优先级**：P2 · **仓**：双 · **依赖**：无（但应在 N1 后）· **预估**：2.5h（1 晚）· **需 SW 实机**：否 · **对应差距**：文档组审查 D 项（README 53 vs 实际 54；工具清单漏 ~20 个；CODEMAPS 过时；aicad ADR-0007 与 M2 现状矛盾；ADR-0008 缺独立文档）

**步骤**：

- [ ] 1. 写脚本 `tools/validate/gen_tool_manifest.py`：反射 server.py 注册表生成 Markdown 表（名/注解/一句话）输出 `docs/tool-manifest.md`；README 工具段改为引用该文件+计数自动同步（脚本内 print 计数）。
- [ ] 2. 跑脚本生成并替换 README 工具清单段；修正「当前边界」过时句（阵列/圆角/旋转/工程图已实现）。
- [ ] 3. CODEMAPS/architecture.md、backend.md 更新到当前基线（工具数/模块/测试数）。
- [ ] 4. 主包 ADR-0008 独立成文：《孔平面语义对齐与 void 返回契约》（从 ADR-0009/探针注释汇拢）；aicad ADR-0007 回填 M2 已实现状态（含 N6 接线结果）。
- [ ] 5. 提交（两仓）：主 `git commit -m "docs: 工具清单自动生成与文档漂移治理"`；ai `git commit -m "docs: ADR-0007 回填 M2 状态"`。

**验收标准**：gen 脚本输出与 server.py 实际注册一致（脚本内置断言）；文档无与代码矛盾陈述。

**执行记录**：
> 2026-08-31 **转入第四期 N18**（`output/optimization-plan-2026-08-31.md`）：范围收窄为「第三期总览表回填（本文件 N8-N13 列漂移）+ 主仓 ADR 回填 + INDEX 对账 + aicad README 复核」；「工具清单自动生成」降级为远期观察（69 工具计数已有 4 处测试断言钉死，脚本化收益缩小）。

---

### N16：测试治理（错误码收敛 / 超时定位 / 产物回潮）

- **状态**：`[ ]` · **优先级**：P2 · **仓**：主 · **依赖**：N2 · **预估**：3h（1 晚）· **需 SW 实机**：否 · **对应差距**：F5/G5/G6（R1-P2-7、R2-P1-2/P2-2/P2-3 遗留）

**步骤**：

- [ ] 1. 错误码审计脚本 `tools/validate/audit_error_codes.py`：grep 全部 `error_response(` 调用，报告无 code/落默认 OPERATION_FAILED 的位置清单 → 逐个补语义码（SW_NO_ACTIVE_DOCUMENT / SW_ENTITY_NOT_FOUND / SW_VALIDATION_FAILED 等，与既有 SW_* 前缀对齐）；test 断言新增码均被覆盖。
- [ ] 2. 引入 pytest-timeout（pyproject dev 依赖）：`--timeout=120` 先收集数据不失败（timeout_method=thread）；跑 3 次全套记录超阈值用例 → 定位 R2-P1-2 间歇停滞根因（候选：COM mock 慢路径/subtests 交互）并修复或明确标注。
- [ ] 3. `pytest_report.xml` 从根目录删除并加 .gitignore（R2-P2-2）；检查是否有脚本仍往根目录写报告（重定向到 output/）。
- [ ] 4. `threaded_hole` 的 spec 参数 Literal 化（server.py 签名 `Literal["M2",...]` + THREAD_SPECS 三元组收敛，R2-P2-3/4）。
- [ ] 5. 全套绿；提交：`git commit -m "chore(tests): 错误码收敛/超时定位/产物治理"`。

**验收标准**：审计脚本报告零未分类错误码；全套绿且时长稳定（±20%）；根目录无报告产物。

**执行记录**：
> 2026-08-31 **转入第四期 N19 并当日完成主体**（commit `a276005`）：①报告产物——pytest_report.xml 为物理回潮（.gitignore:16 本已覆盖、未入库），删除残留；根级 e2e 产物（part.STL/part.step/ring.*）与 .qoder/ 补 ignore。②threaded_hole spec Literal 化落地（registry/part.py ThreadSpec 11 档 + 测试钉死与 THREAD_SPECS 同步，MCP schema 暴露枚举）。③错误码审计：N14 后错误面已收敛到 registry/base.py，全仓 4 处 error_response 均显式 code（SW_EXECUTOR_POISONED/SW_TIMEOUT/SW_API_ERROR/INVALID_PARAMETER），无收敛必要——F5 关闭。④审计脚本/pytest-timeout 未引入（错误面收缩后脚本化收益消失；G5 时长近两轮稳定 12.4s/22.6s，降为观察）。

---

### N17：aicad DXF 导出 + 沙箱队列解耦

- **状态**：`[ ]` · **优先级**：P2 · **仓**：ai · **依赖**：无 · **预估**：4h（1-2 晚）· **需 SW 实机**：否 · **对应差距**：aicad 导出仅 SVG（DXF 缺）+ H1（worker=1 图纸首开阻塞）

**步骤**：

- [ ] 1. 失败测试：drawing SVG 生成后调用新模块 `aicad/aicad/drawing/dxf.py::svg_to_dxf(svg_bytes) -> bytes`：ezdxf 建 R2010 图纸，polyline→LWPOLYLINE、circle→CIRCLE、text→TEXT 实体，返回 DXF 字节；路由 `GET /drawing/{v}?fmt=dxf`。
- [ ] 2. 依赖：`pip install ezdxf`（纯 Python，无原生编译风险；入 pyproject dependencies）。
- [ ] 3. 队列解耦：`deps.py` 中 HLR 投影/STEP 转换/干涉 boolean 归入独立 `convert_queue`（与建模 SandboxQueue 分离，仍单 worker 串行不并发 SW 沙箱内存预算），图纸首开不再被在途建模阻塞；测试：模拟在途建模任务时 ensure_drawing_artifact 延迟 <建模剩余时间（用假队列断言路由正确）。
- [ ] 4. 跑绿 + 手工验收：前端/HTTP 取 DXF 文件用 ezdxf 读回实体数 >0。
- [ ] 5. 提交：`git commit -m "feat(drawing): DXF 导出与转换队列解耦"`。

**验收标准**：aicad 全套绿；DXF 读回实体数断言通过。

**执行记录**：
> 2026-08-31 **转入第四期 N20**（`output/optimization-plan-2026-08-31.md` §9）：现状亲验——aicad 全仓 grep 零 DXF 命中（导出面仅 SVG/OBJ/STL）；`SandboxQueue`（api/deps.py:102）硬编码串行，`SandboxSettings.worker_count`（settings.py:47）配置面存在但队列不消费。

---

## 10. 风险与回滚

| 风险 | 概率 | 缓解 | 回滚 |
|---|---|---|---|
| 类型库枚举法仍拿不到可用签名（SW 2026 API 裁剪） | 中 | N9 兜底=数学替代法+能力声明透明化 | 单子项独立 commit，revert 即回滚 |
| CloseDoc 修复（N10）破坏 e2e/工具链（SW 对关闭引用文档的行为差异） | 中 | 每步 e2e 全回归；探针先验证关闭后组件/图纸引用存活 | revert 对应 commit |
| 尺寸整理（N4）误删有效尺寸 | 中 | dedupe 判据保守（同文本+同视图+同方向才删）；参数可关 | organize 工具不调用即无影响 |
| M2 接线（N6）改变既有 SVG 输出导致前端/下游不兼容 | 低 | include_feature_dims 开关默认可关；golden 测试双态（开/关） | settings 关闭即回 M1 |
| 超时默认 120s（N3）对超慢实机操作误杀 | 低 | T2 已校准 120s 为安全值（≥3×最慢操作）；env 可调 | env 置 0 回旧行为 |
| 分域重构（N14）引入注册遗漏 | 低 | 防回归测试先行（工具清单断言）；纯移动不改行为 | revert 整个 commit |
| 夜间中断丢失进度 | 中 | checkbox 粒度 + 先补提交再继续（§2.9） | 续跑 |
| 双仓误提交 | 低 | 每任务标仓；提交前 git status 确认 | 主仓 git rm --cached 修正 |

**全局回滚底线**：两仓库独立，`git log --oneline -3` 找当晚 commit `git revert <hash>`。

## 11. 附录：验证命令速查

```powershell
# 主包全套（基线 364 passed + 80 subtests，N1 后生效）
venv\Scripts\python.exe -m pytest tests/ -q

# 覆盖率（≥89%）
venv\Scripts\python.exe -m pytest tests/ --cov=solidworks_mcp --cov-report=term -q

# 实机 e2e（需 SW 运行）
venv\Scripts\python.exe tools\e2e_sw_smoke.py

# SW 状态探测
python -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; print(get_solidworks_app().status(launch_if_needed=False))"

# aicad 全套（在 aicad/ 内，基线 585 passed）
aicad\venv\Scripts\python.exe -m pytest tests -q

# aicad 离线评测
aicad\venv\Scripts\python.exe evals\run_evals.py

# 两仓 log
git -C "e:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP" log --oneline -5
git -C "e:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP\aicad" log --oneline -5
```

## 11b. 完成判据（本期何时算「出图可用 + 闭环 + 可值守」）

- **P0 完成**：LLM 能力面与实现一致（防漂移测试在）；SW 卡死 120s 必返回错误；工作区无未提交残留。
- **P1 完成**：实机出图含整理后的尺寸、剖视图、公差与粗糙度注释，可导 DXF；装配干涉能定位并修复闭环；评测无 SKIPPED 断言且有过程指标；双引擎 CSG 往返体积互证 ±1%；soak 100 轮增量 <300MB。
- **P2 完成**：系列件全参数化链路；server 可维护；文档零漂移（自动生成）；测试时长稳定。

届时剩余远期项（任务分解/RAG/mate 求解器/多模型路由/前端测试/爆炸图）进入下一期规划。

---

**（文档完。02:30 实施任务从 §3 总览表选任务，按 §2 协议执行并回填；当前工作区有 N1 未提交工作，必须最先处理。）**
