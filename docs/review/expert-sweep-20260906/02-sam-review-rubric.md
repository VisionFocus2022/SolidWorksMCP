# 02 · Sam — 专家团统一评判标准（Rubric）

> **审查日期**: 2026-09-06 | **角色**: 调研员 Sam（评判标准与校准）
> **代码快照基准**: 与 Alex 地图一致——主仓 HEAD=0762b15（main，`@{u}..HEAD`=0）；工作区 2 项未提交（`output/optimization-plan-2026-09-01.md` M + `docs/review/` 未跟踪）；aicad HEAD=9a80b13（ahead 4，`config/providers.toml` M）。
> **输入锚**: Alex 地图（01-alex-architecture-map.md，下称「地图」）/ evolution-summary（2026-08-31，下称「上轮」）/ coderabbit-j3-review-2026-09-02.md（下称「J3 外审」）/ AGENTS.md（仓规则）。
> **本文用途**: 七位域调研员（03-09）的统一评判语言。所有发现分级、编号、证据强度、输出形态以本文为准。

---

## 1. 使用方式（三阶段操作手册）

**深读前（每人 15 分钟）**：
1. 读地图 §2（mermaid 分层图）+ §7（域表：文件/行数/测试对照）——知道自己的域在架构里的位置与既有测试面。
2. 读本文 §5（自己域的上轮对照清单）——明确必须重证的继承项（E-3 铁律）。
3. 读本文 §8（维度侧重映射）——知道自己是哪些维度的"加重人"，别的主责维度只做顺带扫描。

**深读中**：
1. 按本文 §6 维度检查点逐项过自己主责文件；每个工具函数套 §7 的 C-1~C-8 契约表。
2. 每个候选发现落笔前过 §2 证据铁律 E-1~E-6——不满足者不得入报告。
3. 分级套 §3 判据；命中 §8 一票否决条款的直接 🔴，不走跨级三问。
4. 取证命令优先复用地图附录 B（计数双口径 / 依赖方向 / re-export 差集 / 交付状态）。

**深读后（交报告前自验）**：
1. 按 §9 报告骨架填全六区；自验声明逐条勾选 E-1~E-6。
2. 对照 §10 禁则负面清单逐条自查——命中任何一条即回炉。
3. 校准样例（§10）对照：自己的 🔴/🟠/🟡 条目证据强度是否达到样例水平。

---

## 2. 证据铁律 E-1~E-6（不满足者不得入报告）

- **E-1 行号亲验，禁转抄文档**：每个发现的 `文件:行号` 必须本轮亲 Read 目标文件核对。地图行号是 2026-09-06 快照、上轮报告是 2026-08-31 快照、J3 外审读的是 HEAD~5 diff——三者都只是路标不是证据。反例锚：J3-3 报"N26 仍 [!]"，实为外审读 diff 旧态，地图 §8 已证伪（plan:68 已 `[x]` 关单）。
- **E-2 提交态/工作区态双查**：涉及 `output/`（gitignored 且当前 M）与 `docs/` 的结论，必须用 `git show HEAD:<file>`（或确认该文件不在版本库）区分「盘上态」与「版本态」再下结论。工作区当前已知 2 项未提交（地图头部快照），深读期间可能有新漂移——报告头部记录自己的快照时刻。
- **E-3 上轮继承项一律重证后才标状态码**：G1-G8 / J3-1/2/3 / AR-n 在归属域报告里逐项重新取证，才允许标 ✅/❌/◐/↩/➕。正例锚：G2 上轮"待空闲机复验"→ 本轮 Alex 以 plan:68 `[x] 2026-09-02 关单` + HEAD 提交信息双源定谳关闭。
- **E-4 影响量化**：每条 🟠 及以上必须写「触发频率 × 最坏后果」。频率分档：每次调用可触发 / 特定参数组合 / 特定环境（8.3 短名、junction、CI runner）/ 需罕见条件。后果锚例：AR-2 的影响量化范式——「功能无损（注册由 register_all 全量完成），影响=外部脚本 `server.<tool>` 旧拼写对 10 个新工具失效」（地图 AR-2）。
- **E-5 计数类结论附命令与输出摘要**：凡报数字（工具数/测试数/调用次数/行数），附取证命令 + 输出摘要。命令形态锚：地图附录 B（`grep -c "mcp\.tool("` 与 `grep -c "^def solidworks_"` 双口径必须相等；`comm -23` 差集）。教训锚：附录 A——首轮正则 `[a-z_]` 漏数字致 ring_light_v3 误报，改 `[a-z_0-9]+` 后纠偏。
- **E-6 否定性结论双词形复核（K-9 纪律）**：凡「无 X / 未 Y / 零命中」类断言，必须换第二词形或第二口径复核后才可写。范式锚：地图附录 A 六条复核记录（如"无 @mcp_tool 装饰器"用 `grep -rc` 全模块零命中后改用 `mcp.tool(` 口径计数）。

