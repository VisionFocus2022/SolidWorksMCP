# O 域：材料 / 属性 / 治理（05-ops）

> 返回 `examples/INDEX.md`。

### O-01 设材料与质量属性

- 你说：「把当前零件设为合金钢，读质量属性」
- 工具链：`solidworks_part_set_material` → `solidworks_part_get_material`（回读确认）→ `solidworks_part_get_mass_properties`
- 验收：材料回读=所设名；质量 = 体积×密度（合金钢 ≈ 7.85 g/cm³）。
- 坑：材料名走本机 SW 语言（中文版=「合金钢」）；设材料后质量联动偶有延迟——重算后复核。
- 变体：`solidworks_part_list_bodies`（多实体件逐体信息）。

### O-02 方程式联动

- 你说：「加方程式让全局变量 Height = Width × 0.6，然后改 Width=100 看 Height」
- 工具链：`solidworks_part_add_equation` → `solidworks_dimension_set`（改 Width）→ `solidworks_part_list_equations`
- 验收：Height 自动变 60；方程式列表含该式。
- 进阶：`edit_equation` / `delete_equation`。

### O-03 自定义属性与测量

- 你说：「给零件加自定义属性 Project=Sample-01、Rev=A，然后测量原点到顶面右上角点的距离」
- 工具链：`solidworks_part_set_custom_property` → `solidworks_part_get_custom_properties`（回读）→ `solidworks_measure_distance`
- 验收：属性回读一致；距离 = 对角线长 √(x²+y²+z²)（按盒子尺寸理论值核对）。
- 相关：`solidworks_part_activate_configuration` / `add_configuration`（配置族管理）；`solidworks_part_apply_shell` 见 F-04。
