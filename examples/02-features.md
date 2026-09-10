# F 域：孔 / 阵列 / 装饰 / 编辑（02-features）

> 返回 `examples/INDEX.md`。孔径公差断言按 0.1mm 口径（BRep 几何提取精度）。

### F-01 矩形孔阵

- 你说：「在 100×60×10 的板上开 4 个 ⌀6 通孔，角部均布，孔心距角 15」
- 工具链：`solidworks_part_new` → `solidworks_part_create_plate` → `solidworks_part_create_linear_holes`（4 孔一行/阵列语义按工具参数）
- 验收：`hole_count` 类检查返回 4；每孔 ⌀6（±0.1）；`get_bounding_box` 不变 [100,60,10]。

### F-02 环形孔阵

- 你说：「在 ⌀100 的法兰盘上开 8 个 ⌀8 的通孔，孔心圆周 ⌀70」
- 工具链：`solidworks_part_new` → `solidworks_part_create_cylinder` → `solidworks_part_create_annular_pattern`（或 `pattern_annular_layout`）
- 验收：8 孔均布 45° 间隔；孔心距圆心 35±0.1；体积差 = 8×π×4²×厚。
- 说明：SW 原生阵列特征 API 不可直调（探针实证），实现走等价几何重复——结果一致，特征树形态不同。

### F-03 圆角与倒角

- 你说：「给盒子顶面四条棱 R3 圆角，再给底面边缘 2×45° 倒角」
- 工具链：`solidworks_part_create_box` → `solidworks_part_apply_fillet`（R3）→ `solidworks_part_apply_chamfer`（2mm）
- 验收：体积小于原盒（圆角/倒角减料）；特征树出现圆角/倒角特征。
- 注意：装饰几何链有面不相邻约束（同面圆角后再倒角可能被 SW 拒——分开不相邻面操作）。

### F-04 抽壳

- 你说：「把 60×40×20 的盒子抽成 2mm 壁厚，顶面开口」
- 工具链：`solidworks_part_create_box` → `solidworks_part_apply_shell`（厚 2，移除面=顶面）
- 验收：内腔 56×36×18；体积 ≈ 外体积 − 内腔（边界精度 ±1%）。

### F-05 拔模与圆顶

- 你说：「给盒子的四个侧面 3° 拔模」；变体：「在圆柱顶面加一个高 5 的圆顶」
- 工具链：`solidworks_features_apply_draft`（中性面+拔模面语义）/ `solidworks_part_apply_dome`
- 验收：拔模后顶面尺寸小于底面；圆顶体积增量 ≈ 球冠公式（⌀20 顶+5 高 ≈ 850.85mm³，实证精确）。

### F-06 改尺寸与回滚（编辑流）

- 你说：「把拉伸深度改成 30，然后删掉圆角特征」
- 工具链：`solidworks_dimension_set`（或 angle 变体）→ `solidworks_feature_delete`
- 验收：bounding box z 从原值变 30；特征树中圆角消失；`solidworks_features_list` 复核。
- 注意：孔径若由草图几何驱动（非尺寸驱动），改径=删特征重建而非改尺寸——客户端会按特征类型选择路径。
