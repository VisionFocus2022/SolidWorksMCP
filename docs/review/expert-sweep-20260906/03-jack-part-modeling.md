# 03 · Jack — 零件建模域深审报告

> **调研员**: Jack（报告号 03，域字母 P）
> **审查日期**: 2026-09-06
> **代码快照**: 主仓 HEAD=0762b15（main）；工作区未提交 1 文件（`output/optimization-plan-2026-09-01.md` M）+ `docs/review/` 未跟踪（本轮审查目录）；pytest 基线 538 passed + 105 subtests（快照口径，09 域复核现值）。本域全部取证对象（api/registry/tests）均为 HEAD 可达文件，工作区漂移不影响本域结论。
> **方法**: 全程只读静态深审。Read 精读 api 层 10 模块全文（part/design/features/pattern/geometry/sketch/topology/measure/sheet_metal/decorations，共 ~4200 行）+ registry 2 模块（part/features，808 行）+ 3 份测试深读（test_n9_unlock/test_design 原子性段/test_csg_rebuild 断言面）+ 其余测试 grep 定位；计数双口径；否定性结论双词形复核。

---

## 执行摘要

- 发现计数：🔴 0 / 🟠 0 / 🟡 4 / ⚪ 3。无崩溃级与严重级问题——零件域整体工程质量高（fail-honest 全覆盖、单位换算 C-4 零漏、防御纵深齐、实机契约 docstring 文化成熟）。
- 最重要的发现是 **N9 解锁工具批的两组隐性假设**：P03-2 cut_real_thread 的 19.5mm 魔法数顶面判定（无披露+误导错误信息）与 P03-3 mirror/cut_real_thread 的中文单语硬编码（英文 SW 环境不可用）——mock 测试与生产代码共享同一假设，形成测试盲区。
- P03-1：execute_design_plan 的 `new_part` 中位场景打破 atomic 承诺（跨文档回滚缺口，现有测试全部单文档假设）。
- 上轮对照：**G4 ✅**（8 件长尾工具+测试全在册，本轮逐件 grep 实证）/ **G6 ◐**（v1 4-op 已扩展为 6-op 双版本+N31 测试，但 docstring 滞后 v2 见 P03-4、v2 形态仍受限）/ **AR-5 ⚪ 复核维持**（28 工具/632 行，尚在阈值内）/ **AR-6/G7 远期不变**（pattern 数学重建现状确认）/ **AR-2 ✅ 复核确认**（10 件差集，part 域占 8）。

## 自验声明

- **E-1 ✅** 全部发现的 `文件:行号` 本轮亲 Read 核对（api 10 模块 + registry 2 模块 + 3 份测试逐行；地图/上轮行号仅作路标）。
- **E-2 ✅** 快照时刻记录于头部；本域结论全部基于 HEAD 可达代码与测试文件；工作区仅有的 M（output/ 计划文档）不在本域取证面内，无需 git show 区分。
- **E-3 ✅** G4/G6/AR-5/AR-6(G7)/AR-2 逐项本轮重证后授予状态码（证据见上轮对照表）。
- **E-4 ✅** 4 条 🟡 均附「触发频率 × 最坏后果」。
- **E-5 ✅** 计数均附命令与输出摘要：mm_to_m 62 处（`grep -rc mm_to_m` 聚合 32+8+5+5+5+4+2+1）；registry/part.py 双口径 `mcp.tool(`=28 == `^def solidworks_`=28；AR-2 差集 `comm -23` 输出 10 件清单；零件域测试规模 grep 计 282 个 test 函数+类。
- **E-6 ✅** 否定性结论双词形复核：①「C-4 零漏换算」= SketchManager 全部几何调用点正向逐一核对 + `CreateCircleByRadius|CreateLine|CreateArc|CreatePolygon|CreateSketchSlot|CreateCornerRectangle` 六方法反向全扫；②「_find_face_by_role 唯一调用方」= 函数名 grep + 魔法数 `0.0195` grep 双词形（后者于 tests/ 零命中同时坐实无边界测试）；③「全仓无显式 COM 释放」= `ReleaseComObject|Marshal|CoUninitialize` 三词形 grep（唯一命中 com_executor.py:69 CoUninitialize）。
- **§10 禁则自查 ✅**：无风格偏好类（P03-7 命名项已降 ⚪ 并注明非 bug）；无未取证推测（推测均显式标注）；无转抄宣称（所有 docstring 声明均核到代码/测试现值）；🟡 均有影响量化。

