# 06 · Nora — 安全加固域深审报告

> **审查日期**: 2026-09-06 | **调研员**: Nora（报告号 06，域字母 S）
> **代码快照**: 主仓 HEAD=`0762b15aba049b6cfa4f807f79fb4aa78b62441f`（main）；工作区：`output/optimization-plan-2026-09-01.md`（M，gitignored）+ `docs/review/`（未跟踪，本轮审查目录）。快照取自报告收口时 `git rev-parse HEAD` + `git status --short`。
> **方法声明**: 全程只读（除本报告文件外零写）。所有 `文件:行号` 本轮 Read 亲验；normalize_path 攻击面用 `venv/Scripts/python.exe` 跑**无副作用纯读探针**（仅读文件系统，零写入）；计数类附命令与输出摘要；否定性结论双词形复核（E-6）。

---

## 执行摘要

- 发现计数：🔴 0 / 🟠 1 / 🟡 3 / ⚪ 4（新发现 S06-1..8）。**安全红线一票否决命中 0 处**：run_com 全覆盖（收口 2 处，Dispatch/GetActiveObject 仅 app.py 连接层）、落盘 sink 纪律 100%（17 处 SaveAs3 全用 ensure_sink_path 产物）、无「双门全无」工具。
- 最重要一条：**S06-1 🟠 `file_close` 默认丢弃未保存编辑且无实际确认门**（DESTRUCTIVE hint 在位但 `save_changes=False` 默认即静默丢弃，返回 success，与 `overwrite_confirm=False` 默认拒绝的安全哲学相反）。
- 防线正面实证：normalize_path 攻击面 8 向量实弹探针全部闭合（junction+`..`/8.3 短名/尾随点空格三变体/UNC/expanduser/`..` 穿越/大小写）；0297d77 缓冲区护栏边界条件经 API 语义复核正确。
- 上轮对照：**J3-1 ❌ 未修**（双词形零命中定谳）；AR-9 现状无漂移（3 依赖逐字一致）；修复史三提交（0297d77/5399b24/dddc10b）周边防线完好。

---

## 自验声明

- [x] E-1 行号亲验——本报告所有行号本轮 Read 核对（含探针输出的路径实证）
- [x] E-2 提交态/工作区态双查——快照头部记录；`output/` 结论走盘上态（该文件 gitignored 不在版本库，M 状态不影响本轮任何证据）
- [x] E-3 上轮继承项重证后才标状态码——J3-1 双词形 grep；AR-9 cat 对照；修复史 git log 亲取
- [x] E-4 🟠 及以上附影响量化（S06-1 触发频率×最坏后果已写）
- [x] E-5 计数类附命令与输出摘要（run_com 分布、annotation 分布、overwrite_confirm 清单、sink 盘点）
- [x] E-6 否定性结论双词形复核——"GetLongPathNameW 无 mock" 用 `GetLongPathNameW` + `windll` 双词形（注释命中/调用零命中；windll 全零）；"registry 层零直连" 用 `run_com|_sw()|get_solidworks_app` 聚合 grep
- [x] §10 禁则自查——无风格偏好类、无未取证推测（S06-7/S06-8 的推测成分已显式降 ⚪ 并标注）、无转抄宣称（探针独立验证）

---

## 问题清单

