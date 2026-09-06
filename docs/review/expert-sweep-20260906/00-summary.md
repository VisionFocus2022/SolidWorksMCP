# 00 · SolidWorksMCP 专家团全面审查总报告（expert-sweep-20260906）

- **审查日期/快照基准**：2026-09-06；主仓 HEAD=`0762b15`（未提交 1 文件=output 计划文档 + docs/review/ 本轮产物）；aicad 子仓 HEAD=`4085d455`（审查期间并行会话持续推进，ahead 4→9）。pytest 基线 **538 passed + 105 subtests**（实测，AGENTS.md 记 537）。
- **参与**：9 位编制——Alex(01)/Sam(02) 奠基 + Jack(03)/Tina(04)/Eric(05)/Nora(06)/Paul(07) 深审子代理 + Quinn(08)/Rita(09) 子代理中途阵亡由团长（主会话）接管补完。
- **范围**（探索门禁裁决）：主仓全量深审 + aicad 仅桥接面侧写；上轮对照 = architecture-evolution-2026-08-31 五件套 + coderabbit J3。
- **方法与自验**：奠基串行→深审 2 批（4+3）→交错实证复核→总报告；团长对全部 🟠 项与抽查 🟡 项逐条重证（行号亲验/git 双查/计数复测），**复核 15+ 项零误报、1 项修正（AR-3 ahead 4→6→9）**。

## 一、执行摘要

**发现总数：🔴 0 / 🟠 7 / 🟡 24 / ⚪ 18（+1 观察项）+ 架构层 AR-1~9。**

最严重 Top5（一句话）：
1. **T09-1 🟠** capabilities 仍宣称 "Loft/sweep not yet exposed" 而 4 个工具已建成——防漂移测试按域词匹配结构性漏检，AI 客户端被自我宣称封印能力面。
2. **C08-1 🟠** Dispatch 冷启动半初始化缺陷主仓在身——aicad 已实证修复（_launch_and_wait）未回流（AR-4 双源漂移的实锤代价）。
3. **S06-1+F07-1+F07-4 🟠 合并** file_close 三联风险：默认静默丢弃未保存编辑（无确认门）+ save_changes=True 落点零 allowed_root 校验 + 与 drawing 域「close 释放锁」提示组合成用户成果丢失链。
4. **A04-3 🟠** get_bom 质量按水密度计算与零件域材料密度口径 7.85× 分叉——两工具同表并排自相矛盾。
5. **A04-4 🟠** N32 关键修复的顺序契约零回归锁——7 个测试 patch 掉被测关键函数，代码回退单测仍全绿。

上轮对照处置率：G 系 8 项中 ✅4（G1/G2/G4/G5 主体）/◐3（G3/G5 尾/G6）/⚪维持 1（G7/G8 远期另计）；J3 3 项中 ❌2/不成立 1；AR 9 项中确认 2/升级 1/恶化 1/定谳 1/维持 4。

## 二、发现合并总表（按域；🟠 全量、🟡 择要、⚪ 详分区报告）

