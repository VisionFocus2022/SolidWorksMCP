# AI 驱动 3D 机械图全自动绘制——优化改进规划（第五期：交付可靠 + 质量收口 + 能力长尾）

> **生成**：2026-08-31 结构化会话（蓝本：`output/architecture-evolution-2026-08-31/` 架构演进审查五件套——evolution-summary / migration-roadmap / decision-map / evidence / 两 dot）
> **主题**：审查一句话结论「能力面已建完、架构健康；最大风险不在代码而在交付」的立项修复
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考
> **For agentic workers:** 按任务逐项执行（§2 执行协议），步骤用 checkbox（`- [ ]`）跟踪，完成后回填状态与「执行记录」小节。
> ⚠️ 本计划为自治会话按审查蓝本起草（migration-roadmap S2-S4 为任务、S0/S1 为用户动作），**用户过目确认前首个自动执行夜可先跑无「用户动作」前置的任务**（N26/N27 及解阻塞后的任务），S3/S4 全部新代码任务等 §1.4 用户动作 U1 完成后放行。

---

## 1. 文档定位与背景

本计划**承接第四期**（`output/optimization-plan-2026-08-31.md`，N18-N23）。四期实际执行 N18✓ N19✓ N20✓ N21✓；**N22/N23 依 AGENTS.md「自动任务读最新日期计划」契约承接为本期 N25/N26**（四期总览表已加指针，勿再回四期执行）。

**审查核心判断**（2026-08-31，证据当日采集、置信 high）：

| 差距 | 内容 | 严重度 |
|---|---|---|
| G1 交付可靠 | 主仓领先 origin 15 提交（origin=04bf21f，HEAD=00db3e7）；aicad 69 提交零远端；ci.yml 是 GitHub Actions 语法但远端在 gitee——**CI 从未跑过**。任何磁盘故障=两周工作归零 | P0（S0/S1） |
| G2/G3 质量观测 | perf 预算负载敏感假红待空闲机复验（红线禁放室断言）；缓存命中率有数据无报表；CodeRabbit 未 auth；aicad 前端零测试 | P2（S2/S4） |
| G4/G5 能力长尾 | 零件：loft/sweep/筋/圆顶/参考几何/多实体/通用草图；图纸：BOM 气泡引线/爆炸图 | P2（S3/S4） |
| G6/G7/G8 远期 | CSG v2 扩 op（本期部分承接为 N31）、原生阵列升级、智能自治层 | 远期观察 |

**排序原则**（migration-roadmap）：可逆性与验证成本——S0/S1 零代码风险、验证信号免费；S3-S5 每晚新增代码都应先有异地备份与 CI 门禁兜底。**在 U1（主仓推送）完成前，S3/S4 的每一行代码都只存在于一台机器上**。

### 1.4 用户动作清单（S0/S1 用户侧，不占实施任务，分钟级）

> 自动任务读到本节**不能代做**（红线「绝不 push」）；只在对应任务前置检查时核验完成信号。
> **2026-08-31 执行会话结果**：U1/U2/U5 已闭环，U3 远端接入完成但 CI 被账户计费挡（新增 U6），U4 仍待用户交互。

| ID | 动作 | 对应决策 | 状态（2026-08-31） |
|---|---|---|---|
| **U1** | 主仓 `git push origin main`（15 提交：N8-N14 六特性 + N18-N21） | D1（选 A） | ✅ 完成：`04bf21f..00db3e7` 已推 gitee，`origin/main == HEAD` |
| **U2** | aicad 远端接入 | D2 | ✅ 完成（**路线偏差**）：gitee 建仓不可行（本机存储凭据=账号密码，API v5 401；gitee 无 push-to-create）→ 改走 github：`VisionFocus2022/aicad` 私有仓已建、origin 已接、69 提交全量首推。**gitee 侧可选补充**：手动建仓或提供 gitee PAT 后加第二远端 |
| **U3** | 主仓 CI 激活（选 A：github 第二远端） | D3 | ◐ 远端接入完成：`VisionFocus2022/SolidWorksMCP` 私有仓已建 + 推送（main 上游已切至 `github/main`，gitee 仍为 origin）。**CI 首跑失败=账户计费挡板，非代码问题**（见 U6） |
| **U4** | `coderabbit auth login`（CLI v0.7.5，signed out） | J3 | ⏳ 待用户交互：OAuth 须本人浏览器（`coderabbit auth login`），或提供 API key（`coderabbit auth login --api-key <key>`）后交自动会话补跑外审 |
| **U5** | 确认主仓远端 URL 名 `AICAD.git` 与子仓 `aicad/` 同名异体是否历史误设 | D7 | ✅ 结案：`pengzixiao2025/AICAD.git` 就是主仓的 gitee 仓（持续在用，凭据身份 lancy666 有推送权），**非错接**；撞名歧义已由 github 侧命名消解（主仓=SolidWorksMCP、子仓=aicad）。改名 gitee 仓属可选、无功能必要 |
| **U6（新增）** | github 计费处理：Settings → Billing & plans 修复付款/提高消费限额（私有仓 Actions 分钟需计费通道）；或决定将 SolidWorksMCP / aicad 转公开（公开仓 Actions 免费） | D3 延伸 | ⏳ **CI 解锁唯一前置**。处理后一句话通知即可触发 re-run（N24 步骤 5/6 收口） |

