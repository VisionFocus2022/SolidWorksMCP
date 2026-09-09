# AI 驱动 3D 机械图全自动绘制——优化改进规划（第七期：自治收口 + 终态门面）

> **生成**：2026-09-09 结构化会话（蓝本：`docs/product-vision.md` §5 路线图；用户裁决 D1=第七期 4 个 P0 全包）
> **主题**：北极星直达路径——交付合格率 84.2%→95% 起点、评测集扩容、**批量队列+交付包打包（终态门面）**
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考（AGENTS.md 契约：自动任务读本文件=最新日期计划）
> **承接**：第六期 `output/optimization-plan-2026-09-07.md` N35-N41 **全部 ✅**（余 U4 CodeRabbit auth=用户动作，见 §1.4）。执行协议/安全红线/测试命令基线**继承第五期 §2 与第六期收官口径**（主仓 557+105；aicad 737 全集/CI 口径 not perf）。
> **产品上下文**：`docs/product-vision.md`（六层终态模型+G1-G10 差距矩阵）；本期覆盖 G1/G2/G3 与 G7 的守门前置。

---

## 1. 事实基线（2026-09-09 立项取证）

| 事实 | 状态 | 对本期任务的意义 |
|---|---|---|
| S5 一期 live 评测 | 19 任务：before 57.9% → after 84.2%（零回归）；**翻绿主体=provider 换道（GLM→DeepSeek），S5 真实贡献未剥离** | N42 存在的意义 |
| 归因批 T1-T4 | ✅ 收官：eval 复跑死亡定谳 **OpenBLAS 内存分配失败**（全量连跑压力，非代码 bug）；修复=stdout_tail 透传+验证段单次重试+空闲机纪律 | N42 只剩「复测+报告」，非修复 |
| PTE 多实体小批 | ✅ 已先行落地（`c870368`）：顶层 `solid:single|multi`；**mate_shaft_stack live PASS=PTE plan 路径首次完整兑现** | N43 裁决时核销；B7 观察项已备 |
| aicad API 面 | 会话制（chat/versions/export fmt=step|stl|obj|dxf/assembly/drawing/sw/artifacts）；**无批量端点**；artifacts.py 已有产物管理 | N44 从零建 batch 路由，复用会话原语 |
| 主仓 | 79 工具 / 557+105 / 双 CI 全绿 / 产品终态文档已立 | 本期主仓零改动（除文档） |

## 2. 任务进度总览

状态：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED。「仓」列：主=主仓库，ai=aicad。

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N42 | P0 | 空闲机全量复测 + T5 GLM 同 provider 复测 → S5 真实贡献终版报告 | ai | 空闲机；T5 条件=GLM key（U7） | 1h | `[ ]` | |
| N43 | P0 | S5 v2 裁决（依 N42 数据定范围：script 件 STEP 拼装 / embedding / solver 扩原语 / PTE-B7 观察） | ai | N42 | 1h | `[ ]` | |
| N44 | P0 | 批量队列 API + 交付包打包（终态门面 G3） | ai | 无 | 5h/2晚 | `[ ]` | |
| N45 | P0 | 评测集 19→30+（第一波，G2） | ai | 无 | 3h/1晚 | `[ ]` | |

> 执行顺序建议：N44 与 N45 无外部依赖可先行（N44 大，建议先做核心队列 API 晚 1、打包+前端晚 2；N45 可穿插）→ N42 等空闲机窗口（同 perf 预算纪律：全量连跑需空闲机）→ N43 收口。
> 远期观察项（继承）：宏录制器解锁五族（G4，第八期+用户配合）、GD&T（G5）、CSG v3（G6）、路由策略（G8）、安装包（G9，第九期）、多机（G10）。

### 1.4 用户动作清单

| ID | 动作 | 状态 |
|---|---|---|
| **U4（承接五期）** | `coderabbit auth login`（本人浏览器 OAuth 或 API key） | ⏳ |
| **U7（新增）** | GLM key 恢复后一句话通知（T5/N42 同 provider 复测触发条件；不恢复则 N42 用 DeepSeek 单 provider 复测+报告注明口径受限） | ⏳ 条件 |

---