## 问题清单

### P03-1 execute_design_plan 的 `new_part` 中位场景打破 atomic 回滚承诺（跨文档残留）
- 级别：🟡 —— §3 判据①/⑤（特定路径下 atomic 语义失效；错误结果可被察觉）
- 位置：solidworks_mcp/solidworks_api/design.py:50-59（DESIGN_PLAN_OPERATIONS 无顺序校验）、:529-530（before 快照取自 initial_model）、:754-756（回滚仅作用于 `sw_app.get_active_document()` 当前文档）
- 证据：`new_part` 无首 op 强制（对比 CSG plan 的 box 首 op 校验 :955 与 v2 首 op 校验 :967）。当 plan 为 `[box, new_part, hole(失败)]` 时：before 快照来自旧文档；new_part 后 `NewDocument` 切换活动文档；失败回滚 `_delete_new_features` 的 `model = sw_app.get_active_document()`（:754）拿到的是**新文档**——旧文档中 box op 创建的特征不在回滚范围，永久残留。docstring :510-512 明确承诺 "any failed operation triggers a rollback... retrying a plan never stacks half-applied features"——跨文档场景该承诺失效，且重试会在旧文档继续堆叠。测试盲区实证：tests/test_design.py:375-505 的原子性测试族全部单文档假设（RollbackSolidWorks 恒返回同一 model :354-359；ShellSolidWorks 是 new_part **首位**场景 :362-372），无任何中位 new_part 跨文档用例。
- 影响量化：特定参数组合（new_part 非首位 + 其前有特征创建 op + 后续 op 失败）× 旧文档残留半应用特征并随重试累积（可通过 data.applied 列表与 SW UI 察觉、可手动清理——不谎报）。
- 根因：plan 执行器隐含「单文档」假设，未随 new_part op 的文档切换语义做快照/回滚的多文档化。
- 修复方案：最小修法=在 op 分发处拒绝 `new_part` 于非首位（对齐 CSG plan 的首 op 校验风格，报 INVALID_PARAMETER 并说明 "new_part must be the first operation"）；完整修法=回滚遍历 plan 触达的全部文档（快照按文档分组）。补中位 new_part 的拒绝/回滚测试。
- 维度/契约标签：D1 / C-5

### P03-2 cut_real_thread 的顶面判定魔法数 0.0195/0.005m——适用域未披露 + 误导性错误 + 死代码角色
- 级别：🟡 —— §3 判据⑤（错误信息缺真实原因，不谎报）
- 位置：solidworks_mcp/solidworks_api/features.py:457-479（`_find_face_by_role`：top 判定 `dz < 1e-6 and box[5] > 0.0195`，bottom 判定 `box[2] < 0.005`）、:652（唯一调用方）、:660（`CreateCircleByRadius(0, 0, 0, ...)` 原点中心假设）
- 证据：0.0195m=19.5mm / 0.005m=5mm 是 N9 probe 实机样件（~20mm 高圆柱，见 :469-475 判定值与 N9 证据链同源）的几何假设遗留。零件总高 <19.5mm 或顶面 z ≤19.5mm 时，`_find_face_by_role(model, "top")` 返回 None → 报 **"No top face found on active part"**（:654-656）——顶面明明存在，错误信息把排障方向带偏。`bottom`/`yplus` 两角色 grep 全仓零调用方（死代码）。工具 docstring（registry/features 层与本层 :629-637）均未披露高度阈值与原点对中假设。测试盲区：tests/test_n9_unlock.py:249/:291 夹具 `box_mm=(-10,-10,50,10,10,50)` 等全部用 z=50mm **迎合阈值**；`grep _find_face_by_role|0.0195 tests/` 零命中——无边界测试。
- 影响量化：特定参数组合（零件高度 <19.5mm 或非原点对中，AI 在小零件/偏置零件上切螺纹必撞）× 工具失败且错误信息误导（"No top face found"），AI 调用方排障成本高；另 bottom/yplus 死角色是维护噪声。
- 根因：probe 时代的几何启发式直接进了生产代码，魔法数未提取为具名常量、未在契约层披露适用域；测试夹具复制了 probe 样件几何。
- 修复方案：①阈值提取为模块常量（如 `_TOP_FACE_MIN_Z_M`）并在 docstring 声明 "requires a part whose top face sits above 19.5mm and is centered at the origin"；②错误信息改为带原因（"top face not found by role heuristic (z>19.5mm required); use list_faces-based selection"）；③删除 bottom/yplus 死角色或补调用方；④补一条低零件（z=10mm）失败的边界测试断言错误文案。
- 维度/契约标签：D1 / C-7

