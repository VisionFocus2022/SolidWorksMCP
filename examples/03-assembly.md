# A 域：装配（03-assembly）

> 返回 `examples/INDEX.md`。装配域工具需零件文件已在 ALLOWED_ROOT 下。

### A-01 两件装配（底板+立柱）与配合

- 你说：「新建装配，把 base_plate.sldprt 放进来，再放 pillar.sldprt，把立柱底面贴合底板顶面并对中」
- 工具链：`solidworks_assembly_new` → `solidworks_assembly_add_component`（×2，组件需先在会话中打开）→ `solidworks_assembly_add_mate`（重合/同轴心）
- 验收：`solidworks_assembly_list_components` 显示 2 件；立柱底面 z = 底板顶面 z；无悬空自由度残留（按约束数核对）。
- 坑：组件添加是**替换式变换**语义——位置经 transform 落定后需 rebuild 刷新。

### A-02 干涉检查

- 你说：「检查装配里的干涉」
- 工具链：`solidworks_assembly_check_interference`
- 验收：无干涉返回空/0；故意重叠两件后返回干涉体积（mm³）与涉及组件清单。

### A-03 装配 BOM

- 你说：「列出装配的物料清单」
- 工具链：`solidworks_assembly_get_bom`
- 验收：BOM 行数=去重后组件种类数；含路径/引用配置/数量。

### A-04 爆炸视图

- 你说：「给装配做自动爆炸」
- 工具链：`solidworks_assembly_explode`（AutoExplode）→ `ShowExploded` 切换显示态
- 验收：特征树新增爆炸特征；`solidworks_features_list` 可见爆炸视图项。
- 说明：手工步进爆炸（AddExplodeStep）属进阶路径，客户端按需组合。
