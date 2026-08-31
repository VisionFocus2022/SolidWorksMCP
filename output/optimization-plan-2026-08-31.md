# AI 驱动 3D 机械图全自动绘制——优化改进规划（第四期：治理收尾 + 交付可靠）

> **生成**：2026-08-31 全面审查会话（三技能审查：架构建模 + better-harness 证据包 + 代码级差距扫描；CodeRabbit 待 auth）
> **主题**：第三期收尾治理 + 本期审查新发现的立项修复
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考
> **For agentic workers:** 按任务逐项执行（§2 执行协议），步骤用 checkbox（`- [ ]`）跟踪，完成后回填状态与「执行记录」小节。

---

## 1. 文档定位与背景

本计划**承接第三期**（`output/optimization-plan-2026-08-30.md`，N1-N17）。第三期实际执行 **17/17 全部完成**（计划表未回填，见 §5-I1——N18 第一动作即回填）：

| 第三期任务 | 实际完成证据（git hash） |
|---|---|
| N1-N7 | 计划表已回填（04bf21f/33b1526/e1efbeb 等） |
| N8 装配修复闭环 | `e5afd1d`（干涉空间定位/delete_mate/组件变换/BOM 扩列） |
| N9 BLOCKED 解锁 | `51bd1c3`（镜像/拔模/真实螺纹原生工具 + 线性孔阵数学替代） |
| N10 内存泄漏 | `eca371c`（COM 引用释放与文档关闭约定，soak 收敛） |
| N11 CSG 端到端 | `40708d2`（跨引擎往返与三件套验收）+ aicad `90c6a5a`（CSG 导出路由） |
| N12 参数化闭环 | `0f99bbd`（方程式增删改/角度尺寸/配置激活系列件） |
| N13 aicad 循环增强 II | aicad `58df2e9`（几何拓扑反馈/token 裁剪/重试/干涉回流） |
| N14 server 分域注册 | `17048c8`（server.py 1140→206 行，工具迁入 registry/） |

另：aicad 侧「更像 SolidWorks」12 批次增强（batch 1-12，详见 aicad git log `5baea47..a615e05`）：SW COM 直连通道（Cone/螺纹孔/装饰螺纹/实机语义）、STEP 孔位提取、HLR 三视图+尺寸+BOM、剖视图（全局裁剪面+精确 BRepAlgoAPI_Section）、OBJ 导出、标准件族（轴承/紧固件/T型槽/齿轮）、preview 快速档、沙箱内干涉布尔。

**本期核心判断**：工具链与三大闭环（装配修复/评测验证/双引擎往返）已齐，剩余差距集中在三类——
1. **治理债**：第三期计划表漂移（6 任务完成未回填）、主仓六大特性零 ADR、生成物入库（pytest_report.xml 被 git 追踪）、根目录 e2e 产物无 ignore。
2. **交付可靠**：双仓（69 主仓源文件 + 51 aicad 测试文件）零 AGENTS.md——每日自动化与 AI 会话每次从零探索（better-harness task-understanding 52 分主因）；aicad 子仓无远端无 CI（reliable-delivery 55 分）。
3. **aicad 长尾**：DXF 导出缺失（图纸只有 SVG）；沙箱单 worker 串行（建模/HLR/STEP/干涉共一队列，图纸首开被在途建模阻塞）。

## 2. 执行协议（02:30 实施任务必读）

1. **选任务**：读 §3 总览表，选**第一个**状态 `[ ]` 且依赖全部 `[x]` 的任务。
2. **SolidWorks 前置检查**（标注「需 SW 实机」的任务）：
   ```powershell
   python -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; print(get_solidworks_app().status(launch_if_needed=False))"
   ```
   未运行则改状态 `[!] BLOCKED（SW 未运行，YYYY-MM-DD）`，转下一个可执行任务。
