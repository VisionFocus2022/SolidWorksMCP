# tools/ 探针与验证脚本索引

> 每个探针 = 一份实机 API 取证记录（探针先行协议，§2.4）。
> 有效签名结论同步在各任务执行记录与 `solidworks_api/` 各模块 docstring。
> 目录按域分组（T18，2026-08-30）；脚本用 `parents[2]` 定位仓库根。

## probe_part/ — 零件/特征/面域

| 脚本 | 验证对象 | 有效结论 | 任务 |
|---|---|---|---|
| probe_face_naming.py | 面枚举与命名 | SetEntityName 宿主是 ModelDoc2；SelectByID2 按名选不中 FACE——面选择=遍历+face.Select2(False,0) | T5 |
| probe_revolve.py | 旋转特征 | FeatureRevolve2 20 参实际顺序以 typelib 为准；ConstructionGeometry 中心线为轴 | T6 |
| probe_fillet_chamfer.py | 圆角/倒角 | FeatureFillet 5 参旧版可用；FeatureFillet3+ variant 数组编组不稳（RPC_E_SERVER_FAULT） | T7 |
| probe_shell_draft_mirror_pattern.py | 抽壳/拔模/镜像/阵列 | InsertFeatureShell(米,False) 可用；mirror/pattern 9 组合零产出 BLOCKED；DraftBody 数组编组崩 | T8 |
| probe_front_blind_bands.py | 前视盲孔/深度带 | 前视面上盲孔的深度-平面映射 | 治理期 |
| probe_hole_plane_context.py | 孔-平面上下文 | cut 特征的平面上下文选择 | 治理期 |
| probe_imported_annular_cut.py | 导入体环形切除 | STEP 导入体上的 annular cut | 治理期 |

## probe_assembly/ — 装配域

| 脚本 | 验证对象 | 有效结论 | 任务 |
|---|---|---|---|
| probe_assembly_extras.py | 新建装配/干涉/BOM/mate 常量 | AddComponent4 要求零件预开；InterferenceDetectionManager 干涉/体积；AddMate5 角度走 Angle 槽；tangent=4/angle=6/width=17 | T11 |

## probe_drawing/ — 工程图域

| 脚本 | 验证对象 | 有效结论 | 任务 |
|---|---|---|---|
| probe_drawing.py | 建图/三视图/标注/导出 | 模板 GetUserPreferenceStringValue(10)；Create1stAngleViews2 恒 False→手动三视图；InsertModelAnnotations2(0,True,0,True,True,False) 唯一有效；PDF/PNG SaveAs3 | T12 |

## probe_properties/ — 材料与属性域

| 脚本 | 验证对象 | 有效结论 | 任务 |
|---|---|---|---|
| probe_material_props_eqs.py | 材料/自定义属性/方程式/配置 | byref VARIANT(VT_BSTR) 铁律；材料名必须中文；Add3/Add2/AddConfiguration 返回形态 | T17 |

## validate/ — 验证与巡检脚本

| 脚本 | 用途 | 任务 |
|---|---|---|
| validate_annular_pattern.py | annular pattern 实机验证 | pattern 交付 |
| validate_cone_thread.py | 锥/螺纹孔实机验证 | 治理期 |
| inspect_golden_cyls.py | 金标圆柱几何巡检 | 治理期 |
| inspect_planar_faces.py | 平面巡检 | 治理期 |
| inspect_step_geometry.py | STEP 几何巡检 | 治理期 |

## 根目录

| 脚本 | 用途 |
|---|---|
| e2e_sw_smoke.py | 全工具实机冒烟（T1 建立，每任务追加；62 步） |
| run_pytest_guarded.py / run_suite_traced.py | 测试运行器（守卫/追踪） |
