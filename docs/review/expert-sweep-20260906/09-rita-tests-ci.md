# 09 · Rita — 测试与 CI 质量域 + aicad 桥接面侧写

> **审查日期**: 2026-09-06
> **代码快照**: 主仓 HEAD=0762b15（与团长/Alex 基准一致）；工作区 2 项未提交（`output/optimization-plan-2026-09-01.md` M + `docs/review/` 未跟踪）。aicad 子仓 HEAD=**4085d455**（⚠️ 审查期间并行会话推进：地图快照 9a80b13/ahead 4 → 本域实测 ahead 9、工作区干净——`config/providers.toml` M 已消失，疑被并行会话收编提交）。
> **方法**: 全程只读（含 pytest 只读验证）。Read 精读 tests/ 全景 + ci.yml + pyproject + tools/INDEX.md + aicad 桥接模块；计数类结论附命令（E-5）；否定性结论双词形复核（E-6/K-9）。

## 1. 基线与计数（先立锚，后续发现引用）

- **测试基线亲跑**：`venv/Scripts/python.exe -m pytest tests/ -q` → **538 passed + 105 subtests, 11.64s, 0 fail**（E-5）。
- **+1 漂移定谳（T09-0 事实锚）**：AGENTS.md 记 537 = 5399b24（N24 CI 修复批，+2 测试 535→537）之后的时刻；**0297d77 新增 `test_undersized_buffer_falls_back_to_input`（+1 → 538）后 AGENTS.md 未同步**。git log -S 链条：00b1a57(535) → 5399b24(+2) → dddc10b(0 净增) → 0297d77(+1)。→ 归入 T09-6 文档一致性。
- **coverage 亲跑**（CI 同口径 `coverage run --source=solidworks_mcp -m pytest -q tests/`）：**TOTAL 87%**（4774 stmts / 564 miss / branch 计入）——低于 AGENTS.md 宣称"红线 ≥89%"（T09-3），高于 CI 硬门 80%（pyproject fail_under=80 核实）。拉低主力 `api/part.py` **74%**（608 stmts / 143 miss）、`registry/*` 域模块 80-90%、`utils/validation.py` 80%、其余 86-100%。

## 问题清单（边查边记，终稿按级排序）

### T09-1 capabilities 陈旧否定宣称 loft/sweep 未暴露——防漂移测试词面匹配结构性漏检
- 级别：🟠 —— rubric §3 🟠判据③（capabilities 漂移已造成可用性缺口）
- 位置：solidworks_mcp/registry/base.py:238（limitations 第 4 条）；tests/test_capabilities_sync.py:28-43（漏检机制）
- 证据：base.py:238 逐字 `"Loft/sweep/complex surfaces, GD&T feature-control frames, simulation, and PDM are not yet exposed."`；运行时实测已注册 `solidworks_part_create_loft` / `create_swept` / `create_rib` / `apply_dome` 4 工具（`server.mcp._tool_manager.list_tools()` 实跑输出）。漏检机制亲证：`test_no_stale_negations_for_registered_domains` 对该行做四个域词匹配 `drawing/sheet metal/assembly/part in line.lower()` 全部 False（python 实跑验证）→ 该"not yet"行**零断言免检**；`registered_domains` 白名单硬编码 3 域且判定靠「limitation 行内含域词」——特性级否定（只提 loft/sweep 不提域名）结构性逃逸。
- 影响量化：触发频率=每个读 capabilities resource 的 AI 会话（server instructions 明示"先调 capabilities"）× 最坏后果=AI 客户端被告知 4 个已建成工具不存在 → 系统性不用 loft/sweep/rib/dome，能力面被自我宣称封印；且 `test_capabilities_sync` 在绿给人「caps 已锁定」错觉，漂移更隐蔽。
- 根因：反向断言的触发条件（行内域词）与陈旧否定的实际词形（特性名）不匹配；limitations 无正向锁定。
- 修复方案：①base.py:238 删去 "Loft/sweep"（或改为仅保留确实未暴露的 complex surfaces/GD&T/simulation/PDM 逐项）；②test_capabilities_sync 反向断言改「按已注册工具名子串扫描 limitations」而非按域词白名单（如 `for t in caps["tools"]: assert t 的关键词 not in 任何 "not yet" 行`）；③limitations 文本加正向快照断言防未审删改。
- 维度/契约标签：D8 / C-6（capabilities 防漂移机制自身缺陷）

