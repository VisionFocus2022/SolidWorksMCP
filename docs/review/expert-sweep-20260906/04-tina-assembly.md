# 04 · Tina — 装配域深审报告

> **审查日期**: 2026-09-06 | **调研员**: Tina（报告号 04，域字母 A）
> **代码快照**: 主仓 HEAD=0762b15（与 Alex 地图一致）；工作区 `output/optimization-plan-2026-09-01.md` M + `docs/review/` 未跟踪（本轮审查目录）。`git log -- solidworks_api/assembly.py` 近三提交：00b1a57（N33 爆炸视图）、13ca62a（N32 add_component 修复）、eca371c（N10 COM 释放收敛）。
> **方法**: 全程只读。Read 精读 api/assembly.py(968 行全文)/registry/assembly.py(186 行全文)/tests 三件(test_assembly.py 110 行、test_assembly_explode.py 94 行、test_assembly_extended.py 977 行)/utils/security.py(208 行)/file_io.py 预开链(:49-120)/base.py limitations(:200-240)/part.py get_mass_properties(:1208+ 对照)；git show 13ca62a 取证 N32 断言变更；grep 取证 balloon 残余/e2e 装配步骤/常量值/双口径计数。实机结论（tools/INDEX.md N8/N10/N32/N33/T11）一律引为背景锚，未凭静态读码推翻。

---

## 执行摘要

发现计数：🔴 0 / 🟠 2 / 🟡 3 / ⚪ 2。最重要两条：**A04-4**——N32 修复的顺序契约（先取装配再 preopen）在单元测试层零防护（全部 6 个 add_component 测试 patch 掉 `_get_or_create_assembly` 且 Mock 的 OpenDoc6 无切文档副作用，代码回退到 N32 原顺序测试仍全绿；唯一防线 e2e 需实机不进 CI）；**A04-3**——BOM 的 `mass_g` 按 `GetMassProperties(1000.0)` 水密度假设计算，与 material 列（真实材料名）并排自相矛盾，且与零件域 `get_mass_properties`（CreateMassProperty 走材料密度）口径分叉 7.85×（钢件），实机 mass 槽从未验证（探针只取质心、e2e 无 mass 断言、mock 锁定 volume×1000 单一语义）。上轮对照：G5 装配侧工具面 ✅（AutoBalloon 维持 BLOCKED 但诚实拒绝文案在位）、AddMate5 宣称 ◐（措辞无漂移，concentric 验证状态无记录）、mock-vs-实机 ➕（新抓两例真值陷阱）。

---

## 自验声明（E-1~E-6 + 禁则）

- [x] **E-1 行号亲验**：本报告全部 `文件:行号` 均本轮 Read 亲验（assembly.py 全文、三测试全文、security.py 全文、file_io.py:49-120、base.py:200-240、part.py:1208-1246）。13ca62a diff 经 `git show` 亲验。
- [x] **E-2 提交态/工作区态双查**：本域结论全部基于版本库文件（assembly.py/tests 均干净）；工作区唯一 M 文件为 output/ 计划文档，不涉装配域。
- [x] **E-3 上轮继承项重证**：G5/AddMate5/mock-vs-实机三项逐一取证（见对照表）；AutoBalloon BLOCKED 经全仓 grep（见 A04-6 证据）。
- [x] **E-4 影响量化**：🟠/🟡 条目均含「触发频率 × 最坏后果」。
- [x] **E-5 计数附命令**：registry 双口径 10/10（`grep -c "mcp\.tool("` == `grep -c "^def solidworks_"` 输出均 10）；mate 常量六值（grep constants.py :33-38）；GetMassProperties 在 assembly.py 4 处（grep 计数输出 4）。
- [x] **E-6 否定性结论双词形复核**：「balloon 无替代实现」经 `grep -rni "balloon" --include="*.py" solidworks_mcp/ tests/ tools/` 双语全形态命中（AutoBalloon/balloons/ballooned——末者为 geometry.py 无关注释），确认生产代码仅 drawing.py 拒绝文案在位；「add_component 测试全 patch _get_or_create_assembly」经逐个 Read 6 个测试方法核实 + `grep -n "_get_or_create_assembly" tests/test_assembly*.py` 复核。
- [x] §10 禁则自查：无风格偏好条目；A04-3 的 SW density 语义两分支均如实标注（不伪装修实证）；推测均显式标注；报告外零写操作。