3. **TDD 循环**：写测试 → 跑红 → 实现 → 跑绿 → 实机验证（如需）→ 提交。禁止先实现后补测试。
4. **提交纪律**：每任务 ≥1 次本地 `git commit`（**绝不 push**）；主仓库/aicad 仓库分别提交，绝不跨仓。message：`feat|fix|test|docs|chore(scope): <一行中文描述>`。
5. **回填**：任务状态改 `[x]`（失败 `[!]` 注明原因）；「执行记录」小节回填日期/结果/commit hash/备注；更新 §3 总览行。
6. **节奏**：每晚 1 个任务为宜，最多 2 个（第二个必须 ≤2h 小任务）。
7. **安全红线**（继承）：COM 调用必须经 `run_com(...)`；文件操作在 `allowed_root` 内；破坏性工具标 `DESTRUCTIVE`；MCP 入参 mm、COM 层 m；主仓覆盖率 ≥89%。
8. **测试命令基线**：
   - 主仓库：`venv\Scripts\python.exe -m pytest tests/ -q` → 基线 **485 passed + 95 subtests，约 12-22s**（2026-08-31，N19 后含新 Literal 测试）；
   - aicad 仓库（在 aicad/ 内）：`venv\Scripts\python.exe -m pytest tests -q` → **620 passed + 1 perf 假红**（2026-08-31 实测 437s；tessellate 预算负载敏感，见 §12/N23——空闲机复验）；
   - 实机 e2e：`venv\Scripts\python.exe tools\e2e_sw_smoke.py`（需 SW 运行）。
9. **中断恢复**：读到未勾选步骤继续；已勾选产物未提交则先补提交。以 `git status`/`git log` 实时状态为准，勿信旧快照。

## 3. 任务进度总览

状态：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED。「仓」列：主=主仓库，ai=aicad，双=两者。

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N18 | P1 | 文档漂移治理（第三期回填 + ADR 回填 + INDEX 对账） | 双 | 无 | 3h/1晚 | `[x]` | 2026-08-31 主 76ac84b + ai d06fe43 |
| N19 | P1 | 仓库卫生与测试治理（生成物出库 + ignore + Literal 化 + 错误码审计） | 主 | 无 | 2h/1晚 | `[x]` | 2026-08-31 a276005 |
| N20 | P1 | aicad DXF 导出 + 沙箱队列解耦 | ai | 无 | 5h/2晚 | `[x]` | 2026-08-31 ai 25abb4c + afa700e（一晚完成 a+b） |
| N21 | P2 | AGENTS.md 双仓落地（AI 会话/自动任务导航） | 双 | 无 | 1.5h/1晚 | `[x]` | 2026-08-31 主 00db3e7 + ai df24618 |
| N22 | P2 | aicad 远端与 CI 绑定 | ai | 无 | 1h | `[!]` 承接至五期 N25（`output/optimization-plan-2026-09-01.md`；自动任务读最新日期计划，勿在本文件执行） | |
| N23 | P2 | aicad perf 预算空闲机复验（tessellate 100k ≤0.3s） | ai | 无 | 0.5h | `[ ]` 承接至五期 N26（同上） | |

> 远期观察项（本计划不排期，继承第三期）：任务分解 plan-then-execute、RAG 示例检索、mate 约束求解器、多模型路由、前端测试、特征级缓存、爆炸图、BOM 气泡引线、环阵原生 FeatureCircularPattern4、缓存命中率报表（H2）。

## 4. 现状快照（2026-08-31 基线）

### 4.1 主仓库 solidworks_mcp

- **测试**：484 passed + 95 subtests（12.39s，2026-08-31 实测）；工具数 69（`tests/test_infrastructure.py:167` 等四处断言钉死，README 已对齐）。
- **结构**（N14 后）：`server.py` 206 行只留 FastMCP 实例 + 3 resources + stdio 入口；11 个工具域模块在 `solidworks_mcp/registry/`（assembly/drawing/features/file_io/misc/part/products/prompts/properties/base）；产品工具（ring_light）env 门控。
- **源码卫生**：`grep TODO|FIXME|BLOCKED` 源码零残留。
- **新发现的问题**：见 §5。

### 4.2 aicad 仓库

- **12 批次增强**全部落地（`5baea47..a615e05` + T13-T23 收尾 5 提交）：SW COM 直连子集（makepy 静态代理）、preview 快速档、沙箱内干涉布尔、HLR 图纸、剖视图、OBJ/STL 导出、标准件族、M2 生产接线、评测 hole 断言、CSG 路由、循环增强 II。
- **残留**：DXF 导出缺失（`grep -rn dxf aicad/aicad/` 零命中）；`SandboxQueue` 硬编码串行（`deps.py:102` "Mirrors worker_count = 1"，`settings.py:47` 配置存在但队列不消费）。