## 3. N42 空闲机复测 + S5 真实贡献终版报告（P0，aicad，1h）

**目标**：G1 第一步——在干净环境重取全量数字，剥离 provider 变量，给出「S5 特性净贡献」的可信结论（v2 裁决 N43 的数据前置）。

- [ ] 1. **空闲机全量复测**（条件：SW 关+CPU<20%，同 N26 纪律）：`python evals/run_evals.py --live --provider deepseek --baseline evals/output/report-20260902-203236-s5-after-deepseek.json`——验证 84.2% 在非内存压力环境可复现（归因批 T4 的 14/19 判环境性红，本步定谳）。
- [ ] 2. **T5 GLM 同 provider 复测**（条件：U7；不恢复则跳过并在报告注明）：`--provider glm --baseline evals/output/report-20260902-163045-s5-before-baseline.json`——同 provider 前后对比=剥离换道效应的 S5 净贡献。
- [ ] 3. **终版报告** `docs/s5-net-contribution-report.md`：三口径并列（before-GLM / after-DeepSeek / 复测口径），归因分层（provider 效应 / S5 特性 / 环境），残留失败逐件定性；product-vision G1 的 95% 差距分解（哪 pp 来自基建/哪 pp 来自能力）。
- [ ] 4. 回填本表 + aicad `agents.md` 基线（若评测结论影响文档口径）。

**验收**：复测报告落盘；84.2% 复现性有定谳（可复现/环境敏感两说其一，附证据）；S5 净贡献数字或明确「口径受限无法剥离」的诚实结论。

## 4. N43 S5 v2 裁决（P0，aicad，1h，依赖 N42）

**目标**：守门条款兑现（一期 PRD §4：归因数据齐前 v2 不立项）——用 N42 数据裁决 v2 范围并出 PRD-lite。

- [ ] 1. 核销 PTE 多实体先行批（`c870368`）：B7 两任务在复测中的 mode 分布（plan 接管率）——若 plan 路径稳定接管且过，PTE 主线收口；若仍诚实回退，登记件型表达力缺口。
- [ ] 2. **裁决矩阵**（依 N42 数据四选 N）：① script 件 STEP 拼装（六角螺栓/垫圈超 v1 件型——B7 回退主因）② embedding 检索替换 n-gram（RAG 升级）③ mate solver 扩原语 ④ PTE-B7 观察续跑。每项附「N42 数据依据 + 预期 pp 提升」。
- [ ] 3. 产出 `aicad/docs/prd-s5-v2.md`（PRD-lite：范围=数据驱动裁定的 1-2 项；反目标=不为一指标堆四项）。
- [ ] 4. 回填本表；v2 实施任务**不进本期**（第八期蓝本）。

**验收**：裁决有数据依据（引用 N42 报告条目）；PRD-lite 落盘；守门条款闭环留痕。

## 5. N44 批量队列 + 交付包打包（P0，aicad，5h/2晚）

**目标**：product-vision G3「终态门面」——从「单任务对话」到「需求表进、交付包出」。v1 范围=API 完整+前端最小面（列表页）；并发=1（串行逐任务，诚实记录每任务状态）。

**架构**（复用会话原语，不另起炉灶）：

```
POST /api/batch                {"requests": [ {"prompt": "...", "title": "..."}, ... ], "max_rounds": 3}
  → {batch_id, total, accepted}   # 每请求=一个新 session（复用 CorrectionLoop 全链）
GET  /api/batch/{id}           → {status: running|done, items: [{title, session_id, status,
                                 pass|fail|error, report_path, package_path}]}
GET  /api/batch/{id}/package   → application/zip（全部交付包聚合）
```

**交付包 zip 结构**（每任务一目录；`report.json` 是产品原则 3「诚实失败」的载体）：

```
batch-{id}/
  {idx}-{title}/
    model.step            # build123d 引擎产物（必有；SW 原生 .sldprt 若经 /api/sw 通道可达则附，不可达在 report 注明）
    drawing.pdf / .dxf    # 图纸（任务产出图纸时）
    bom.csv               # BOM（装配任务）
    report.json           # {ok, mode(plan|loop), rounds, metrics(volume_mm3/bbox/entities/hole_count),
                          #  assertions[pass|fail+diff], cost_tokens, provider}
```