---

## 3. 四级分级量化判据

分级哲学承上轮 evolution-summary 排序原则：**可逆性与验证成本**——不可逆损失 > 可验证功能错误 > 积累性质量债 > 改进建议。

### 🔴 崩溃级（数据丢失 / 安全红线突破 / 进程不可用）
- **判据**（满足其一）：① 可致用户文件/工作成果不可逆丢失；② 突破 AGENTS.md 五条安全红线之一（见 §8 一票否决）；③ SW/MCP 进程挂死或崩溃且无自愈路径（毒化退程机制本身失效）；④ 错误结果**静默**产出且用户无法察觉（fail-honest 底线突破：吞异常谎报 success）。
- **先例锚**：上轮 G1 曾定 P0——「15 提交未推 + aicad 69 提交零远端 + CI 从未跑 = 磁盘故障两周归零」（evolution-summary §一）；本轮主仓已闭环、aicad 余尾（AR-3 降 🟠，因远端已建、损失面从"全部"缩到"4 提交"）。
- **门**：必须有 E-4 影响量化 + 可复现证据链（命令/调用序列），否则降档或挂待证。

### 🟠 严重（功能错误 / 资源泄漏 / 契约破坏）
- **判据**：① 特定路径下工具返回错误结果（但可被用户察觉或测试暴露）；② COM 资源泄漏/句柄未释放累积致长会话劣化；③ 明确契约被破坏（注册↔文档↔re-export↔capabilities 漂移已造成可用性缺口）；④ 双源维护分叉已达行为级差异；⑤ 安全护栏有洞但需特定条件才可穿透（如 junction 组合特定路径形态）。
- **先例锚**：AR-4 双仓 sw_app.py 同源改编漂移——错误模型分叉（异常 vs dict 信封），主仓修复不自动流入 aicad，桥面随 v2 演进扩大（地图 AR-4）；AR-2 re-export 缺 10 工具——兼容承诺（server.py:6-8 注释）未随新工具维护（地图 AR-2，🟠 下限、🔴 不至：注册链全量、运行时无感）。
- **门**：须给出触发条件与频率量化；「mock 全绿但实机零验证」类缺口（G4/G5 新件）若确认 mock 未覆盖关键语义，按 🟠 起报。

### 🟡 中等（质量与可维护性 / 文档漂移）
- **判据**：① 导航/宣称文档与实现漂移（计数/口径/承诺过期）；② 测试基线或断言陈旧（钉死值与现值不符）；③ 无护栏的双源（文件/配置）但现状一致；④ 代码组织债（域膨胀、职责越界）尚在可维护范围；⑤ 错误信息缺原因或下一步（可观测性不足但不谎报）。
- **先例锚**：AGENTS.md:4「69 个工具」vs :30「79/81」vs README:9「79」（AR-1/J3-2，同文件自相矛盾）；测试基线 AGENTS.md:23 记 537 vs Alex 实测 538（地图 §9 头注，09 域复核）；AR-9 requirements.txt 与 pyproject 双源（现状 3 项逐字一致、无漂移护栏）。
- **门**：文档漂移须 E-5 计数证据；「双源现状一致」必须写明复核命令。