## 2. 执行协议（02:30 实施任务必读）

1. **选任务**：读 §3 总览表，选**第一个**状态 `[ ]` 且依赖全部满足（任务依赖为 `[x]`；用户动作依赖 U* 见 §1.4 完成信号）的任务。`[!]` BLOCKED 跳过转下一个，不阻塞其余任务。
2. **SolidWorks 前置检查**（标注「需 SW 实机」的任务）：
   ```powershell
   python -c "from solidworks_mcp.solidworks_api.app import get_solidworks_app; print(get_solidworks_app().status(launch_if_needed=False))"
   ```
   未运行则改状态 `[!] BLOCKED（SW 未运行，YYYY-MM-DD）`，转下一个可执行任务。
3. **TDD 循环**：写测试 → 跑红 → 实现 → 跑绿 → 实机验证（如需）→ 提交。禁止先实现后补测试。
4. **提交纪律**：每任务 ≥1 次本地 `git commit`（**绝不 push**——含 github 第二远端，推送一律用户执行或显式授权）；主仓库/aicad 仓库分别提交，绝不跨仓。message：`feat|fix|test|docs|chore(scope): <一行中文描述>`。
5. **回填**：任务状态改 `[x]`（失败 `[!]` 注明原因）；「执行记录」小节回填日期/结果/commit hash/备注；更新 §3 总览行。**承接任务（N25/N26）完成后须回填四期 §11/§12 双处**。
6. **节奏**：每晚 1 个任务为宜，最多 2 个（第二个必须 ≤2h 小任务）。
7. **安全红线**（继承）：COM 调用必须经 `run_com(...)`；文件操作在 `allowed_root` 内；破坏性工具标 `DESTRUCTIVE`；MCP 入参 mm、COM 层 m；主仓覆盖率 ≥89%（CI 硬门 80% 不得降）；perf 断言禁放宽。
8. **测试命令基线**：
   - 主仓库：`venv\Scripts\python.exe -m pytest tests/ -q` → 基线 **485 passed + 95 subtests，约 12-22s**（2026-08-31，N19 后）；
   - aicad 仓库（在 aicad/ 内）：`venv\Scripts\python.exe -m pytest tests -q` → **631 passed**（2026-08-31 两轮负载下 perf 均绿；严格空闲条件未验=N26）；
   - 实机 e2e：`venv\Scripts\python.exe tools\e2e_sw_smoke.py`（需 SW 运行）。
9. **中断恢复**：读到未勾选步骤继续；已勾选产物未提交则先补提交。以 `git status`/`git log` 实时状态为准，勿信旧快照。
10. **工具计数同步**：S3/S4 主仓任务凡新增工具，先改 `tests/test_infrastructure.py` 与 `tests/test_server.py` 的 4 处计数断言（现 69 默认 / 71 开产品工具），再动实现。

## 3. 任务进度总览