### S06-1 file_close 默认丢弃未保存编辑且无实际确认门
- 级别：🟠 —— rubric §3 判据⑤（安全护栏有洞需特定条件穿透）+ §8 精确化条款「仅有 annotation 无实际门 → 🟠 起」；不触发一票否决（DESTRUCTIVE annotation 在位，非双门全无）
- 位置：`solidworks_mcp/registry/file_io.py:34-42`（签名+注册）+ `solidworks_mcp/solidworks_api/file_io.py:146-185`（实现）
- 证据：签名 `def solidworks_file_close(save_changes: bool = False, ...)`（:35）；实现中 `save_changes=False` 时直接 `sw_app.app.CloseDoc(title)`（:170）不保存、无任何确认参数；注册处 `annotations=DESTRUCTIVE`（:94）。docstring 明示 "unsaved edits are discarded unless save_changes=true"（:38）。对照同仓安全默认范式：`overwrite_confirm: bool = False` 是**默认拒绝覆盖**（check_overwrite_confirm 拦截，security.py:180-188）；file_close 是**默认执行丢弃**。
- 影响量化：触发频率=AI 建模工作流中调用 file_close 且当前文档有未保存修改（常见序列「建模→关闭」中 AI 忘记先保存）× 最坏后果=整个建模会话成果不可逆丢失，且工具返回 success（`data={"title":..., "saved": False}`），AI 侧无失败信号——成果丢失**静默**。
- 根因：非安全默认值 + 确认门缺失；与 overwrite_confirm 的默认拒绝哲学不一致。
- 修复方案（最小）：加 `discard_confirm: bool = False` 参数——检测到文档有未保存修改（`model.GetSaveFlag`，需实机验证 API 名）且 `save_changes=False` 且 `discard_confirm=False` 时返回错误（提示二选一）；或 `save_changes: Optional[bool] = None` 三态（None=有脏修改时拒绝执行，要求显式选择）。补红绿测试。
- 维度/契约标签：D3 / C-3

### S06-2 落盘类工具 annotation 漂移：16 个带 overwrite_confirm 实际门的工具未挂 DESTRUCTIVE 系 hint
- 级别：🟡 —— rubric §8 精确化「annotation 缺失但实际确认门+测试在位 → 降 🟡」
- 位置：`registry/part.py:539-620`（part_new/plate/box/cylinder/cone/revolved/swept/loft/polygon/slot/annular_pattern/sheet_metal_base_flange/design_execute_plan 中的 13 个——create 族挂 STATE_CHANGE，仅 cut 族挂 DESTRUCTIVE）+ `registry/assembly.py`（assembly_new，STATE_CHANGE）+ `registry/products.py:85-92`（ring_light ×2，STATE_CHANGE）
- 证据：`grep -rn "overwrite_confirm" solidworks_mcp/registry/*.py | grep "bool = False"` → 21 处签名；对照 `grep -A3 "annotations=DESTRUCTIVE"`（12 函数）与 `annotations=IDEMPOTENT_WRITE`（5 导出）——落盘 21 件中 16 件挂 STATE_CHANGE（destructiveHint=False）。实际门与测试在位：check_overwrite_confirm（security.py:171-188，默认拒绝）+ validate_output_file 链 + test_utils.py:122-137 双测 + test_hardening.py:176-207（ring_light 派生产物拒绝）。
- 影响量化：触发频率=每个 AI 客户端会话读 hint 预判 × 后果=客户端把「可覆盖既有文件的落盘工具」当非破坏性工具（destructiveHint=False），破坏性预判面漏 16 件；运行时拦截无洞（默认拒绝覆盖仍生效）。
- 根因：hint 分档只按「材料切除=破坏」语义（cut 族）划分，落盘保存类工具未按「覆盖文件」语义归入 destructiveHint=True。
- 修复方案：带 save_path 的工具 annotation 统一换 IDEMPOTENT_WRITE（与 export 五件对齐，destructiveHint=True）；capabilities 的 safety 数组已正确宣称 "Overwriting an existing file requires overwrite_confirm=true"（base.py:230），hint 补齐即闭环。
- 维度/契约标签：D3 / C-3 / D8

### S06-3 test_hardening.py 的 `__main__` 块位于最后一个测试类之前——直接运行模式静默丢 3 用例
- 级别：🟡 —— rubric §3 判据②（测试基线/组织陈旧）
- 位置：`tests/test_hardening.py:253-259`
- 证据：`if __name__ == "__main__": unittest.main()` 在 :253-254；`class TestNormalizeExpands8_3ShortNames` 定义在 :257（其后）。Python 顺序执行：直接 `python tests/test_hardening.py` 时 unittest.main() 在类定义前运行且不返回 → 该类 3 用例（8.3 短名两防线 + undersized buffer 护栏）**永不定义、永不执行**。CI 走 pytest（模块导入全收集）不受影响。
- 影响量化：触发频率=开发者本地直接运行该文件（非 pytest）× 后果=安全防线最关键的 3 用例（CI 曾红的 8.3 短名 run 33582839316 + 0297d77 缓冲护栏）本地验证假绿。
- 根因：追加测试类时落在 main 块之后。
- 修复方案：main 块移到文件末尾（机械一行移动）。
- 维度/契约标签：D7

