# 08 · Quinn — COM 基础设施域深审报告

> **审查日期**: 2026-09-06
> **调研员**: Quinn（报告号 08，域字母 C）
> **代码快照**: 主仓 HEAD=0762b15（main）；工作区未提交（`output/optimization-plan-2026-09-01.md` M + `docs/review/` 未跟踪=本轮审查目录）。pytest 基线 538 passed + 105 subtests（AGENTS.md 记 537，09 域复核口径）。
> **方法声明**: 全程只读（红线 5 延伸）——除本报告文件外零写操作。所有 `文件:行号` 本轮亲 Read 核对（E-1）；计数类结论附命令与输出摘要（E-5）；否定性结论双词形复核（E-6）。
> **输入锚**: Alex 地图（01）/ Sam rubric（02）/ evolution-summary 2026-08-31（上轮）/ Jack/03 与 Nora/06 移交情报（批 1）。

---

## 中间发现落盘区（按子域，交报告前归并为问题清单）

### 子域 A：C-1 一票否决项独立交叉验证 —— **未命中，零绕过**

- 生产包内 COM 获取（Dispatch/GetActiveObject）仅 `solidworks_api/app.py:141`（GetActiveObject）与 `:146`（Dispatch），两处均在 `SolidWorksApp.connect()` 内——而 connect 由 `registry/base.py:143` 的 invoke lambda 调用、经 `:149 run_com(invoke, timeout=...)` 在 STA 线程执行。**合规**。
- E-6 双词形复核（第一轮 path=仓根 glob=`*.py`；第二轮 path=包目录）：`gencache|makepy|__oleobj__|GetModule|CoCreateInstance|ReleaseComObject` 真实命中面——
  - `gencache.GetModuleForProgID("SldWorks.Application")` 6 处（assembly.py:668-670,922-929 / drawing.py:674-676 / features.py:435-437 / part.py:10,569 / properties.py:247-249）＝**N5 typed-wrapper 提升模式**：将已持有 dynamic dispatch 包装为 makepy 静态类，**不创建新 COM 连接**；这些 wrap 函数均在 api 层（run_com 体内）调用——不构成 C-1 绕过。
  - `ReleaseComObject` 零命中（双词形+双口径）——Jack/03 移交「全仓零显式 COM 释放」独立证实（知情性评估见子域 D）。
  - 其余 CoInitialize 命中全在 `tools/`（探针/验证脚本，非生产运行路径）与 `tests/`（mock）。
- **方法论事故记录（E-6 现场教训）**：首轮复核用 glob=`solidworks_mcp/**/*.py` + path=仓根 → 两轮返回 No matches 假零命中（geometry.py:23 明明有 `/ 1000.0`）；改 path=包目录 + glob=`*.py` 后真命中。凡零命中结论必须以第二口径复活验证。

### 子域 B：连接生命周期（app.py 深读）

**B-1 已连接自愈 + status 自愈（同源双径，行为一致）**
- `connect()` 已连接路径（app.py:122-134）：RevisionNumber 探测失败 → `_app = None` → 走重连。`status()`（:178-188）同构。两处探测都在 COM 线程（connect 经 base.py:143 invoke；status 经 server.py:183 `run_com(_sw().status, ...)`）——合规。
- 自愈语义边界：`disconnect()`（:190-193）仅置 None（引用丢弃，非显式 COM 释放）——RCW 交 GC。见子域 D。

**B-2 connect() 决策矩阵（:136-148 逐分支实证）**

| GetActiveObject | should_launch | already_running | 走向 |
|---|---|---|---|
| 成功 | - | - | 直接连 |
| 失败 | False | False | raise SolidWorksNotRunningError（:145）|
| 失败 | False | True | **Dispatch**（:146，附到 ROT 延迟中的实例）|
| 失败 | True | True | **Dispatch**（同上）|
| 失败 | True | False | **Dispatch 冷启动**（:146-148，+Visible=True）|

- **发现 C08-1 候选（Dispatch 冷启动半初始化——aicad 已实证修复未回流）**：aicad/interop/sw_app.py:157-163 注释实证「Dispatch("SldWorks.Application") also spawns the exe, but the instance it creates sits half-initialised and rejects NewDocument (batch-10 probes)」，其解法是 `_launch_and_wait()`（:184-208：直接 Popen SLDWORKS.exe + 240s ROT 轮询 + 5s 间隔）。主仓 app.py:146-148 仍是 Dispatch 冷启动——**主仓带着 aicad 已修掉的已知缺陷**。触发面：`auto_start=True`（或 launch_if_needed=True）且 SW 未运行时首个建模类工具调用（NewDocument 族）。归 AR-4 升级证据（详见子域 F）。
- 边缘语义（记录不立项）：should_launch=False 且 already_running=True 且 GetActiveObject 持续失败（ROT 损坏）时，Dispatch 行为依赖 SW 单实例激活语义——aicad else 分支注释（:165-167）认可此路径（"already running but not yet in the ROT"），主仓同构。两仓一致，无发现。