- [ ] 1. **TDD**：`tests/test_batch.py`——batch 创建/状态流转（fake sandbox）/失败任务不阻断后续/zip 结构与 report.json 键齐全/空请求 400。
- [ ] 2. **实现**：`api/routes_batch.py`（queue 存内存 dict+串行 worker 线程，v1 不落盘不持久——重启丢队列如实声明）；复用 chat_service 的执行路径与 artifacts 的产物收集；聚合 zip 用标准库 zipfile。
- [ ] 3. **前端最小面**：`frontend/src/pages/Batch.tsx`——提交表单（多行需求）+ 状态表（逐任务 pass/fail/链接）+ 聚合包下载按钮；`npm test` 补 2 冒烟用例。
- [ ] 4. aicad 全套绿（+新测）；CI 双 job 绿。
- [ ] 5. commit + 回填本表。

**验收**：curl 提交 3 请求（含 1 个必失败任务）→ 全部出终态（失败者 report.json 含断言 diff）→ 聚合 zip 下载且结构符合；前端可见状态与下载；全套绿。
**反目标**：v1 不做并发>1（COM/沙箱串行纪律）、不做持久化队列/断点续跑（v2 观察项）、不做 SW .sldprt 强制（可达性如实）。

## 6. N45 评测集扩容 19→30+（P0，aicad，3h/1晚）

**目标**：G2 第一波——「同一把尺子」加宽，覆盖 product-vision 标注的能力面缺口。每任务=mock 脚本+机械断言（离线可验），live 可跑。

新增 ≥11 个任务的靶向分配：

| 域 | 任务（示例） | 断言要点 |
|---|---|---|
| BLOCKED 域数学替代 | `mirror_bracket`（镜像特征→数学对称件）、`ribbed_box`（筋板加强件） | 对称性（bbox 中点）、筋条数/体积窗口 |
| 装配 10+ 件 | `b7_pump_base`（底板+4 螺栓+泵体+联轴器，10 件）、`grid_gussets`（12 件阵） | entities、bbox、间隙断言 |
| 编辑型 | `edit_fillet_chain`（建件→圆角链编辑）、`edit_bore_resize` | 特征数、体积窗口、hole_count |
| 材料/参数化 | `material_steel_flange`（材料+质量断言）、`equation_driven_plate`（方程式联动厚宽） | mass>0 且窗口、尺寸联动比 |
| 图纸 | `drawing_export_bundle`（建件→出图→PDF+DXF 双格式） | 文件存在+PDF 字节头+DXF SECTION 头 |
| 阶梯/复合 | `stepped_shaft`（三段轴）、`complex_gear_plate` | 段径/体积窗口 |

- [ ] 1. 写任务 JSONL + mock 脚本 + 断言（断言全部机械可验——数值窗口/计数/文件存在性）。
- [ ] 2. 离线全套：旧 19 零回归 + 新增全绿（mock 层）。
- [ ] 3. 抽 3 个新任务 live 冒烟（DeepSeek，费用敏感：只抽验不全量）。
- [ ] 4. commit + 回填本表；`docs/s5-autonomy-phase1-report.md` 头部加「评测集已扩容至 N 任务」指针。

**验收**：离线 30+ 任务全绿；旧任务零改零回归；live 抽验 3 个 ≥2 过（新任务首跑允许暴露问题——这正是扩容目的，如实记录）。

---

## 7. 风险与未决（诚实披露）

- **N42 空闲机窗口**：与 N26 同纪律，窗口不可预约——计划顺序上 N44/N45 先行不空等。
- **GLM key 不恢复**：T5 跳过，S5 净贡献以「口径受限」诚实结论替代（不编造剥离数字）。
- **N44 内存队列 v1 的重启丢失**：如实声明+前端提示；持久化为 v2 观察项，不为 v1 加存储依赖。
- **N45 新任务的 live 首跑失败率可能拉低总体数字**：扩容报告须分列「旧 19 vs 新增」两组口径，避免与 84.2% 直接比较产生误读。
- 本期主仓零代码改动（文档除外）——79 工具/计数锁/覆盖率红线全部冻结，风险面集中在 aicad。