## 5. 差距分析（本期审查发现，含证据）

> 标【亲验】者为本审查会话直接验证。

### I 治理债（文档与仓库卫生）

- **I1 第三期计划表总览列漂移**【亲验更正：N8-N13 各任务「执行记录」小节内容完整，仅 §3 总览表状态列未翻 `[x]`——git 已落（e5afd1d/51bd1c3/eca371c/40708d2/0f99bbd/17048c8/aicad 58df2e9）】→ N18。总览表是 02:30 自动任务选任务的唯一入口，列不翻会导致重复执行。
- **I2 主仓六大特性零 ADR**【亲验：`docs/adr/` 仅 0009 + 2026-08-28 一份；N8-N14 的架构决策（干涉定位算法、螺纹 helix 路线、COM 释放约定、CSG 契约、分域注册边界）无记录】→ N18。aicad 侧 ADR 0001-0008 齐备，主仓落后。
- **I3 tools/INDEX.md 未对账**【亲验：38 行 vs tools/ 5 个探针目录 + 4 个脚本，N8-N14 新增探针（probe_n10_leak 等 output/ 有产物但 INDEX 未核）】→ N18 步骤 3。
- **I4 pytest_report.xml 物理回潮（已被 ignore 覆盖，未入库）**【亲验更正：`git ls-files` 零命中，`.gitignore:16` 已含该名——第三期 G6 的"回潮"实为历史会话显式 `--junitxml` 落根的物理残留，非 git 卫生问题】→ N19 步骤 1 收窄为物理清理。
- **I5 根目录 e2e 产物无 ignore**【亲验：`part.STL`/`part.step`/`ring.generated.stl`/`ring.layout.json` 四件 untracked 挂根】→ N19。
- **I6 threaded_hole spec 未 Literal 化**【亲验：`registry/part.py:215` `spec: NonEmptyString`，docstring 说 M2-M20 但 schema 不暴露枚举——LLM 只能猜】→ N19。第三期 G6 遗留，N14 迁移后仍未修。

### J 交付可靠性（AI 协作基础设施）

- **J1 双仓零 AGENTS.md**【亲验 + better-harness task-understanding 52 分：69 源文件主仓与 aicad 均无；每次 AI 会话/自动任务重新探索结构、命令、红线】→ N21。这是「无人值守」目标下杠杆最高的文档投资。
- **J2 aicad 子仓无远端无 CI**【better-harness reliable-delivery 55 分；与主仓 T19 遗留同源】→ N22。BLOCKED：等用户提供远端 URL。
- **J3 CodeRabbit 外审通道未通**（CLI v0.7.5 已装但 `auth status` = signed out）→ 等用户 `coderabbit auth login` 后补跑，非本计划任务。

### K aicad 长尾

- **K1 DXF 导出缺失**【亲验：全仓 grep 零命中；图纸导出面只有 SVG（batch 7）+ OBJ/STL（batch 9）】→ N20。机械图交付惯例 DXF 是下游 CAD/CAM 交换格式，SVG 不能替代。
- **K2 沙箱单 worker 串行**【亲验：`deps.py:102-105` SandboxQueue 注释自认 "one child process at a time"；第三期 H1：图纸首开被在途建模阻塞】→ N20。`SandboxSettings.worker_count`（`settings.py:47`）配置面已存在，队列实现不消费——接线即可，不必新造机制。

### L 已缓解项（本期验证后降级/关闭）

- **F5 错误码不统一**：N14 后错误面收敛到 `registry/base.py`（registry 各域仅 4 处显式 error_response，2 处带 code）——审计面从 54 工具缩到单文件，降级为 N19 内的只读审计步骤。
- **G5 测试时长间歇回归**：484 tests 12.39s（第三期记录 50-240s），近两轮稳定——降为观察项，不在本计划立项。
- **A1/A2 capabilities 漂移**：N2 已修且有 `tests/test_capabilities_sync.py` 钉死，484 绿含此断言——关闭。

## 6. 核心判断

第三期把「能力面」补齐后，当前距「AI 全自动出图且可无人值守」的最后三类缺口全部是**治理与可靠性**：
1. **状态源可信**（I1 计划表漂移会让下一晚自动化重复执行已完成任务）；
2. **协作者导航**（J1 AGENTS.md 缺失让每个会话付重复探索税）；
3. **交付格式与并发**（K1 DXF / K2 队列是 aicad 生产化的最后两块板）。

