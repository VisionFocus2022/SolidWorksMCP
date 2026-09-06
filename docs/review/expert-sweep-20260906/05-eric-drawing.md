# 05 · Eric — 工程图域深审报告（drawing）

> **审查日期**: 2026-09-06
> **代码快照**: 主仓 HEAD=0762b15（`git rev-parse` 亲验 `0762b15aba049b6cfa4f807f79fb4aa78b62441f`）；工作区 ` M output/optimization-plan-2026-09-01.md` + `?? docs/review/`（与 Alex/Sam 快照一致，审查期间无新漂移）。
> **方法**: 全程只读。Read 精读 api/drawing.py（1036 行全量）+ registry/drawing.py（206 行全量）+ tests/test_drawing.py（1099 行）+ test_drawing_bom.py（131 行）；grep 亲验 re-export 差集 / 测试计数 / ADR 内容（E-5/E-6）；实机结论对照 tools/INDEX.md N32/N33 + e2e_n32.py + e2e_n33.py 原文（不凭静态读码推翻实机实证）。
> **维度加重**: D1（●）/ D8（●）主责，D3/D4/D7（◐）共担。

---

## 执行摘要

工程图域整体质量**良好**：10 工具全走 `_call_connected`（C-1/C-8 合规）、mm→m 换算无遗漏（C-4 双路径核验）、N4/N5/N32 三批新能力全部有探针+实机 e2e 双锚（无「mock 全绿但实机零验证」项）、错误路径 fail-honest 纪律强（SW_NO_EFFECT/结构化 code/known-views 列举）。

本轮新发现 **0🔴 / 0🟠 / 5🟡 / 4⚪**。最重的两条：**D05-1** set_tolerance 的 "verified by reading them back" docstring 宣称与实现不符（读回值只透传不断言，SW 静默拒绝时仍报 success——data 可察觉故未到 🟠）；**D05-4** 图纸尺寸名发现缺口（无 list-dimensions 工具且失配报错不列候选，AI 调 set_tolerance 前唯一路径是试错猜名）。

上轮对照：**G5 爆炸态投影仍留观察项**（INDEX.md:27 + e2e_n33.py:3 现值确认，未解决）；**BOM 气泡 BLOCKED 有诚实拒绝**（message/docstring/probe/INDEX 四处在案，✅）；**insert_bom_table 三面（registry↔api↔tests）签名一致 ✅ + 实机 e2e 在案，唯 re-export 缺口（AR-2 drawing 侧亲验成立，缺 1 件）→ ◐**。

---

## 自验声明（E-1~E-6 + §10 禁则）

- [x] **E-1 行号亲验**：本报告所有 `文件:行号` 均本轮 Read/grep 亲验（drawing.py 全文精读；INDEX.md/e2e/ADR/prompt 逐个打开）。未转抄 Alex 地图行号——地图 §9 给的是路标，本文行号独立取证。
- [x] **E-2 提交态/工作区态双查**：本域结论不涉 `output/` 版本态（INDEX.md/计划文档只作对照引用且已注明 gitignored 属性）；快照时刻记录于头部。
- [x] **E-3 上轮继承项重证**：G5 两子项 / insert_bom_table 三面 / 导出交叉均已本轮重新取证后才标状态码（见 §上轮对照表）。
- [x] **E-4 影响量化**：全部 🟡 条目附「触发频率 × 最坏后果」。
- [x] **E-5 计数附命令**：工具计数（10=10 双口径）、测试计数（64+6+10）、re-export 差集（10−9=1）均附命令与输出摘要（见各条目及附录）。
- [x] **E-6 否定性结论双词形复核**：「ADR-0011 无 balloon 记录」用 balloon/T8/静默/drawing 四词形 grep 复核；「test_drawing.py 无 BOM 引用」用 `grep -c insert_bom_table`=0 复核；「api/drawing.py 无绕过 _call_connected 的自定义路径」由 registry 全文精读 + 逐函数核对完成。
- [x] **§10 禁则自查**：无风格偏好条目；推测均显式标注并降 ⚪；未转抄 docstring 宣称作证据（D05-1 恰是宣称与实现分叉的实证）；🟡/🟠 均有影响量化；报告外零写文件。