### S06-4 normalize_path 对盘符相对路径（`C:foo`）的语义歧义：拼入进程 CWD 而非解析到 C 盘当前目录
- 级别：🟡 —— rubric §3 判据⑤（护栏有洞但需特定条件；当前不可利用，防御性提示）
- 位置：`solidworks_mcp/utils/security.py:53-54`
- 证据：探针实弹——`normalize_path("C:foo.sldprt")` → `"E:\\SolidWorks 2026\\SolidWorksMCP\\SolidWorksMCP\\C:foo.sldprt"`，`is_path_allowed → True`。机制：`os.path.isabs("C:foo")` 为 False（有盘符但非绝对）→ `expanded = os.getcwd() + os.sep + expanded`（:54）把 `C:foo` 当相对段拼进 E 盘 CWD。Windows 真实语义是「C 盘当前目录下 foo」。**当前不可利用**：全仓 17 处 SaveAs3 sink 均传 ensure_sink_path/normalize 产物（本轮盘点），SW 收到含冒号路径 → 文件名非法 → SaveAs3 报错 fail-honest。
- 影响量化：触发频率=特定参数（AI 传盘符相对路径的传参错误）× 最坏后果=当前=SW 报错（无害）；**条件性升级**——若未来任一 sink 改用原始串传 SW，`C:foo` 会被 SW 按 C 盘当前目录解析=写出 allowed_root 之外（校验/使用分裂），届时升 🔴（红线 2）。此条兼作 sink 纪律的回归锚。
- 根因：`isabs` 检查先于 `splitdrive`，盘符相对形态落入纯相对分支。
- 修复方案：normalize_path 入口先 `splitdrive`——drive 非空且 `not isabs` 时直接拒绝（返回输入或抛错），或用 `os.path.abspath` 语义按该盘 CWD 展开。
- 维度/契约标签：D3 / C-2

### S06-5 status resource 的 run_com 调用无异常归一——毒化/超时抛裸异常
- 级别：⚪ —— 可观测性不一致，无安全后果（推测成分已验证：代码路径静态确证）
- 位置：`solidworks_mcp/server.py:181-185`
- 证据：`status = run_com(_sw().status, timeout=_com_timeout())` 无 try 包裹。毒化后每次读 resource 抛 `ComExecutorPoisonedError` → FastMCP 层报资源内部错误；对比工具侧 `_call_connected` 三分支归一（base.py:148-160，毒化给 SW_EXECUTOR_POISONED 结构化结果+恢复指引）。
- 影响量化：触发频率=毒化后每次 status 读取 × 后果=错误形态不一致（客户端看到裸异常而非恢复指引）。
- 修复方案：status resource 包 try，毒化时返回 `{"connected": false, "poisoned": true, "recovery": "restart-mcp-session"}`。
- 维度/契约标签：D4 / C-8

### S06-6 「零/负超时→None 无超时模式」从 env 不可达——base.py 防御分支为死代码，docstring 有误导
- 级别：⚪
- 位置：`solidworks_mcp/registry/base.py:111-114` + `solidworks_mcp/config.py:31-39`
- 证据：`_env_positive_float`（config.py:39 `parsed if parsed > 0 else default`）保证 `com_timeout_seconds` 恒正；test_config_timeout.py:30-33 锁定 `"abc"/"-5"/"0"` 全落回 120。故 `_com_timeout()` 的 `else None` 分支仅当代码级直接构造 ServerConfig 才可达。docstring "None keeps the historic no-timeout mode"（:112）暗示可配置关闭超时——读者认知漂移。
- 影响量化：无行为影响 × 文档误导。
- 修复方案：docstring 注明「env 层不可达，仅防御未来 config 变更」或删除分支。
- 维度/契约标签：D5 / D8