**路线**：N18+N19 一晚治理批 → N20 两晚 aicad 长尾 → N21 半晚导航 → N22 等远端解阻塞。

---

## 7. N18 文档漂移治理（P1，双仓，3h）

**目标**：让计划表、ADR、INDEX 三个状态源重新可信。

- [ ] 1. **第三期回填**：`output/optimization-plan-2026-08-30.md` §3 表 N8-N13 改 `[x]` 填日期/commit hash（N14 已回填）；各任务「执行记录」小节补一行（引用 §1 表格的 hash 即可，不重写）。
- [ ] 2. **主仓 ADR 回填**：`docs/adr/` 新增 2-3 份浓缩 ADR 覆盖 N8-N14 六特性（建议归并：`0010-assembly-repair-loop.md` 干涉定位+delete_mate+组件变换；`0011-native-features-and-memory.md` 螺纹/helix 路线+COM 释放约定+soak 结论；`0012-csg-cross-engine-and-registry.md` CSG 契约+分域注册边界）。每份 ≤60 行：背景/决策/取舍/证据 commit。
- [ ] 3. **INDEX 对账**：`tools/INDEX.md` 38 行 vs `tools/` 实际（5 探针目录 + 4 脚本）逐行对账，缺行补、死行删；N8-N14 期间新增探针（若有）登记。
- [ ] 4. **README 宣称复核**：主仓 69 工具已对齐（勿动）；aicad README 复核 12 批次能力宣称（preview/剖视图/OBJ/标准件族/CSG 路由是否已列）——缺则补。
- [ ] 5. 提交（双仓各一）：`docs(plan): 第三期 N8-N14 回填 + 主仓 ADR 回填（N18）`。
- [ ] 6. 回填本文件状态与执行记录。

**验收**：第三期表 N1-N17 全 `[x]` 或显式 BLOCKED；`docs/adr/` 覆盖六大特性；INDEX 与 tools/ 零差；两仓 README 宣称与实现一致。

**执行记录**：
> **2026-08-31 完成（主 `76ac84b` + ai `d06fe43`）**。①第三期 §3 表 N8-N13 翻 `[x]` 带 hash，N15-N17 补「转入第四期」指针记录（N16 记录当日完成主体）。②ADR 三份落 `docs/adr/`：0010 装配修复闭环 / 0011 特征解锁方法论+COM 内存 / 0012 CSG 契约+分域注册（各 ≤55 行，决策/依据/代价/证据 hash）。③INDEX 对账：probe_properties 补 `probe_equation_cfg_edit`（N12）、validate/ 补 `csg_roundtrip`+`triple_artifact`（N11）共 3 行；其余 24 行与实际零差。④aicad README：Roadmap 补 batch 9-12（OBJ/COM 子集/preview/沙箱干涉）+ 新增「循环增强 II」节（N13）。勘误两处自查：审查时曾误判「report.xml 被追踪」（实为 check-ignore 回显误读，见 I4 更正）与「validate/ 不存在」（ls 截断误判）——均已在计划中更正留痕。

---

## 8. N19 仓库卫生与测试治理（P1，主仓，2h）

**目标**：生成物出库、根目录干净、LLM 可见的参数枚举化。