---

## 问题清单

### D05-1 🟡 set_tolerance 宣称 "verified by reading them back" 与实现不符——读回值只透传不断言
- 级别：🟡 —— §3 判据①/⑤（错误结果可被察觉 + docstring 宣称漂移；不构成 C-5 谓报：data 如实透传）
- 位置：`solidworks_mcp/solidworks_api/drawing.py:697`（docstring 宣称）vs `:755-759`（实现）
- 证据：
  ```python
  # :697 docstring: "Values are verified by reading them back."
  # :755-758 实现（逐字）：
  wrapper.SetToleranceType(TOLERANCE_PLUS_MINUS)
  wrapper.SetToleranceValues(lower_m, upper_m)
  back_type = wrapper.GetToleranceType()
  back_values = wrapper.GetToleranceValues()
  ```
  读回值 `back_type/back_values` 仅放入 success data（:760-768），无任何 `back_type == TOLERANCE_PLUS_MINUS` 或 `back_values == (lower_m, upper_m)` 断言；`SetToleranceType/SetToleranceValues` 的返回值（SW 侧 bool）被丢弃。对照域内纪律：`insert_model_dimensions`（:257-263）对无效插入有主动 `after <= before` 验证转 `SW_NO_EFFECT`——同域验证标准不一致。mock 侧 `test_drawing.py:913-914` 断言 `tolerance_type==5 / tolerance_values==(-5e-05,1e-04)` 在 FakeStaticDimension（永远回写成功）上恒真——属「mock 绿但语义边界未验证」的轻微形态。
- 影响量化：触发频率=特定条件（SW 静默拒绝 setter，如维度处于只读/被抑制状态）× 最坏后果=工具返回 `success=true` 但公差未落图（读回值在 data 中如实可见，AI/用户须自查才发现；自动化链路若不检查 data 即带病前进）。
- 根因：docstring 写在 N5 探针轮（探针流程中人工比对过读回值），生产化时验证步未随行。
- 修复方案：读回后断言 `back_type == TOLERANCE_PLUS_MINUS` 且 `math.isclose(back_values[0], lower_m)` / `[1] == upper_m`（容差 1e-9），不符则 `error_response(code="SW_NO_EFFECT")`；或最低限度把 docstring 改为 registry 版口径（"Readback values are returned"，registry/drawing.py:108 已是准确表述——两处 docstring 现已互相矛盾）。
- 维度/契约标签：D4 / C-5、C-7

### D05-2 🟡 organize_dimensions 的 shift 堆叠判定只比 Y 不比 X——左右远距标注纵向对齐时被误移
- 级别：🟡 —— §3 判据①（特定参数组合下产出次优结果，可察觉）
- 位置：`solidworks_mcp/solidworks_api/drawing.py:488`（`if prev is not None and abs(y - prev) < OVERLAP_GAP_M`）；`OVERLAP_GAP_M = 0.002`（:309）
- 证据：分组按 `(y, x)` 排序（:483）后，堆叠判定仅用 y 差 <2mm，x 维度完全不参与。同一视图内左右两侧的标注（例如主视图左侧宽度尺寸与右侧高度尺寸恰在同一水平线附近，y 差 <2mm、x 差 100mm+）会被判为「堆叠」而 shift。shift 恒向 +Y（:492-494），被误移的标注抬高 `index*shift_step_mm`。mock 用例 `test_drawing.py:716-733` 的两个 fake 标注 x 同为 0.33——恰是「真堆叠」形态，未覆盖「y 近 x 远」判别用例。
- 影响量化：触发频率=特定图纸布局（左右双列标注 y 对齐，实机三视图+剖视图布局下并不罕见）× 最坏后果=合法位置的尺寸被无端抬高 8mm（默认步长），可能反向遮蔽上方标注；可被用户察觉、可再调，但工具返回的 `moved` 计数虚高，AI 无法区分真堆叠与误判。
- 根因：pile 判定语义从「视觉堆叠」（二维邻近）简化为「一维 y 邻近」。
- 修复方案：堆叠判定改为二维判定——`abs(y-prev_y) < OVERLAP_GAP_M and abs(x-prev_x) < OVERLAP_GAP_X_M`（新增 x 向阈值，建议同 2mm 或按标注文字宽度放宽至 ~15mm）；补「y 近 x 远不移」判别用例（照 `test_distant_annotations_are_not_shifted` 同构）。
- 维度/契约标签：D1 / C-7