### ⚪ 建议（改进方向 / 观察项 / 信息级）
- **判据**：① 性能微优化点（有量化推测但无瓶颈证据）；② 架构观察（未来阈值预警）；③ 流程/信息管理建议；④ 远期能力缺口（上轮已定性远期且未变）。
- **先例锚**：AR-7 get_config() 无缓存（μs 级、推测标注）；AR-5 part 域膨胀观察（推测阈值 ~40 工具/1500 行再切）；AR-6/G7 pattern 数学重建（远期定性不变）；AR-8 计划台账仅存本地（信息级，gitignored 有意设计）。
- **门**：推测必须显式标注「推测」（AR-7 范式），不得伪装成实证。

### 跨级裁决三问（🔴🟠🟡 边界摇摆时依次回答）
1. **触发面**：主路径每次可达，还是特定参数/特定环境（短名、junction、CI runner）/理论不可达？（AR-2 定 🟠 不定 🔴 的关键：运行时主路径无感，只有旧拼写消费方踩坑。）
2. **后果终态**：最坏终态是文件丢失（→🔴）/ 错误结果但可察觉（→🟠）/ 文档误导认知（→🟡）/ 无后果仅成本（→⚪）？
3. **护栏现状**：有无测试锁定、实际拦截门、文档披露在位？（例：DESTRUCTIVE annotation 缺失但 overwrite_confirm 实际拦截+测试在位（registry/file_io.py:53-62 范式）→ 降 🟡 考量；两者皆无 → §8 一票否决。）

---

## 4. 编号规则

- **本轮新发现** = `{域字母}{报告号}-{序号}`。域字母表：**03 零件建模=P、04 装配=A、05 工程图=D、06 安全加固=S、07 文件IO=F、08 COM基建=C、09 测试CI=T**。报告号 = 本域报告的两位编号。例：`P03-1`（03 号报告第 1 个零件域发现）、`S06-3`、`T09-2`。序号域内自增不复用。
- **Alex 遗留**沿用 `AR-n`（AR-1~AR-9，定义见地图 §8；引用时不改号，状态变化在 §5 对照表体现）。
- **上轮对照项**沿用 `G1-G8` / `J3-1/2/3` + 状态码：`✅已修`（本轮实证修复在 HEAD）/ `❌未修`（本轮实证仍在）/ `◐部分`（部分清偿，例：G1 主仓闭环、aicad 余 4 提交）/ `↩回退`（曾修后又回退）/ `➕新增`（上轮定性远期或未立项，本轮发现已实质变化需升级关注）。
- 状态码只能由 E-3 重证后授予；无法重证的写「待证」并移入移交项，不得猜。

---

## 5. 各调研员上轮对照清单（重证义务，源自地图 §8/§9）

**03 零件建模（P）**：
- G4（长尾工具面）：地图已实证 defs+tests 在册（create_swept/loft/rib/apply_dome/ref_plane/ref_axis/polygon/slot）——你的任务转为**质量与契约深度**：docstring↔行为↔capabilities 三向是否同步；这 8 件全在 AR-2 re-export 缺口内（顺带实证）。
- G6（CSG 契约）：核实 test_csg_rebuild.py 的 op 范围现值 vs capabilities 宣称（v1 仅 4-op？），rebuild_csg_plan 被 part+features 两域引用的契约一致性。
- AR-5 part 域膨胀（观察项复核，⚪ 预期）。

**04 装配（A）**：
- G5 残余子项：爆炸图/BOM 工具已建（地图实证）——核实「气泡引线等残余子项」是否如上轮定性仍缺。
- AddMate5 兼容路径：base.py:237 limitations 自述 "basic mate types"——核实宣称与实现的 mate 类型集是否一致（capabilities 反向断言测试在位，test_capabilities_sync.py:28-30）。
- explode/interference/BOM 三新件 mock 测试深度 vs 实机验证缺口（🟠 候选）。

