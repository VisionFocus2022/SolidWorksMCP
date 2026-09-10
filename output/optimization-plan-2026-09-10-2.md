# AI 驱动 3D 机械图全自动绘制——优化改进规划（第九期：产品化波 G9/G8）

> **生成**：2026-09-10 结构化会话（蓝本：`docs/product-vision.md` §5 路线图「第九期（产品化波）」+ D5 裁决前置；用户指令「根据规划，继续实施下一步」）
> **主题**：从开发者产品→可分发产品——frozen 打包实测、D5 安装形态裁决、用户文档与示例库
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考（AGENTS.md 契约：自动任务读本文件=最新日期计划）
> **承接**：第八期 `output/optimization-plan-2026-09-10.md` N46/N47 **全部 ✅**（终验 27/30=90% 伪影归零）。执行协议/安全红线/测试命令基线**继承第五期 §2 与第八期收官口径**（主仓 557+105；aicad 732 not-perf+18 deselected）。文件名带 `-2` 后缀=同日第二份计划（排序仍为最新，契约不变）。

---

## 1. 事实基线（2026-09-10 立项取证）

| 事实 | 状态 | 对本期任务的意义 |
|---|---|---|
| 主仓依赖面 | 仅 3 个运行时依赖：pywin32 / mcp[cli]<1.29 / pydantic<3 | frozen 打包的理想靶（无 ezdxf/numpy 重型依赖） |
| 入口 | `solidworks_mcp/server.py:main()` → FastMCP stdio | 单入口单形态，spec 简单 |
| pywin32 COM | 运行时 dynamic Dispatch + %TEMP%/gen_py typed 缓存（易失，quirks#30） | frozen 下 EnsureDispatch 走 %TEMP% 缓存，需实测验证 |
| D5 裁决（vision §D5） | frozen exe vs 容器 vs 源码+脚本——**先实测 PyInstaller 再裁决** | N48 就是裁决输入本身 |
| G8 路由策略 | providers.toml local-relay 已就位；[llm.routing] 配置位空 | 路由策略=aicad 配置面+评测对比，无代码 |
| 工具计数锁 | 79 默认/81 产品（5 处测试断言钉死） | frozen 构建必须注册同样的 79——smoke 断言用 |

## 2. 任务进度总览

状态：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED。「仓」列：主=主仓库，ai=aicad。

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N48 | P0 | PyInstaller frozen 打包实测（主仓 MCP server）→ 构建脚本+spec+MCP stdio smoke | 主 | 无 | 1晚 | `[x]` 2026-09-10（**一次成功**：16s 构建/47MB/0.6s 握手/79 工具逐位一致/诚实失败 PASS；pywin32 零配置；ezdxf 观察项对主仓 N/A；报告 docs/packaging-frozen-report.md；D5 建议=frozen onedir 采纳） | 2026-09-10 |
| N49 | P0 | D5 安装形态裁决 + 用户文档 v1（安装/配置/首跑）+ 示例库首波（20+ 取自 examples/） | 主 | N48 | 1晚 | `[x]` 2026-09-10（D5=frozen onedir 回填 vision/报告；user-guide v1（10 环境变量从 config.py 源头核验+模板发现链+首跑 4 步清单+排障表）；examples/ 24 卡 5 域目录化（验收数字引 e2e 实证，含 BLOCKED 边界诚实声明）） | 2026-09-10 |
| N50 | P2 | G8 路由策略固化：[llm.routing] 双 provider 对比评测 + 配置文档 | ai | 无 | 1晚 | `[ ]` | |
| N51 | P2 | G10 多机部署评估（观察性质，无实施承诺） | — | 无 | 0.5晚 | `[ ]` | |

> 执行顺序：N48 → N49（同一价值链）；N50/N51 可穿插。远期观察项（继续继承）：宏录制器解锁五族（G4，**需用户配合 ~30min/族**——最高价值挂起项）、GD&T（G5）、CSG v3（G6）；S5 v2 观察项：B7 件型表达力复验、GLM 通道补 T5、规划轮路由非 flash 档。

### 1.4 用户动作清单（顺承）

