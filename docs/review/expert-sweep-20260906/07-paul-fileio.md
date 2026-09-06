# 07 · Paul — 文件IO导出域深审报告

> **审查日期**: 2026-09-06
> **代码快照**: 主仓 HEAD=0762b15（与地图/rubric 基准一致）；工作区未提交项同地图头部（`output/optimization-plan-2026-09-01.md` M + `docs/review/` 未跟踪）。本轮深读期间工作区无新增漂移（所有亲验文件 mtime 均早于本会话）。
> **域**: 文件 IO 与导出（F）——`solidworks_api/file_io.py`(354) / `registry/file_io.py`(107) / `tests/test_file_io.py`(311) + test_hardening 交叉 + 落盘点全仓扫描。
> **方法**: 全程只读（Read/Grep，零写操作，本报告文件除外）。所有行号本轮亲验（E-1）。

---

## 执行摘要

- 发现 **0🔴 / 2🟠 / 3🟡 / 3⚪**（共 8 项）。一票否决零直接命中，但 **F07-1 含 §8 条款 2（allowed_root）的边界形态**，因触发需特定前置场景且语义为用户明示的保存/关闭指令，按 🟠 定级、上报团长裁决是否升 🔴。
- **F07-1（🟠）活动文档信任盲区**：`file_close(save_changes=True)` 的 `Save3` 落点=文档自身路径，**未经任何 allowed_root 校验**（越界写第三形态：路径来自文档状态而非 MCP 参数）——用户在 GUI 打开的 root 外文档可被 AI 触发保存；`save_changes=False` 默认路径则会丢弃**用户的人工未保存编辑**（S06-1 的 AI 自编辑变体之外的更强场景）。
- **F07-2（🟠）Save3 无 typed-wrapper 容错**：同文件 `_open_doc6` 有双形态容错（T1 实证 makepy wrapper 拒 byref VARIANT），`Save3`（file_io.py:159 + ring_light_v3.py:520 共 2 处）没有——gen_py 缓存环境下「保存并关闭」通道 TypeError 断裂；registry 层**无独立 save 工具**加重影响。
- 上轮对照：AR-9 双源现状 3 项逐字一致（护栏缺失未修，◐）；CWD 污染族攻击面已闭合（✅，残留语义漂移见 F07-8）；四格式错误路径完备性呈三档不对称（DXF header 验证 > drawing getsize > STEP/STL 仅返回码，F07-3）。

## 自验声明

- [x] **E-1**：全部 `文件:行号` 本轮 Read 亲验（file_io.py 全文 354 行、security.py 全文 208 行、registry/file_io.py 全文、test_file_io.py 全文、test_hardening.py 全文、ring_light.py/ring_light_v3.py 目标段、drawing.py 目标段、constants.py、app.py、requirements.txt、pyproject.toml）。
- [x] **E-2**：AR-9 比对对象 requirements.txt / pyproject.toml 均在版本库内（git ls-files 口径），无需 HEAD/盘上态二分；未涉 output/ 结论。
- [x] **E-3**：AR-9、CWD 污染族、S06-1 交叉、四格式错误路径（rubric §5 F 域四项）全部重证后标码，见 §5 对照表。
- [x] **E-4**：2 条 🟠 均写触发频率 × 最坏后果。
- [x] **E-5**：计数类结论（SaveAs3=17、Save3=2、原生写=3、工具数 6/6、依赖 3 项）附命令与输出摘要（§4 各条 + 附录）。
- [x] **E-6**：否定性结论双词形复核（落盘点完备性：「无非 SaveAs3 写盘点漏网」用 `SaveAs3|SaveAs2|Save3|Save2|Save(` + `open(.*[wab]|write_bytes|write_text|os.remove|os.rename|shutil|DumpSave|SaveToFile|ExportTo` 两族正则交叉，见附录 A）。
- [x] **§10 禁则自查**：无风格偏好项、推测显式标注、无转抄文档宣称、报告外零写文件。

---

## 问题清单