**05 工程图（D）**：
- G5 BOM 气泡引线子项核实（与 04 域分界：drawing_insert_bom_table 归你）。
- insert_bom_table 在 AR-2 缺口内——审注册/测试/re-export 三面完备性。
- PDF/PNG 导出与 06/07 域路径校验交叉（drawing.py 1036 行 vs file_io 的 allowed_root 链）。

**06 安全加固（S）**：
- **J3-1 重证**：tests/test_hardening.py:297-298 GetLongPathNameW mock 是否仍「返回 len(tiny)+1 触发不足分支」未修（地图判「仍挂账」）——E-1 亲读现值后标状态码。
- normalize_path 攻击面：junction/8.3/`..` 组合（utils/security.py:21-43，0297d77 刚加固缓冲区分支——审加固完备性）。
- poisoned_exit 语义链（base.py:117-132 sys.exit(1) → stdio 宿主重启）实际恢复假设。
- DESTRUCTIVE 双门覆盖面盘点：哪些写/删/覆盖工具漏 annotation 或漏 overwrite_confirm。
- allowed_root 默认收窄到项目根的涟漪（config.py:10-16 注释链）；AR-9 顺带核 requirements.txt 现值。

**07 文件IO导出（F）**：
- AR-9：requirements.txt vs pyproject dependencies 逐项比对（E-5 附命令）。
- 上轮族历史坑「导出产物落 CWD 污染」在本仓现状（相对路径 save 的落点审计）。
- STEP/STL/PDF/DXF 四格式导出参数面与错误路径 fail-honest（import_step 与导出的模板/单位假设）。

**08 COM基建（C）**：
- AR-4 桥面细节（与 09 共担）：aicad/interop/sw_app.py 与主仓 api/app.py 的 diff 级漂移清单（连接自愈逻辑是否已分叉）。
- AR-7 重证：get_config() 无缓存的调用次数实测（每工具调用触发几次 os.getenv 链）。
- mm_to_m 漏换算审计：api 层 62 处消费（geometry.py:21）之外是否有直传 mm 进 COM 的路径（C-4 全查）。
- call_or_value Mock 兼容语义（utils/com.py 24 行）与 CoUninitialize/atexit 收尾。

**09 测试CI（T）**：
- **测试基线复核**：AGENTS.md:23 记 537，地图实测 538+105——亲跑 `venv\Scripts\python.exe -m pytest tests/ -q` 定谳现值（E-5）。
- G3 两项未见动作的确认：aicad 前端零测试、缓存命中率无报表。
- J3-1 状态与 06 域共享（test_hardening.py 归属）。
- aicad 侧写：AR-3 ahead 4 内容清点；CI run 33599347169 之后是否有后续跑；coverage 80 硬门 vs AGENTS 89% 实绩的差距面（哪些模块拉低）；mock 真值陷阱在案情况（上轮 wave2 抓过两例）。

---

## 6. 八维评判维度 D1~D8（检查点 + 锚点 + 加重人）

