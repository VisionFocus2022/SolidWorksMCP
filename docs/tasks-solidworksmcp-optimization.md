# Tasks：SolidWorksMCP 架构优化实施规划（③ 实施规划文档）

**版本**: 1.0
**日期**: 2026-08-28
**关联审查**: `docs/architecture-review-solidworksmcp.md`（①架构解析 + ②量化评估）
**档位**: 🔴 L3（SDW 定档声明见关联审查文档头部）

> 本文档把审查发现的缺点（P0/P1/P2）展开为可派工条目，分三波按 ROI 排序。
> 第一波为行为保持型修复（不改任何对外行为/几何契约），已于本次审查会话内执行并验证；
> 第二、三波为后续工作，需用户逐波裁决后启动。

---

## 0. 定档与门禁留痕（SDW 兼容）

- **定档**: 🔴 L3 — 确定性低（审查前问题分布未知）× 影响半径大（跨模块优化 + 架构审查硬触发器 #5「无版本管理/无回滚机制」命中）
- **门禁留痕（自治会话降级，阶梯 S1/S3）**: 本会话为自治运行（AskUserQuestion 类门禁无法获得实时响应），按 SDW 自治降级协议以 **S1 用户显式指令**（"使用架构技能对项目进行全面审查优化"）放行审查与第一波行为保持型修复；行为变更类动作（第二/三波）一律**只规划不执行**，留待用户裁决。留痕载体 = 本文档 + 关联审查文档 + 会话最终汇报。
- **回滚安全网**: 无 VCS，故第一波执行前已将待改文件备份至 `.audit-backup-20260828/`（8 个文件）。

---

## 1. 方案总览（三波 × ROI）

| 波次 | 主题 | 解决缺点 | 风险 | 状态 |
|------|------|----------|------|------|
| 🚑 第一波 止血 | 恢复可运行/可验证/文档对齐，不改行为 | P0-1(缓解)、P0-2、P1-2、P1-3(部分)、P2-1、P2-2、P2-4(部分) | 低 | ✅ 2026-08-28 |
| 🔧 第二波 可测化+解耦 | git 落地、消重复、拆层、补测试 | P0-1(根治)、P1-4、P1-5、P1-2(根治)、P2-5 | 中 | ✅ 2026-08-28（用户裁决"继续实施"） |
| 🚀 第三波 现代化 | COM 超时、ring_light 通用化、CI | P1-1、P1-6、P2-3、P2-6 | 高（需 PoC） | ◐ 部分提前完成（P1-7/P1-9/动作17/18），其余待办 |

---

## 2. 风险登记册（Risk Register）

| ID | 风险 | 概率 | 影响 | 缓解 |
|----|------|------|------|------|
| R1 | 无 VCS 下改动无法回滚 | 已发生 | 高 | 已做文件级备份；第二波首要动作即 git init |
| R2 | 误删 ring_light 已确认几何契约（tests 固化 225 LED / 44mm 球面等） | 低 | 高 | 第一波只删不可达死代码；每步跑全量测试 |
| R3 | 红基线（1 failed + coverage 63%）掩盖新引入的失败 | 中 | 中 | 第一波先修红 → 后续改动才有可信信号 |
| R4 | venv 重建后 pip/pywin32 版本与旧机器不一致 | 中 | 低 | 依赖有版本约束（mcp<1.29 等）；测试全绿即可信 |
| R5 | COM 挂死场景（SW 模态框）在无超时机制下无法自愈 | 中 | 高 | 第三波 P1-1 专项；此前 README 已提示手动启动 SW |

---

## 3. 第一波：止血（✅ 已执行，逐条验收）

### 动作 1：修复测试计数漂移（P1-2）
- **背景**: server.py 注册 22 个工具（`grep -c "@mcp.tool"` = 22，已验证），tests/test_server.py:22 断言 21 → 测试红。README 声称 20。三处数字互不一致。
- **验收标准（DoD）**: test_standard_surfaces_are_registered 断言 22 且通过；**新增**注册工具名集合与 `_capabilities()["tools"]` 列表集合相等的断言（消灭这一类漂移，而非只修本次数字）。
- **改动文件**: `tests/test_server.py`
- **风险/回滚**: 无行为影响；备份可回滚。

