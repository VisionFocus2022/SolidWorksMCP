# 合格机械图验收清单 v1（机器可断言项）

> 适用对象：aicad HLR SVG 通道产出的工程图（SW MCP 重建链路的出图端）。
> 原则：v1 只收录可由脚本/测试自动断言的检查项；语义类标准（尺寸标注合理性、
> 视图选择惯例、公差完备性）明确推迟到 v2。

## 1. 三视图 polyline 非空

- 断言点：`drawing_stats.json` → `stats.view_count >= 3` 且 `stats.edge_count > 0`
  （`edge_count` 为各视图 visible+hidden 折线段总和，来源 `aicad/aicad/drawing/hlr.py:215-225`）。
- 生成前置：`views_extent_check(views)` 必须通过（`aicad/aicad/api/deps.py:366`，
  模型包围盒各轴非零的守卫）。

## 2. 总体尺寸非零（M1 标注）

- 断言点：模型 bbox 三轴尺寸全部 `> 0`（总体尺寸标注直接取自模型 bbox，
  见 `aicad/aicad/drawing/hlr.py:159-166` `_VIEW_DIM_AXES`）。
- 由 `ensure_drawing_artifact` 的 extent 守卫间接保证；e2e 脚本可对
  `stats.sheet_width_mm > 0 && stats.sheet_height_mm > 0` 再加显式断言。

## 3. BOM 行数 > 0

- 断言点：`drawing_stats.json` → `bom_row_count >= 1`
  （来源 `aicad/aicad/drawing/hlr.py:224` 与 `aicad/aicad/api/deps.py:383`）。

## 4. drawing_ready 事件恰好一次

- 断言点：首次物化后 `aicad/aicad/api/routes_drawing.py:43-51` 向会话事件流
  追加 `drawing_ready`（fresh=True）；缓存命中不重复发。e2e 断言事件流中
  该事件出现次数 == 1，且负载含 `drawing_url`、`stats`、`bom_row_count`。

## 5. 三件套产物落盘

- 断言点（SW 侧链路）：`output/` 下同基名 `.sldprt`、`.step`、`.svg` 三文件
  存在且非空（SLDPRT/STEP 由 SW COM 保存导出，SVG 为 HLR 工程图）。
- 已实测（2026-08-30）：`tools/validate/triple_artifact.py` 退出码 0 —— 同一
  环件脚本双引擎产出 `ring.svg`（HLR 三视图 edge_count=32）+ `ring.sldprt`
  （rebuild_csg_plan 2 特征保存）+ `ring.step`（COM 导出）同目录落盘，报告
  `output/triple-artifact-20260830-192223/report.json`；体积自洽另见
  `tools/validate/csg_roundtrip.py`（rel_diff 2.9e-16，±1% 门限）。

## 6. 体积窗口（几何自洽）

- 断言点（SW 侧链路）：重建零件质量属性体积落在闭式公式 ±2% 窗口内
  （圆台 V=πh/3·(R²+Rr+r²)；板+孔=板体积−Σ孔圆柱）。已验证精度可达 1e-15
  相对误差（2026-08-29 cone 核销实测）。

## v1 明确排除（推迟到 v2）

- 定形尺寸链（孔位/孔径标注）、公差符号、表面粗糙度符号。
- 图框与标题栏、图幅规格（A3/A4）合规性。
- DXF/DWG/PDF 矢量导出。
- 视图布局与制图惯例的语义正确性（需人工或更强模型评审）。
