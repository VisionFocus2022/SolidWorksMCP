# CSG 契约 v3 互证矩阵（N54，2026-09-10）

> **v3 增量**：导出方向（build123d 脚本 → SW op 序列）的识别面扩展——方法风格 CSG（`.cut()`/`.fuse()`）、
> 字面列表/星号实参展开、`extrude(RegularPolygon(R,n), h)` → `polygon_prism` op（含方法式 `.extrude` 防御分支）。
> **互证锚点**：六角柱 build123d 实跑体积 vs SW `create_polygon` 体积公式 `N/2·R²·sin(2π/N)·h`
> —— **rel diff 2.33e-16**（v2 ring 基准 2.9e-16 同数量级，逐位一致）。

## 1. 双向覆盖矩阵（诚实边界表）

| 几何域 | 导出方向（脚本→SW op） | 重建方向（SW→脚本） | 互证态 |
|---|---|---|---|
| box（首建） | ✅ `box` | ✅ v2 | 离线互证（既有） |
| cylinder 堆叠 | ✅ `cylinder` | ✅ v2 | 离线互证（既有） |
| cone 堆叠 | ✅ `cone` | —（重建方向未做，观察项） | 单向 |
| cut_cylinder（任意心位） | ✅ | ✅ v2 | 离线互证（既有） |
| **polygon_prism（首建）** | ✅ **v3**（`extrude(RegularPolygon, h)` / `.extrude(h)`） | ✅ v2（主仓 `CSG_V2_OPS` 消费端，字段 sides/circumradius/height/inscribed/at 逐字对齐） | **离线公式互证 2.33e-16**；SW 实机 roundtrip 留观察项（SW 未运行窗口） |
| swept_arc（首建） | ❌（build123d 弧扫描语法不在确定性子集） | ✅ v2 | 单向（重建向） |
| `.cut()`/`.fuse()` 方法风格 | ✅ **v3**（与中缀 `-`/`+` 同语义） | n/a（风格层） | 单测等价性钉死 |
| 字面列表 / `*starred` 实参 | ✅ **v3**（拍平展开） | n/a | 单测 |
| 列表推导（`[... for x in ...]`） | ❌ 循环语义不可确定性折叠——如实归类不猜 | n/a | 边界（单测钉住拒绝） |
| 未 extrude 的 RegularPolygon | ❌（非体，拒绝带原因） | n/a | 边界 |
| 非首个 polygon/box | ❌（消费端 first-op-only 契约） | 同 | 边界 |
| Pos 偏移 profile | ❌（堆叠轴向约束） | 同 | 边界 |

## 2. 语义对齐注记（零损关键）

- **半径语义**：build123d `RegularPolygon(R, n)` 的 R=顶点距（外接圆半径）＝ SW `create_polygon(sides, radius, h, inscribed=True)` 的 inscribed=True 外接半径——**逐位一致**，export 恒产 `inscribed: true`。
- **方法风格等价性**：`body.cut(a, *b)` ≡ `body - a - b`（测试钉死 ops 序列相等）；`.fuse` ≡ `+`。
- **消费端零改动**：主仓 `rebuild_csg` 的 v2 校验器/执行器直接消费 v3 导出的 polygon_prism op（字段名逐一核对 design.py 校验器源码）。

## 3. SW 实机 roundtrip 观察项

离线互证已覆盖「识别面→op 契约→SW 语义公式」三方一致；**SW 实机**建 polygon_prism→导出脚本→再识别的
闭环留 SW 运行窗口执行（与 N52 GTOL e2e 同窗口，届时一并补）。

## 4. 证据

- 测试：`tests/test_csg_export.py` +9（方法风格/starred 列表/polygon_prism 导出/堆叠/未 extrude 拒/
  first-only 拒/ListComp 边界/函数式 extrude 真实形态）
- 互证运行：本节头部数字（2026-09-10 实跑，Sandbox 真实 build123d）
- hex_nut_plate（评测集任务）完整 mock 现已 100% 识别（`polygon_prism` + `cut_cylinder`）