### 动作 2：删除 ring_light.py 不可达死代码（P2-1）
- **背景**: [ring_light.py:821](../solidworks_mcp/solidworks_api/ring_light.py:821) 无条件 `return _save_native_fallback(...)`，其后 824-865 行（STL 导入路径）永不执行；`_split_open_doc_result`（779-785 行）与 `swOpenDocOptions_Silent` 常量仅被死代码引用。
- **验收标准**: 删除后 `py_compile` 通过；全量测试通过；`write_ring_light_stl` 副产物（.generated.stl / .layout.json）行为不变。
- **改动文件**: `solidworks_mcp/solidworks_api/ring_light.py`
- **风险/回滚**: 死代码无测试依赖（test_ring_light.py 仅测几何与路径拒绝，已验证）；备份可回滚。

### 动作 3：消除 get_features 双实现（P1-5 部分）
- **背景**: [part.py:247](../solidworks_mcp/solidworks_api/part.py:247) 与 [features.py:110](../solidworks_mcp/solidworks_api/features.py:110) 几乎相同；server.py 只 import features 版，part 版为生产死代码（仅 test_part.py 引用）。
- **验收标准**: part.py 删除该函数；test_part.py 改从 features.py import；相关测试全绿。
- **改动文件**: `solidworks_mcp/solidworks_api/part.py`、`tests/test_part.py`

### 动作 4：修正搬迁漂移的配置与文档（P0-2、P1-3 部分）
- **背景**: .mcp.json/README 指向旧机器 `E:\机械设计\Solidworks\...`（当前实际 `E:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP`，.mcp.json 按原样直接用会启动失败）；README 工具数 20 → 实际 22；tests/test_ring_light.py:99 硬编码旧绝对路径导致 skipTest。
- **验收标准**: .mcp.json 的 command/env 路径指向当前机器真实位置；README 安装路径与工具数（22，含两个 ring_light 工具）与实现一致；test_ring_light.py 的 fixture 路径改为相对测试文件的锚定路径，skip 消除且测试真实执行。
- **改动文件**: `.mcp.json`、`README.md`、`tests/test_ring_light.py`

### 动作 5：重建损坏的 venv（P0-2 根因之一）
- **背景**: venv/pyvenv.cfg `home = C:\Users\one\.cache\codex-runtimes\...`（原机器 Codex 运行时，本机不存在）→ venv/Scripts/python.exe 无法启动。已用独立 `.venv-audit`（Python 3.12.9）验证依赖可装、测试可跑。
- **验收标准**: `venv/Scripts/python.exe -m pytest -q` 全绿（121 passed / 0 failed / 0 skipped）；venv 内 pip 升级至无已知 CVE 版本（pip-audit 复核）；`.venv-audit` 临时目录清理。
- **风险/回滚**: venv 为可再生构建产物（旧 venv 已损坏无价值），失败可再次重建。

### 动作 6：日志初始化移出 import 期（P2-2）
- **背景**: [server.py:114](../solidworks_mcp/server.py:114) 在模块 import 时调用 `_configure_logging()`，测试导入 server 即把 mock 堆栈写进运行日志（solidworks_mcp.log 中已实证）。生产入口 `python -m solidworks_mcp.server` 走 `main()`。
- **验收标准**: `_configure_logging()` 移入 `main()` 首行；测试运行后 solidworks_mcp.log 无新增测试堆栈；`-m solidworks_mcp.server` 路径日志行为不变。
- **改动文件**: `solidworks_mcp/server.py`

### 动作 7：补齐声明的 LICENSE（P2-4 部分）
- **背景**: pyproject.toml 声明 `license = {text = "MIT"}`，但项目树无 LICENSE 文件。
- **验收标准**: LICENSE 文件存在且与 pyproject 声明一致（MIT，著作权人 = pyproject authors 字段 "SolidWorks MCP Contributors"）。
- **改动文件**: `LICENSE`（新增）

### 第一波验证命令（三件套）
```bash
venv/Scripts/python.exe -m pytest -q                          # 实测：122 passed / 0 failed / 0 skipped（修复前 119P/1F/1S）
venv/Scripts/python.exe -m coverage run --source=solidworks_mcp -m pytest -q && venv/Scripts/python.exe -m coverage report   # 实测：63%（删死代码后分母 1792→1766 语句；缺口集中于 ring_light COM 路径，二波动作 12 解决）
venv/Scripts/python.exe -m py_compile solidworks_mcp/solidworks_api/ring_light.py solidworks_mcp/server.py   # 实测：0 error
```

---

## 4. 第二波：可测化 + 解耦（✅ 2026-08-28 执行完毕，逐条验收见 §10）