| 维度 | 检查点 | 锚点 | 加重人 |
|---|---|---|---|
| **D1 COM 调用与几何正确性** | 数学替代路径（pattern 数学重建 vs 原生 API 的正确性）；单位 mm↔m 换算无遗漏；几何参数域校验（正数/有限）；坐标/角度语义与 SW 惯例一致 | geometry.py:21 mm_to_m（62 处消费基准）；base.py:40-64 Annotated 别名（PositiveMM/FiniteMM 均 allow_inf_nan=False）；AR-6 pattern | P 主责；A/D/F 顺带 |
| **D2 COM 资源生命周期与内存** | COM 对象/文档句柄释放；异常路径不泄漏；毒化后快速失败不半死；长会话累积（浸泡测试在案否） | com_executor.py:24-30 毒化语义；app.py:190 disconnect；test_memory_guard.py 在册 | C 主责；P/A/D 顺带 |
| **D3 安全** | run_com 全覆盖（C-1）；allowed_root 无穿透（junction/短名/`..`）；DESTRUCTIVE 标注；路径规范化 | utils/security.py:21-43；config.py:10-16 收窄史；AGENTS.md 红线 1-3 | S 主责；F 深度共担 |
| **D4 日志与可观测性** | 错误响应含 code+details+下一步动作；不吞异常不谎报；异常日志留栈但不泄给客户端 | base.py:72-77 ToolResult error {code,details}；base.py:135-160 三分支归一（SW_TIMEOUT/SW_API_ERROR 记日志不泄栈）；server.py:131-147 RotatingFileHandler | S/F 共担；全域通用 |
| **D5 并发与超时稳定性** | COM STA 串行假设无破坏；超时默认 120s×3 语义；零/负超时=无超时历史模式的知情面；重试不死循环 | com_executor.py:46-63 STA；config.py:79-81 默认 120s；base.py:111-114 零/负→None | C 主责；S 共担 |
| **D6 性能** | 缓存机会与缺失（AR-7）；耗时预算断言（N23 0.3s 预算线范式）；特征走查上限语义 | AR-7 get_config；geometry.py MAX_FEATURE_WALK；G2/N23 关单范式（预算线不动、禁放室断言） | C 主责；P 顺带 |
| **D7 测试覆盖与质量** | capabilities sync 三向锁定（运行时 list_tools vs docstring vs JSON）；计数钉死 5 处现值；mock 真值陷阱；覆盖差距面 | test_capabilities_sync.py:28-30 反向断言；test_infrastructure.py:167,180 + test_server.py:26,157,164 钉 79/81；pyproject:43 fail_under=80 | T 主责；全域供证据 |
| **D8 契约一致性** | registry↔api↔tests 三对齐；AGENTS/README 宣称 vs 现值；server re-export 完备性；capabilities 与 limitations 自述真实性 | AR-2 缺 10 工具；AR-1 计数 69；base.py:237 limitations 自述；AGENTS.md:27 两口径并存（Alex 判成立） | T 主责；D/A 域内自查 |

---

## 7. 工具契约符合度检查表 C-1~C-8（每个工具逐项过）

锚：registry/base.py 共享类型与 AGENTS.md 红线。「怎么查」给出可执行方法。

| # | 契约 | 怎么查 |
|---|---|---|
| C-1 | COM 调用经 run_com | 追调用链：registry 域函数 → `_call_connected`（base.py:135-160）的 invoke lambda → api 层。lambda 体内一切 COM 交互（含 `sw.connect`）即合规。例外白名单：measure.py 纯计算零 COM（地图 §7 注明）。grep api/ 层 `Dispatch|GetActiveObject|EnsureDispatch` 应仅集中于连接层且经包装 |
| C-2 | 文件操作在 allowed_root | 列本域全部带 file_path/template/path 参数的工具 → grep api 层对应函数是否经 utils/security.py normalize_path + allowed_root 校验；对照 registry/file_io.py:53-62 范式 |
| C-3 | 破坏性工具标 DESTRUCTIVE | 枚举本域写文件/覆盖/删除/不保存关闭类工具 → 查注册处 annotations 预设（base.py:79-102 四档）+ api 层确认门（overwrite_confirm 语义）。双门全无 = §8 一票否决 |
| C-4 | 入参 mm→COM 层 m 换算收口实现层 | 本域 api 函数中长度/距离/坐标参数逐一对 mm_to_m 消费（62 处基准，geometry.py:21）；对照 capabilities 单位声明（base.py:188-193 tool_length=mm / internal=m）。发现直传 mm 进 COM = 🟠 起（D1） |
| C-5 | 错误 fail-honest（不吞不谎报） | 抽查错误路径：COM 异常/参数非法/文档缺失时返回 error_response（utils/common.py 唯一构造点）而非静默 success；对照 base.py:72-77 五字段信封。吞异常返回 success=🔴 候选（§3 判据④） |
| C-6 | 注册与计数同步 | 地图附录 B 双口径：`grep -c "mcp\.tool("` == `grep -c "^def solidworks_"`（域内相等）；新工具是否同步 5 处计数断言与 capabilities JSON |
| C-7 | 参数校验与 docstring | 参数用 Annotated 别名（PositiveMM/FiniteAngle/NonEmptyString/MateType Literal）而非裸类型；docstring 与行为一致（test_capabilities_sync 锁 docstring——自审一遍别让 sync 测试替你兜底） |
| C-8 | 超时与毒化退程配置 | 工具走 `_call_connected` 即自动获得 run_com+`_com_timeout()`+毒化退程（SOLIDWORKS_MCP_POISONED_EXIT=1→sys.exit(1)，base.py:117-132）；grep 本域有无绕过 `_call_connected` 直连 `sw`/单例的自定义路径——有则重点审 |