### S06-7 poisoned_exit 默认 False：毒化后进程存活的知情面观察
- 级别：⚪
- 位置：`solidworks_mcp/config.py:73` + `solidworks_mcp/registry/base.py:117-132`
- 证据：`_env_bool("SOLIDWORKS_MCP_POISONED_EXIT", False)`；默认路径返回 SW_EXECUTOR_POISONED 结构化错误（test_config_timeout.py:42-50 锁定）+ `=1` 时 `sys.exit(1)`（:61-67 锁定 SystemExit）。评估：stdio 无监督者的部署下退程=断连，默认 False 是合理保守；AGENTS.md 红线 1 的表述（`SOLIDWORKS_MCP_POISONED_EXIT=1`）暗示启用态，两者知情面存在张力；capabilities 的 safety 数组（base.py:227-233）未披露此开关。
- 影响量化：配置面知情 × 后果=配了监督器的用户不知道应开 1（毒化后需手动重启会话）。
- 修复方案：capabilities.safety 数组加一行披露；或 README 部署节注明。
- 维度/契约标签：D4 / D5

### S06-8 is_path_allowed("")==True——空串独立调用时放行（入口防线在 validate_path）
- 级别：⚪
- 位置：`solidworks_mcp/utils/security.py:75-90`（对照 :127-128）
- 证据：探针——`normalize_path("")` → CWD（项目根），`is_path_allowed("", root) → True`。`validate_path` 入口有 `if not path` 拦截（:127-128）；但 `ensure_sink_path`（:93-112）无空串检查——SW 收到 CWD 目录串会保存失败，fail-honest，无当前可利用面。
- 影响量化：防御深度不均 × 无后果。
- 修复方案：normalize_path 或 is_path_allowed 入口拒空。
- 维度/契约标签：D3

---

## 子域审计记录（一票否决三项的清账）

### 1. run_com 全覆盖（C-1）——✅ 零违规，不触发一票否决
- 收口形态：`run_com(` 全仓生产代码仅 2 处——`registry/base.py:149`（`_call_connected` 的 invoke，含 `sw.connect()` 在执行体内）+ `server.py:183`（status resource）。命令：`grep -rn "run_com(" solidworks_mcp/ --include="*.py" | grep -v "def run_com" | grep -v com_executor.py` → 2 行。
- registry 层 78 处 `_call_connected`（misc 3/part 27/features 10/properties 10/file_io 6/drawing 10/assembly 10/products 2）；差额 3 件全为纯计算白名单：`measure_distance`（misc.py:55）、`pattern_annular_layout`（part.py:434，docstring "without touching SolidWorks"）、`design_capabilities`（misc.py:47，静态声明）。
- `Dispatch|GetActiveObject|EnsureDispatch` 生产代码仅 `solidworks_api/app.py:141,146`（连接层单点，均在 connect 内=run_com 体内）；`gencache.GetModuleForProgID` 6 处（assembly/drawing/features/part/properties）全是函数内类型库查询（不产生 COM 对象调用），所在函数全部经 `_call_connected` 到达。
- registry 层直连形态（`run_com|_sw()|get_solidworks_app` 在域模块）双词形聚合 grep **零命中**。
- pythoncom 使用全为参数哨兵（Nothing）/VARIANT 构造/CoInitialize——非独立 COM 调用。

### 2. allowed_root / normalize_path 攻击面（C-2）——✅ 防线闭合
实弹探针（纯读，`venv/Scripts/python.exe -c`）结果矩阵：