### F07-1 「活动文档信任盲区」：Save3 落点未经 allowed_root 校验 + 默认丢弃用户人工编辑
- 级别：🟠 —— §3 判据⑤（安全护栏有洞但需特定条件穿透）+ §3 判据①候选；**含 §8 一票否决条款 2 的边界形态（路径校验缺失形态之三：路径来自文档状态而非 MCP 参数），上报团长裁决是否升 🔴**
- 位置：`solidworks_mcp/solidworks_api/file_io.py:159`（Save3 落点）/ `:146-185`（close_document 全体）/ `:195-200`（app.py get_active_document 无身份校验）
- 证据：`close_document` 中 `saved = bool(model.Save3(swSaveAsOptions_Silent, errors, warnings))`（:159）——Save3 无路径参数，落点=活动文档自身路径，**全程不经 `is_path_allowed`/`ensure_sink_path`**（本文件 17 处 SaveAs3 sink 均有 ensure_sink_path，唯一写盘点裸奔）。活动文档来源枚举：MCP `file_open`（validate_path 校验过 ✓）、建模工具产物（SaveAs3 sink 校验过 ✓）、**用户 GUI 手动打开 / SW 启动恢复的上次会话文档（零校验 ✗）**。`get_active_document`（app.py:195-200）仅取 `ActiveDoc`，无 title/path 回显或身份确认机制。
- 影响量化：触发频率=特定场景（用户在 SW GUI 打开 root 外文档或带未保存人工编辑的文档成为活动文档，同时 AI 调用 `file_close`）× 最坏后果双分支：① `save_changes=True` → 用户的 root 外文件被写入（AGENTS.md 红线 2「文件操作必须在 allowed_root 内」被文档状态路径绕过）；② `save_changes=False`（默认）→ **用户人工编辑（GUI 草绘/标注数小时成果）被静默丢弃，不可逆**——比 S06-1 已立项的「AI 自身编辑丢失」场景更强（受害者从 AI 变成用户本人）。
- 根因：allowed_root 防线只覆盖「MCP 参数传入的路径」，未覆盖「COM 对象自带状态中的路径」；`get_active_document` 的活动文档信任假设无二次确认门。
- 修复方案（最小可执行）：`close_document` 在 Save3 前读取文档路径（`model.GetPathName`）过 `is_path_allowed`；不在 root 内时拒 `save_changes=True`（诚实报错提示路径）；可选加 `expected_title` 参数供调用方校验文档身份。测试：mock 文档 GetPathName 返回 root 外路径断言拒绝。
- 维度/契约标签：D3 / C-2、C-3
- 关联：S06-1（Nora 已立项 close 默认丢弃的 discard 确认门——本条是其「用户人工编辑」+「root 外写」双变体扩展，建议合并处置）；与 F07-2 同点位（Save3 调用形态）。