### P03-3 N9 解锁工具的中文单语硬编码——英文 SW 环境不可用（仓内双语防御模式的不一致缺口）
- 级别：🟡 —— §3 判据①（特定环境下工具返回错误；可察觉）
- 位置：solidworks_mcp/solidworks_api/features.py:418-421（`_MIRROR_PLANES = {"right": "右视基准面", ...}` 单语值）、:667-671（`"螺旋线" in name` 子串匹配 helix 特征名）
- 证据：mirror_feature :520-522 `SelectByID2(plane_cn, "PLANE", ...)` 只尝试中文名——英文 SW 上基准面名为 "Right Plane"，选择必失败 → "SolidWorks refused to select plane"。cut_real_thread :667-671 以「螺旋线」子串定位 helix 特征——英文 SW 生成 "Helix/Spiral1"，匹配必失败 → "Helix was not created"。对照仓内既有双语防御模式：design.py:42-46 `PLANE_ALIASES`、part.py:53-54、sheet_metal.py:32、assembly.py:52-57（双向映射）全部中英双名——**唯一两个单语点都在 N9 批工具里**。测试同病：tests/test_n9_unlock.py:151/:158/:162 断言中文平面名调用、:250/:264/:299 夹具特征名「螺旋线/涡状线1」——生产与测试共享中文假设，零英文环境覆盖。
- 影响量化：特定环境（非中文 SolidWorks 2026）× mirror_feature 与 cut_real_thread 两工具 100% 不可用（错误诚实失败不谎报，但工具面静默缩水——capabilities 不披露语言依赖）。
- 根因：N9 解锁批（2026-08-30）在本机中文 SW 上 probe 定型，实机契约直接内嵌了本地化名称；未复用仓内既有的中英候选列表基建（geometry.select_plane + 双语 alias 表）。
- 修复方案：`_MIRROR_PLANES` 改为 `{"right": ["Right Plane", "右视基准面"], ...}` 走 `select_plane` 或 SelectByID2 双语循环；helix 定位改「螺旋线」与 "Helix" 双子串（或按 `GetTypeName2() == "ICEThread"...`/特征类型判定而非名字）；docstring 与 capabilities 披露语言依赖；测试补英文平面名路径一例。
- 维度/契约标签：D1 / C-7

### P03-4 rebuild_csg 工具 docstring 滞后 v2——polygon_prism/swept_arc 对 AI 调用方不可发现
- 级别：🟡 —— §3 判据①（D8 文档/宣称与实现漂移；判据锚=AR-1 同族）
- 位置：solidworks_mcp/registry/features.py:36（docstring 现值逐字："Rebuild a cross-engine CSG plan (v1: box/cylinder/cone/cut_cylinder, stacking semantics) as an SW feature tree."）
- 证据：实现现值 = design.py:794-796 `CSG_V2_OPS=("polygon_prism","swept_arc")`、`CSG_OPS` 6-op、:804-806 `_validate_csg_plan` 接受 version 1/2；tests/test_csg_rebuild.py:469-573（N31）对 v2 双 op 的 dispatch/stacking/拒绝路径测试齐备。但工具层 docstring 仍只描述 v1 4-op——MCP 工具描述是 AI 的能力发现面，v2 能力（多边形棱柱/圆弧扫掠）无法经工具描述被发现（仅 aicad 侧契约文档 docs/csg-plan-v1.md §v2 记载）。test_capabilities_sync.py 对 csg 零命中（grep 实证），不锁 op 清单——sync 测试不兜底此漂移。
- 影响量化：每个经 MCP 工具面认识 CSG 能力的 AI 会话 × v2 两个 op 不可发现（功能在册可直调，参数契约需读仓内文档——发现成本升高，无运行时错误）。
- 根因：N31 v2 扩展批更新了 api 层与测试，漏更 registry 层工具 docstring（新工具走 test_capabilities_sync 锁 docstring，但 op 范围扩张不在锁内）。
- 修复方案：docstring 更新为 "(v1: box/cylinder/cone/cut_cylinder; v2 adds polygon_prism and swept_arc — first-op only; stacking semantics)"；可选在 test_capabilities_sync 增加 CSG op 清单↔CSG_OPS 常量的锁定断言防再漂移。
- 维度/契约标签：D8 / C-6、C-7

