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
| probe_sheet_metal_thread.py | 钣金基体法兰/真实螺纹 | BaseFlange 16 参（PCBA=Nothing）；InsertHelix 10 参 def=0 可建可选中（REFERENCECURVES）但 InsertCutSwept4 三形态零产出 BLOCKED | T21 |
| probe_featuremgr_enum.py | FeatureManager 类型库枚举 | makepy def 签名：FLP4=20 参/FLP5=22、InsertMirrorFeature2=5 参(ScopeOptions)、InsertMultiFaceDraft=6 参、InsertCutSwept5=22 参(CircularProfile)；枚举常量不在 makepy vars()，需 PowerShell 反射 swconst.dll（swFmLPattern=6/swFmLocalLPattern=108/swFmSweepThread=87） | N9 |
| probe_n9_unblock.py | mirror/draft/pattern/螺纹解锁 | 13 轮收敛 3/4：mirror=InsertMirrorFeature2(...,ScopeOptions=0)+基准面 mark2；draft=typed FM InsertMultiFaceDraft+拔模面 mark1 先中性面 mark2 后；thread=helix REFERENCECURVES mark4+InsertCutSwept5(**Alignment=False**)+CircularProfile；pattern BLOCKED（直调全组合零产出/AccessSelections serverfault/属性 put 编组崩）→生产走数学替代；typed FM 铁律+call_or_value 方法/属性二义 | N9 |

## probe_assembly/ — 装配域

| 脚本 | 验证对象 | 有效结论 | 任务 |
|---|---|---|---|
| probe_assembly_extras.py | 新建装配/干涉/BOM/mate 常量 | AddComponent4 要求零件预开；InterferenceDetectionManager 干涉/体积；AddMate5 角度走 Angle 槽；tangent=4/angle=6/width=17 | T11 |
| probe_interference_transform.py | 干涉空间/组件变换/mate 删除 | GetInterferenceBody→GetBodyBox()+GetMassProperties(1000)[0:3]；TransformComponent2 已移除→CreateTransform(16 元素 VARIANT)→SetTransformAndSolve3(替换式)+EditRebuild3 才刷新；mate 删除=SelectByID2(name,"MATE")+EditDelete（复检须含 MateGroup 一层子特征）；装配面选择唯一可靠=IEntity(face).Select2；typed 包装 gencache.GetModuleForProgID | N8 |
| probe_tangent_width.py | tangent mate 复验 + delete_mate 闭环 | 面遍历 GetNextFace 仅 typed 可达；面积最大面启发（box 顶面 2400/cyl 侧面 2513 mm²）；AddMate5(4)→「相切1」实机成功；生产 delete_mate 删除复检通过；width 需 4 面 fixture→N15 | N8 |

## probe_drawing/ — 工程图域

| 脚本 | 验证对象 | 有效结论 | 任务 |
|---|---|---|---|
| probe_drawing.py | 建图/三视图/标注/导出 | 模板 GetUserPreferenceStringValue(10)；Create1stAngleViews2 恒 False→手动三视图；InsertModelAnnotations2(0,True,0,True,True,False) 唯一有效；PDF/PNG SaveAs3 | T12 |
| probe_dim_organize_section.py | 尺寸遍历/删除/错开+剖视图 | GetDisplayDimensions 零参属性；删除链 GetNameForSelection→SelectByID2("DIMENSION")→DeleteSelection(True)；SetPosition 错开；CreateSectionViewAt4(x,y,0,草图名,0,0) | N4 |
| probe_section_debug.py | 剖切线放置契约 | 剖切线必须画 sheet 空白区（视图区域上的线归视图草图→失败）；At5/ICreate/MakeSectionLine 全拒；SW 长会话后 InsertModelAnnotations2 可能零产出，重启恢复 | N4 |
| probe_tolerance_finish_dxf.py | 公差/粗糙度/注释/DXF | IDimension 需 makepy 静态包装（mods.IDimension(dim._oleobj_)）；SetToleranceType(5)+SetToleranceValues(min,max 米)；粗糙度 14 参签名；CreateText2；DXF SaveAs3 恒返 1，判据=文件+SECTION 头 | N5 |

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