状态：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED。「仓」列：主=主仓库，ai=aicad，双=两者。

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N24 | P1 | 主仓 CI 激活与首跑修复批（D3） | 主 | U6（原 U1+U3 远端部分已完成） | 2h/1晚 | `[!]` BLOCKED（远端接入+推送已完成 2026-08-31；CI 首跑被**账户计费挡板**拦停——等 U6 后 re-run 观测，run 33389164476 定谳非代码问题） | |
| N25 | P1 | aicad 远端接入与 CI 绑定（承接四期 N22） | ai | 无（U2 已完成） | 1h/1晚 | `[ ]`（远端接入+69 提交首推已由 2026-08-31 会话完成；余步：untracked 脚本处置 + CI 绑定（同受 U6 计费挡）+ 双回填） | |
| N26 | P2 | aicad perf 预算空闲机复验（承接四期 N23） | ai | 无（需空闲机） | 0.5h | `[ ]` 需空闲机 | |
| N27 | P2 | 缓存命中率报表导出 CSV/JSON（H2） | ai | 无 | 2h/1晚 | `[ ]` | |
| N28 | P2 | 零件长尾波1：loft/sweep（放样/扫描） | 主 | U1 | 5h/2晚 | `[ ]` 需 SW 实机 | |
| N29 | P2 | 零件长尾波2：筋/圆顶/参考几何 | 主 | U1 | 5h/2晚 | `[ ]` 需 SW 实机 | |
| N30 | P2 | 零件长尾波3：多实体 combine + 通用草图原语 | 主 | U1 | 5h/2晚 | `[ ]` 需 SW 实机 | |
| N31 | P2 | CSG 契约 v2 扩 op（D5 范围随波次驱动） | 主 | U1 + N28-N30 任一完成 | 3h/1晚 | `[ ]` | |
| N32 | P2 | BOM 气泡引线（drawing 域） | 主 | U1 | 3h/1晚 | `[ ]` 需 SW 实机 | |
| N33 | P2 | 爆炸图（assembly 域 + 图纸投影） | 主 | U1 | 4h/2晚 | `[ ]` 需 SW 实机 | |
| N34 | P2 | aicad 前端冒烟测试（React/three.js 零测试兜底） | ai | U2 | 4h/2晚 | `[ ]` | |

> 远期观察项（本计划不排期，继承四期/审查 S5）：plan-then-execute 任务分解、RAG 示例检索、mate 约束求解器、多模型路由、原生 FeatureCircularPattern4 升级（G7，探针路径已留）、特征级缓存。
> 建议执行顺序（依赖满足时）：N26/N27 先行（无前置）→ N24/N25（用户动作解锁）→ S3 波次 N28→N29→N30 与 S4 的 N32/N33/N34 可按晚穿插（域不相交可并行排期，但每晚仍单任务执行）→ N31 收口。
> **2026-08-31 更新**：U1/U2 已完成——N28-N33 的 U1 依赖、N34 的 U2 依赖**均已满足**（新代码异地备份已就位，S3/S4 随时可开）；N25 远端前置亦已满足；唯一待解前置为 U6（github 计费，仅阻塞 N24/N25 的 CI 类收尾步，不阻塞代码任务）。

## 4. 现状快照（2026-08-31 基线）

- **主仓库**：485 passed + 95 subtests（~12s）；69 工具（4 处断言钉死）；server.py 206 行门面 + registry/ 11 域模块；ADR 0001-0012 十二家族齐；源码零 TODO/FIXME；覆盖率 ≥89%。
- **交付面（2026-08-31 执行会话后）**：主仓**双远端**——origin=gitee `pengzixiao2025/AICAD.git`（已同步 00db3e7）+ github `VisionFocus2022/SolidWorksMCP`（已同步；main 上游现为 github/main，推送须带远端名）；aicad origin=github `VisionFocus2022/aicad`（69 提交全量备份，此前零远端）。**CI 已触发但被账户计费挡板拦停**（私有仓 Actions 分钟；首跑 run 33389164476 annotations 定谳非代码问题，等 U6）——U6 后 re-run，届时真正风险点才轮到：pip-audit 传递依赖 CVE、覆盖率门、runner 环境差异。
- **aicad**：69 提交、零远端、2 个 untracked 脚本（`tools/e2e_four_ring.py`/`tools/golden_flange_sample.py`，归属在 N25 处置）；631 passed（perf 两轮负载下绿，严格空闲未验）；前端零测试；`/api/health` 已有缓存命中率数据、无导出面。

---

## 5. N24 主仓 CI 激活与首跑修复批（P1，主仓，2h）

**目标**：U3 选 A（github 第二远端）后，让从未运行过的 ci.yml 真正跑绿，交付闭环（每行新代码有 CI 门禁兜底）。