---

## 问题清单

### A04-4 N32 修复的顺序契约零回归锁——mock 不建模 OpenDoc6 切活动文档副作用
- 级别：🟠 —— §3 判据③（契约破坏：实机行为契约无测试防护）+ G4/G5 新件 mock 深度范式（rubric §5「mock 全绿但实机零验证」🟠 起报条款的同族）
- 位置：solidworks_mcp/solidworks_api/assembly.py:208-219（先取装配→preopen→AddComponent4 顺序契约本体）；tests/test_assembly_extended.py:567-580（唯一提及顺序的测试）
- 证据：`git show 13ca62a -- tests/`——N32 修复提交把 `get_asm.assert_not_called()` 改为 `get_asm.assert_called_once()`（附注释 "the assembly is now resolved BEFORE the pre-open"），但 **`assert_called_once()` 只断言被调用、不断言调用先于 OpenDoc6**。触及装配链的 7 个 add_component 测试（test_assembly_extended.py:64/75/358/378/397/415/567：meter 坐标、插入失败、preopen、失败关文档、成功不关、用户已开不关、preopen 拒绝）全部 `@patch("...assembly._get_or_create_assembly")`，且 `sw.app.OpenDoc6` 是无副作用 Mock——若代码回退为 N32 原顺序（preopen 先、`_get_or_create_assembly` 后），patch 掉的函数使真实活动文档切换逻辑根本不执行，**单测全绿**。唯一回归防线是 tools/e2e_sw_smoke.py:210-238（两组件场景 + `expect_bom_2x` count==2 断言），但 e2e 需实机 SW 运行、不进 CI（ci.yml 只跑 pytest）。
- 影响量化：触发频率=任何后续重构触碰 add_component 语句顺序（回归即触发）× 最坏后果=N32 原症状复发——组件静默落入新建装配、原装配组件消失、AddComponent4 返回成功（静默错误结果），且 CI 全绿掩盖。
- 根因：Mock 未建模 OpenDoc6 的副作用（切活动文档）；N32 修复只翻转了既有断言方向，未补副作用建模测试。
- 修复方案：新增副作用 mock 测试——不 patch `_get_or_create_assembly`，`sw.app.OpenDoc6` 配 side_effect 把 `sw.get_active_document` 返回值切为零件 Mock，断言 (a) `AddComponent4` 的调用宿主是原装配对象 (b) `ActivateDoc3` 被调用（api/assembly.py:233）(c) 成功路径不 CloseDoc。三断言即把 N32 顺序契约钉进 CI。
- 维度/契约标签：D7 / D8 / C-6

### A04-3 get_bom 的 mass_g 按水密度假设——跨工具质量口径分叉，实机语义未定谳
- 级别：🟠 —— §3 判据①（特定路径下工具返回系统性偏差结果）+ §5「explode/interference/BOM 三新件 mock 深度 vs 实机验证缺口（🟠 候选）」的直接命中项
- 位置：solidworks_mcp/solidworks_api/assembly.py:838-846（`body.GetMassProperties(1000.0)` → `props[5]` 当质量）、:850-855（`GetMaterialIdName` 返回真实材料名）；对照 part.py:1208-1246（零件域 `CreateMassProperty().Mass` 走材料密度）
- 证据：①代码固定传密度 1000.0（kg/m³=水）；②测试 FakeBomBody（tests/test_assembly_extended.py:194-202）按 `mass = volume × density` 语义造假数据，test_rows_carry_volume_mass_material（:731-745）断言 `mass_g=40.0` 与 `material="普通碳钢"` 并排——碳钢密度 7850 下真值 314g，测试自证矛盾形态；③实机验证缺失：tools/INDEX.md N8 条目只记 `GetMassProperties(1000)[0:3]`（质心——密度无关分量），e2e_sw_smoke.py:236-245 对 BOM 只断言 `count==2` 与 `volume_mm3>0`，**mass 槽实机零断言**；④口径分叉：同一钢件经 `part.get_mass_properties`（材料密度）与 `assembly.get_bom`（水密度假设，若 SW density 参数为覆盖语义）将给出 7.85× 差异的两个质量数。
- 影响量化：触发频率=每次 get_bom 含有材料零件时（若 SW 语义为覆盖）× 最坏后果=BOM 质量列系统性错误且与 material 列、与零件域工具互相矛盾——用户静默拿到错误质量数据。若 SW 语义为「仅无材料 body 用传入密度」则降级为无材料件按水计算（material=None 时自洽、无矛盾）——**两分支均未经实机定谳，mock 只锁定了前一支的理解**。
- 根因：N8 BOM 扩列直接复用了探针的质心调用形态 `GetMassProperties(1000)`，未区分质心（密度无关）与质量（密度敏感）；mock 按单一语义理解造数据（上轮 wave2 mock 真值陷阱家族第三例）。
- 修复方案：实机一测定谳（对已知材料零件读 GetMassProperties(1000)[5] 与 CreateMassProperty().Mass 比对）；若覆盖语义成立，改传 density=0（SW 用材料密度）或统一走 CreateMassProperty；无论何分支，docstring 至少披露「mass 按密度 1000 kg/m³ 计算」。
- 维度/契约标签：D1 / D7 / C-5

