# AI 驱动 3D 机械图全自动绘制——优化改进规划（第六期：结构债收口 + 治理权威化）

> **生成**：2026-09-07 结构化会话（蓝本：`output/architecture-review-2026-09-06/` 专家团五视角审查五件套——review-summary + 五角色 JSON）
> **主题**：审查一句话结论「交付质量扎实，但 part.py 击穿治理红线——先还结构债再扩能」的立项实施
> **用途**：供每日 02:30 自动实施任务读取执行；亦供人工实施参考（AGENTS.md 契约：自动任务读本文件=最新日期计划）
> **承接**：第五期 `output/optimization-plan-2026-09-01.md` N24-N34+N26 **全部 ✅**（仅余 U4 CodeRabbit auth=用户动作，见 §1.4 指针，无实施任务）。执行协议/安全红线/测试命令基线**全量继承第五期 §2**，此处不重复。

---

## 1. 审查结论与任务来源

| 审查发现 | 内容 | 本期任务 |
|---|---|---|
| H-1 | part.py 1243 行击穿 <1100 治理线（E-12 基线 1011，N28-N30 +232） | **N35** |
| M-2 | makepy typed 包装 3 处生产重复且语义漂移；decorations 跨模块取 part 私有符号 | **N35（联动，新代码用 utils/com；存量 assembly/features 替换入 N37）** |
| M-4 | 基线数字多会话漂移（文档 537/637 vs 实测 542/712+18） | **N36** |
| M-1 | save_path 双块样板 ≥6 处复制 + feature 失败响应 code 不一致 | N37 |
| M-3 | CSG v2 stack_top=None 哨兵对未来 op 脆弱；rebuild_csg_plan 180 行 6 分支长链 | N38 |
| L-1/6/7 | 方法名 71 残留 / csg prompt 未宣发 v2 / CSG_VERSION 死值 | N39 |
| L-2/3/4/5 | Literal 未收紧 / NaN 绕开校验 / STATE_CHANGE vs DESTRUCTIVE / 缓冲不重试 | N40 |
| L-8 | 探针缺「已完成」标注 / FakeModel 三文件重复 / 探针 helper 六脚本重复 | N41 |

明确不做（审查判定合理样板）：registry launch_if_needed 样板抽象；已完成探针删除（契约已转录 docstring，脚本留档）。

### 1.4 用户动作（承接，无新增）

- **U4（承接五期）**：`coderabbit auth login` 需用户本人浏览器 OAuth 或供 API key——处理后触发外审补跑（J3）。

## 2. 任务进度总览

状态：`[ ]` 待执行 · `[~]` 进行中 · `[x]` 完成 · `[!]` BLOCKED。「仓」：主=主仓库，ai=aicad。

| ID | 优先级 | 标题 | 仓 | 依赖 | 预估 | 状态 | 完成日期 |
|---|---|---|---|---|---|---|---|
| N35 | P1 | part.py 域拆分（H-1）+ utils/com.py 统一包装（M-2 联动） | 主 | 无 | 3h/1晚 | `[ ]` | |
| N36 | P1 | 基线权威化（M-4）：AGENTS.md 实测刷新 + 回填纪律 + 多会话协调 | 双 | 无 | 0.5h | `[ ]` | |
| N37 | P2 | save helper 上提 + 错误 code 统一（M-1）+ makepy 存量替换（M-2 收口） | 主 | N35 | 2h/1晚 | `[ ]` | |
| N38 | P2 | CSG op→handler 字典化（M-3，v3 前置） | 主 | 无 | 2h/1晚 | `[ ]` | |
| N39 | P2 | LOW 批 1：方法名 71 / csg prompt v2 / CSG_VERSION 常量治理 | 主 | 无 | 0.5h | `[ ]` | |
| N40 | P2 | LOW 批 2：Literal 收紧 / NaN 排除 / 注解统一 / 缓冲重试 | 主 | 无 | 1h | `[ ]` | |
| N41 | P2 | LOW 批 3：探针标注 / FakeModel 合并 / 探针 helper 收敛 | 主 | 无 | 1h | `[ ]` | |

> 远期观察项（继承五期，不排期）：S5 智能自治层二期（等 API key 基线数据）、宏录制器队列（mirror/pattern/rib/combine/AutoBalloon 五族）。
> 排序原则（审查 §4）：**结构债先于扩能**——N35/N36 首批必做；N37 依赖 N35；其余按晚穿插。

---

## 3. N35 part.py 域拆分 + utils/com.py（P1，3h/1晚）

**目标**：H-1 收口——part.py 1243→约 620 行（<800 用户线、<1100 治理线），新域模块各 <700；M-2 联动：makepy 包装抽 `utils/com.py::static_wrap`（assembly._wrap_static 蓝本），新代码全部用公共版，decorations 私有引用清偿。

**拆分布局**（方案=门面 re-export，公开 API 零破坏）：