- [ ] 1. **前置核验**：U1 完成（origin/main == HEAD）；U3 裁决=A 且用户已建 github 仓库。若裁决=B（Gitee Go）：本任务改为 ci.yml 语法迁移 Gitee Go 并在其控制台首跑；裁决=C：本任务改 `[x]` 并注明「用户裁决维持休眠，CI 兜底缺位已留痕」。
- [ ] 2. 接第二远端：`git remote add github <用户提供的URL>`（仅 add，不 push——推送在用户侧或显式授权）。
- [ ] 3. **首跑观测**：github Actions 出现 CI 首跑后读结果（gh CLI 或用户贴日志）。
- [ ] 4. **修复批（首跑红时）**，候选按概率排查：①pip-audit 报传递依赖 CVE → 升级依赖版本或 `--ignore-vuln` 豁免（豁免必须在 commit message 注明 CVE 号与理由）；②覆盖率 <80 → 补测试，**禁降门**；③windows runner 环境差异（pywin32 装载、路径、依赖缺失）→ 对症补。每次修复本地 commit，累积后由用户推送或显式授权推送，再观下一轮。
- [ ] 5. 绿后回填：本文件状态 + AGENTS.md「测试与基线」节补一行 CI 现况（远端、门禁值）。
- [ ] 6. 回填本文件状态与执行记录。

**验收**：github Actions CI 全绿且 coverage≥80 实测通过；`git remote -v` 双远端；修复有 commit 可溯；pip-audit 若有豁免已注明。

**执行记录**：
> **2026-08-31 执行会话（U3-A 实施）**：仓库 `VisionFocus2022/SolidWorksMCP`（私有）经 API 创建（凭据库 PAT，X-OAuth-Scopes=repo+workflow 齐备，gh CLI 未装不阻塞）；`git remote add github` + 推送 main 成功（上游切至 `github/main`，origin=gitee 不变）。CI 首跑 run `33389164476` **5 秒失败、步骤列表空、logs 端点 BlobNotFound**——check-run annotations 定谳：**「recent account payments have failed or your spending limit needs to be increased」**（私有仓 Actions 计费挡板，非代码问题）。步骤 ①②③ 完成；④ 修复批不适用（无代码可修）；⑤⑥ 待 U6 计费处理后 re-run 观测收口。

---

## 6. N25 aicad 远端接入与 CI 绑定（P1，aicad，1.5h，承接四期 N22）

**目标**：aicad 69 提交获得异地备份；CI 按 D2/D3 裁决结果落地。

- [ ] 1. **前置核验**：U2 完成（远端 URL 已交付）。
- [ ] 2. **untracked 脚本归属处置**：`tools/e2e_four_ring.py`/`tools/golden_flange_sample.py` 默认**入库**（属可复用工具脚本，若 aicad 有 INDEX 惯例则登记）；确属一次性验证产物则移 `output/`。处置后 `git status` 干净。
- [ ] 3. 接远端：`git remote add origin <URL>`；首推 `git push -u origin main`（**推送属用户动作或显式授权**，自动化只备好远端与干净工作树）。
- [ ] 4. **CI 绑定（按远端平台）**：远端=github → 复刻主仓 ci.yml 模板双 job（pytest + npm build，`.github/workflows/ci.yml`）；远端=gitee → 仓库存档 ci.yml 供未来 github 镜像用，Gitee Go 是否迁移**留用户裁决**（与 D3 联动），本步标注留痕即可。
- [ ] 5. 回填**双处**：本文件 + 四期 `optimization-plan-2026-08-31.md` §11 N22 状态。
- [ ] 6. 回填本文件状态与执行记录。

**验收**：aicad 远端 SHA == 本地 HEAD（`git -C aicad status -sb` 无 ahead）；工作树干净；CI（若 github）首跑绿。

**执行记录**：
> **2026-08-31 执行会话（U2 实施）**：gitee 建仓不可行（本机存储凭据=账号密码，API v5 401「Access token does not exist」；gitee 亦无 push-to-create）→ 改走 github：`VisionFocus2022/aicad`（私有）创建 + origin 接入 + `master` 全量首推（69 提交，`## master...origin/master` 零 ahead）。**余步移交本任务**：步骤 1 前置已满足；步骤 3 实质完成（首推）；步骤 2（untracked 脚本处置——不影响已完成的推送）、步骤 4（CI 绑定，同受 U6 计费挡）、步骤 5（回填四期 §11 N22 双处）待自动任务执行。