- [ ] 1. **pytest_report.xml 出库**：`git rm --cached pytest_report.xml` + `.gitignore` 增 `pytest_report.xml`（本文件物理删除——可再生产物）。TDD 注意：先 grep 测试是否断言该文件存在（预期无）。
- [ ] 2. **根目录产物 ignore**：`.gitignore` 增 `/part.STL`、`/part.step`、`/ring.generated.stl`、`/ring.layout.json`（或归并为 `/part.*` + `/ring.*` 精确两族）。物理文件保留（本地产物）还是删除由实施时判断——若 `git status` 干净化即可达，保留。
- [ ] 3. **threaded_hole Literal 化**：`registry/part.py` `spec: NonEmptyString` → `Literal["M2","M2.5","M3","M4","M5","M6","M8","M10","M12","M14","M16","M18","M20"]`（枚举以 `solidworks_api/features.py` 的 THREAD_SPECS/tap 表为准，先 grep 实际支持的键）。TDD：新增测试断言工具 schema 的 enum 字段含全部档位 + 非法值被 pydantic 拒绝。**注意**：`design.py` execute_plan 的 threaded_hole op 若共享校验需同步；`tests/test_infrastructure.py` 工具 schema 快照若有需更新。
- [ ] 4. **错误码只读审计**：`registry/base.py` 错误路径列出现有 code 集合（预期 SW_TIMEOUT/INVALID_PARAMETER/OPERATION_FAILED/COM_POISONED 类）；若发现同一语义两种 code 或裸默认，收敛。产出写进执行记录即可（不强制改码——若 diff ≤10 行则顺手改+补测试）。
- [ ] 5. 全套测试绿：`venv\Scripts\python.exe -m pytest tests/ -q` → ≥484 passed + 95 subtests（Literal 化若加测试则 +N）。
- [ ] 6. 提交：`chore(repo): 生成物出库与 ignore 收口 + threaded_hole 枚举化（N19）`；`git status --short` 应只剩有意保留项。
- [ ] 7. 回填本文件状态与执行记录。

**验收**：`git ls-files | grep -E "pytest_report|\.STL$"` 零命中；`git status --short` 无 e2e 产物；schema enum 可见于 MCP 客户端；全套绿。

**执行记录**：
> **2026-08-31 完成（`a276005`，全套 485 passed + 95 subtests；aicad 顺带 `ecdae1f`）**。①步骤 1 收窄：report.xml 从未被追踪（I4 更正），物理删除残留；`.gitignore` 补根级产物（/part.STL、/part.step、/ring.generated.stl、/ring.layout.json）与 `/.qoder/`——主仓 `git status --short` 归零；**aicad 侧顺带**：`.gitignore` 整体 ignore `output/`（11 件 CAD/SVG 验收产物）与 `~$*` SW 锁文件。②TDD Literal 化：先加 `test_threaded_hole_spec_is_literal_enum`（断言 `ThreadSpec` get_args ≡ `THREAD_SPECS` 键集 + 工具 schema enum 透出）跑红（ImportError）→ `registry/part.py` 定义 `ThreadSpec = Literal[11 档]`（**实查 THREAD_SPECS 无 M14/M18**，计划草稿的 M2-M20 连续枚举是错的）+ 签名 `spec: NonEmptyString` → `spec: ThreadSpec`（保持必填契约，一度误加默认值 "M6" 已当场回退）→ 绿。③错误码审计（只读）：全仓 4 处 error_response 均显式 code（SW_EXECUTOR_POISONED/SW_TIMEOUT/SW_API_ERROR/INVALID_PARAMETER），F5 正式关闭。④审计脚本/pytest-timeout 未引入（N14 后错误面单文件化，脚本化收益消失；G5 近两轮稳定降观察）。遗留注记：aicad 两个既有未跟踪脚本 `tools/e2e_four_ring.py`/`tools/golden_flange_sample.py` 非本批产物，留归属会话处置。

---

## 9. N20 aicad DXF 导出 + 沙箱队列解耦（P1，aicad，5h/2晚）

**目标**：图纸可交付 DXF；图纸/导出类请求不再被建模阻塞。

### 9a DXF 导出（3h）

- [x] 1. **选型**：`ezdxf`（纯 Python，写 R2010 ASCII DXF；LINE/CIRCLE/ARC/TEXT/LWPOLYLINE 实体覆盖图纸所需）。加依赖进 `pyproject.toml`。
- [x] 2. **TDD**：`tests/test_dxf_export.py` —— box/cylinder 两夹具：导出文件可被 `ezdxf.readfile` 回读；实体计数断言（三视图轮廓线段数 > 阈值、中心线/尺寸文本存在）；与 SVG 路径同源（同一 HLR 几何输入）。
- [x] 3. **实现**：`aicad/export/dxf.py`（复用 drawing sheet 的 HLR 投影几何 → DXF 实体映射；图层分层：轮廓/中心线/尺寸/文字）；路由 `GET /api/sessions/{id}/versions/{v}/export?fmt=dxf`（fmt 已有 svg/obj/stl 先例——batch 9 的 lazy route 模式照抄）。
- [x] 4. **前端**：导出栏 DXF 按钮（OBJ 按钮旁，同构接线）。
- [x] 5. aicad 全套测试绿 + 主仓不动；提交 aicad：`feat(export): DXF 图纸导出（N20a）`。