### D05-3 🟡 capabilities limitations 未披露工程图域两条实机定谳的能力缺口
- 级别：🟡 —— §3 判据①（宣称与实现漂移；capabilities 是 AI 规划的一等输入）
- 位置：`solidworks_mcp/registry/base.py:234-239`（limitations 现值 4 条，无 drawing 条目）；对照 `drawing.py:984-986`（docstring "The AutoBalloon family (bubbles) is BLOCKED on this machine"）与 `tools/INDEX.md:27`（N33 "爆炸态图纸投影留观察项"）
- 证据：limitations 覆盖了 design-plan 原语 / ring_light / AddMate5 mates / "Loft/sweep/complex surfaces, **GD&T feature-control frames**, simulation, and PDM are not yet exposed"——GD&T 形位公差框已披露 ✅，但 **AutoBalloon 气泡 BLOCKED**（N32 探针 10+ 变体静默 None 实机定谳）与**爆炸态图纸投影观察项**（N33）两条均未入 limitations。AI 客户端按 capabilities 做工作流规划（「装配图+BOM+气泡」）时无预警，只有执行 `insert_bom_table` 后才从 success message 得知气泡不可用。`test_capabilities_sync.py` 的反向断言（:28-30）管「不得对已注册域声明不支持」，管不到「已知不支持却未声明」方向。
- 彾响量化：触发频率=每次 AI 依 capabilities 规划含气泡/爆炸投影的工程图流程 × 最坏后果=规划失败后重规划（多轮往返，浪费轮次；非静默数据错误）。
- 根因：limitations 列表维护节奏未跟上 N32/N33 的实机定谳产出。
- 修复方案：limitations 追加一条："Drawing BOM balloons (AutoBalloon family) are blocked on the verified machine; exploded-state drawing projection is an observed follow-up (see tools/INDEX.md N32/N33)."；同步 test_capabilities_sync 的 expectations。
- 维度/契约标签：D8 / C-7（capabilities 防漂移体系的正向缺口）

### D05-4 🟡 图纸尺寸名发现缺口：无 list-dimensions 工具，set_tolerance 失配报错不列候选
- 级别：🟡 —— §3 判据①/⑤（功能可用性缺口 + 错误信息缺下一步）
- 位置：`solidworks_mcp/solidworks_api/drawing.py:741-745`（失配报错仅 "No display dimension matches {name!r}"）；对照同文件 :443-446 与 :592-596（organize/section 的未知 view 报错均列出 `known views` 名单）
- 证据：`set_tolerance` 需要 `dimension_name` 精确匹配 FullName（或去尾段形态，:736），但**全工具面没有任何工具能枚举图纸显示尺寸的 FullName**——`_view_reports`（:99-124）只返回每视图 `dimensions`/`annotations` 计数；`insert_model_dimensions` 返回 delta 计数；`organize_dimensions` 的 data 也不含尺寸名清单（`_collect_dimension_records` :367-400 明明已收集 `full`/`selname` 却只内部消费）。AI 的名字来源只能靠试错：猜 `D1@特征名@零件名`（特征名可从 part 域 `features_list` 拿，但 `D1/D2` 草图内部编号 SW 侧不可知）。域内错误信息纪律不一致：view 失配列 known，dimension 失配不列。
- 影响量化：触发频率=每次调用 set_tolerance 前（无例外，除非用户显式给出名字）× 最坏后果=AI 多轮试错往返；更坏形态是 AI 用 part 域特征名拼出「真实存在但非预期」的维度名，公差设置到错误维度上（错误可由读回 data 中的 `dimension` 字段察觉）。
- 根因：N4/N5 分批落地时 `_collect_dimension_records` 的记录面只服务 dedupe/shift，未暴露成查询能力。
- 修复方案（低成本，数据现成）：① `organize_dimensions` 的 success data 增加 `dimensions: [{view, full_name}]` 清单（`_collect_dimension_records` 已有）；或 ② set_tolerance 失配时在 error details 里附上当前全部 FullName 候选（截断至 N=20）；③ 长期可加独立 `solidworks_drawing_list_dimensions` 工具（注意联动 5 处计数断言与 capabilities）。
- 维度/契约标签：D4/D8 / C-5（错误信息缺下一步）