---

## 7. N26 aicad perf 预算空闲机复验（P2，0.5h，承接四期 N23）

**背景**（四期 §12 全量继承）：`test_tessellate_100k_faces_under_0.3s` 曾在 94% CPU 负载下 0.434s 假红；四期 N20 当日两轮全套（51%/62% 负载、SW 运行中）perf 均绿（627/631），假红判断进一步坐实，但**严格空闲条件未满足**。

- [ ] 1. 空闲机（SW 关闭、CPU <20%）复跑 `venv\Scripts\python.exe -m pytest tests/test_perf_budgets.py -q`：绿 → 关单（假红确认）；仍红（>0.3s）→ 开提取循环微优化批（候选：`nodes.tolist()` 一次转列表后纯列表切片 extend，预期能拿回 20-40%）。
- [ ] 2. 结论回填本节 + 四期 §12（双处）；若走优化批，**预算线不动**（禁放室断言过闸）。

**执行记录**：
> （待回填）

---

## 8. N27 缓存命中率报表导出 CSV/JSON（P2，aicad，2h）

**目标**：缓存命中率「有数据无报表」收口（审查 G3）——`/api/health` 已有命中率数据，补可导出面供 nightly 观测。

- [ ] 1. **TDD**：`tests/test_stats_export.py` —— 断言导出面（建议 `GET /api/stats/export?fmt=csv|json`，与 N20 的 `fmt=` 先例同构）：CSV 含表头+命中率行、JSON 键齐全（hit/miss/rate/条目数）；无缓存数据时返回空表而非 500。
- [ ] 2. **实现**：从现有 health/stats 数据源同源取数（勿复制第二份统计逻辑）；CSV 用标准库 `csv` 模块，无新依赖。
- [ ] 3. aicad 全套绿（631+新测）；若 N25 已接 github CI 则同步进 CI。
- [ ] 4. 提交：`feat(api): 缓存命中率报表导出（N27）`；回填状态与执行记录。

**验收**：`curl .../api/stats/export?fmt=csv` 与 `fmt=json` 均可导出且数值与 `/api/health` 一致；全套绿。

**执行记录**：
> （待回填）

---

## 9. N28 零件长尾波1：loft/sweep（P2，主仓，5h/2晚，需 SW 实机）

**目标**：解锁多草图特征族（放样/扫描），AI 覆盖面从箱体/回转体扩到自由曲面件（审查 G4）。

**方法论**（ADR-0011，全波次通用）：先类型库取证（PS 反射枚举 InsertProtrusionLoft/Swept 系签名与依赖接口）→ `tools/probe_*` 实机探针数值窗口取证 → TDD（FakeModel 红→绿）→ 工具注册 → 实机 e2e。

- [ ] 1. **类型库取证**：探针确认放样（ProfileFeatures/LoftedFeature 系）与扫描（SweptFeature/路径+轮廓）API 可达性与参数签名；不可达面如实记录并走数学替代路线（先例：T21 螺纹 InsertHelix 可建）。
- [ ] 2. **TDD**：`tests/test_part_loft.py`（或并入既有 part 域测试）—— FakeModel 双打：工具调用序列、剖面有序性校验、错误契约（剖面数 <2 报 INVALID_PARAMETER）。
- [ ] 3. **实现**：`registry/part.py` 新增 `part_create_loft` / `part_create_swept`（预览 READ_ONLY 与执行 DESTRUCTIVE 分离，先例 ADR-0007）；实现在 `solidworks_api/` 对应模块；工具计数 4 处断言 69→71 同步（§2 第 10 条）。
- [ ] 4. **实机 e2e**：放样两圆截面→体积数值窗口断言；扫描圆沿路径→体积断言；ad-hoc 脚本**随手 close_document**（实机坑：文档挂着会让 SaveAs3 报 code 1）。
- [ ] 5. 全套绿 + 提交 `feat(part): loft/sweep 放样扫描工具（N28）`；若路线有取舍，ADR-0011 追加一段。
- [ ] 6. 回填本文件状态与执行记录。

**验收**：FakeModel 测试绿；实机两特征体积窗口断言过；工具数 71（默认）；README 工具清单同步。