### 动作 8：git 版本管理落地（P0-1 根治）【本波第一优先】
- **背景**: 项目根无 .git，父目录 .git 为空目录，git 命令报 not a repository（已验证）。两次搬迁历史证明该项目会被移动，无版本管理 = 每次优化都裸奔。
- **DoD**: 项目根 `git init` + 首次提交（含 .gitignore：venv/、__pycache__/、*.egg-info/、.coverage、*.log、output/、.audit-backup*/）；`git log` 有基线提交。**commit 需用户显式批准（SDW 铁律：不自动 commit）**。
- **依赖**: 无（阻塞后续所有动作的回滚安全网）
- **工时**: 0.5h

### 动作 9：抽取共享模块消除重复（P1-5）
- **背景**: `swDocPART` 等 SW 常量在 5 个文件重复；`_linspace` ×2；`_latest_feature_name` ×2；`_select_plane`/`_select_front_plane`/`_select_top_plane` 三处近似实现；FeatureExtrusion2 的 23 参调用表 ×3 处；`_error_variants` ×2（file_io 与 ring_light_v3）。
- **DoD**: 新建 `solidworks_mcp/solidworks_api/constants.py` 与 `geometry.py`（或 sketch_helpers.py）；全仓 `grep -rn "^swDocPART" solidworks_mcp/` 命中 1 处；全量测试绿；覆盖率不降。
- **依赖**: 动作 8（有回滚网）
- **工时**: 4h

### 动作 10：_capabilities() 从注册表派生工具清单（P2-5）
- **背景**: tools 列表 22 项手维护字符串，与实际注册靠人肉同步（本次 20/21/22 三重漂移根源）。
- **DoD**: 列表由 `mcp._tool_manager.list_tools()` 名称派生（保持现有展示顺序需白名单排序或维持手排顺序+相等性测试）；新增契约测试：注册名集合 == capabilities 列表集合（第一波已先行加了该测试的静态版）。
- **依赖**: 动作 8
- **工时**: 2h

### 动作 11：ring_light v1/v3 去留裁决与物理隔离（P1-4）
- **背景**: 两个专用工具（MV-LRSS-H-80-W 环形灯）占源码 37%，v1 是 v3 的前身试错版本，能力上 v3（STEP 保形）覆盖 v1（原生 24 环带近似）的多数场景但依赖外部 STEP 源文件。
- **DoD（三选一，用户裁决）**: A) 删除 v1 工具与模块（保留 git 历史）；B) 迁移至 `examples/ring_light/` 与核心包解耦；C) 维持现状但归档说明。裁决后 server.py 相应减注册。
- **依赖**: 动作 8
- **工时**: A 1h / B 3h / C 0.5h

### 动作 12：补测试恢复覆盖率 ≥80%（P1-2 根治）
- **背景**: 总覆盖 63% < pyproject fail_under=80（已验证）。缺口集中：ring_light.py 25%（COM 建模路径 316 语句未覆盖）、ring_light_v3.py 45%、app.py 70%（20-62 行进程快照函数零覆盖）、com_executor.py 73%（关停路径）。非 ring_light 模块按实测表算术约 84%。
- **DoD**: 用现有 mock 模式补齐：ring_light 系 COM 构建路径（FakeModel 双）、app.py 的 `_is_solidworks_process_running`（ctypes 打桩或集成标注）、com_executor shutdown 分支；`coverage report` ≥80% 且 CI 化（见动作 14）。
- **依赖**: 动作 8、（动作 11 裁决影响范围）
- **工时**: 8h

### 动作 13：README/design 文档与实现对账（P1-3 根治）
- **背景**: design 文档（tools/ 分域层、fastmcp 选型、30/120s 超时、6 个错误码）与实现漂移；建议补 ADR 段记录两次搬迁与 ring_light 试错史。
- **DoD**: design 文档更新为 as-built 架构；新增 `docs/adr/0001~0003`（COM STA 单线程决策、晚绑定 vs 早绑定、ring_light 专用工具引入）。
- **依赖**: 无
- **工时**: 3h

---

## 5. 第三波：现代化 / 演进（⏸ 充分 PoC 后）

### 动作 14：CI 流水线（P1-2 长效）
- GitHub Actions windows-latest：pytest + coverage --fail-under=80 + pip-audit。阻止再出现"红基线合入"。依赖动作 8、12。工时 4h。

### 动作 15：COM 调用超时与挂死检测（P1-1）
- **背景**: [com_executor.py:62](../solidworks_mcp/utils/com_executor.py:62) `future.result()` 无超时；design §7 承诺 30s/120s 未实现。SW 模态对话框/挂死时所有工具无限期阻塞。
- **DoD**: `run_com(fn, timeout=...)` 支持超时并返回结构化 TIMEOUT 错误（不杀 STA 线程——COM 无法安全中断，超时后标记 executor 为 poisoned，后续调用快速失败并提示重启 server）；README 声明该行为。需 PoC 验证 SW 弹框场景。
- **依赖**: 动作 8、12。工时 8h（含 PoC）。