### D05-5 🟡 insert_bom_table 的 "ADR-0011" 出处引用漂移——AutoBalloon BLOCKED 实证不在该 ADR
- 级别：🟡 —— §3 判据①（引用指向错误，误导追溯）
- 位置：`solidworks_mcp/solidworks_api/drawing.py:1027`（message "balloons unavailable — AutoBalloon BLOCKED, ADR-0011"）
- 证据：ADR-0011（`docs/adr/0011-native-features-and-com-memory.md`，99 行）全文双词形复核——`grep -i "balloon|T8|silent|静默|explode|drawing"` 仅命中 N9/N10 特征解锁与 COM 内存内容（:18 T8 提及是 mirror/pattern 队列，:42-43 是 soak 分组统计），**无任何 AutoBalloon/BOM 气泡记录**。AutoBalloon BLOCKED 的真实实证链 = `tools/INDEX.md:21`（N32 行）+ `tools/probe_drawing/probe_n32_bom_balloon.py` 探针头 + `tests/test_drawing_bom.py:1-5` 文件头。按 message 指引去 ADR-0011 找证据的读者会落空。
- 影响量化：触发频率=每次 insert_bom_table 成功返回（message 常驻）× 最坏后果=证据追溯落空（fail-honest 披露本身在位且内容准确，仅出处号错）。
- 根因：N32 落地时 ADR 编号凭印象引用（BLOCKED/T8 族语义与 ADR-0011 主题相邻）。
- 修复方案：message 与 docstring（:984-986）中的 "ADR-0011" 改为 "probe_n32（tools/INDEX.md N32）"，或在 ADR-0011 增补一节收录 N32 的 AutoBalloon 定谳（前者更小）。
- 维度/契约标签：D8 / C-7

### D05-6 ⚪ insert_bom_table 坐标无图幅范围校验，与同域四工具不一致
- 级别：⚪ —— §3 判据①（一致性弱偏差，无实害）
- 位置：`solidworks_mcp/solidworks_api/drawing.py:996-997`（仅 `finite_number` 拦 NaN/Inf）；对照 `insert_surface_finish:811-815` / `insert_note:865-869` / `insert_section_view:568-583` 均有 `MAX_SHEET_COORD_M`（±1500mm）界检
- 证据：`insert_bom_table(sw, x_mm=1e9, ...)` 会原样换算成 1e6 m 传给 `InsertBomTable5`——表被放到极远处（SW 不报错），用户需手动寻回。`finite_number`（utils/validation.py:11-23，亲读）确认拦 NaN/Inf/bool ✅。
- 影响量化：触发频率=特定参数（畸形坐标）× 最坏后果=表放置在可视图幅外（无数据损坏，可再插一张）。
- 根因：N32 落地时校验面照 BOM 语义精简，未对齐同域坐标纪律。
- 修复方案：补 `abs(mm_to_m(x_mm)) <= MAX_SHEET_COORD_M` 双参校验（两行 + 一个用例）。
- 维度/契约标签：D1 / C-7

### D05-7 ⚪ drawing prompt 工作流指引滞后：N4/N5/N32 六个新工具均未入链
- 级别：⚪ —— §3 判据④（信息级）
- 位置：`solidworks_mcp/registry/prompts.py:52-64`（drawing prompt 全文只覆盖 create→insert_dimensions→export_pdf/png 四步链）
- 证据：prompt 未提 organize_dimensions / insert_section_view / set_tolerance / insert_surface_finish / insert_note / insert_bom_table 六个 N4/N5/N32 工具。capabilities 的 tools 列表有全量工具名（AI 可自行发现），且 prompt 无「全工具覆盖」承诺、无测试锁定 prompt 内容——故仅信息级。叠加 D05-4（尺寸名发现缺口）后，prompt 也没教 AI 如何获取 dimension_name。
- 影响量化：触发频率=AI 走 prompt 入口做工程图任务 × 最坏后果=新工具使用率/链路完整度下降（无功能错误）。
- 修复方案：prompt 增补一句级指引（插入尺寸后 organize → 剖视图 → 公差/粗糙度/注释 → BOM）。
- 维度/契约标签：D8