---

## 8. 调研员×维度侧重映射 + 安全红线一票否决

**映射表**（●主责 ◐共担 ○顺带）：

| 调研员 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 |
|---|---|---|---|---|---|---|---|---|
| 03 P 零件 | ● | ◐ | ○ | ○ | ○ | ◐ | ◐ | ◐ |
| 04 A 装配 | ● | ◐ | ○ | ○ | ◐ | ○ | ◐ | ◐ |
| 05 D 工程图 | ● | ◐ | ◐ | ◐ | ○ | ○ | ◐ | ● |
| 06 S 安全 | ○ | ○ | ● | ● | ◐ | ○ | ○ | ○ |
| 07 F 文件IO | ○ | ○ | ● | ● | ○ | ○ | ◐ | ◐ |
| 08 C COM基建 | ◐ | ● | ◐ | ○ | ● | ● | ○ | ◐ |
| 09 T 测试CI | ○ | ○ | ○ | ○ | ○ | ○ | ● | ● |

**安全红线一票否决特别裁决**（锚 AGENTS.md:38-42 五条红线之前三条）：

凡发现以下三者之一，**直接 🔴，不经 §3 跨级裁决三问**：
1. **COM 调用绕过 run_com**——存在 COM 对象交互（Dispatch/GetActiveObject/COM 方法调用）却不在 run_com 执行体内（C-1 精确定义；纯计算白名单除外）。
2. **文件操作越出 allowed_root**——路径校验缺失，或可被 `..`/junction/8.3 短名组合穿透至 allowed_root 之外（C-2；utils/security.py:21-43 为在位防线，审的是防线之洞）。
3. **破坏性工具未标 DESTRUCTIVE**——行为导致不可逆数据变更（覆盖已有文件/删除特征/不保存关闭）且无任何确认门（既无 DESTRUCTIVE annotation 也无 overwrite_confirm 语义拦截，C-3 双门全无）。

补充精确化：annotation 缺失但实际确认门+测试在位 → 降 🟡（hint 层漂移，AI 客户端无法预判破坏性）；仅有 annotation 无实际门 → 🟠 起（协议 hint 非强制拦截，地图 §3 已注明）。红线 4（mm↔m）违规按 D1 定 🟠 起；红线 5（绝不 push/不跨仓提交）对调研员自身的约束：**全程只读，报告外零写文件**。

---

## 9. 发现条目输出模板 + 分区报告骨架

**发现条目模板**（每条发现完整填七栏）：

```markdown
### {编号} {一句话标题}
- 级别：🔴/🟠/🟡/⚪ —— {引用 §3 判据条目号；命中一票否决者注明 §8 条款}
- 位置：{文件路径}:{行号}（E-1 亲验）
- 证据：{命令 + 输出摘要（计数类 E-5）/ 关键代码逐字引用}
- 影响量化：{触发频率：每次调用/特定参数/特定环境/罕见} × {最坏后果}（🟠 及以上必填，E-4）
- 根因：{一句话}
- 修复方案：{最小可执行修法；涉及测试钉死值者注明联动 5 处断言}
- 维度/契约标签：{D1-D8} / {C-x}
```