| 新模块 | 内容（自 part.py 迁出） | 行数约 |
|---|---|---|
| `solidworks_api/part_advanced.py` | `_sweep_path_sketch`、`create_swept`、`create_loft`、`create_rib`、`create_polygon`、`create_slot`（N28-N30 五特征族） | 620 |
| `solidworks_api/part_refgeom.py` | `create_ref_plane`、`_cylindrical_face_by_name`、`create_ref_axis` | 130 |
| `utils/com.py` | `static_wrap(obj, iface)`（gencache makepy 静态包裹，PyIDispatch 类型防误判） | 40 |
| `part.py`（保留） | 基础体+helpers+质量属性（L1-562、L1208-1242 区）+ **尾部 re-export 高级特征**（registry/design/e2e/探针零改动） | 620 |

**兼容策略**：part.py 文件末尾 `from .part_advanced import create_swept, ...`（part→advanced→part 无环：advanced 在 part 初始化后期 import，所需 helpers 已定义）。decorations 的 `_typed_doc2` 改 `utils.com.static_wrap`。

**测试更新**（patch 点跟实现走）：test_part_loft.py / test_part_refgeom.py / test_part_primitives.py 的 `patch("...part._select_plane"/"part.latest_feature_name"/"part._extrude_sketch")` 改指 part_advanced / part_refgeom 命名空间；调用目标同步。**判据=全套绿（用例数不减）+ py_compile + e2e 抽验 1 个（e2e_n29 走门面路径）**。

- [ ] 1. utils/com.py 新建 static_wrap（TDD：单测断言 dynamic/typed 包裹行为）
- [ ] 2. part_refgeom.py 迁出三符号 + part_advanced.py 迁出五特征族（import part 的共享 helpers）
- [ ] 3. part.py 删迁出段 + 尾部 re-export + 行数核验（<800）
- [ ] 4. decorations 改用 utils.com（清偿私有引用）；三测试文件 patch 点更新
- [ ] 5. 全套绿（542+105 不减）+ e2e_n29 实机抽验 + commit + 回填

## 4. N36 基线权威化（P1，0.5h）

- [ ] 1. AGENTS.md「测试与基线」刷新为**当日实测**（主仓 542+105@09-06 实测 / aicad 712+18 perf deselected）+ 增「**基线回填纪律**：凡增减测试数的任务，同 commit 刷新本节数字与日期」。
- [ ] 2. 增「多会话协调」两行纪律：动 `output/` 前先 `git status` 确认无并行会话未提交产物（09-06 审查 JSON 被外部清理事件留档）；基线以**最新实测**为准，文档快照仅供参考。
- [ ] 3. commit + 回填（aicad 侧 AGENTS/agents.md 若有基线数字同步检查）。

## 5-10. N37-N41（后续批，按总览依赖序执行，细则实施时展开）

- **N37**：M-1+M-2 收口——save helper（validate+sink 两段）上提 utils 层供 create_* 复用（design._save_active_model 语义蓝本）；feature 失败响应统一 `code="SW_API_ERROR"`；assembly._wrap_static/features._typed_fm 替换为 utils.com.static_wrap。
- **N38**：M-3——rebuild_csg_plan 重构 op→handler 字典：每 handler 自带 stack_top 前置断言（None 消费显式化）；未知 op 显式 unknown 分支替代 else 兜底；行为不变（既有 27 用例全绿为门）。
- **N39**：L-1 方法名 `test_default_subprocess_registers_71_tools`→79；L-6 csg_rebuild prompt 增 v2 契约段；L-7 CSG_VERSION 死常量删除或改为合法集元组。
- **N40**：L-2 plane/path_type 改 Literal（schema fail-fast，base.py MateType 先例）；L-3 _validate_csg_plan 数值排 NaN/inf/bool；L-4 rebuild_csg 注解对齐 DESTRUCTIVE；L-5 _expand_long_path 按所需尺寸重试一次。
- **N41**：L-8——INDEX.md 四探针加「✅已完成」标注；test_part_loft/refgeom/primitives 共享 FakeModel 抽 tests/part_fakes.py；探针 _vol/_select 脚手架收敛（容忍工具脚本重复，仅收敛明显 3+ 次重复）。

**验收（各任务通用）**：全套绿且用例数不减；py_compile 0 error；计数断言不变（79/81）；每任务本地 commit + 回填本表。

---

## 11. 风险与未决（诚实披露）

- 拆分的最大风险=patch 点遗漏（tests 对 part 命名空间的 patch 在实现迁走后静默失效→用例反而可能假绿）：N35 步骤 5 要求**用例数逐文件对照**（拆分前后各文件收集数相等）。
- N38 重构 CSG 有 27 用例护栏 + 互证 roundtrip 可复跑（实机）。
- aicad 侧基线漂移的根因（多会话）超出单任务范围：N36 用纪律缓解，长效待 S5 协作机制。