### D05-8 ⚪ registry 层参数多为裸类型，与全仓 Annotated 惯例弱偏差（行为等价）
- 级别：⚪ —— §3 判据④（禁则 1 边界：不构成 D8 契约破坏才降 ⚪）
- 位置：`solidworks_mcp/registry/drawing.py:72-74, 87-90, 103-107, 116-119, 130-133, 143-146`（`view_name: str = ""` / `mode: str` / `shift_step_mm: float` / `upper_mm: float` 等裸类型）
- 证据：字符串入参用了 `NonEmptyString`（part_path/text/dimension_name/source_view_name ✅），但坐标/步长/公差数值全为裸 `float`、枚举串（mode/direction/bom_type/symbol）为裸 `str`——对照 base.py:40-64 的 `PositiveMM/FiniteMM/FiniteAngle` 预设（misc/part 域在用）。**行为不受影响**：api 层对每个裸参数都有完整的手动校验（mode/direction/symbol 枚举查、bounds 查、finite_number），测试覆盖在案（如 test_drawing.py:779-796）。pydantic 层拦不住 NaN 交给 api 层拦，净效果一致。
- 影响量化：触发频率=无（行为等价）× 最坏后果=客户端侧 schema 描述信息量略低（Annotated description 会进工具 schema）。
- 修复方案：批量换 Annotated 别名属风格统一批，非本域单独事项；建议随下次域内改动顺带。
- 维度/契约标签：D8 / C-7

---

## 上轮对照表（E-3 重证）

| 继承项 | 上轮定性 | 本轮重证证据 | 状态码 |
|---|---|---|---|
| **G5-a 爆炸图投影**（evolution-summary「图纸（爆炸图/BOM 气泡）」长尾） | 远期/长尾 | `assembly.explode` 工具+e2e_n33 实机 ✅ 已建（04 域件）；但**爆炸态图纸投影**仍留观察项——`tools/INDEX.md:27` 现值「爆炸态图纸投影留观察项」+ `e2e_n33.py:3-4` docstring "exploded-state projection is an observed follow-up"（e2e 只验收 explode 创建，:47-53，不含投影断言）；drawing.py 侧无爆炸态投影参数面（CreateDrawViewFromModelView3 第 2 参恒空串，:179-181，N33 实证爆炸视图名/配置名均被拒） | **◐**（爆炸创建闭环；爆炸态投影观察项未解决，且不在 capabilities limitations 披露——见 D05-3） |
| **G5-b BOM 气泡（AutoBalloon BLOCKED）** | 缺口，待诚实拒绝 | 诚实拒绝四重在位：api docstring drawing.py:984-986 + success message :1026-1028 + probe_n32_bom_balloon.py（INDEX.md:21）+ test_drawing_bom.py:1-5 文件头；工具不提供气泡入口（无假成功路径） | **✅**（诚实拒绝在位；唯出处引用错号 = D05-5，limitations 未披露 = D05-3） |
| **insert_bom_table 三面完备性**（rubric §5） | AR-2 缺口内待审 | 三面亲验一致：registry（registry/drawing.py:142-153，view_name/x_mm=240/y_mm=20/bom_type="parts_only"）↔ api（drawing.py:974-986 同签名同默认值）↔ tests（test_drawing_bom.py:71-93 锁 11 参米制契约 `(False, 0.240, 0.020, 1, 1, "", "", False, 0, False, False)` + anchor=1/PartsOnly=1）；实机 e2e_n32.py:62-72 全链验收（含 PDF >10KB 落盘断言）。**第 4 面 re-export 缺**：server.py re-export 9 件 vs registry 10 defs（差集=`solidworks_drawing_insert_bom_table`，命令见附录） | **◐**（三面+实机 ✅；re-export 缺口归 AR-2，不另占号） |
| **导出路径交叉**（rubric §5，与 07 域移交协调） | 待核 | drawing PDF/PNG 走 `_export_drawing`（drawing.py:908-949）：`validate_output_file`（:916）+ `ensure_sink_path`（:924-926）与 file_io 域同一条 security 链，无独立路径逻辑；导出实现本体（SaveAs3 语义/PNG IHDR 判读 :893-905）健康 | **✅**（交叉面无洞；细节归 07 域） |
| AR-2（Alex 遗留，re-export 缺 10 工具） | 🟠 下限 | drawing 侧亲验成立：缺 1 件（insert_bom_table）；server.py:6-8 兼容承诺注释在案 | 引用 AR-2（drawing 份额 1/10） |

