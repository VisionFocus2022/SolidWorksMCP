# D 域：图纸与导出（04-drawing-export）

> 返回 `examples/INDEX.md`。图纸默认 A3/GB 模板自动发现（user-guide §5）；导出路径必须在 ALLOWED_ROOT 内。

### D-01 从零件出三视图工程图

- 你说：「给当前零件出三视图工程图」
- 工具链：`solidworks_drawing_create_from_part`（主视图+两个展开视图）
- 验收：图纸含 3 个模型视图；标题栏来自 GB 模板（若机器装有 gb_a* 模板）。
- 坑：SW2026 的一键三视图 API 恒失败（实证），实现=手动逐视图放置——结果等效。

### D-02 入图标注

- 你说：「把模型尺寸自动标进三视图」
- 工具链：`solidworks_drawing_insert_dimensions`（模型注解自动入图）
- 验收：视图含尺寸注解；数量与零件驱动尺寸数一致（草图几何驱动的孔除外）。
- 进阶：`organize_dimensions` 错开重叠、`set_tolerance` 加公差、`insert_note` 文字注记。

### D-03 工程图 BOM 表 + PDF 导出

- 你说：「装配工程图插入 BOM 表，导出 PDF」
- 工具链：`solidworks_drawing_insert_bom_table` → `solidworks_drawing_export_pdf`
- 验收：PDF 生成且含 BOM 表格；字节头 `%PDF`。
- 说明：气泡标注（AutoBalloon）族 API 不可用（BLOCKED，探针实证）——表格式 BOM 完整可用。

### D-04 全格式导出

- 你说：「当前零件依次导出 STEP、STL、DXF 到 D:\CAD_Work\out\」
- 工具链：`solidworks_file_export_step` / `solidworks_file_export_stl` / `solidworks_file_export_dxf`
- 验收：三文件齐；STEP 可被重新导入（见 D-05）。
- 注意：DXF 针对平面图/钣金件最有意义；3D 零件导 DXF 取决于 SW 的 2D 投影。

### D-05 导入外来 STEP 再加工

- 你说：「导入 D:\CAD_Work\supplier_bracket.step，看看它的特征和包围盒」
- 工具链：`solidworks_file_import_step` → `solidworks_features_list` / `solidworks_get_bounding_box`
- 验收：导入成功（3D Interconnect 路径）；返回体信息/尺寸。
- 坑：外来格式必须走 LoadFile4 通道（OpenDoc6 拒开 STEP，实证）；路径必须**绝对路径**。