**执行记录**：
> （待回填）

---

## 10. N29 零件长尾波2：筋/圆顶/参考几何（P2，主仓，5h/2晚，需 SW 实机）

同 N28 的 0011 方法论，三特征族一批（支撑类零件）。

- [ ] 1. 类型库取证：RibFeature（InsertRib 系，厚度/拉伸方向）、DomeFeature（InsertDome 系）、参考几何（基准面/轴 InsertRefPlane/InsertRefAxis 系——**先于筋做**：筋依赖草图面）。
- [ ] 2. TDD：FakeModel 红→绿（含参考几何创建后被特征消费的调用序断言）。
- [ ] 3. 实现 + 工具计数断言同步（参考几何 2 + 筋 1 + 圆顶 1 ≈ 71→75，以实际拆分为准）。
- [ ] 4. 实机 e2e：L 型件加筋体积增量窗口断言；圆顶体积断言。
- [ ] 5. 全套绿 + 提交；回填状态与执行记录。

**验收**：同 N28 口径（测试绿 + 实机窗口断言 + 计数同步 + README 同步）。

**执行记录**：
> （待回填）

---

## 11. N30 零件长尾波3：多实体 combine + 通用草图原语（P2，主仓，5h/2晚，需 SW 实机）

- [ ] 1. 类型库取证：多实体（InsertFeatureBlend/BodyAdd 系——FeatureManager 多实体布尔）、草图原语（多边形 CreatePolygon 系 / 槽 CreateSlot 系 / 样条 SketchSpline 系）。
- [ ] 2. TDD：combine 的实体选择集契约（错误路径：单实体调用 combine 报 INVALID_PARAMETER）；草图原语参数枚举化先例（N19 ThreadSpec Literal 模式）。
- [ ] 3. 实现 + 工具计数断言同步。
- [ ] 4. 实机 e2e：box+cylinder 两实体 add → 体积=两体积之和窗口断言；等体积 subtract 验证。
- [ ] 5. 全套绿 + 提交；回填状态与执行记录。

**验收**：同 N28 口径。

**执行记录**：
> （待回填）

---

## 12. N31 CSG 契约 v2 扩 op（P2，主仓，3h/1晚，D5）

**目标**：跨引擎可迁移集从 v1 的 4-op（box/cylinder/hole/cut_hole）扩容，范围按 N28-N30 已落地特征驱动（决策 D5：装饰 fillet/chamfer → 阵列 → 螺纹，按评测集失败样本优先）。

- [ ] 1. **范围裁决**：读 N28-N30 执行记录，选已实机验证 ≥1 轮的特征族进 v2 首批；评测集失败样本（aicad 评测框架 10 任务）交叉验证优先级。
- [ ] 2. **TDD（0012 契约+互证模式）**：契约 schema 扩 op → 跨引擎（SW 主仓 ↔ build123d 沙箱）往返体积互证测试先行红。
- [ ] 3. 实现：主仓侧 op 路由 + aicad 侧 CSG 导出路由扩容（先例 aicad `90c6a5a`）；双仓分别提交。
- [ ] 4. 跨引擎往返互证绿 + 双仓全套绿；ADR-0012 追加 v2 范围记录。
- [ ] 5. 回填本文件状态与执行记录。

**验收**：新增 op 在两引擎各自建模后往返体积互差在容差内；契约测试锁死；ADR-0012 更新。

**执行记录**：
> （待回填）

---

## 13. N32 BOM 气泡引线（P2，主仓，3h/1晚，需 SW 实机）

**目标**：制造级图纸装配表达件（审查 G5）——BOM 表已有（N8 扩列），补气泡引线成套。

- [ ] 1. 类型库取证：BOM 气泡 API（InsertBOMBalloon 系 / Annotation 视图级接口）可达性与参数签名。
- [ ] 2. TDD：FakeModel 红→绿（气泡附着组件 ID 契约、行号与 BOM 表一致）。
- [ ] 3. 实现：`registry/drawing.py` 新增 `drawing_insert_bom_balloons`；工具计数断言同步。
- [ ] 4. 实机 e2e：装配图插 BOM 表 + 气泡 → 导出 PDF 断言气泡文本存在（复用既有 PDF 断言先例）。
- [ ] 5. 全套绿 + 提交；回填状态与执行记录。