### 9b 沙箱队列解耦（2h）

- [x] 6. **TDD**：`tests/test_sandbox_queue.py` —— `worker_count=2` 时两慢任务并发执行（总时长 < 串行之和，用 monkeypatch 假沙箱 sleep 0.5s 断言 <0.9s）；`worker_count=1` 行为不变（既有测试守护）。
- [x] 7. **实现**：`SandboxQueue`（`deps.py:102`）改为消费 `settings.worker_count`：N>1 时用 `asyncio.Semaphore(N)` + 任务集（保持单 worker 的有序语义可选：默认并发、prewarm 不变）。**红线**：OCCT/BRep 全局状态若非线程安全，worker 池 = 多**子进程**而非线程——先读 `kernel/sandbox.py` 确认 Sandbox 是进程隔离（是——每 Sandbox 一子进程），则池化安全。
- [x] 8. 默认值保守：`worker_count` 默认仍 1（行为不变，配置面打开）；`config.toml`/文档标注推荐值 2-3。
- [x] 9. aicad 全套绿；提交：`feat(sandbox): 队列消费 worker_count 配置（N20b）`。
- [x] 10. 回填本文件状态与执行记录。

**验收**：DXF 可导出且可被 CAD 读回；双慢任务并发实测提速；默认配置零行为变化。

**执行记录**：
> **2026-08-31 完成（ai `25abb4c` N20a + `afa700e` N20b，一晚做完 a+b；全套 631 passed exit 0 含新 10 测）**。**N20a**：落点偏差——渲染器放 `aicad/drawing/dxf.py`（与 hlr.py 同包复用布局数学）而非计划草案的 `aicad/export/dxf.py`（export/ 目录不存在，drawing/ 内聚更优）；配套把 render_sheet 的选尺度+填 ViewPlan 逻辑抽成 `select_sheet_layout` 单源共享（SVG/DXF 同布局，测试断言两侧 scale/sheet 尺寸一致）。ezdxf 1.4.4 venv 已有，显式入依赖 `>=1.3`。图层 OUTLINE/HIDDEN/DIMS/TEXT/FRAME（虚线设图层 linetype，实体 BYLAYER——探针实证后修正测试断言）；M2 孔标注在 DXF 落**真 CIRCLE 实体**（比 SVG 的标记点更 CAD 化）；HLR 曲线本就是离散折线，无 ARC 实体（诚实映射不做曲线拟合）；BOM 表/剖视留 SVG-only（stats 标注）。TDD：5 测先红（模块缺失+路由 400）→ 绿；补真实 OCCT 端到端 1 测（Box 40×30×10 HLR→DXF 回读，edge_count=24 与 SVG 金标一致）。路由 fmt=dxf 惰性物化+记忆化（复用 drawing 物化的 views.json，API 进程内映射，无 OCCT import）；前端 exportUrl 类型联合扩 "dxf"+按钮；npm build 绿。两处测试自身笔误被 RED 抓出（圆柱轮廓 1+2+2=5 写成 4；ezdxf 实体 linetype=BYLAYER 非 HIDDEN）。**N20b**：勘察发现 `WorkerPool` 已存在（kernel/sandbox.py，N 热子进程由 worker_count 喂，队列锁是唯一串行点）——计划"接线即可"判断正确；但**热路径也写 workdir/script.py+params.json**（runner `_worker_job`），纯信号量化会放同 workdir 并发踩scratch 文件 → 实现= `BoundedSemaphore(N)` 全局门 + **按 workdir 加锁**（同 dir 恒串行，不同 dir 并发——图纸/导出不再排建模后面）；用 threading 而非计划草案的 asyncio.Semaphore（run() 是同步线程池路径，FastAPI sync def 跑线程池）。TDD 4 测（并发 <0.9s / 默认 1 串行 ≥0.9s / 同 dir 双 worker 仍串行 / settings 接线 monkeypatch=3）。tier 计数补锁；config/default.toml 注释推荐 2-3；AGENTS.md 沙箱概念+基线 631 同步。提交拆分：deps.py 混 a+b 改动，用备份→checkout→重插 9a 块→提交→恢复→提交，两 commit 各自可编译（中间态 import+6 测验证过）。frozen 包 ezdxf 依赖 hooks-contrib 数据钩子，未实测 frozen 导出——留观察。**N23 顺带证据**：本日两轮全套（51%/62% CPU 负载、SW 运行中）perf 预算均绿（627/631），假红判断进一步坐实；严格空闲条件（SW 关+CPU<20%）未满足，N23 保持待执行。