**B-3 进程探针（_is_solidworks_process_running :46-92）**
- ctypes Toolhelp32 快照 + PROCESSENTRY32W 逐进程比对 `sldworks.exe`，handle 有 finally CloseHandle（:91-92）✓。
- `_same_session`（:18-43）：ProcessIdToSessionId 双查防跨会话误附（RDP/fast user switching）✓——**aicad 侧已删掉 session 过滤**（sw_app.py:79-80 无 `_same_session` 调用）——漂移方向：主仓保留、aicad 简化（aicad 沙箱环境单会话，合理）。

### 子域 C：单位换算收口跨域审计（C-4）

- **mm→m 正向**：收口函数 `mm_to_m`（geometry.py:21-23）全仓 62 处消费（Jack/03 零遗漏结论限于零件域）；**跨域复核发现 17 处 `/ 1000.0` 直写绕过收口**（数值等价、语义正确，但散落）：
  - `design.py:394`（螺纹 spec 直径 1 处）
  - `assembly.py:219,366,747,748,749`（AddComponent4 坐标×3、mate 距离、move 增量×3 共 5 处）
  - `drawing.py:478,581,582,601,705,706,799,800,859,860`（剖切线/公差/注记坐标共 10 处——:572 为校验表达式内、非独立换算，合计 11 行命中 10 处独立点）
  - 取证命令：`grep -rn "/ 1000" solidworks_mcp --include=*.py`（path=包目录口径）→ 18 行命中（含 geometry.py:23 定义本体）。
- **m→mm 反向**：无收口函数（geometry.py 无 m_to_mm），`* 1000.0` 直写 8 处（assembly.py:520,527,846 / features.py:218 / measure.py:60,61,64,65）——输出侧全直写。
- **角度 deg→rad**：无收口函数，`math.radians` 散写（decorations.py:242、features.py:328,596、assembly.py:364,802、part.py:581、pattern.py:171、ring_light 族若干）——capabilities 自述 `angle: "radian unless a tool says otherwise"`（base.py:192）与工具面 FiniteMM/FiniteAngle(deg)（base.py:48-51）的换算责任全在各 api 函数内散写。
- **结论**：换算正确性无发现（无漏换算/无直传 mm 进 COM——drawing.py:616 CreateLine 抽验：pos(x0,y0) 取自视图 Position 属性（米），cut_m/half/clear 常量全米制后缀，CreateLine(*line) 6 分量米制闭环 ✓，Jack/03 移交项清偿）；发现的是**收口纪律漂移**（mm→m 62 收口 vs 17 绕过；反向与角度零收口）→ C08-x 🟡 候选。
- E-6 复核：`* 0.001|1e-3` 词形零命中（path=包目录口径）——无第二换算字面量形态。

---

## 主会话接管段（2026-09-06 团长补完）

> ⚠️ 偏差登记：Quinn 子代理于子域 C 后无声阵亡（报告冻结 97 分钟，K-1 阵亡指纹），剩余子域（D/E/F + call_or_value + server.py）由团长主会话压缩收尾——深读范围收窄，验收标准不变（E 铁律照守）。

### 子域 D（压缩）：COM 释放知情性评估（Jack/03 移交清偿）
- `Marshal.ReleaseComObject` 全仓零命中（Quinn 子域 A 双词形已证 + Nora 互证）。**知情接受**：单 STA 线程（com_executor.py:33-42 `solidworks-com-sta` 守护线程）+ 进程生命周期 = RCW 交 GC 的常规 pywin32 形态；`test_memory_guard.py` 防线在位（Nora 域已审）。`disconnect()`（app.py:190-193）仅置 None 同语义。**不立项**——记 ⚪ 观察项 C08-4（若未来长会话多文档循环出现句柄压力再升格）。

### 子域 E（压缩）：STA 线程模型与毒化退程
- com_executor.py:1-60 亲读：单线程 apartment（`pythoncom.CoInitialize` 在 worker 首行 :50）+ 超时→`ComCallTimeoutError`→毒化→后续调用 fail-fast `ComExecutorPoisonedError`（:16-27 docstring 语义自证）+ `atexit` 注册收尾（:10）。**设计干净，无发现**——与 capabilities 自述 "serialized on one STA thread"（base.py）一致。
- 毒化后的 `SOLIDWORKS_MCP_POISONED_EXIT` 退程语义 Nora/06 已审（S06-7 ⚪ 知情面），本域不重复。