**验收**：PDF 内气泡实体存在且与 BOM 行对应；FakeModel 测试绿；计数同步。

**执行记录**：
> （待回填）

---

## 14. N33 爆炸图（P2，主仓，4h/2晚，需 SW 实机）

**目标**：装配表达最后一块（assembly 域 ExplodedView + drawing 投影双域联动）。

- [ ] 1. 类型库取证：爆炸视图 API（ExplodeConfiguration / InsertExplodeStep 系）+ 工程图投影视图对爆炸配置的引用方式。
- [ ] 2. TDD：FakeModel 红→绿（爆炸步骤的组件+变换向量契约；调用序：激活配置→步骤→保存）。
- [ ] 3. 实现：`registry/assembly.py` 新增爆炸配置工具 + `registry/drawing.py` 视图插入支持爆炸配置引用；计数断言同步。
- [ ] 4. 实机 e2e：三件装配爆炸→组件包围盒分离断言（x/y/z 间距窗口）；爆炸态投影出图 PDF 断言。
- [ ] 5. 全套绿 + 提交；回填状态与执行记录。

**验收**：爆炸后组件 AABB 互不重叠（窗口断言）；PDF 含爆炸视图；计数同步。

**执行记录**：
> （待回填）

---

## 15. N34 aicad 前端冒烟测试（P2，aicad，4h/2晚）

**目标**：最终交付物视觉正确性的第一道自动防线（现状零测试——审查 G3；不做像素级比对，先立「渲染不炸 + 关键交互通」冒烟线）。

- [ ] 1. **选型**：Vitest + @testing-library/react（组件级冒烟）；three.js 场景用实例存在性断言（mount 后 canvas 节点与 scene 实例非空），不做视觉快照（visual 类失败路由人工，不自动改生产代码——UIA 创建侧纪律）。
- [ ] 2. **TDD**：先写 3-5 个冒烟用例跑红（预览面板渲染、参数表单提交触发 mock API、导出按钮 fmt 联动——含 N20 的 dxf）。
- [ ] 3. **实现**：测试脚手架 + 必要的 mock 层（fetch/WS mock）；`npm test` 脚本入 package.json。
- [ ] 4. `npm run build` + `npm test` 双绿；若 N25 已接 CI 则 pytest+npm build 双 job 均含。
- [ ] 5. 提交：`test(frontend): 冒烟测试脚手架与首批用例（N34）`；回填状态与执行记录。

**验收**：`npm test` 绿且覆盖 ≥3 关键交互路径；CI（若已接）双 job 绿。

**执行记录**：
> （待回填）

---

## 16. 依赖与顺序总图（文字版）

```
U1(用户推送主仓) ──┬─→ N24(CI激活修复) ─┐
                   ├─→ N28→N29→N30 ──→ N31(CSG v2)
                   ├─→ N32(BOM气泡)      │
                   └─→ N33(爆炸图)       │（N28-N30 任一完成即可）
U2(用户给aicad远端) ─┬→ N25(aicad远端CI) ─┤
                     └→ N34(前端冒烟)    │
无前置 ──→ N26(perf复验) · N27(缓存报表) ─┴→ 收尾（本期 N31 完成后评估远期观察项立项）
```

## 17. 风险与未决（诚实披露）

- CI 首跑从未验证过，pip-audit 传递依赖 CVE 是最大概率红灯源（N24 修复批已兜底，豁免须留痕）。
- 「gitee 不执行 GitHub Actions」为平台行为推断，D3 裁决时在仓库设置页实测（审查原文保留）。
- aicad 631 基线引用 2026-08-31 实测（两轮），本计划未重跑——N26 执行时顺带确认。
- N28-N33 全部「需 SW 实机」且走 0011 取证方法论——存在 API 不可达需数学替代的风险（先例：T8 BLOCKED、T21 螺纹绕行），届时如实记 BLOCKED/替代路线，不硬凑。
- D7（远端命名）仅影响认知不影响执行，U5 低优先级。
- **github 账户（VisionFocus2022）私有仓 Actions 计费挡板（2026-08-31 实证）**：U6 处理前 N24/N25 的 CI 步全部挂起；git 推送不受影响（备份已达成）。
- **gitee 侧自动化天花板**：本机存储的是账号密码非 PAT，API 建仓 401——gitee 补充远端需用户手动建仓或提供私人令牌（U2 偏差注记）。