### 动作 16：ring_light 参数化升级为通用环形阵列工具（P1-4 演进方向）
- 把"9 行 21-29、225 LED"硬编码参数化为通用环形 LED 阵列生成器（行数/每行数量/角度域可变），旧契约用回归测试锁定。工时 16h。依赖动作 11、12。

### 动作 17：派生文件确认与 allowed_root 收敛（P1-6、P2-3）
- ring_light 系写 `.generated.stl`/`.layout.json` 副产物时同样走 `check_overwrite_confirm`；`.mcp.json` 显式设 `SOLIDWORKS_MCP_ALLOWED_ROOT` 为不含 aicad 的目录（或 aicad 迁出父目录）。工时 2h。

### 动作 18：模板发现版本参数化（P2-6）
- `DEFAULT_*_TEMPLATE_CANDIDATES` 的 `SolidWorks 2026` 硬编码改为由 `SOLIDWORKS_MCP_SOLIDWORKS_VERSION` 驱动，为 SW2027 升级做准备。工时 1h。

---

## 6. 依赖关系图

```
动作8 git落地 ──┬──> 动作9 消重复 ──> 动作10 capabilities派生
               ├──> 动作11 ring_light裁决 ──> 动作16 通用化(三波)
               ├──> 动作12 补测试 ──> 动作14 CI ──> 动作15 COM超时(三波)
               └──> 动作13 文档对账
动作1-7 (第一波, 已完成, 无依赖)
动作17/18 (独立, 可与二波并行)
```

## 7. 里程碑

| 里程碑 | 内容 | 累计工时 |
|--------|------|----------|
| M1 ✅ | 第一波止血完成（可运行/可验证/文档对齐） | 本次会话 |
| M2 | 二波完成（git + 消重复 + 覆盖率 ≥80% + 文档对账） | ~18h |
| M3 | 三波完成（CI + COM 超时 + 通用化） | ~31h |

---

## 8. 门禁勾选（SDW L3 · Tasks 门禁 = 门禁 4）

- [x] 探索门禁（S1 自治替代：用户显式指令 + 三栏账落盘于关联审查文档 §12.E）
- [x] PRD/审查门禁（S3 自治替代：①+② 文档落盘 = `docs/architecture-review-solidworksmcp.md`）
- [x] Design 门禁（S3 自治替代：第一波为行为保持型修复，设计决策内联于本表动作条目；行为变更类全部留待裁决）
- [x] Tasks 门禁（本文档；第一波已按本表执行并验证，见 §9 执行记录）
- [ ] 收尾门禁（最终汇报时由用户确认；本会话以最终消息呈现验证结果供事后复核）

## 9. 第一波执行记录（✅ 2026-08-28 回填）

| 动作 | 结果 | 验证 |
|------|------|------|
| 1 修测试计数+新增集合相等契约测试 | ✅ 21→22；新测试 `test_advertised_tool_list_matches_registration` 通过 | pytest |
| 2 删 ring_light 死代码 | ✅ 删除 824-865 不可达块 + `_split_open_doc_result` + 孤儿常量（swDocPART/swOpenDocOptions_Silent）+ 未用 `import os` | py_compile + pytest |
| 3 消 get_features 重复 | ✅ part.py 删函数，test_part.py 改 import features 版 | pytest |
| 4 修搬迁漂移 | ✅ .mcp.json/README 指向 E:\SolidWorks 2026\...；README 工具数 20→22 并补列 2 个 ring_light 工具；test_ring_light.py fixture 改相对锚定（skip→真实执行） | pytest（skip 消除） |
| 5 重建 venv | ✅ py -3.12 --clear 重建；pip 升级至 26.2.1（pip-audit：No known vulnerabilities）；`pip install -e ".[dev]"`（egg-info SOURCES 刷新含 ring_light×4）；.venv-audit 临时目录已清理 | venv pytest 122 passed |
| 6 日志初始化移入 main() | ✅ server.py:114 模块级调用移除；**solidworks_mcp.log 大小/mtime 纹丝不动（176622B / 07-22 11:20）**——当日多次测试运行零写入 | ls 对比 |
| 7 补 LICENSE | ✅ MIT 文本与 pyproject 声明一致 | find |