### A04-1 add_component 的 config_name 死参数——api 层在、registry 不透传、MCP 面恒空串
- 级别：🟡 —— §3 判据④（域内契约 registry↔api 参数面不对齐 + 功能缺口）
- 位置：solidworks_mcp/solidworks_api/assembly.py:194（`config_name: str = ""` 参数）、:219（AddComponent4 第 2 参消费）；solidworks_mcp/registry/assembly.py:60-71（`solidworks_assembly_add_component` 参数面与 lambda 均无 config_name）
- 证据：api 层签名有 config_name 且测试 test_adds_component_with_meter_coordinates（tests/test_assembly_extended.py:67-73）直调 api 传 `"Default"` 并断言 `AddComponent4("part.sldprt", "Default", 0.01, 0.02, 0.03)`——api 功能完好；registry 层参数面缺失 → MCP 工具调用永远传 `""`（SW 取文档默认配置）。多配置零件（Default/长版/短版）无法从 MCP 侧选择配置。
- 影响量化：触发频率=每次需要非默认配置的组件插入 × 最坏后果=静默落入默认配置（无报错、用户不知配置未选上——轻度的 fail-honest 缺口，但结果可被 get_bom 的 configuration 列察觉）。
- 根因：N14 registry 拆分/AddComponent4 接入时参数面未对齐（api 演进快于 registry 门面）。
- 修复方案：registry 函数加 `config_name: str = ""` 透传 + docstring 补「empty = document default configuration」。
- 维度/契约标签：D8 / C-7

### A04-2 add_mate 的 distance 参数双语义——负角度被非负校验拒绝 + FiniteMM 类型标注错位
- 级别：🟡 —— §3 判据⑤（参数域过度收紧导致的功能受限，有明确报错、可察觉）
- 位置：solidworks_mcp/solidworks_api/assembly.py:299-311（`if distance < 0: return error_response("distance must be zero or greater")` 对 DISTANCE 与 ANGLE 统一生效）、:362-364（angle 分支 `math.radians(distance)`）；registry/assembly.py:85（`distance: Optional[FiniteMM]`——类型别名的 description 是毫米语义）
- 证据：distance 参数承载双语义（distance mate=毫米 / angle mate=度，registry docstring :90 有文字披露）；非负校验对毫米合理（SW 距离配合尺寸非负）但对度过度——SW 角度配合负值合法（-15°），当前被 INVALID_PARAMETER 拒绝，需 workaround 传 345°。FiniteMM 注解的毫米语义与 angle 的度语义错位（C-7）。
- 影响量化：触发频率=特定参数组合（负角度配合需求）× 最坏后果=功能受限（明确报错非静默错误），AI 客户端可能因报错放弃本可直接表达的角度。
- 根因：单一 distance 槽复用于双语义时，校验规则只按其中一种语义写。
- 修复方案：ANGLE 分支跳过非负校验（角度域放宽至 ±360）；类型注解改 `SignedMM` 或联合注释标注双语义。
- 维度/契约标签：D1 / C-7