| 向量 | 输入 | normalize/is_path_allowed 行为 | 判定 |
|---|---|---|---|
| junction+`..`（不存在尾段） | root\link\..\escape.sldprt | → base\escape.sldprt，allowed=False | ✅（test_hardening:76-97 锁定） |
| junction+`..`（存在尾段） | 同上且 escape 存在 | 入口 lexists→realpath OS 语义同结果 | ✅（静态推理+API 语义，未单测） |
| 8.3 短名 | PROGRA~1 类 | _expand_long_path 展开（RUNNER~1 CI 实战修复链 5399b24） | ✅（test_hardening:257-289 三用例） |
| 尾随点/空格/三点（目标已存在） | optimization-plan-…md + `.`/` `/`...` | realpath **全部剥离**（探针 stripped:True ×3）→ check_overwrite_confirm 命中真名拦截 | ✅ 实弹闭合 |
| 尾随点（目标不存在） | 新文件+尾点 | normalized 保留尾点传 SW → Win32 CreateFileW 剥离写同名（同目录=root 内）；overwrite 被前置存在检查拦截 | ✅ 闭合 |
| UNC | \\server\share\x | commonpath ValueError → False（security.py:85-89 防护） | ✅ 探针实证 |
| expanduser | ~/escape.sldprt | → C:\Users\888\…，allowed=False | ✅ 探针实证 |
| `..` 穿越 | root\..\..\escape | → E:\SolidWorks 2026\escape，allowed=False | ✅ 探针实证 |
| 大小写 | 大写输入 | is_path_allowed normcase 统一比较（:90） | ✅ 探针实证 |
| 盘符相对 | C:foo | 拼入 CWD，语义歧义 | 🟡 S06-4 |
| 空串 | "" | =CWD，allowed=True | ⚪ S06-8 |
| symlink | — | realpath 同 junction 语义（_getfinalpathname） | ✅（与 junction 同防线） |

- **sink 纪律 100%**（盘符相对向量的安全前提）：全仓 SaveAs3 真实调用 17 处（assembly 1/design 1/drawing 1/file_io 3/part 8/sheet_metal 1/ring_light 2 + 探针上下文）**全部传 `sink_path`（ensure_sink_path 产物）**；OpenDoc6/LoadFile4 读路径也全走 normalize（file_io.py:91,210-212；ring_light_v3）。命令与输出见审计过程（grep SaveAs3|Save3|LoadFile4|OpenDoc6 → 全 sink_path/normalized 形态）。
- 0297d77 缓冲护栏边界复核：GetLongPathNameW 成功返回 L（不含 null），信任条件 `0 < result < len(buffer)` 即 L ≤ len(buffer)−1——恰好覆盖「缓冲至少留 1 位 null」的正确边界；缓冲不足时返回所需尺寸（≥len(buffer)）→ 条件 False → fallback 输入（fail-closed 方向：CI 短名场景下 root 侧同步失败保留短名形态，commonpath 一致性按同形态比对，安全方向正确）。

### 3. 毒化退程（SOLIDWORKS_MCP_POISONED_EXIT）——✅ 语义链完整
- 毒化触发完备性：**仅** `FuturesTimeoutError`（com_executor.py:94-100）毒化；COM 异常（com_error）正常传播不毒化——正确设计（COM 错误可重试，线程卡死才不可恢复）。worker 的 `future.set_exception(BaseException)`（:66-67）保证单次调用异常不杀线程。
- 退程清理：`sys.exit(1)` 触发 atexit → `_executor.shutdown()`（com_executor.py:111-112 注册，join 2s 有界）。SW 侧文档不关闭（进程死后 COM 代理释放，SW 文档留给用户）——已知权衡，非缺陷。
- 毒化后行为：后续所有 call 快速失败（:84-85 检查在 put 之前，队列不积压）；不退程路径返回结构化错误+恢复指引（test_config_timeout.py:42-67 三测试锁定含 SystemExit）。
- 观察项 S06-5（resource 无归一）/S06-7（默认值知情面）。

### 4. DESTRUCTIVE 双门盘点（C-3）——见 S06-1/S06-2，无 🔴
- 双门齐备：export 五件（IDEMPOTENT_WRITE=destructiveHint True + overwrite_confirm 默认拒绝 + validate_output_file）✅
- 单门-annotation：file_close（S06-1 🟠）
- 单门-实际门：16 件落盘工具（S06-2 🟡）
- 超标注（无害）：feature_rename/feature_set_suppression 挂 DESTRUCTIVE 但行为可逆（rename 可改回、suppression 可翻转）——过度保守标注，对客户端预判无负面影响，⚪ 不单列。
- 非 DESTRUCTIVE 但合理：文档内建模修改（fillet/chamfer/shell 等）挂 STATE_CHANGE——SW 有 undo，不落盘，合理。