### F07-2 Save3 无 typed-wrapper 容错——「保存并关闭」唯一显式通道在 gen_py 缓存环境断裂
- 级别：🟠 —— §3 判据①（特定路径下工具返回错误结果，可察觉）
- 位置：`solidworks_mcp/solidworks_api/file_io.py:159`；同款形态 `solidworks_mcp/examples/ring_light_v3.py:520`
- 证据：同文件 `_open_doc6`（:80-102）对 makepy wrapper 做了完整双形态容错——T1 实机证据（test_file_io.py:99 注释原文："Real-machine evidence (T1, 2026-08-29): makepy-generated wrappers coerce VT_BYREF|VT_I4 parameters with int(), which raises TypeError on the pre-built VARIANTs"）+ TypeError 回退 + 返回 tuple 解析。而 `Save3` 调用（:159）传入同样的 `_make_error_variants()` 产物，**无 TypeError 回退、无 tuple 解析**。typed-wrapper 环境现实性坐实：本仓 `properties.py:240-249` 主动使用 `gencache.GetModuleForProgID("SldWorks.Application")`（makepy 缓存在同机被消费）；pywin32 的 `Dispatch` 在 gen_py 缓存命中时返回 early-bound wrapper（app.py:141/146 连接路径即 Dispatch/GetActiveObject）。加重项：`grep "def solidworks_.*save" registry/` 零命中——**registry 层没有独立 save 工具**，`file_close(save_changes=True)` 是 MCP 层保存既有文档的唯一显式通道。
- 影响量化：触发频率=特定环境（SldWorks.Application 的 gen_py 缓存在场——同机任何进程跑过 EnsureDispatch 即全局生效）× 特定参数（save_changes=True）× 最坏后果=该环境「保存并关闭」功能整体 TypeError 失败（诚实 error_response，非静默）；ring_light_v3 的收尾保存（:520）同环境同断。理论残余分支：若 wrapper 版本不强转而接受 VARIANT 并把 out-param 打包进返回值，`bool(tuple)` 恒真 → 假成功（未实证，标注：推测——T1 实证的行为模型是 int() 强转 TypeError 路径）。
- 根因：同文件容错范式未对齐——OpenDoc6 吃过的坑（T1）修了，同家族 byref 消费者 Save3 没跟着修（「抄近亲已实证形态」的遗漏实例）。
- 修复方案：照 `_open_doc6` 范式给 Save3 加 TypeError 回退（plain int 0,0 重试 + 返回 tuple 解析取首位 bool）；ring_light_v3:520 同步。测试：复用 `_typed_wrapper_open_doc6` 形态写 `_typed_wrapper_save3` 双形态用例。
- 维度/契约标签：D8 / C-5（fail-honest 主线成立，功能可用性缺口）；测试范式 D7

### F07-3 STEP/STL 导出无文件级落盘验证——同仓三档验证深度不对称
- 级别：🟡 —— §3 判据⑤（可观测性不足但不谎报——返回码为 SW 权威语义时的信任不对称）
- 位置：`solidworks_mcp/solidworks_api/file_io.py:258-265`（export_step）/ `:291-298`（export_stl）——对比 `:333-345`（export_dxf 有 open+SECTION header 验证 + size_bytes）与 `drawing.py:933-937`（_export_drawing 有 getsize 验证 + size_bytes + PNG 分辨率）
- 证据：export_step 判据仅 `if result != swFileSaveErrorNone: return error_response(...)`，成功即返回 `data={"path": file_path}`——无文件存在性/大小验证，无 size_bytes。同仓两个更强范式在位：① DXF：`with open(sink_path, "rb")` 读头验 `b"SECTION"`，OSError 时返回 "reported success but no file was written"（:336-339）；② drawing PDF/PNG：`os.path.getsize(sink_path)` OSError 同款兜底（drawing.py:934-937）。DXF 的探针注释（:313 "SolidWorks returns warning code 1 for every DXF SaveAs3 (probe-verified)"）证明作者已知 SaveAs3 返回码在导出场景语义不可靠过一次（假失败方向）；drawing 补了 getsize 防假成功方向；STEP/STL 两档都没沾。tools 层部分补位：`tools/validate/triple_artifact.py:17` 注释 "export_step success, non-empty file"（验证脚本自做非空检查）——但库层裸露。测试侧：test_file_io.py:216-229 只测返回码 0/9 分支，无文件验证可测（因为功能不存在）。
- 影响量化：触发频率=罕见条件（SaveAs3 返回 0 但文件未写——SW 异常态/磁盘满/权限，方向未实证）× 最坏后果=假成功 + AI 基于其继续下游交付声明，消费失败滞后暴露。
- 根因：验证深度按「格式踩过坑才补」被动生长（DXF 探针踩坑→header 验证；drawing→getsize），未拉齐为统一 sink 验证范式。
- 修复方案：export_step/export_stl 补 drawing 同款 `os.path.getsize` 兜底 + size_bytes 返回（3 行/处）；可选 STEP 头验证（`b"ISO-10303-21"`）对齐 DXF 范式。
- 维度/契约标签：D4 / C-5
- 上轮对照：即 rubric §5 F 域「四格式错误路径 fail-honest」任务项的结论——DXF ✅ 完整、drawing PDF/PNG ✅ 完整（getsize）、STEP/STL ◐（仅返回码）。

