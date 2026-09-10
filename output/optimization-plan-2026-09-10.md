# AI 驱动 3D 机械图全自动绘制——优化改进规划（第八期：S5 v2 自治韧性）

> **生成**：2026-09-10 结构化会话（蓝本：`aicad/docs/prd-s5-v2.md`——N43 数据裁决产物；用户指令「继续处理挂起项」当日提前实施）
> **主题**：把 N42 定谳的两个伪影源修掉——「数字只反映能力，不反映基建」
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考（AGENTS.md 契约：自动任务读本文件=最新日期计划）
> **承接**：第七期 `output/optimization-plan-2026-09-09.md` N42-N45 **全部 ✅**（N42 复测：84.2% 精确复现+规划伪影定谳 6 任务/-20pp）。执行协议/安全红线/测试命令基线**继承第五期 §2 与第七期收官口径**（主仓 557+105；aicad 728 not-perf+18 deselected，2026-09-10 N46 后）。

---

## 1. 任务进度总览

状态：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED。「仓」列：主=主仓库，ai=aicad。

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N46 | P0 | S5 v2 实施：V2-1 planner LlmError 回退（TDD）+ V2-2 max_output_tokens 8192→16384 | ai | 无 | 0.5天 | `[x]` 2026-09-10（+2 回退用例 9/9 绿；验收 6/6 伪影任务复跑**全 PASS 且全 mode=loop 首轮 5/6**） | 2026-09-10 |
| N47 | P0 | v2 后全量 30 任务 live 连跑 → 终验报告 + product-vision G1 差距矩阵回填 | ai | N46 | 1h | `[x]` 2026-09-10（**27/30=90% 单次干净连跑**，first_pass 25/30，+11 vs N42 主跑；**PTE plan 首次批量兑现 4/5**；过程中挖出并修复 **harness warm-worker 进程泄漏**（N42「瞬态 OpenBLAS」真凶）+4 测；G1/product-vision 已回填） | 2026-09-10 |

> 远期观察项（继承第七期）：宏录制器解锁五族（G4，需用户 ~30min/族）、GD&T（G5）、CSG v3（G6）、路由策略（G8）、安装包（G9）、多机（G10）；S5 v2 观察项（prd-s5-v2 §3）：B7 件型表达力（planner 修复后复验）、GLM 通道补 T5、规划轮路由非 flash 档。

### 1.4 用户动作清单（顺承第七期）

| ID | 动作 | 状态 |
|---|---|---|
| **U4（顺承五期）** | `coderabbit auth login`（本人浏览器 OAuth 或 API key） | ⏳ |
| **U8（顺承七期，09-10 复核）** | GitHub Billing 修复——计费挡板已确认拦停**双仓全部 6 个 run**（主仓 91109c2/ed43d77/ca639e6、aicad 040d1f5/7e41553/19626c4，annotation 一字不差）。修复后 re-run 最新 run 即可收口（主仓 ca639e6/aicad 本期推送各一；历史 docs-only commit 的旧 run 可不补）。**09-10 用户报「Billing 已修」后三次 re-run（12 分钟跨度）均被同签即拦**（API 受理 201 但 job 不启动，steps=0）——修复未生效，需查：①VisionFocus2022 账户（非个人账户）Billing & plans 的失败发票是否已清算；②**Spending limits → Actions and Packages 是否 >0**（annotation 双条件：支付失败**或** spending limit 过低）；③支付生效延迟 | 🔴 |

---

## 2. N46 S5 v2 实施（P0，aicad，已完成 2026-09-10）

- [x] 1. **TDD**：`tests/test_plan_executor.py` +2 用例——`test_plan_provider_llm_error_falls_back`（复现 N42 空补全 LlmError 形态→断言回退纯 loop+`plan_fallback` history 含 LlmError）、`test_plan_round_unexpected_error_falls_back`（monkeypatch `build_assembly_script` 崩溃→同构回退）。RED→GREEN 9/9。
- [x] 2. **实现**：`aicad/ai/planner.py` 规划轮 except 增补通用回退分支（`plan round crashed: {类型}: {信息}`，与格式回退同构；PlanFormatError 分支保留原消息）。
- [x] 3. **V2-2 配置**：`config/default.toml` `max_output_tokens` 8192→16384（依据：hex_nut_plate 实证 + v4 推理挤占正文）。
- [x] 4. **验收（超预期）**：N42 的 6 个伪影任务逐个 live 复跑（flash 档，默认预算）——**6/6 PASS**（PRD 验收线=100% 产终态；实际全部通过且 5/6 首轮）。**mode 全部=loop**：plan 路径 flash 档仍 0 兑现（推理失控未变），但死亡已转化为通过。逐任务报告 report-20260910-06{3040,3441,3743,4307,4624,4919}.json。
- [x] 5. 全套 **728 not-perf + 18 deselected**（+2 零回归）；AGENTS.md 基线 746 同 commit（N36 纪律）。

