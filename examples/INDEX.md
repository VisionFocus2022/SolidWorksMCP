# 示例库 INDEX（N49 首波，24 张卡）

> 用法：开 SolidWorks → 在 MCP 客户端里**照抄「你说」**那句话（参数按需改）→ 对照「验收」行检查产出。
> 卡片编号域：P=零件 / F=特征 / A=装配 / D=图纸与导出 / O=材料属性与治理。
> 前置说明：所有示例需 SolidWorks 已运行且 connect 成功；文件类操作路径必须在 ALLOWED_ROOT 之内。
> 标注 ⚠ 的验收数字来自仓库 e2e 实证记录（tools/e2e_*.py），其余为几何理论值。

| # | 卡片 | 域文件 |
|---|---|---|
| P-01 | 第一个盒子（建件→测量→导出 全链入门） | 01-parts.md |
| P-02 | 圆盘 / 圆环 / 圆锥 | 01-parts.md |
| P-03 | 旋转成形体（轴类回转件） | 01-parts.md |
| P-04 | 扫描件（圆截面沿弧路径）⚠ 体积 2467.40mm³ 精确 | 01-parts.md |
| P-05 | 放样件（变截面过渡）⚠ ⌀10→⌀15 距 30 圆台 14922.04±1% | 01-parts.md |
| P-06 | 六角柱与腰形槽 ⚠ 2598.08 / 1186.19mm² 0.000% | 01-parts.md |
| F-01 | 矩形孔阵（4×⌀6 均布） | 02-features.md |
| F-02 | 环形孔阵（8 孔均布 ⌀70 圆周） | 02-features.md |
| F-03 | 圆角与倒角（装饰链） | 02-features.md |
| F-04 | 抽壳（薄壁盒） | 02-features.md |
| F-05 | 拔模与圆顶 | 02-features.md |
| F-06 | 改尺寸与回滚（编辑流） | 02-features.md |
| A-01 | 两件装配（底板+立柱）与配合 | 03-assembly.md |
| A-02 | 干涉检查 | 03-assembly.md |
| A-03 | 装配 BOM | 03-assembly.md |
| A-04 | 爆炸视图 | 03-assembly.md |
| D-01 | 从零件出三视图工程图 | 04-drawing-export.md |
| D-02 | 入图标注（模型尺寸自动入图） | 04-drawing-export.md |
| D-03 | 工程图 BOM 表 + PDF 导出 | 04-drawing-export.md |
| D-04 | 全格式导出（STEP/STL/DXF） | 04-drawing-export.md |
| D-05 | 导入外来 STEP 再加工 | 04-drawing-export.md |
| O-01 | 设材料与质量属性 | 05-ops.md |
| O-02 | 方程式联动（改一参数全联动） | 05-ops.md |
| O-03 | 自定义属性与测量 | 05-ops.md |

**已知边界（诚实声明）**：镜像/阵列特征、筋、combine、气泡标注等族工具受 SolidWorks API 限制为数学替代实现或不可用（详见 `tools/INDEX.md` 各探针结论）；涉及这些域时客户端会用等价几何手段达成意图。