### A04-5 add_component 内部路径形态三处不一致——was_open 检测用原始形、OpenDoc6 用规范形
- 级别：🟡 —— §3 判据⑤（一致性缺口，特定环境触发，无数据损坏）
- 位置：solidworks_mcp/solidworks_api/assembly.py:164（`GetOpenDocumentByName(file_path)` 原始字符串）、:215→file_io.py:87（`_open_doc6` 内部 `normalize_path(file_path)` 规范形）、:219（`AddComponent4(file_path)` 原始形）、:227（`CloseDoc(file_path)` 原始形）
- 证据：`_document_is_open` docstring 自述 "matching is by FULL PATH only"；同一调用链中 OpenDoc6 走规范形而 GetOpenDocumentByName/AddComponent4/CloseDoc 走原始形；validate_path（security.py:130）校验的是 normalized 形但原始字符串继续向下传递。CI runner 8.3 短名环境真实存在（AGENTS.md:33 RUNNER~1 教训）。
- 影响量化：触发频率=特定路径形态组合（8.3 短名/斜杠变体/相对路径——同一文档以两种形态先后被 open_document 与 add_component 使用）× 最坏后果=was_open 误判 False → 失败路径 CloseDoc 按原始形关不掉真实文档（无害残留）+ OpenDoc6 幂等重开（无害）；不致数据损坏，但 N10 失败清理契约在路径形态漂移下失效。
- 根因：入口校验（normalize）与消费（原始串）分离，三处消费点未统一。
- 修复方案：add_component 入口 `file_path = normalize_path(file_path)` 一次，后续四处统一用规范形。
- 维度/契约标签：D3 / C-2

### A04-6 爆炸视图手工步进缺口（诚实披露在位）+ 无回切配套
- 级别：⚪ —— §3 判据④（远期能力缺口，上轮已定性且未变）
- 位置：solidworks_mcp/solidworks_api/assembly.py:913-921（explode 仅 AutoExplode；docstring 明示 "Manual per-component steps (AddExplodeStep) are a future extension"）
- 证据：N33 实机结论"AddExplodeStep 4 参手工步进未走（v1 自动）"延续——当前 explode() 零参数（无爆炸方向/距离控制），ShowExploded(True) 后无 ShowExploded(False)/删除爆炸视图的回切工具。docstring 与 registry docstring（:146 "automatic exploded view"）均诚实披露 ✓。
- 影响量化：触发频率=需要定向/可调爆炸布局时 × 后果=只能用 SW 自动布局（无成本损失，纯能力边界）。
- 根因：N33 v1 范围决策。
- 维度/契约标签：D8（宣称一致）/ 无契约违规
- **G5 气泡残余顺带确认**：AutoBalloon 家族维持 BLOCKED（上轮定性不变），全仓 grep 实证无替代实现；诚实拒绝文案在位——drawing.py:1027 `"(balloons unavailable — AutoBalloon BLOCKED, ADR-0011)"`（装配域视角确认，细节归 05 域）。

### A04-7 concentric mate 实机验证状态无记录（mock-only 验证清单成员）
- 级别：⚪ —— §3 判据④（观察项）
- 位置：solidworks_mcp/solidworks_api/assembly.py:266-272（docstring 逐一标注 coincident/distance/angle=T11、tangent=N8、width=N15 未验证——**concentric 无任何验证记录**）；tools/INDEX.md probe_assembly_extras 行同样未提
- 证据：6 类型提供面中实机确证 4 个（coincident/distance/angle=T11、tangent=N8），width 在 docstring 披露未验证（N15），**concentric 的验证状态在 docstring 与探针索引双处均无记录**；测试 test_tangent_and_width_are_mapped（test_assembly_extended.py:471-479）只锁常量映射不锁实机。测试 test_constants_match_swconst_values（:434-435）锁 (4,6,17) 与 constants.py:33-38 六常量值全部与 SW swMateType_e 一致（本轮 grep 亲验：COINCIDENT=0/CONCENTRIC=1/TANGENT=4/DISTANCE=5/ANGLE=6/WIDTH=17）。
- 影响量化：触发频率=首次实机使用 concentric mate × 后果=未知（可能直接可用——CONCENTRIC=1 常量正确、选择链路与已验证类型同构；也可能撞未知的 SW 侧拒收形态）。
- 根因：docstring 验证状态标注遗漏。
- 维度/契约标签：D7 / C-5
- 附：AddMate5 宣称（base.py:237 "basic mate types"）与 6 类型提供面无措辞级漂移（"basic" 宽松涵盖），归入 ◐ 见对照表。