**分区报告骨架**（六区，文件名 `0{N}-{域}-review.md`）：
1. **头部**：域/调研员/快照（`git rev-parse HEAD` + 工作区状态 + 时刻）/方法声明（只读）。
2. **执行摘要**：≤8 行——发现计数按级分布 + 最重要 1-2 条 + 上轮对照变化。
3. **自验声明**：E-1~E-6 逐条勾选 + §10 禁则自查通过声明。
4. **问题清单**：按 🔴→⚪ 排序的发现条目（模板七栏）。
5. **上轮对照表**：本域继承项（§5 清单）+ 状态码 + 重证证据一行。
6. **移交项与交主会话复核清单**：交其他域的线索（注明目标域编号规则）、需实机/需用户裁决项、推荐进总报告的 Top 发现。

---

## 10. 校准样例 + 禁则负面清单

**校准样例**（证据强度标尺，三例均用已知真实例子）：

```markdown
### 🔴 样例（假设演示，非真发现——allowed_root 绕过模板形态）
- 级别：🔴 —— §8 一票否决条款 2（不经三问）
- 位置：solidworks_mcp/solidworks_api/file_io.py:{ hypothetical 行号}
- 证据：`export_step` 在 normalize_path 之前拼接用户输入 → `Path(full).resolve()` 直接落盘，
  构造 `..\..\..\victim.txt` 相对路径可写出 allowed_root 之外（附复现命令与实际落点）
- 影响量化：特定参数（恶意/畸形路径）× 任意文件覆盖 = 用户文件不可逆丢失
- 根因：路径校验晚于拼接 / 校验结果未用于最终写
- 修复方案：所有落盘路径统一先 normalize_path 再比对 allowed_root 再打开；补穿透回归测试
- 维度/契约标签：D3 / C-2
```

**🟠 样例 = AR-4 双仓漂移**（地图 AR-4 全文为证）：同源改编（sw_app.py docstring 自证）→ 错误模型分叉（aicad 抛类型化异常 vs 主仓返回 response dict）→ 主仓修复不自动流入 → 桥面随 S5 v2 持续扩大。影响量化：触发频率=双仓任一侧演进即漂移 × 后果=同源代码行为级差异无同步机制。证据形态：docstring 引用 + 双侧函数对照。

**🟡 样例 = AGENTS.md:4 计数漂移**（AR-1/J3-2）：`:4 "69 个工具"` vs `:30 "79 默认/81"` vs README:9 "79"——同文件自相矛盾；E-5 证据：附录 B 双口径命令输出 81 defs/79 注册 + 5 处测试钉死现值。影响量化：触发频率=每个新会话读导航 × 后果=工具面认知少计 10 个（纯认知误导，运行时零影响）。

**禁则负面清单**（命中任一条即回炉，不入报告）：
1. ❌ 风格偏好类（命名/格式/注释密度）——除非造成 D8 契约破坏。
2. ❌ 无证据推测——「可能」「应该」类未取证断言；推测必须降 ⚪ 并显式标注（AR-7 范式）。
3. ❌ 转抄文档宣称——AGENTS.md/README/docstring/capabilities 说什么不算证据，须核到代码与测试现值（capabilities 防漂移测试存在的意义正是宣称会漂，地图 §3）。
4. ❌ 否定性结论未双词形复核——「无 X/零命中」未过 E-6 不得写。
5. ❌ 上轮结论未重证就标 ✅/❌——状态码只能由本轮取证授予（E-3；J3-3 读旧态报假问题是反面教材）。
6. ❌ 无影响量化的 🟠/🔴——「感觉严重」不是分级依据。
7. ❌ 报告外的写操作——调研员全程只读（红线 5 延伸）；唯一例外是本 rubric 与各自报告文件。

---

## 附：与团长对账口径

- 测试基线：AGENTS.md:23 记 537 / 地图实测 538+105 —— 以 09 域本轮亲跑为准，报告统一引用一个数。
- 工具计数：81 defs / 79 默认注册（ring_light 2 件 env 门控）—— 本 rubric 全文沿用此双口径，不写 69。
- 一票否决三项（§8）与跨级三问（§3）互斥：命中前者不走后者。
- 编号冲突防串：域字母+报告号全局唯一；发现跨域时在主责域编号、副责域移交项里引用编号不复制。

（完）