### F07-4 close 默认丢弃 × drawing「close to release file locks」提示的组合涟漪（S06-1 导出侧交叉）
- 级别：🟡 —— §3 判据①/⑤（跨域文档提示把 AI 引向数据丢弃路径）
- 位置：`solidworks_mcp/registry/file_io.py:34-42`（save_changes=False 默认 + docstring "unsaved edits are discarded unless save_changes=true"）；交叉 `registry/drawing.py:33`（docstring "close the drawing (solidworks_file_close) when done to release file locks"——未提保存语义）；`solidworks_api/file_io.py:311-354`（export_dxf）与 `drawing.py:908-949`（_export_drawing）
- 证据：PDF/DXF 导出走 `SaveAs3(sink_path)`（衍生格式路径）——**不保存 .slddrw 本体**，drawing 创建后的尺寸/注记/BOM 编辑（insert_dimension/organize_tolerance 等工具不落盘）停留在内存。drawing.py:33 教 AI「做完就 close 释放锁」且不提 save_changes——AI 遵嘱调用 `solidworks_file_close()`（默认 False）→ 全部 drawing 编辑丢弃。file_close 自身 docstring 有披露（registry/file_io.py:38），但两处 docstring 语义打架：一处教 close、一处警告丢弃，AI 合成行为取决于读哪份。**设计合理性评估**（任务书要求）：默认 save_changes=False 是「防意外覆盖源文件」的保守设计（写操作须显式），方向正确；真正的缺口是**保存通道闭环缺一角**——registry 无独立 save 工具（F07-2 证据），「保存 drawing」只能 a) 重走建模工具隐式 SaveAs3（drawing 域多为增量编辑无此路径）或 b) file_close(save_changes=True)（F07-2 已证 typed 环境断裂）。即：正确路径存在但唯一且脆。
- 影响量化：触发频率=每次 drawing 工作流收尾（AI 按 docstring 提示操作即中）× 最坏后果=drawing 全部编辑丢弃、需重建（AI 可察觉——重开为空图——但损失已成）。
- 根因：跨域 docstring 提示未携带保存语义；保存通道单一且无独立工具。
- 修复方案：① drawing.py:33 提示改为 "close with save_changes=true when the drawing should be kept"（1 行，移交 05 域）；② 中期：加 `solidworks_file_save` 独立工具（SaveAs3 回存自身路径形态，过 F07-1 的 root 校验）补全闭环。
- 维度/契约标签：D8 / C-7；跨域移交 05（Eric）。

### F07-5 overwrite 确认门存在 TOCTOU 窗口——ensure_sink_path 只复检 root 不复检 overwrite
- 级别：🟡 —— §3 判据⑤（护栏有洞需特定时序穿透）
- 位置：`solidworks_mcp/utils/security.py:93-112`（ensure_sink_path 仅复检 is_path_allowed）；`:171-188`（check_overwrite_confirm 只在 validate_output_file 时点执行一次）
- 证据：`validate_output_file` 的 docstring 自述 "Validate a safe output path **before any SolidWorks model is mutated**"——overwrite 检查发生在长建模调用之前；`ensure_sink_path` docstring 自知 TOCTOU（"Validation happens minutes before long modeling calls; the filesystem can change in between... re-checks the allowed root right before the sink"）——但复检项只有 allowed_root，**不含 overwrite**。窗口：validate 时目标不存在 → 建模数分钟 → 他方进程创建同名文件 → sink 复检通过（只查 root）→ SaveAs3 静默覆盖。
- 影响量化：触发频率=特定时序（验证后、写前并发创建同名文件——单用户 AI 工作流极低）× 最坏后果=刚出现的同名文件被无确认覆盖。
- 根因：TOCTOU narrowing 的复检清单不完整（root 进了、overwrite 没进）。
- 修复方案：ensure_sink_path 增可选 `overwrite_confirm` 参数，sink 时点复跑 `check_overwrite_confirm`（~5 行）；与 F07-1 同属 security 层收口，移交 06 域统一处置。
- 维度/契约标签：D3 / C-3（双门的第二门时点性）
- 移交：S/06（Nora）——若 11 攻击向量清单未含此 TOCTOU 时序向量则补。