---

## 上轮对照表（E-3 重证）

| 继承项 | 上轮定性 | 本轮重证证据 | 状态码 |
|---|---|---|---|
| **G5 能力长尾（装配侧：爆炸图/BOM/气泡）** | 远期缺口（loft/sweep/爆炸/BOM 气泡） | 爆炸视图已建（explode + N33 实机 + test_assembly_explode.py 契约锁定）；BOM 数据聚合已建（get_bom + N8 实机 + 55 测例）；工程图 BOM 表已建（N32，drawing 域）；AutoBalloon 维持 BLOCKED **且诚实拒绝文案在位**（drawing.py:1027） | ✅（工具面建成；气泡子项维持 BLOCKED 定性、披露合规，与 05 域共担） |
| **AddMate5 宣称一致性**（rubric §5） | base.py:237 limitations "basic mate types" | 实证 6 类型提供/常量六值正确（constants.py:33-38）/实机确证 4 + width 披露未验证 + **concentric 验证状态无记录**（A04-7）；"basic" 措辞宽松，无漂移 | ◐（宣称无漂移；concentric 无记录为遗留观察） |
| **explode/interference/BOM 三新件 mock vs 实机缺口**（rubric §5 🟠 候选） | —（本轮新立项核查项） | explode=N33 实机一次通过 + 契约测试锁定（合格）；interference=T11/N8 实机 + 形态防御四分支测试（合格）；**BOM mass 槽实机零验证 + mock 锁单一密度语义（A04-3 🟠）**；另抓 add_component 顺序契约 mock 零防护（A04-4 🟠，上轮 wave2 mock 真值陷阱家族续例） | ➕（新发现两例 🟠） |

无 ↩ 回退项；G1-G4/G6-G8 不在装配域管辖（Alex 地图 §8 已处置）。

---

## 移交项与交主会话复核清单

**交其他域**：
- → **05 工程图域（D）**：AutoBalloon BLOCKED 的拒绝文案链（drawing.py:985/1027）与 BOM 表工具完备性由 D 域深审；本域仅确认无装配侧替代（编号 A04-6 引用，不复制）。
- → **03 零件域（P）**：part.py get_mass_properties 与 assembly get_bom 的质量口径分叉（A04-3）——零件域侧实现（CreateMassProperty）是正确基准，若统一口径应在装配侧改。
- → **09 测试CI域（T）**：A04-4 的「mock 不建模 COM 副作用」模式可并入 mock 真值陷阱在案清单（上轮 wave2 两例 + 本轮两例 = 四例家族）；e2e 不进 CI 的防线空洞是结构性观察。

**需实机定谳项（只读审查无法完成）**：
1. A04-3：对已知材料零件实测 `GetMassProperties(1000)[5]` vs `CreateMassProperty().Mass`——判定 SW density 参数是覆盖语义还是无材料兜底语义（一测定谳，两分支修复方案已备）。
2. A04-7：concentric mate 一次实机验证（常量与链路同构已验证类型，预期可用）。

**推荐进总报告 Top 发现**：A04-4（N32 顺序契约零回归锁——复发即静默组件丢失且 CI 全绿）、A04-3（BOM 质量水密度假设——跨工具口径分叉）、A04-1（config_name 死参数——契约面最轻但修复最便宜的 quick win）。

**复核清单（主会话抽验锚点）**：
- A04-4：`git show 13ca62a -- tests/test_assembly_extended.py` 看 `assert_not_called` → `assert_called_once` 的翻转；tests/test_assembly_extended.py:64-80 与 :357-430 确认全部 patch `_get_or_create_assembly`。
- A04-3：api/assembly.py:840 `GetMassProperties(1000.0)` vs part.py:1226 `CreateMassProperty`；tests/test_assembly_extended.py:744 `mass_g=40.0` + :745 `material="普通碳钢"` 并排。
- A04-1：registry/assembly.py:68-71 lambda 三参数（file_path/x/y/z）vs api/assembly.py:194 四参数签名。

（完）
