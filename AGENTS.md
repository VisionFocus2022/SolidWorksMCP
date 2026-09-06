# AGENTS.md — SolidWorksMCP 主仓导航

MCP 服务器（官方 Python SDK，stdio）：把 SolidWorks 2026 COM 自动化暴露为
79 个工具给 AI 调用（81 开产品工具）——零件建模、特征、装配、工程图、导出、参数化全链路。
目标：AI 全自动绘制 3D 机械图（零件 → 装配 → 工程图 → PDF/STEP/STL）。

## 目录地图

| 路径 | 内容 |
|---|---|
| `solidworks_mcp/server.py` | 门面（~206 行）：FastMCP 实例 + 3 resources + stdio 入口 + 全量 re-export |
| `solidworks_mcp/registry/` | **79 工具按域落此**（N14；默认注册，开产品工具 81）：`base.py` 共享类型/执行件 + `part/assembly/drawing/features/file_io/misc/properties/products/prompts` 域模块；新工具加域模块，别加 server.py |
| `solidworks_mcp/solidworks_api/` | COM 实现 16 模块（app/design/drawing/assembly/features/pattern/…） |
| `solidworks_mcp/examples/` | 产品专用工具（ring_light）——env 门控，默认不注册 |
| `tests/` | 单元测试（mock COM，无需 SW 实机） |
| `tools/` | 探针（`probe_*/`，实机 API 取证）与验证脚本（`INDEX.md` 索引） |
| `docs/adr/` | 冻结决策（0009-0012） |
| `output/` | **gitignored**：N 系列优化规划（`optimization-plan-*.md`）与验收产物 |

## 测试与基线

```powershell
venv\Scripts\python.exe -m pytest tests/ -q     # 540 passed + 105 subtests（~10s，2026-09-06 F1 守卫后）
venv\Scripts\python.exe tools\e2e_sw_smoke.py   # 实机 e2e（需 SW 运行；tracked 台账 output/e2e-summary.md）
```

- 覆盖率红线 ≥89%（CI 硬门 80%）。
- **CI 已激活（2026-09-02 全绿）**：GitHub Actions `VisionFocus2022/SolidWorksMCP`
  windows runner——pytest+coverage≥80+pip-audit；推送 main 自动跑。
- 工具计数被 5 处测试钉死（79 默认 / 81 开产品工具）——改工具数先改
  `tests/test_infrastructure.py` 与 `tests/test_server.py` 断言。
- capabilities 与实现由 `tests/test_capabilities_sync.py` 锁定，勿手写漂移。
- CI runner 的 tempfile 基址是 8.3 短名（RUNNER~1）：路径断言必须走
  `normalize_path` 规范形（tests/test_hardening.py 的教训，2026-09-02）。
- **即席改动验证约定**：凡不经 N 系列计划的即席源码/配置改动，收尾回复必须
  贴出所跑的验证命令与退出码（未验证须写明原因）——让改动正确性可被后来者
  凭记录核验（better-harness F5，2026-09-06）。

## 安全红线

1. COM 调用必须经 `run_com(...)`（超时默认 120s×3，毒化退程 `SOLIDWORKS_MCP_POISONED_EXIT=1`）。
2. 文件操作必须在 `allowed_root` 内。
3. 破坏性工具标 `DESTRUCTIVE`。
4. MCP 入参 mm，COM 层 m——换算在实现层完成。
5. 绝不 push；提交不跨仓（`aicad/` 是独立 git 仓库，见下）。

## N 系列优化规划惯例

每日自动化（02:30 实施任务）读取 `output/optimization-plan-<最新日期>.md`
按 §2 执行协议逐任务执行：选第一个 `[ ]` 且依赖全 `[x]` 的任务 → TDD →
本地 commit → 回填状态与执行记录。**总览表状态列必须实时翻转**——它是
选任务的唯一入口（第四期 I1 漂移教训）。

## 子仓

`aicad/` 是独立 git 仓库（AI 驱动参数化 CAD：FastAPI + build123d 沙箱 +
React/three.js + SW COM 桥），有自己的 AGENTS.md 与 ADR；双仓分别提交，
绝不跨仓。