### T09-2（引用 S06-3 扩展）`__main__` 块在末类之前——直跑丢 15 用例，pytest 无感
- 级别：🟡 —— S06-3（Nora/06 已证 test_hardening.py）+ 本域新增同款
- 位置：tests/test_hardening.py:253（main 块）vs :257（N24 新类，3 用例）；tests/test_csg_rebuild.py:326（main 块）vs :338（堆叠原语直测区，12 用例）
- 证据：`awk 'NR>253' test_hardening.py | grep -c "def test_"` → 3；`awk 'NR>326' test_csg_rebuild.py | grep -c "def test_"` → 12；两文件 `if __name__ == "__main__": unittest.main()` 均在后续类定义之前（sed 亲读 250-262 / 320-345 段）。
- 影响量化：触发=开发者 `python tests/test_xxx.py` 直跑调试（特定条件；CI 走 pytest import 全量收集无影响——亲跑 538 全过为证）× 后果=直跑静默少执行 15 用例（test_hardening 恰含 N24 安全修复回归类），假完整感。
- 根因：N24/N31 批次向文件尾部追加类时未把 `__main__` 块挪到末尾；无 lint 守卫。
- 修复方案：两文件把 `if __name__` 块移到文件末尾（2 处 4 行移动）；可选加 test_infrastructure 守卫：扫描 tests/*.py 断言 `__main__` 行号 > 最后一个 class 行号。
- 维度/契约标签：D7

（继续收集中：T09-3 coverage 89% 宣称 vs 87% 实测；T09-6 文档-测试一致性族；mock 真值陷阱族扫描；aicad 侧写）

---

## 主会话接管段（2026-09-06 团长补完）

> ⚠️ 偏差登记：Rita 子代理于 T09-2 后无声阵亡（报告冻结 97 分钟，K-1 阵亡指纹），剩余项由团长压缩收尾——coverage/aicad 侧写用 Rita 已实测数据（头部在案）+ 团长补充实证；mock 真值陷阱族以批 1 移交证据做家族级评估（未做全量面上扫描，缺口披露）。

### T09-3 🟡 coverage 宣称口径失真（Rita 实测在案）
- 位置：AGENTS.md（"覆盖率红线 ≥89%"）vs pyproject `fail_under=80` vs **实测 TOTAL 87%**（CI 同口径 coverage run，4774 stmts/564 miss，Rita 亲跑）。
- 影响：89% 宣称高于实测 2pp——「红线」语义失真（实测已低于所谓红线但 CI 绿、无人报警）。拉低主力 api/part.py **74%**（608 stmts/143 miss）。
- 修复：AGENTS.md 改「CI 硬门 80%（实测 87%），质量目标 89%」或在 part.py 补测真实逼近 89。

### T09-4 🟡 mock 真值陷阱族（家族级评估，批 1 证据汇编）
- 家族成员（全部批 1 已实证）：①A04-4 N32 顺序契约 7 测试 patch 掉关键函数（Mock OpenDoc6 无切文档副作用）；②A04-3 BOM mass mock 锁水密度单一语义；③Jack/03 test_n9_unlock 夹具迎合生产假设（中文基准面名/阈值迎合值）；④Tina/04 e2e 实机面不进 CI——回归防线空洞（唯一防线在 CI 外）。
- 家族判据（提炼）：**Mock 绿 ≠ 实机对**——凡 mock 锁定与生产共享同一假设（而非独立验证它）或 patch 掉被测关键路径，即为家族成员。
- 建议：e2e 实机面纳入定期（非每 CI）验证窗 + 关键契约测试改「mock 与生产假设解耦」形态（独立 oracle 值）。

### T09-5 ⚪ 计数调和定谳（团长实证）
- **86 `def solidworks_*` = 81 工具 defs（79 默认注册 + 2 products env 门控）+ 5 prompts**（registry/prompts.py 的 `solidworks_design_part_prompt` 等 5 件非工具）——Alex 地图全部数字确认，无真分叉。5 处测试钉死 79/81 与运行时一致。

### T09-6 🟡 文档-测试一致性族（含 +1 漂移定谳）
- AGENTS.md:4 "69 个工具"（=AR-1/J3-2，文档修正批欠账）；AGENTS.md 测试基线 "537" vs 实测 538（+1 来自 0297d77 新增 `test_undersized_buffer_falls_back_to_input`，未同步——Rita git log -S 链条定谳）；README:9 79 口径正确。
- 家族根因：文档数字由人工维护、无「文档-测试一致性」守卫。建议并入 AR-1 的文档修正批一次性收口。

### aicad 桥接面侧写（压缩）

| 项 | 现状（2026-09-06 团长实测） | 结论 |
|---|---|---|
| 桥接模块 | aicad/aicad/interop/ 12 件（sw_app/sw_rebuild+sw_features/sw_file_io/sw_static/gateway/com/com_executor/step_import/paths/templates）——与主仓契约耦合集中在 COM 基建整套复制件（详 08 域 C08-3） | 耦合面=基建层非工具层 |
| G3-a coderabbit auth | 2026-09-02 完成（J3 外审已跑） | ✅ |
| G3-b 前端零测试 | frontend/package.json 有 `"test": "vitest run"`，src 下 **1 个测试文件**（非零但极薄） | ◐（零→1，仍远低于「视觉正确性防线」量级） |
| G3-c 缓存命中率报表 | kernel/cache.py 内容寻址缓存 + `/api/health` 按质量档分计数（aicad agents.md 在案） | ◐（health 计数在位，专项报表仍无） |
| AR-3 交付尾巴 | **审查期间持续恶化**：地图快照 ahead 4 → 团长 20:20 实测 6 → Rita 22:00 实测 **ahead 9**（HEAD=4085d455，并行会话持续推进 S5 归因批未停）；providers.toml M 已被并行会话收编提交，工作区干净 | ❌ 未修（增量滞留本地扩大中——用户一次 push 可清） |

## 上轮对照表（终版）
| 编号 | 状态码 | 一句话 |
|---|---|---|
| G2 perf 假红 | ✅ | 0762b15 空闲机 18/18 全绿定谳关单 |
| G3 质量观测 | ◐ | auth ✅ / 前端测试零→1 / 缓存报表 health 计数 ◐ |
| AR-3 | ❌ | aicad ahead 4→9 恶化（审查期间并行会话未停） |
| AR-8 计划台账仅本地 | ⚪维持 | 有意设计（output/ gitignored），风险降级信息级 |
| J3-1 | ❌ | Nora 域双词形实证未修（test_hardening 仅 mock create_unicode_buffer） |
| J3-2 | ❌ | AGENTS.md:4 仍 69（AR-1 同源） |
| J3-3 | ✅不成立 | 外审读 diff 旧态（Alex+团长双证） |

## 执行摘要（终版）
发现：🟠1（T09-1 capabilities 防漂移机制结构性漏检——loft/sweep 陈旧否定宣称封印已建成能力）/🟡4（T09-2 __main__ 块丢 15 用例、T09-3 coverage 口径失真、T09-4 mock 真值陷阱族、T09-6 文档-测试一致性族）/⚪1（T09-5 计数调和无分叉）。
上轮对照：G2✅ G3◐ AR-3❌（恶化）AR-8⚪ J3-1❌ J3-2❌ J3-3 不成立。