### 子域 F：AR-4 双仓漂移量化（团长实证）
- **函数级对照**（`grep -E '^(def |    def )'` 双侧 sort -u diff）：
  - 共享核 **10 函数**（connect/status/disconnect/_is_solidworks_process_running 等）；
  - **aicad 独有 4**：`_launch_and_wait`（:184-208 Popen SLDWORKS.exe + 240s ROT 轮询——冷启动修复机器）、`_find_sldworks_exe`、`_sw_exe_candidates`、`restart`；
  - **主仓独有 1**：`_same_session`（ProcessIdToSessionId 防跨会话误附——aicad 沙箱单会话删除，合理简化）。
- **漂移面比 Alex 估计更宽**：aicad/aicad/interop/ 下存在 **整套 COM 基建复制件**——`com.py`（16 行 vs 主仓 24 行）、`com_executor.py`（171 行 vs 主仓 122 行，aicad 侧多 49 行）——双源已实质分叉，且分叉方向**双向**（冷启动修复 aicad 领先、会话过滤主仓领先）。

### AR-7 实测定谳
- `get_config()` 生产调用面 **12 处**（registry/base.py、server.py、api/app.py、api/drawing.py、utils/security.py、utils/templates.py）——每工具调用链 2-3 次重建 frozen dataclass 属实，但 μs 级、无性能证据。**维持 ⚪（C08-5）**，Alex 推测标注成立。

### call_or_value 深审——**偏差登记：未完成**
- 24 行小工具（utils/com.py），Nora/06 与各域交叉引用均无异常信号；本轮接管未独立深读，留待后续审查（非缺陷信号，仅覆盖缺口披露）。

---

## 问题清单（终版）

### C08-1 🟠 Dispatch 冷启动半初始化缺陷——aicad 已实证修复未回流主仓
- 位置：solidworks_mcp/solidworks_api/app.py:146-148 vs aicad/aicad/interop/sw_app.py:157-163,184-208
- 证据：aicad 侧注释实锤「Dispatch("SldWorks.Application") also spawns the exe, but the instance it creates sits half-initialised and rejects NewDocument (batch-10 probes)」；其解法 `_launch_and_wait()`（Popen + 240s ROT 轮询）。主仓 connect() 仍走 Dispatch 冷启动。
- 影响量化：触发=`auto_start=True`（或 launch_if_needed=True）且 SW 未运行时首个 NewDocument 族调用 × 后果=半初始化实例拒建文档（工具报错，需人工重启 SW）。
- 根因：AR-4 双源无同步机制——修复停在 aicad 侧。
- 修复方案：把 `_launch_and_wait`+`_find_sldworks_exe`+`_sw_exe_candidates` 三件套回流主仓 connect() 冷启动分支（带实机验证）。

### C08-2 🟡 单位换算收口纪律漂移（数值正确、结构散落）
- 位置：mm→m 17 处 `/1000.0` 直写（design:394 / assembly×5 / drawing×10，行号见子域 C）；m→mm 反向 8 处直写；角度 deg↔rad 零收口（math.radians 散写）。
- 影响：换算正确性无虞（本轮零漏换算/零直传 mm），但「收口在 geometry.py mm_to_m」的架构承诺（AGENTS.md 红线 4 的实现层）只覆盖 62/79 场景——未来新增代码抄错方向的风险面敞开。
- 修复：反向/角度建收口函数 + 渐进归一（或 lint 守卫禁 `/ 1000.0` 直写）。

### C08-3 🟡 双仓 COM 基建整套双源分叉（AR-4 升级定谳）
- 证据：子域 F 量化（共享 10/aicad+4/主仓+1）+ com.py/com_executor.py 整套复制件（16↔24、171↔122 行）。修复方向双向：冷启动修复回流主仓（C08-1）、会话过滤取舍成文。
- 修复建议：ADR 化「同源契约」——或在 aicad 侧声明 fork 基线 commit 并记回流的单通道，或抽共享包（重投资，S5 v2 前评估）。

### C08-4 ⚪ 零显式 COM 释放的知情接受（子域 D）
### C08-5 ⚪ AR-7 get_config 无缓存维持推测级（12 调用点实证，μs 级）

## 上轮对照表
| 编号 | 状态码 | 本轮实证 | 一句话 |
|---|---|---|---|
| AR-4 | ➕升级 | 子域 F 函数级 diff | 漂移量化完成 + 比预估宽（整套基建复制），升级为 C08-3 🟡 + C08-1 🟠 载体 |
| AR-7 | ✅定谳 | 12 调用点 | 推测成立但维持 ⚪ |
| G8 相关（aicad 桥接） | 引用 09 域 | — | 桥接面归 Rita 域侧写 |

## 执行摘要（终版）
发现：🟠1（C08-1 冷启动缺陷未回流）/🟡2（C08-2 换算收口纪律、C08-3 双源分叉）/⚪2（C08-4/5）。
上轮对照：AR-4 升级定谳（双向漂移+整套复制件）、AR-7 定谳维持 ⚪。
STA/毒化/内存防线设计干净；call_or_value 深审因接管压缩未完成（偏差披露）。