**任务书清单交叉验证**（「精确清单以 Alex 地图 §9 为准」执行项）：任务书把 `test_dimension_edit.py` 列入本域——**实为 features 域**（`tests/test_dimension_edit.py:9-14` import `solidworks_mcp.solidworks_api.features.{delete_feature,set_dimension,set_dimension_angle}`，3D 模型尺寸编辑链，与图纸公差链 `drawing.set_tolerance` 是两条独立链路，零 import 交叉）。Alex 地图 §7 将其正确列在 features 行。**以 Alex 地图为准的裁定成立，任务书原清单有 1 项归属偏差**（移交 09 域知悉即可，非问题）。

---

## C-1~C-8 契约逐项结论（10 工具全量）

| 契约 | 结论 | 证据锚 |
|---|---|---|
| C-1 run_com | ✅ 全合规 | registry/drawing.py 10 函数全部经 `_call_connected`（全文精读，无一绕过；lambda 体内无游离 COM 交互——`sw_app.app` 访问发生在 invoke 内部） |
| C-2 allowed_root | ✅ | create_from_part `validate_path(must_exist=True)`（:150）；export 双验 `validate_output_file`+`ensure_sink_path`（:916,:924）；其余工具无文件路径参数（不适用） |
| C-3 DESTRUCTIVE | ✅ | export 带 `overwrite_confirm` + `IDEMPOTENT_WRITE`；organize 删除的重复维度可由重插恢复（STATE_CHANGE 恰当）；无双门全无项 |
| C-4 mm→m | ✅ 双路径核验 | 常量面：FRONT/TOP/SIDE_XY 等模块常量注释明示 "sheet metres"（:62-65）；参数面：`mm_to_m(x_mm)`（:1015 BOM）+ 六处手动 `/1000.0`（section :561/:580-583、tolerance :705-706、surface :799-801、note :859-860）逐一核对面单位参数，无漏换算 |
| C-5 fail-honest | ✅（D05-1 一处弱化） | SW_NO_EFFECT 语义（:257-263）、known-views 列举（:443-446,:592-596）、异常路径 `logger.exception`+结构化 error（每工具）；弱化点=D05-1 读回不断言 |
| C-6 计数同步 | ✅ | `grep -c "mcp\.tool(" registry/drawing.py` = 10 = `grep -cE "^def solidworks_"` = 10；79/81 总数断言 5 处含 drawing 10 件（tests/test_infrastructure.py:167,180 + test_server.py:26,157,164） |
| C-7 参数校验 | ✅（D05-6/D05-8 弱偏差） | 枚举/边界校验完备（mode :427-431、step :432-437、direction :555-560、cut ±500 :561-566、placement ±1500 :568-583、tolerance ±100 :711-715、Ra [0.008,100] :805-810、bom_type :990-995、finite_number :996-997）；偏差两处见 ⚪ 条目 |
| C-8 超时毒化 | ✅ | 全走 `_call_connected` 即继承 run_com+`_com_timeout()`+毒化退程；域内无自定义直连路径 |

## 「mock 绿但实机存疑」清单（深读方向⑥）

