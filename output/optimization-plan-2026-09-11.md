# AI 驱动 3D 机械图全自动绘制——优化改进规划（第十一期：用户解锁冲刺波）

> **生成**：2026-09-11 结构化会话（蓝本：PM 回顾裁决——能力面收官，剩余杠杆全在用户侧；用户指令「今晚 12 点后开展实机三合一（挂机）」）
> **主题**：触发驱动冲刺——用户动作（SW 窗口/宏/批准/上游）→ AI 批量兑现；北极星 90% → 95% 冲线
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考（AGENTS.md 契约：自动任务读本文件=最新日期计划）
> **承接**：第十期 `output/optimization-plan-2026-09-10-3.md` N52-N54/N56 ✅+残留裁决 ✅（终态 45/50=90%）；**N55 等 U9 续挂**。测试基线继承（主仓 565+106/80 工具；aicad 741 not-perf）。

---

## 1. 事实基线（2026-09-11 立项取证）

| 事实 | 状态 | 意义 |
|---|---|---|
| 北极星 | **46/50=92%**（U10 后终态）；95% 差 2 任务（装配堆叠=plan 强档域） | N59 冲线 |
| 待清观察项 | ①N52 GTOL 实机 e2e（NewGtol 定谳）②N48/49 frozen COM 实机 ③N54 CSG SW roundtrip | N57 一晚清（互独立） |
| 装配堆叠败 | b7 系列+mate_shaft_stack+stepped_sleeve_pair=plan 强档域 | N59（等上游第二家） |
| two_step_bore_plate | 稳定 24504 超窗 2.1%（窗口边际） | **U10 批准即 +1（92%）** |
| 五族 BLOCKED | 宏=唯一解锁路径 | N58（等 U9） |
| github pending | aicad 061402c/53d8917+主仓 3d1d09a（网络窗口） | 窗口恢复即补推 |

## 2. 任务进度总览

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N57 | P0 | **实机三合一**（GTOL e2e / frozen COM / CSG SW roundtrip）——今晚 00:05 定时启动，SW 挂机窗口 | 主 | SW 窗口（用户挂机） | 1晚 | `[ ]` 已预置资产 | |
| N58 | P1 | G4 宏转录管线首跑（用户交 .swp 即开工该族；mirror 优先） | 主 | U9 | 1晚/族 | `[ ]` 条件 | |
| N59 | P0 | plan 强档路由对比评测 → 装配堆叠回收 → **95% 冲线** | ai | 上游第二家 provider | 1晚 | `[ ]` 条件 | |
| N60 | P2 | github pending 补推 + U8 后双仓 CI re-run 收口 | — | 网络窗口/U8 | 0.1晚 | `[ ]` 条件 | |

### 2.4 用户动作清单（顺承）

| ID | 动作 | 状态 |
|---|---|---|
| **U4** | coderabbit auth login | ⏳ |
| **U8** | Billing 失败发票清算（页无欠款仍拦则工单） | 🔴 |
| **U9** | 录 mirror 族宏（~30min）→ 一句话通知 | ⏳ 条件 |
| **U10（新增）** | 批准 two_step_bore_plate 体积窗口 [21000,24000]→[21000,24800] → +1 任务=92% | ✅ 2026-09-12 批准并执行：改窗+离线 50/50 维持+live 复跑 PASS——**终态 46/50=92%**（aicad e4c7b92）；报告 §8.5 补记 |

---

## 3. N57 实机三合一（P0，今晚执行详案）

**启动机制**：定时任务 fireAt 2026-09-12T00:05——自包含 prompt：检 SW 进程→按本节顺序执行→回填本表。
**红线**：探针随手 `CloseAllDocuments(True)`；全部文件在 allowed_root 下；探针先行（每批次先最小观测再全链）；每批独立定谳互不阻塞。

### 批次 A：GTOL 实机 e2e（N52 观察项）

- [ ] A1 **探针** `tools/probe_n52_gtol.py`（已预置）：建图纸→`NewGtol()` 返回值观测（**None=AutoBalloon 同族 BLOCKED 定谳**）→ SetFrameSymbols2(flatness)/SetFrameValues2/SetPosition → GetFrameCount 判据 → 清理。
- [ ] A2 A1 通过→MCP 工具链 e2e：connect→part_new+create_box→drawing_create_from_part→`drawing_insert_gtol`(flatness 0.05)→export_pdf；判据=GetFrameCount==1+PDF %PDF 头+体积正常。A1 BLOCKED→如实定谳（工具降级观察+数学替代评估，不硬凑）。

### 批次 B：frozen COM 实机（N48/N49 观察项）

- [ ] B1 **预置批（白天已完成）**：frozen 重建（N52 后代码→80 工具）+ smoke_frozen EXPECTED_TOOLS 79→80 同步（N52 遗漏联动补）+ smoke PASS。
- [ ] B2 实机：MCP stdio 起 frozen exe→`solidworks_connect`（真附着）→part_new→create_box→get_bounding_box（实机值 [60,40,10] 断言）→关闭。判据=frozen 下 COM 附着+gen_py typed 缓存首生成路径工作。

### 批次 C：CSG SW roundtrip（N54 观察项）

- [ ] C1 build123d 六角柱（R20 h10 理论 2598.08）→ `csg_plan_from_script`（离线已验 2.33e-16）→ 主仓 `rebuild_csg` SW 实机重建 → 体积互证（窗口 ±1%）→ 清理。判据=导出方向在 SW 实机闭环。

### 收尾

- [ ] 三项各自定谳（tools/INDEX 取证行+本表回填+必要时修复走 TDD）；全套回归；提交推送。

**验收**：3 观察项各有定谳（通过/如实 BLOCKED）；无静默失败；全套绿。
**反目标**：不为过 e2e 硬凑判据；SW 异常状态不强行续跑（如实报告暂停）。

## 4. N58 宏转录管线（条件 on U9，1晚/族）

- [ ] .swp 宏解析器（VBA 提取 API 调用序列→typelib 对照契约卡）→ 探针复现 → TDD → 工具+计数锁+示例卡+BLOCKED 撤销。无宏不猜。

## 5. N59 路由对比+95% 冲线（条件 on 上游第二家）

- [ ] routing-guide §4 命令取数（plan 强档 vs 全快档）→ b7/mate/stepped 装配堆叠复跑 → 50 任务终态 ≥95% → vision 北极星结项回填。

## 6. N60 补推+CI 收口（条件）

- [ ] 网络窗口恢复→双仓补推（aicad 2+主仓 1+本期新增）；U8 后 re-run 最新 run。

---

## 7. 风险与未决

- **N57 批次 A 的 NewGtol 可能静默 None**（AutoBalloon 同族）——A1 探针首跑即定谳，BLOCKED 不阻塞 B/C。
- **SW 挂机窗口内许可弹窗/睡眠**——执行前检查进程+首调用连通性；异常即停如实报告。
- **frozen 80 工具重建**若失败（依赖面变化）→ 白天预置批即发现即修，不带病过夜。
- U10 未批不影响 N57-N59；批准即 +1（92%）。