### P03-5 DESTRUCTIVE/STATE_CHANGE 三档标注语义未成文，域内归类不一致
- 级别：⚪ —— 观察（hint 层一致性，方向偏保守=安全侧）
- 位置：solidworks_mcp/registry/part.py:587-598（apply_dome/fillet/chamfer/shell 标 STATE_CHANGE）、:551/:599-617（cut 系标 DESTRUCTIVE）；registry/features.py:162-176（dimension_set 标 STATE_CHANGE 但 rename/suppression 标 DESTRUCTIVE）
- 证据：rename 完全可逆、suppression 可逆，却标 DESTRUCTIVE；shell（挖空减材）与 dimension_set（改几何可致重建失败）语义更重却标 STATE_CHANGE。三档（READ_ONLY/STATE_CHANGE/DESTRUCTIVE）无成文判定规则（base.py:79-102 只列预设不等判定标准）。全部标注方向偏保守（宁可多标），无实际漏拦——非缺陷。
- 影响：AI 客户端对破坏性预判的 hint 精度受损（过度告警稀释 DESTRUCTIVE 信号）；维护者新增工具时无规则可依。
- 修复方案：在 base.py 注解预设区补 5 行判定标准（如「DESTRUCTIVE=减材/删除/不可逆或需确认的操作」），据规则复核存量标注。
- 维度/契约标签：D8 / C-3

### P03-6 create_slot 的 CreateSketchSlot 14 参调用无逐参注释
- 级别：⚪ —— 可维护性（非 bug，几何经 e2e 锁定）
- 位置：solidworks_mcp/solidworks_api/part.py:1169-1175
- 证据：本仓长参向量调用的成熟范式是逐参注释（对照同文件 create_swept :660-681 的 InsertProtrusionSwept4、create_revolved :511-532 的 FeatureRevolve2、sheet_metal.py:83-94 的 InsertSheetMetalBaseFlange——全部逐参标注）；CreateSketchSlot 是仓内唯一无注释的长参向量（14 参），几何正确性仅由 N30 e2e 面积断言（length·width+π(width/2)²）锁定，后续维护者无法从代码判位。
- 修复方案：按 N30 probe 契约补 14 个参数的行内注释（slotType/xStart/.../angle）。
- 维度/契约标签：D1 / C-7

### P03-7 extrude_boss 首参命名 `reverse` 实为 FeatureExtrusion2 的 Sd（single-direction）位
- 级别：⚪ —— 命名误导（行为经实机验证正确，非 bug）
- 位置：solidworks_mcp/solidworks_api/sketch.py:12-18（`def extrude_boss(model, height_m, reverse: bool = True)` → `FeatureExtrusion2(reverse, False, False, 0, 0, height_m, ...)`）
- 证据：SW API FeatureExtrusion2 首参为 Sd（true=单向拉伸）；参数名 `reverse` 会让维护者误以为控制拉伸方向反转。默认 True 与全部调用方（part.py/pattern.py 多处）不传该参的用法一致，行为正确（T5/T16/N 系列实机验证链）。
- 修复方案：重命名为 `single_dir: bool = True`（全调用方零改动——均不显式传参）。
- 维度/契约标签：D1

## 上轮对照表