### F07-6 STL/STEP 导出参数面缺口——SW 系统默认导出选项不可控且未披露
- 级别：⚪ —— §10 判据①（能力缺口/改进方向）
- 位置：`solidworks_mcp/solidworks_api/file_io.py:258`（`model.SaveAs3(sink_path, 0, swSaveAsOptions_Silent)`——三参形态，无 ExportData）
- 证据：SaveAs3 的第 4 参数 ExportData（STL 导出选项：二进制/ASCII、偏差、角度；STEP 版本 AP203/214/242）从不传入——导出格式细节完全由 SW 系统选项（Tools > Options > Export）决定，MCP 层不可控也不回读。registry 签名（registry/file_io.py:53-74）无任何格式参数；docstring 未披露「使用系统默认导出选项」。对 3D 打印工作流，STL 分辨率默认值可能导致曲面细分失真而 AI 无从知晓/修正。e2e_sw_smoke.py:177-178 实机链验证导出成功但不验证导出参数语义。
- 影响量化：每次导出参数面受限（非错误）× 后果=格式质量不可控、跨机器行为随 SW 选项漂移（信息级）。
- 修复方案：短期 docstring 披露默认行为；中期暴露 `stl_binary/stl_deviation/step_version` 参数并构造 ExportData（`swApp.GetExportFileData`）传入 SaveAs3 第 4 参。
- 维度/契约标签：D8 / C-7

### F07-7 ring_light 衍生产物写入未使用 ensure_sink_path 返回值（TOCTOU 收窄契约字面违背）
- 级别：⚪ —— §10 判据④（观察项，实际暴露面≈0）
- 位置：`solidworks_mcp/examples/ring_light.py:691-698`
- 证据：`for derived in (stl_path, metadata_path): ... ok, message, derived = ensure_sink_path(derived)`——返回的 normalized 值赋给循环变量 `derived` 后**未使用**，:698-699 写入用的是外层 `stl_path`/`metadata_path`。ensure_sink_path docstring 规定 "``normalized`` is the path the caller must hand to SolidWorks"——caller 未用。缓解：stl_path/metadata_path 本身由 `normalize_path(save_path)` 派生（:688-690），且两次 normalize 间只有纯计算（无长窗口），双 resolve 漂移实际不可达；但 SW 侧 SaveAs3（:626）用的是返回值、Python 侧写入不用——同函数内两种口径。ring_light_v3 无此问题（:524-527 用了 sink_layout）。
- 影响量化：理论时序窗口 × 落点漂移（实际≈0）。
- 修复方案：写入改用循环内 derived 收集的 normalized 值（2 行重构）。
- 维度/契约标签：D3 / C-2（形式合规）

### F07-8 normalize_path 相对路径 CWD 锚定——CWD 污染族攻击面闭合、语义漂移残留
- 级别：⚪ —— §10 判据④（上轮对照项的残留面）
- 位置：`solidworks_mcp/utils/security.py:53-54`（`if not os.path.isabs(expanded): expanded = os.getcwd() + os.sep + expanded`）
- 证据：历史坑形态（相对路径 save 副作用文件落 CWD——J3 外审族/上轮 coderabbit 旧发现）的当前防线完整：所有 export 链 `validate_output_file → normalize_path（相对→CWD 绝对化）→ is_path_allowed（root 比对）→ ensure_sink_path（sink 时点复检）`，SaveAs3 收到的是绝对规范路径（test_hardening.py:121 `assert_called_once_with(normalize_path("part.sldprt"), 0, 1)` 锁定）。攻击面闭合：CWD 在 root 外时相对路径被拒（安全兜底在位）。残留：相对路径的**语义**随宿主 CWD 漂移（.mcp.json 启动目录决定）——stdio 宿主以非项目根 CWD 启动时，`"out.step"` 落点跟随漂移（root 内语义漂移，非越界）；无固定锚（如强制锚到 DEFAULT_ALLOWED_ROOT）。
- 影响量化：特定环境（宿主 CWD≠项目根）× 落点目录漂移（root 内，信息级）。
- 修复方案（可选）：相对路径锚定 DEFAULT_ALLOWED_ROOT 而非 getcwd（~2 行，语义确定性）；或文档披露。
- 维度/契约标签：D3 / C-2