### 5. 超时配置链（D5）——✅ 完备
- 三态锁定：unset→120 / 合法值→解析 / 垃圾+非正→120（test_config_timeout.py:21-33）。
- AR-7 关联（get_config 无缓存）归 C 域，不重复报。

### 6. memory guard（D2）——✅ 在位
- test_memory_guard.py：裸 Mock 容忍 6 组入口 + RSS 预算断言（200MB，对 T10 O(n²) 事故 GB 级）——D2 维度良好实践，无发现。

---

## 上轮对照表

| 继承项 | 上轮定性 | 本轮重证证据 | 状态码 |
|---|---|---|---|
| J3-1 test_hardening GetLongPathNameW mock 细化 | minor 建议（地图判「仍挂账」） | test_hardening.py:296-297 仅 mock `ctypes.create_unicode_buffer`；`GetLongPathNameW`/`windll` 双词形在 tests/ 零 mock 命中（:292 仅注释提及）——undersized buffer 测试依赖**真实** API 调用，其走 buffer-growth 分支还是 result=0 失败分支取决于宿主机 `C:\PROGRA~1` 是否存在，非确定性 | ❌ 未修 |
| normalize_path 攻击面（P1-7 修复链 + 0297d77/5399b24/dddc10b） | 修复史周边=回归高发区 | 8 向量实弹探针全闭合（§子域2 矩阵）；护栏边界 API 语义复核正确；修复史三提交 git log 亲取确认无回退 | ✅ 防线完好（+S06-4 新观察） |
| poisoned_exit 语义链 | 上轮 N3 交付 | base.py:117-132 + test_config_timeout.py:42-67 三测试（结构化结果/connect 工具/SystemExit）锁定 | ✅ 在位（+S06-5/S06-7 观察） |
| DESTRUCTIVE 双门覆盖面 | 上轮未系统盘点 | 本轮全量盘点（§子域4）：🟠1 + 🟡1 簇 | ➕ 新盘点（S06-1/S06-2） |
| allowed_root 默认收窄涟漪（config.py:10-16） | 2026-08-28 收窄到项目根 | 注释链在位；默认=`_project_root()`（config.py:17-21）；测试基线全绿无越界回归 | ✅ 无涟漪 |
| AR-9 requirements.txt vs pyproject 双源 | 地图判「现状一致、无护栏」（07 域主责，顺带核） | `cat requirements.txt` 3 项（pywin32>=306 / mcp[cli]>=1.28.1,<1.29.0 / pydantic>=2.12.0,<3.0.0）与 pyproject dependencies 逐字一致 | 现状无漂移（双源无护栏风险仍在，移交 07 域） |

---

## 移交项与交主会话复核清单

**移交其他域**：
- → 07 F 域：S06-4 的条件性升级条款（「若任一 sink 改用原始串传 SW，盘符相对路径即成 🔴 绕过」）建议纳入 07 域 sink 审计的回归锚；AR-9 双源护栏（requirements.txt 无 CI 一致性检查）主责在 07。
- → 09 T 域：S06-3（main 块位置）修复后 test_hardening 直接运行收集数变化（+3）；测试基线 538 复核归 09。
- → 08 C 域：app.py 连接层（connect 自愈/status 断连探测/design.py:709 空白壳文档 CloseDoc 清理）本轮扫描无安全发现，行为细节归 C 域精读。

**需实机/需用户裁决项**：
- S06-1 修复方案的 API 选型（`model.GetSaveFlag` 是否为脏修改探测的正确属性）需实机验证。
- S06-7 poisoned_exit 默认值是否改 True（涉及部署形态：有监督器的客户端收益、无监督器的断连代价）——用户裁决。

**推荐进总报告 Top 发现**：
1. S06-1（🟠 file_close 静默丢弃——本域唯一严重级）
2. S06-2（🟡 16 件落盘工具 hint 漂移——AI 客户端预判面系统性缺口）
3. J3-1（❌ 未修——外审挂账第三次延续，与 S06-3 同文件可一并修）

**一票否决条款命中情况：0 处**（C-1 零绕过 / C-2 防线实弹闭合 / C-3 无双门全无）。

（完）