| 上轮项 | 上轮定性 | 本轮状态码 | 重证证据（一行） |
|---|---|---|---|
| **G4 能力长尾**（loft/sweep/筋/圆顶/参考几何） | 缺口（远期） | **✅ 已修（工具面+测试全在册）** | grep 实证：create_swept/create_loft→test_part_loft.py、create_polygon/create_slot→test_part_primitives.py、create_ref_plane/create_ref_axis/create_rib/apply_dome→test_part_refgeom.py、swept 另见 test_csg_rebuild.py；8 件 docstring 均在 registry/part.py:201-341 亲读；**质量深审产出 P03-2/P03-3**（N9 批的 mock 未覆盖本地化与几何假设两个维度——但 N9 工具在目标环境（本机中文 SW）有 N9 probe 实机验证，非「实机零验证」） |
| **G6 CSG 契约 v1 仅 4-op** | 远期（v2 待扩） | **◐ 部分（v2 已扩 2-op，受限形态）** | design.py:794-796 CSG_OPS=6-op（box/cylinder/cone/cut_cylinder+polygon_prism/swept_arc）；test_csg_rebuild.py:469-573 N31 v2 测试齐备；但 v2 仍受限（swept_arc 只能单 op :985-990、polygon_prism 只能首 op :967-972、solid 仍只轴向堆叠无 x/y 偏移 :1007-1011）+ docstring 滞后（P03-4） |
| **G7/AR-6 native 阵列数学重建** | 远期 | **远期不变（⚪）** | api/pattern.py 全文亲读：每环独立 sketch+cut/boss 重建（:256-317），grep `FeatureCircularPattern|FeatureLinearPattern` 于 solidworks_api/ 零命中（N9 probe 13 变体 BLOCKED 证据链未变，create_linear_holes docstring :284-290 自述 NOT parametric-linked） |
| **AR-5 part 域膨胀** | 观察（⚪） | **⚪ 维持（阈值内）** | registry/part.py 双口径 28=28（`grep -c "mcp.tool("` == `grep -c "^def solidworks_"`）+ 632 行；api/part.py 1242 行——全仓最大件未变；N 系列 8 新工具全落 part 域未拆分；仍在 Alex 预估阈值（~40 工具/1500 行）之下 |
| **AR-2 re-export 缺 10 工具** | 🟠（Alex 定级） | **✅ 复核确认（差集一致）** | `comm -23 defs.txt reexp.txt` 输出 10 件：part 域 8 件（create_swept/loft/polygon/slot/ref_plane/ref_axis/rib、apply_dome）+ assembly_explode + drawing_insert_bom_table——与地图 AR-2 逐件吻合（本域复核部分域即可，归属 08 域跟进） |

## 移交项与交主会话复核清单

**移交其他域**：
- → **05 工程图域（D）**：drawing.py:616 `sketch_manager.CreateLine(*line)` 的单位口径未核（drawing.py 全文件仅 2 处 mm_to_m，零件域视角可疑——请按 C-4 对 drawing 全部 SketchManager/坐标调用面核单位）。
- → **08 COM 基建域（C）**：全仓零 Marshal.ReleaseComObject/显式 COM 释放（grep ReleaseComObject|Marshal|CoUninitialize 三词形唯一命中 com_executor.py:69 的线程级 CoUninitialize）——零件域特征/面/体 COM 引用全靠 RCW/GC 回收，属仓内一致设计；长会话累积风险请结合 test_memory_guard.py/soak_session.py 评估知情性（D2）。
- → **09 测试CI域（T）**：①本域 282 个测试函数+类（grep 粗计）供覆盖面分析；②test_n9_unlock.py 的「夹具迎合生产假设」模式（z=50mm 迎合 0.0195、中文特征名与生产共享）可作为 mock 真值陷阱族新样本归档。

**需主会话二次实证/需实机的发现**：
- **P03-1**（new_part 中位原子性）：建议实机或 FakeSolidWorks 多文档夹具复现一次跨文档残留（现报告基于代码路径推演+测试盲区实证，无运行时复现）——推演链完整但未跑。
- **P03-2**（19.5mm 阈值）：建议实机 SW 上用 10mm 高圆柱调 cut_real_thread 复现 "No top face found"（现证据=代码+夹具迎合，无实机失败样本）。
- **P03-3**（英文 SW）：本机为中文 SW 无法复现英文环境——按代码路径定级，若部署域确认仅中文 SW 可降 ⚪（披露义务不变）。

**推荐进总报告的 Top 发现**：P03-2、P03-3、P03-1（按序）。

---

## 附录：中间发现暂存区（深审过程留档，与正文重复处以正文为准）

（子域 1-9 的过程记录已整合进上文问题清单与对照表；保留要点：mm_to_m 62 处复核 ✅；C-4 零漏换算（零件域）；resources 释放形态移交 08；G4 八件测试在册；test_n9_unlock 夹具迎合假设；HOLE_PLANE_ALIASES/typed FM/tree-diff 判定等成熟范式正面确认未列入问题。）