本域**无 🟠 级此类项**——N4（probe_dim_organize_section.py 8 轮）/ N5（probe_tolerance_finish_dxf.py 5 轮）/ N32（probe_n32_bom_balloon.py + e2e）三批全有探针+e2e 双锚，mock fake 形态按探针真实形状建模（文件头自证）。存疑仅两条轻微形态：① D05-1 的 mock 断言在恒真 fake 上成立（验证语义未被 mock 拓扑覆盖）；② `insert_bom_table` 的 `GetSelectedObject6(1,-1)` 返回值无类型校验（drawing.py:1008-1012）——实机已由 N32 e2e 覆盖，理论异形对象会落 `except → SW_API_ERROR` 兜底，不谎报。**实机实证结论（N32 InsertBomTable5 11 参 / N33 空串投影）本轮全部尊重未推翻**。

---

## 移交项与交主会话复核清单

**移交其他域**：
- → **07（F 文件IO）**：导出交叉面结论——drawing PDF/PNG 与 file_io 共用 security 链无洞（本报告上轮对照表末行）；07 域可引用，无需重查 drawing 侧。
- → **09（T 测试CI）**：① test_dimension_edit.py 归属澄清（features 域，任务书清单偏差）；② 测试计数补充：drawing 域 64+6=70 用例（test_drawing.py 64 / test_drawing_bom.py 6，`grep -c "def test_"` 实证），test_drawing.py 的 not-running 批量测试（:530-545）不含 insert_bom_table（该文件 0 引用，BOM 测试自包含于专用文件——非缺口，SolidWorksNotRunningError 分支 :1030-1031 无直接单测，属极轻观察）。
- → **04（A 装配）**：G5-a 爆炸态投影观察项的另一半在装配侧（爆炸视图创建已闭环）；若后续立项「爆炸态图纸投影」，两侧需协同（drawing 侧需 CreateDrawViewFromModelView3 之外的投影路径，N33 实证按名投影被拒）。

**需实机/需用户裁决项**：
- D05-2 修复后的 x 向阈值取值（建议 15mm 文字宽量级，需实机标定一次）。
- set_tolerance 对「同一 FullName 出现在多个视图」（跨视图同名显示维度）时只设第一个命中（:723-740 首个 break）——若 SW 公差存于模型维度层则一次设置全局生效（无害），若存于显示层则其余视图不更新。**静态不可定谳**，建议实机一测（同一维度投两视图→设公差→查另一视图读回值）。当前无证据表明是缺陷，列为待实机观察项 ⚪。

**推荐进总报告的 Top 发现**：D05-4（尺寸名发现缺口——AI 工作流实际效率瓶颈，修复成本最低收益最高）、D05-3（capabilities limitations 能力缺口披露）、D05-1（verified 宣称与实现分叉）。

---

## 附录：取证命令留档（E-5）

```bash
# 工具计数双口径（registry/drawing.py）
grep -c "mcp\.tool(" solidworks_mcp/registry/drawing.py        # → 10
grep -cE "^def solidworks_" solidworks_mcp/registry/drawing.py # → 10

# re-export 差集（AR-2 drawing 侧）
grep -E "^def solidworks_drawing" solidworks_mcp/registry/drawing.py | sed 's/(.*//' | sort  # → 10 defs
grep -oE "solidworks_drawing_[a-z_0-9]+" solidworks_mcp/server.py | sort -u                 # → 10 命名（含 prompt，工具 9）
# 差集 = solidworks_drawing_insert_bom_table（prompt 非工具，10−9=1 工具缺口）

# 测试计数
grep -c "def test_" tests/test_drawing.py tests/test_drawing_bom.py tests/test_dimension_edit.py
# → 64 / 6 / 10（第三项归 features 域）

# ADR-0011 无 balloon 记录（双词形复核）
grep -n -i -E "balloon|T8|silent|静默" docs/adr/0011-native-features-and-com-memory.md
# → 仅 :18(T8 mirror/pattern)、:90-97(T8 同队列)，无 AutoBalloon/BOM 内容

# test_drawing.py 无 BOM 引用（E-6）
grep -c "insert_bom_table" tests/test_drawing.py   # → 0
```

（完）
