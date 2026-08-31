# 证据清单（evidence）— SolidWorksMCP 架构演进审查 2026-08-31

> 产出技能：architecture-visualization:evolution-planner。全部证据 2026-08-31 当日采集。
> 置信度：high = 当日命令直接验证；med = 文档+git 双源一致；low = 单源推断。

## 当前态节点

| ID | 节点/断言 | 证据 | 置信 |
|---|---|---|---|
| E-1 | 主仓测试基线 485 passed + 95 subtests（10.06s） | 当日实跑 `pytest tests/ -q` | high |
| E-2 | 默认注册 69 工具 | 当日 FastMCP 注册探针 `len(list_tools())==69` | high |
| E-3 | server.py 206 行门面 + registry/ 11 域模块 | `solidworks_mcp/server.py`（当日 Read）；目录列表 | high |
| E-4 | COM 执行件：单 STA + 超时默认启用 + 毒化路径 | `utils/com_executor.py` 存在；commit e1efbeb；ADR-0006.1 | high |
| E-5 | ADR 0001-0012 十二决策家族 | `docs/adr/`（0009/0010/0011/0012 + 2026-08-28-architecture-decisions.md 含 0001-0007） | high |
| E-6 | 四期进度 N18✓N19✓N20✓N21✓ / N22 BLOCKED / N23 待 | `output/optimization-plan-2026-08-31.md` §3 表 + git hash（76ac84b/a276005/00db3e7 + ai 25abb4c/afa700e） | high |
| E-7 | 主仓领先 origin/main 15 提交（origin=04bf21f T21 钣金） | 当日 `git fetch && git status -sb` → `[ahead 15]`；`git log origin/main -1` | high |
| E-8 | 主仓远端 = gitee.com/pengzixiao2025/AICAD.git；CI=ci.yml（GitHub Actions 语法） | 当日 `git remote -v`；`.github/workflows/ci.yml`（on: push branches:[main]）→ gitee 不跑 GH Actions，CI 休眠 | high |
| E-9 | aicad 子仓 69 提交、零远端、2 个 untracked 脚本 | 当日 `git -C aicad remote -v`（空）+ `rev-list --count`（69）+ status | high |
| E-10 | aicad 测试 631（1 perf 负载敏感红） | 四期计划 §2.8 引 2026-08-31 实测（本会话未重跑 aicad 套件） | med |
| E-11 | 源码零 TODO/FIXME；工作树干净 | 当日 grep=0；`git status` clean | high |
| E-12 | 代码热点 design.py 1011 / drawing.py 969 / assembly.py 898 行 | 当日 `wc -l`（全部 <1100 行，无治理红线） | high |

## 目标态/缺口节点

| ID | 缺口 | 证据 | 置信 |
|---|---|---|---|
| G-1 交付可靠 | 主仓未推送 + aicad 无远端 + 主仓 CI 休眠 | E-7/E-8/E-9；N22 条目（计划 §11） | high |
| G-2 perf 复验 | N23 待空闲机，禁放室断言 | 四期计划 §12 | high |
| G-3 质量观测 | 前端零测试 / H2 缓存报表无导出 / CodeRabbit 未 auth | 三期计划 H2、B 项；四期 J3；aicad 目录无前端测试目录（当日 ls 未见） | med |
| G-4 零件长尾 | loft/sweep/多实体/通用草图/参考几何/筋/圆顶 | 三期计划 C5「部分入 N9 方法论范围，其余远期」 | high |
| G-5 图纸长尾 | 爆炸图 / BOM 气泡引线 | 三期+四期「远期观察项」两处列举 | high |
| G-6 CSG v2 | 契约 v1 仅 4-op（box/cylinder/hole/cut_hole） | ADR-0012 决策 1「代价：v1 只覆盖 4 op」 | high |
| G-7 原生阵列 | 线性/环阵=数学重建非参数联动 | ADR-0011 决策 2 + ADR-0007 决策 3（探针留升级路径） | high |
| G-8 智能自治 | plan-then-execute/RAG/mate 求解器/多模型路由 | 三期 B7（>10 件装配 8192 token 瓶颈）+ 远期观察项 | high |

## 假设与验证缺口（诚实披露）

- aicad 套件未在本会话重跑（引用 2026-08-31 当日另一会话实测）——S2 实施前应重跑确认。
- 「gitee 不执行 GitHub Actions」为平台行为常识推断，未在 gitee 仓库设置页实测（D3 裁决时验证）。
- 远端仓库名 AICAD 与 aicad 子仓的关系（D7）未询问用户——仅提出问题，不预设结论。
