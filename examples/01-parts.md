# P 域：基础件与成形（01-parts）

> 返回 `INDEX.md` 看全部 24 卡。单位一律毫米（mm）。

### P-01 第一个盒子（全链入门）

- 你说：「新建一个 60×40×10 的盒子，测量它的包围盒，然后导出 STEP 到 D:\CAD_Work\first_box.step」
- 工具链：`solidworks_part_new` → `solidworks_part_create_box` → `solidworks_get_bounding_box` → `solidworks_file_export_step`
- 验收：bounding box = [60, 40, 10]（±0.5）；导出返回文件路径且文件存在。
- 前置：SW 已运行；D:\CAD_Work 在 ALLOWED_ROOT 内。

### P-02 圆盘 / 圆环 / 圆锥

- 你说：「新建一个 ⌀60 的圆盘，厚 10」；变体：「内孔 ⌀40 的圆环」「底 ⌀50 顶 ⌀20 高 30 的圆锥」
- 工具链：`solidworks_part_new` → `solidworks_part_create_cylinder`（圆盘）/ `solidworks_part_create_plate`+`solidworks_part_cut_round_hole`（环）/ `solidworks_part_create_cone`
- 验收：圆盘体积 ≈ π×30²×10 = 28274（±1%）；圆锥体积 ≈ π×h/3×(R²+Rr+r²) = π×30/3×(625+250+100) = 31416×0.975 ≈ 30630（±1%）。

### P-03 旋转成形体（轴类回转件）

- 你说：「画草图：从原点起 20×15 的矩形轮廓加一条中心线，绕中心线旋转 360° 成实体」
- 工具链：`solidworks_part_new` → `solidworks_part_create_revolved`
- 验收：体积 ≈ π×(15²)×20 ≈ 14137（轮廓在轴线一侧时）；特征树出现旋转特征。
- 说明：轴=草图内构造几何中心线（绕模型 Y）；角度按弧度语义处理。

### P-04 扫描件（圆截面沿弧路径）⚠

- 你说：「前视面上画一条 R20 的 90° 圆弧作路径，扫一个 ⌀10 的圆截面实体」
- 工具链：`solidworks_part_new` → `solidworks_part_create_swept`（圆截面免轮廓：路径 mark4 + CircularProfile）
- 验收：⚠ 体积 2467.40mm³（e2e_n28 实证，理论圆环四分之一段精确吻合）。

### P-05 放样件（变截面过渡）⚠

- 你说：「底面 ⌀10 圆、距 30 的平行面上 ⌀15 圆，两剖面之间放样」
- 工具链：`solidworks_part_new` → `solidworks_part_create_loft`（剖面自动建基准面）
- 验收：⚠ 体积 14922.04mm³（e2e_n28 实证；理论圆台 14922.57，差 0.35%，断言窗口 ±1%）。

### P-06 六角柱与腰形槽 ⚠

- 你说：「新建 R20 正六边形柱，高 10」；变体：「在顶面开一个 50×10 的腰形槽」
- 工具链：`solidworks_part_new` → `solidworks_part_create_polygon` / `solidworks_part_create_slot`
- 验收：⚠ 六角柱 2598.08mm³（0.000% 精确）；腰形槽面积 = L×W+π(W/2)²（1186.19mm² 实证 0.000%）。
- 注意：`create_polygon` 的 R=顶点距（对边距 = R×√3）。