**总验证**：122 passed / 0 failed / 0 skipped / 22 subtests；coverage 63%（<80%，属二波动作 12 范围，未解决非未申报）；py_compile 0 error；pip-audit 0 CVE。
**偏差记录**：①原计划期望覆盖率小幅提升，实测持平 63%（死代码行多为未覆盖行，删除同时缩小分子分母）——已如实回填；②动作 5 的 venv 重建使用 `--clear` 原地重建（旧 venv 已损坏无保留价值，142MB→重建）。

## 10. 第二波执行记录（✅ 2026-08-28 回填）

**授权留痕**：用户指令"根据推荐继续实施"（S1，含上轮报告列明的 #1 推荐 git init + 首提交）；ring_light 处置经 AskUserQuestion 显式裁决为"子包隔离+保留工具"。提交序列：

| 提交 | 内容 | 对应动作 |
|------|------|----------|
| `e6916e1` | git 基线（48 文件，venv/aicad/output/日志/egg-info/备份均被 .gitignore 正确排除） | 动作 8（P0-1 根治） |
| `c52ace8` | ring_light v1/v3 迁入 `solidworks_mcp/examples/`，22 工具全保留、行为零变化 | 动作 11（用户裁决选项 1） |
| `047b7ee` | 抽 constants.py / geometry.py / sketch.py / utils.com.make_error_variants 消 10 组重复；`_capabilities()` 改从注册表派生 + 契约测试升级为列表相等 | 动作 9、10 |
| `1787298` | 逐组件路径解析（junction 回归测试 RED→GREEN）+ 全部 sink 用规范化路径 + 派生文件 overwrite_confirm + 动态 LED 计数 + 模板版本化 | 三波提前项：P1-7、P1-6、P1-9、动作 17/18 |
| `197c5e7` | 覆盖率 63%→89%（ring_light 原生路径/v3 STEP 回退/进程探测/executor 分支/22 工具包装器/模板 getter 全覆盖）+ 删第二处死代码 `_create_spherical_dome_boss`（~70 行） | 动作 12 |
| （本提交） | ADR×5、design 文档 as-built 对账附录、README 补充 | 动作 13 |

**验证**：150 passed / 0 failed / 42 subtests；coverage **89% ≥ fail_under=80（项目质量门恢复绿色）**；无 CWD 测试污染（曾发现并修复）。
**偏差记录**：①动作 9 实施中 `part._select_plane` 的共享化曾引入语义变化（SelectByID2 兜底），被既有测试拦截 → 按"改实现不改测试"原则以 `use_extension_fallback=False` 保留原语义；②`normalize_path` 第一版实现（最深存在祖先法）被新 junction 测试**当场证伪**（`..` 末段时 `_getfinalpathname` 失败回退折叠）→ 重写为逐组件解析后转绿——TDD 闭环实证；③模板候选为装配体/工程图补了 Program Files 语言兜底（超集扩展，行为只增不减）；④测试期曾把副产物写入项目根（相对路径 save_path），已修复并清理。
**动作 11 备注**：审查文档 §11.4 P1-4 的"37% 占比"以迁移前统计为准；迁移后 `solidworks_api/` 仅含通用模块。

## 11. 三波剩余待办（2026-08-28 第三批执行后更新）

**已在本批完成**（用户指令"继续实施剩余待办" + 两项 AskUserQuestion 裁决）：
- ✅ 动作 15 COM 超时 + poisoned executor（默认关闭，`SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS` 开启；SW_TIMEOUT/SW_EXECUTOR_POISONED 错误码落地）
- ✅ auto-start 会话过滤（`ProcessIdToSessionId`，P1-8）
- ✅ TOCTOU 收紧（`ensure_sink_path` 写盘时刻复查，窗口分钟级→微秒级，P1-7 残余）
- ✅ P2-3 默认 allowed_root 收敛到项目根（显式配置不受影响）
- ✅ P2-8 → 新增 `solidworks_file_close` 第 23 个工具（用户裁决；显式关闭而非自动关闭）
- ✅ 动作 16 ring_light 行数通用化（1-64 行自由，默认 9 行产品布局不变；用户裁决本轮实施，见 ADR-0006.6）
- ✅ 动作 14 CI workflow 文件就绪（`.github/workflows/ci.yml`：pytest + coverage≥80 + pip-audit，windows runner）

**真正剩余（需外部条件）**：
- CI 生效需远端仓库（git remote + push 后自动激活）
- COM 超时启用后的实机验证（SW 模态框场景，确认超时值合理）
- CloseDoc/会话过滤的实机长会话验证
- 完整"通用环形阵列工具"如需独立立项（ADR-0006.6 边界声明）