---

## 10. N21 AGENTS.md 双仓落地（P2，双仓，1.5h）

**目标**：AI 会话与每日自动任务的「一次探索，处处复用」导航文件。

- [ ] 1. **主仓 `AGENTS.md`**（根目录，≤80 行）：项目一句话定位；目录地图（registry/ 11 域模块 ↔ solidworks_api/ 实现 ↔ tests/ ↔ tools/）；测试命令与基线（484+95）；安全红线五条（run_com/allowed_root/DESTRUCTIVE/mm↔m/覆盖率≥89%）；N 系列规划惯例（output/optimization-plan-*.md 的执行协议指针）；「改工具先看 test_infrastructure 工具数断言」。
- [ ] 2. **aicad `AGENTS.md`**（≤80 行）：双引擎架构一句话（build123d worker + SW COM 通道）；测试命令与基线；沙箱/preview/缓存三概念索引（batch 11 commit message 与 README 已有素材）；ADR 指针（docs/adr/0001-0008）。
- [ ] 3. 两文件互相交叉引用（主仓提 aicad 子仓存在与自治边界：绝不跨仓提交）。
- [ ] 4. 提交（双仓各一）：`docs(agents): AGENTS.md 落地（N21）`。
- [ ] 5. 回填本文件状态与执行记录。

**验收**：新会话冷启动读 AGENTS.md 后能直接说出测试命令与红线，无需 grep 探索。

**执行记录**：
> **2026-08-31 完成（主 `00db3e7` + ai `df24618`）**。两文件各 ~52 行：主仓含目录地图（registry/ 11 域模块定位 + "新工具加域模块别加 server.py"）、测试基线（485+95）、五条安全红线、N 系列规划惯例（含第四期 I1 总览表漂移教训）、工具计数 4 处断言提醒、aicad 子仓边界；aicad 含目录地图、三概念（沙箱 worker_count / preview 档 / 内核缓存）、测试基线 620 + **perf 预算负载敏感警告**（2026-08-31 实测 94% CPU 载下 0.434s 假红，禁放室断言）、评测集命令、双仓纪律。互相交叉引用达成。

---

## 11. N22 aicad 远端与 CI 绑定（P2，BLOCKED）

- [ ] 1. **等用户提供远端 URL**（gitee/github 均可）。
- [ ] 2. 解锁后：`git remote add` + 首推；主仓 CI 模板（若有）复刻到 aicad（pytest + npm build 两 job）。
- [ ] 3. 回填状态。

**执行记录**：
> （待回填）

---

## 12. N23 aicad perf 预算空闲机复验（P2，0.5h，需空闲机）

**背景**【2026-08-31 亲验】：全套 620 passed + 1 failed——`tests/test_perf_budgets.py::test_tessellate_100k_faces_under_0.3s` 实测 0.434s（预算 0.3s）。定性为**环境假红**：①当帧 CPU 负载 94%、SLDWORKS.exe 在跑；②全套 437s vs 第三期基线 219s（OCCT 重载套件整体 ~2x 慢），主仓纯 Python 套件速度正常（12.4s）——整机慢而非 tessellate 回归；③分相实测 BRepMesh 原生 0.07s 正常、提取循环被负载拖慢；④提取代码自 batch 9（预算校准提交）后零改动。

- [ ] 1. 空闲机（SW 关闭、CPU <20%）复跑 `venv\Scripts\python.exe -m pytest tests/test_perf_budgets.py -q`：绿 → 关单（假红确认）；仍红（>0.3s）→ 开提取循环微优化批（候选：`nodes.tolist()` 一次转列表后纯列表切片 extend，替代 array 切片；预期能拿回 20-40%）。
- [ ] 2. 结论回填本节；若走优化批，预算线不动（禁放室断言过闸）。

**执行记录**：
> （待回填）