---

## 上轮对照表

| 继承项 | 状态码 | 本轮重证证据（一行） |
|---|---|---|
| **AR-9**（requirements.txt vs pyproject 双源无护栏） | **◐**（现状一致、护栏缺失未修） | E-5 亲验：requirements.txt 3 行 `pywin32>=306` / `mcp[cli]>=1.28.1,<1.29.0` / `pydantic>=2.12.0,<3.0.0` 与 pyproject.toml:11-15 dependencies **逐字一致**（与 Nora/06 结论互证）；护栏缺失本体：无任何测试/CI 锁定双源一致，README:30 仍引导 `pip install -r requirements.txt` 路线（非 editable 安装，行为与 CI 的 `pip install -e ".[dev]"` 有安装形态差异）。修复建议两选一：test_infrastructure 加双源一致性断言（读两文件比对，~10 行）；或删 requirements.txt 收敛单源（README 改引 pyproject，需查外部消费方）。 |
| **CWD 污染族**（上轮 coderabbit 旧发现：导出产物落 CWD） | **✅**（攻击面闭合） | normalize 收口三重链（validate_output_file→root 比对→ensure_sink_path 复检）+ SaveAs3 sink 实证（17 处全传 normalized，Nora 互证 + 本轮 file_io 3 处亲验 :255-258/:288-291/:326-329）；test_hardening.py:110-154 双测试锁定。残留语义漂移 → F07-8（⚪）。 |
| **S06-1**（close 默认 save_changes=False 丢弃未保存编辑） | 交叉引用 ➕ 扩展 | Nora 已立项本体；本轮从导出/生命周期侧扩展两个变体：用户 GUI 人工编辑被丢弃 + Save3 落点 root 外写（F07-1）；并补保存通道闭环缺口证据（registry 无独立 save 工具，`grep "def solidworks_.*save" registry/` 零命中）——F07-4。 |
| **四格式错误路径 fail-honest**（rubric §5 F 域任务） | **◐**（三档不对称） | DXF ✅（SECTION header 验证 :333-345 + 探针注释）、drawing PDF/PNG ✅（getsize drawing.py:933-937）、STEP/STL ◐（仅返回码）→ F07-3。import_step 错误路径 ✅（ext 拒绝 :207-208 / LoadFile4 tuple 解析 :213-221 / model None 拒绝，实机 T1 证据链在 docstring + e2e_sw_smoke.py:202 覆盖）。 |
| **G1**（交付 P0） | 不归本域 | 地图 §8 已定谳（主仓闭环/aicad 余 4），无文件 IO 侧增量。 |

---

## 移交项与交主会话复核清单

**移交其他域**：
1. **→ S/06（Nora）**：F07-1（Save3 落点盲区 = allowed_root 第三形态「文档状态路径」——若 11 攻击向量清单未含此形态请补录）；F07-5（overwrite TOCTOU 时序向量）；F07-2 的理论假成功分支（bool(tuple) 恒真——wrapper 接受 VARIANT 而非强转的版本形态，未实证）。
2. **→ D/05（Eric）**：F07-4 的 drawing.py:33 docstring 侧修复（提示补 save_changes 语义，1 行）——你域文件我未改动，按你的编号规则立项。
3. **→ T/09**：test_file_io.py 的 overwrite 门测试空缺（本域测试全部 patch 掉 validate_output_file，overwrite 语义仅在 test_hardening ring_light 侧有覆盖——file_io 域自身的 C-3 门测试薄弱）；AR-9 修复建议的测试化落点。