| 编号 | 级 | 域 | 标题 | 位置 | 复核 |
|---|---|---|---|---|---|
| T09-1 | 🟠 | 测试CI | capabilities 陈旧否定 + 防漂移测试结构性漏检 | base.py:238; test_capabilities_sync.py:28-43 | ✅团长+Rita+Eric 三证 |
| C08-1 | 🟠 | COM基建 | Dispatch 冷启动半初始化（aicad 已修未回流） | app.py:146-148 vs aicad sw_app.py:157-208 | ✅团长 |
| S06-1 | 🟠 | 安全 | file_close 默认丢弃未保存编辑无确认门 | file_io.py:146 | ✅团长 |
| F07-1 | 🟠 | 文件IO | Save3 落点零 allowed_root 校验（状态派生写） | file_io.py:159 | ✅团长（维持🟠裁决在案） |
| F07-2 | 🟠 | 文件IO | Save3 无 typed 容错——唯一保存通道 gen_py 环境断裂 | file_io.py:159; ring_light_v3.py:520 | ✅团长结构级 |
| A04-3 | 🟠 | 装配 | BOM 质量水密度 vs 材料密度 7.85× 口径分叉 | assembly.py:521 vs part.py:1208 | ✅团长双侧 |
| A04-4 | 🟠 | 装配 | N32 顺序契约零回归锁（7 测试 patch 掉关键函数） | test_assembly_extended.py ×7 | ✅团长结构级 |
| A04-1 | 🟡 | 装配 | add_component config_name 死参数（registry 不透传） | registry/assembly.py | ✅ |
| A04-2 | 🟡 | 装配 | add_mate distance 双语义/FiniteMM 标注错位 | assembly.py:366 | 分区证 |
| A04-5 | 🟡 | 装配 | 内部路径形态三处不一致 | assembly.py | 分区证 |
| P03-1 | 🟡 | 零件 | design plan 跨文档原子性缺口（new_part 中位失败残留） | design.py | 留实机复现档 |
| P03-2 | 🟡 | 零件 | cut_real_thread 魔法阈 0.0195 + 误导性错误 | features.py:470,474 | ✅团长 |
| P03-3 | 🟡 | 零件 | N9 工具中文单语硬编码（英文 SW 不可用） | features.py:418,498,669 | ✅团长 |
| P03-4 | 🟡 | 零件 | rebuild_csg docstring 滞后 v2 | registry/features.py | 分区证 |
| D05-1 | 🟡 | 工程图 | set_tolerance "verified" 宣称与读回不断言不符 | drawing.py:697,755-759 | ✅团长 |
| D05-2 | 🟡 | 工程图 | organize_dimensions 只比 Y 不比 X | drawing.py | 分区证 |
| D05-3 | 🟡 | 工程图 | limitations 漏披露两条实机缺口 | base.py:234-239 | ✅团长（+T09-1 加成） |
| D05-4 | 🟡 | 工程图 | 尺寸名发现缺口（失配报错不列候选） | drawing.py:743 | ✅团长 |
| D05-5 | 🟡 | 工程图 | "ADR-0011" 出处引用漂移 | drawing.py:1027 | 分区证 |
| S06-2 | 🟡 | 安全 | 16 件 overwrite 工具挂 STATE_CHANGE 非 destructiveHint | registry/* | ✅结构级（58:4） |
| S06-3 | 🟡 | 安全 | __main__ 块在末类前（直跑丢用例） | test_hardening.py:253 | ✅团长（T09-2 扩展：+csg_rebuild 12 例=15 例） |
| S06-4 | 🟡 | 安全 | normalize_path 盘符相对路径 C:foo 语义歧义 | security.py | 分区证 |
| F07-3 | 🟡 | 文件IO | STEP/STL 导出无文件级验证（三档不对称） | file_io.py | 分区证 |
| F07-4 | 🟡 | 文件IO | close 默认丢弃×drawing 释放锁提示组合涟漪 | 跨域 | 分区证 |
| F07-5 | 🟡 | 文件IO | overwrite 确认门 TOCTOU 窗口 | file_io.py | 分区证 |
| C08-2 | 🟡 | COM基建 | 单位换算收口纪律漂移（17 处直写/反向角度零收口） | 跨 4 模块 | ✅团长（数值正确） |
| C08-3 | 🟡 | COM基建 | 双仓 COM 基建整套双源分叉（AR-4 升级） | aicad/interop vs utils | ✅团长函数级 |
| T09-3 | 🟡 | 测试CI | coverage 宣称 89% vs 实测 87% 口径失真 | AGENTS.md/pyproject | Rita 实测在案 |
| T09-4 | 🟡 | 测试CI | mock 真值陷阱族（4 成员家族级） | tests/* | 批1证据汇编 |
| T09-6 | 🟡 | 测试CI | 文档-测试一致性族（537→538、69→79） | AGENTS.md | ✅（git -S 链定谳） |
| ⚪ 18 项 | ⚪ | 各域 | 详各分区报告问题清单 | — | — |

架构层（Alex AR 系列，经复核）：AR-1 文档 69 陈旧（=J3-2/T09-6 同源）｜AR-2 re-export 缺 10 工具（确认，与 G4 新工具同源现象）｜AR-3 aicad ahead 9 恶化｜AR-4→C08-3 升级｜AR-5 part 域膨胀观察｜AR-6 pattern 数学重建维持｜AR-7 定谳维持 ⚪｜AR-8 计划台账本地化维持 ⚪｜AR-9 双源依赖一致无护栏（◐）。

## 三、上轮对照汇总

| 上轮编号 | 状态 | 本轮实证（一句话） | 分区 |
|---|---|---|---|
| G1 交付 P0 | ✅（主仓） | github/main 与 gitee main 双 0/0；aicad 残留转 AR-3 ❌ | 团长+09 |
| G2 perf 假红 | ✅ | 0762b15 空闲机 18/18 定谳关单 | 09 |
| G3 质量观测 | ◐ | auth ✅/前端测试零→1（vitest 1 文件）/缓存 health 计数在位专项报表无 | 09 |
| G4 零件长尾 | ✅ | 8 工具+测试在册；但恰 8 件在 re-export 缺口（AR-2）+capabilities 陈旧否定（T09-1） | 03 |
| G5 图纸长尾 | ✅/◐ | BOM 表 ✅（三面一致）；爆炸投影留观察项；气泡 BLOCKED 诚实拒绝在位 | 04/05 |
| G6 CSG v2 | ◐ | 4-op→6-op；v2 受限形态+docstring 滞后 | 03 |
| G7 原生阵列 | ⚪维持 | 数学重建未变（远期） | 03/Alex |
| G8 智能自治 | ⚪ | aicad S5 一期 84.2% 收官；v2 评估中 | 09侧写 |
| J3-1 mock 细化 | ❌ | GetLongPathNameW/windll 零 mock，非确定性依赖宿主机 | 06 |
| J3-2 计数 69 | ❌ | AGENTS.md:4 仍 69 | Alex+团长 |
| J3-3 N26 [!] | ➡移除 | 不成立（外审读 diff 旧态） | Alex+团长 |

处置率：已修/闭环 5；部分 3；未修 3（J3-1/J3-2/AR-3）；不成立移除 1；升级 1（AR-4）；维持远期 2。

## 四、复核记录（团长实证）

全部 7 项 🟠 + 抽查 🟡 8 项重证：**确认 14 / 修正 1（AR-3 ahead 数字随审查窗口演进 4→6→9，并行会话在途）/ 移除 0**。关键实证命令留档各分区报告附录与 session-state。F07-1 边界裁决：维持 🟠（一票否决条款 2 精确语义=AI 可控参数路径逃逸；本项为用户 GUI 中介的状态派生写）——裁决理由全文在 session-state 2026-09-06 条目。

## 五、处置建议（修复走 structured-dev-workflow 定档，不在本审查内执行）

**近期修（🟠，建议一批 L2 定档收口，部分需实机）**
1. **文档/capabilities 一次性收口批**（T09-1+AR-1+AR-2+D05-3+P03-4+T09-6+T09-3，可合并提交）：capabilities limitations 重写+防漂移测试改按已注册工具名扫描；server.py 补 10 工具 re-export；AGENTS.md 69→79/537→538/coverage 口径；CSG docstring。——零实机依赖，收益最大。
2. **file_close 三联批**（S06-1+F07-1+F07-2+F07-4）：save 路径过 allowed_root + Save3 typed 容错 + 丢弃/保存确认语义（对齐 overwrite_confirm 哲学）。
3. **口径与回归锁批**（A04-3+A04-4+A04-1）：BOM 质量口径实机定谳（GetMassProperties density 参数语义）+ N32 顺序契约 mock 解耦锁 + config_name 透传（quick win）。
4. **冷启动回流批**（C08-1，需实机）：_launch_and_wait 三件套回流主仓 connect()。

**排期（🟡⚪）**：C08-2 换算收口纪律、C08-3 双源 ADR 化、T09-2 __main__ 修正（2 处 4 行可顺手并入批 1）、P03-1 跨文档原子性（实机复现后立项）、T09-4 mock 家族治理（e2e 定期验证窗）。

**用户动作项**：aicad push（ahead 9 持续扩大——一次 push 清零，G1 残留的最后一块）。

## 六、本轮方法论沉淀

- 编排：奠基串行 2 + 深审 2 批（4+3）全部完成 9/9；**批 2 两子代理同时刻无声阵亡**（报告冻结 97 分钟、任务注册表已无——K-1 速率限制新形态：无失败通知的静默死亡），降级阶梯（主会话亲做）+ K-2 边查边落盘铁则拯救两份报告约 60% 已完成内容零损失回收。
- 复核：交错实证复核 15+ 项零误报——rubric E 铁律 + 一票否决精确化条款有效（F07-1 边界案例按条款语义而非字面裁决）。
- 技能改进点（记 evolve）：「子代理无声阵亡」应增补指纹（报告冻结 N 分钟 + TaskStop 报 No task found 双证）与探活动作（冻结 >10 分钟即接管，勿等）。
- 下次审查输入：本报告处置建议 4 批为对照项；capabilities 重写后的正向快照断言为新增防线锚。