| ID | 动作 | 状态 |
|---|---|---|
| **U4（顺承五期）** | `coderabbit auth login`（本人浏览器 OAuth 或 API key） | ⏳ |
| **U8（顺承七八期）** | GitHub Billing 失败发票清算——五轮 re-run 实证：Spending limit=50 已设仍拦，check-run 时间戳证实现行挡板；账户=VisionFocus2022 个人 free 单层。billing 页无欠款仍拦则提工单 | 🔴 |
| **U9（新增，G4 解锁）** | 宏录制器对照实测：用户开 SW 录制宏（mirror/pattern/rib/combine/AutoBalloon 任一族 ~30min），产出 .swp 宏文件后一句话通知——解锁 BLOCKED 五族的 ground truth | ⏳ 条件 |

---

## 3. N48 PyInstaller frozen 打包实测（P0，主仓，1晚）

**目标**：D5 裁决的实测输入——把 `solidworks_mcp` 打成 onedir frozen 分发包，证明「目标机器无 Python 也能跑 MCP server」的路径可行，并固化可复现的构建脚本。

- [x] 1. **环境**：venv 装 PyInstaller（不动 pyproject——避免 CI pip-audit/覆盖面变化；版本与安装命令记录在构建文档）。
- [x] 2. **构建脚本** `tools/build_frozen.py`：onedir + console，entry=server.main，含 pywin32/mcp 的隐性依赖处置（实测发现的坑逐一记录）。
- [x] 3. **MCP stdio smoke** `tools/smoke_frozen.py`：起 frozen exe，stdin 发 JSON-RPC（initialize → notifications/initialized → tools/list），断言：握手返回 serverInfo、**工具数 == 79**（计数锁口径）、无 SW 进程时 connect 类工具的优雅失败信息（诚实失败）。SW 实机联动留 e2e 观察项（frozen 下 gen_py typed 缓存首生成路径）。
- [x] 4. **实测记录** `docs/packaging-frozen-report.md`：体积、启动时长、坑清单（pywin32 DLL/gen_py/mcp cli extras）、限制（onedir 防病毒误报等），D5 裁决建议。
- [x] 5. 回填本表；全套测试零回归（557+105，9.3s）（不动运行时代码——预期零变化）。

**验收**：frozen exe 在本机（模拟无源码环境：独立目录、非 venv shell）完成 MCP 握手+列出 79 工具；构建脚本可复现；报告落盘。
**反目标**：不做安装器 UI（N49 裁决后另立）、不做许可/激活（远期 G9 尾项）、不分析 onefile（onedir 启动更快且杀软误报少，先测主路径）。

## 4. N49 D5 裁决 + 用户文档 v1 + 示例库首波（P0，主仓，1晚，依赖 N48）

- [x] 1. **D5 裁决**：依 N48 实测数据三选一（frozen onedir / 源码+bootstrap 脚本 / 容器），裁决记录进 product-vision §D5 与 packaging 报告。
- [x] 2. **用户文档 v1** `docs/user-guide.md`：安装（两形态）、.mcp.json 客户端配置（修 P0-2 旧路径注记）、环境变量表（ALLOWED_ROOT/AUTO_START/SOLIDWORKS_VERSION 等）、首跑验证清单。
- [x] 3. **示例库首波**：examples/ 现有素材盘点整理为 20+ 可跑示例（目录化+INDEX），frozen 用户可经 MCP 客户端直接复用。
- [x] 4. 回填本表；文档走 docs/（不动代码）。

## 5. N50 G8 路由策略固化（P2，aicad，1晚）

- [ ] 1. [llm.routing] plan/exec 双 provider 配置对比评测（当前上游仅 DeepSeek 单家——配置位就绪后若上游仍单一，如实记「单上游无法对比」并固化为配置文档）。
- [ ] 2. `docs/routing-guide.md`（aicad）：路由槽语义、何时配 plan_provider、评测复跑命令。
- [ ] 3. 回填本表。

## 6. N51 G10 多机部署评估（P2，观察，0.5晚）

- [ ] 1. 评估备忘：多机场景（车间多台 SW 工位）对当前单机架构的差距清单（会话隔离/端口/许可），**只评估不实施**——product-vision G10 数据输入。

---

## 7. 风险与未决（诚实披露）

- **frozen + COM 实机路径未验**：smoke 只覆盖握手/工具注册（无需 SW）；gen_py typed 缓存在 frozen 下的首生成留 e2e 观察项（需 SW 开机窗口）。
- **PyInstaller 引入的依赖树**（pyinstaller 只装在构建机 venv，不进运行时依赖；不进 pyproject 则 CI 零影响——代价是构建机需手动 `pip install`，文档写明）。
- **pip-audit 面不变**（本期不动 pyproject）。
- U8 未解：本期推送的 CI 验证继续挂起（同挡板）；本地全套绿是收口基础。