**需实机/需用户裁决**：
- F07-2 的 typed-wrapper 环境实测（gen_py 缓存在场时跑 `file_close(save_changes=True)`——实机验证 TypeError vs tuple 两分支哪条真实，影响是否叠加假成功风险）。
- F07-1 定级裁决（团长）：🟠 vs 🔴——判据③「用户文件不可逆丢失」在「用户 GUI 双活编辑 + AI 同时操作」场景字面坐实，但该场景在 AI 独占 SW 的工作流假设下罕见。

**推荐进总报告 Top 发现**：F07-1（安全边界形态）、F07-2（唯一保存通道环境断裂）、F07-3（验证范式拉齐，一行修复 × 2）。

---

## 附录 A：落盘点完备性扫描记录（E-6 双词形）

**第一族（COM 保存形态）**：`grep -n "SaveAs3|SaveAs2|\.Save3\(|\.Save2\(|\.Save\(" solidworks_mcp/`
- SaveAs3 sink：17 处（design:118 / sheet_metal:114 / file_io:258,291,329 / assembly:115 / part:286,346,431,542,690,806,1104,1187 / ring_light_v3:508 / drawing:929 / ring_light:626）——与 Nora「17 处 100% 传 ensure_sink_path 产物」互证一致（本轮抽验 file_io 3 处 + drawing 1 处 + ring_light 2 处 + ring_light_v3 1 处的调用链均确认 ensure_sink_path 在位）。
- **非 SaveAs3 形态 2 处**（本轮新增核验）：`file_io.py:159` Save3（→ F07-1/F07-2：路径盲区+容错缺失）；`ring_light_v3.py:520` Save3（落点= :508 已校验 sink，间接锚定 ✓，容错缺失同 F07-2）。

**第二族（Python 原生写形态）**：`grep -n "open\(.*['\" ][wab]|write_bytes|write_text|os\.remove|os\.rename|shutil\.|DumpSave|SaveToFile|ExportTo" solidworks_mcp/`
- 3 处，全部在 examples（ring_light.py:433 ASCII STL 写 / :699 metadata JSON / ring_light_v3.py:527 layout JSON）——校验链核验：ring_light_v3:497+524（check_overwrite_confirm + ensure_sink_path 双门 ✓，写入用返回的 sink_layout ✓）；ring_light.py:691-697（双门 ✓，返回值未用 → F07-7 ⚪）。
- **结论**：无非 SaveAs3 写盘点漏网（两族正则交叉 + 逐处校验链亲验；`os.remove/rename/shutil/unlink/DumpSave/SaveToFile/ExportTo` 在生产代码零命中——ring_light.py:433 的 `open(stl_path,"w")` 是唯一 `ExportTo` 族外的裸 open，已核验上游双门）。

## 附录 B：域内契约快查

- 工具计数：registry/file_io.py `grep -c "mcp.tool("` = 6 = `grep -c "^def solidworks_"` = 6 ✓（open/close/import_step/export_step/export_stl/export_dxf）。
- C-1 run_com：6 工具全部经 `_call_connected` ✓（registry/file_io.py:31/39/50/59/71/83）；api 层无绕过。
- C-2 allowed_root：export×3（validate_output_file+ensure_sink_path 双重）✓ / open+import（validate_path must_exist）✓ / **close 的 Save3 ✗**（F07-1）。
- C-3 双门：export×3 = IDEMPOTENT_WRITE 注解 + overwrite_confirm 实门 ✓（注解档位讨论：覆盖既有文件时实际执行破坏性写入而 hint 层为 idempotent——overwrite_confirm 参数本身即显式确认语义，双门成立，hint 档位偏松记入 F07-4 关联观察，不单独立项）；close = DESTRUCTIVE 注解 ✓ + 无 discard 实门（S06-1 在案）。
- C-5 fail-honest：全域 error_response 构造、无吞异常谎报 ✓（DXF 的 warning-1 容忍有探针实证注释支撑，非弱化断言）。

（完）