## 3. N47 v2 终验全量复测（P0，aicad，已完成 2026-09-10）

- [x] 1. 全量 30 任务 live 连跑（空闲机；`--provider local-relay --model deepseek-v4-flash`；baseline=N42 主跑）：**27/30 = 90%**，单次连跑 7 分钟（fixes=12、regressions=1：two_step_bore_plate 体积超窗口上界 2.1%）；live_stats：first_pass 25/30、avg_rounds 1.17；**mode 分布 loop 25 / plan 5（PTE plan 首次批量兑现 4/5：assembly_two_plates/mate_shaft_stack/b7_pump_base/grid_gussets 过，b7_frame_stack 尺寸解释失配）**；报告 `evals/output/report-20260910-084116.json`。
- [x] 2. 终验报告：`aicad/docs/s5-net-contribution-report.md` §7（v2 前后对比 + 残留 3 败定性（全 assert_mismatch：two_step_bore_plate 边际窗口 / b7_flange_bolts+b7_frame_stack 装配解释差异）+ **§7.1 根因修订**：N42「瞬态环境性 OpenBLAS」实为 harness warm-worker 泄漏的内存挤压，已诚实更正）。
- [x] 3. product-vision G1 差距矩阵回填：G1 现状 84.2%→**90%**（北极星距 95%≈1.5 任务）；first_pass 护栏 25/30；头部数据基线同步。
- [x] 4. 回填本表 + prd-s5-v2.md 执行记录。

**验收**：全量连跑报告落盘 ✅；伪影类失败归零（3 败全 assert_mismatch）✅；G1 矩阵回填留痕 ✅。
**计划外重大交付（N47 执行中发现）——harness warm-worker 进程泄漏三连修**：
- 现象：连跑中 python 进程爬到 90+（~19GB），任务挤压停滞；N42 的 6 个「瞬态」死亡同源。
- 根因三层：① 评测每任务新建 `Sandbox` 实例、warm worker 无人回收；② `WorkerPool._spawn_async` 的 straggler（close 后完成构建的 worker）照旧入队泄漏；③ **live 路径每任务的 `CorrectionLoop` 懒建自带池的 Sandbox**（无 run_script 注入时）——最大单源。
- 修复（TDD，+4 测试）：`run_task` 冷路（worker_count=0）+ finally `Sandbox.close()`；池 straggler 收割；`_eval_run_script()` 包装注入 loop（含 workdir=None 兜底——首版漏兜底致 0/30 全零，被连跑当场抓住后以测试钉死契约）。
- 验证：修复后连跑全程 python 进程数恒定（≈4+评测自身），30 任务 7 分钟（修复前同配置 25-30 分钟且中途停滞）。全套 **732 not-perf + 18 deselected** 绿；AGENTS 基线 750 同 commit。

---

## 4. 风险与未决（诚实披露）

- ~~全量连跑的瞬态 OpenBLAS 死亡~~ **已定谳并修复（N47）**：真凶=harness warm-worker 进程泄漏的内存挤压（非环境性）——三连修后连跑进程数恒定，终验 27/30 单次干净跑过。N42 报告已作根因修订（§7.1）。
- **flash 档 plan 兑现已从 0/3 升至 4/5**（伪影修复后 PTE 主线收口条件实质达成）；plan 失败件=b7_frame_stack 尺寸解释差异，属能力项。
- **U8 未解**：本期 aicad 推送的 CI 验证继续挂起（同挡板）；本地全套绿是收口基础。
- 残留 3 败（two_step_bore_plate 窗口边际 2.1% / b7_flange_bolts+b7_frame_stack 装配解释差异）全是能力/解释项——**反目标维持：不为凑 95% 改断言/措辞**；下一阶观察：体积窗口是否过紧（two_step_bore_plate）、装配断言的解释容差。
