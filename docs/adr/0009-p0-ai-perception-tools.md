# ADR-0009：P0「AI 可感知模型」工具族的决策（T3-T5 及后续）

日期：2026-08-30 · 状态：已接受（实机验证）

## 背景

二期优化计划（output/optimization-plan-2026-08-29.md）判断：AI 经 MCP 操作
SolidWorks 的核心断点不是「能建」，而是「能看」——特征只有名字、没有尺寸，
面没有可引用的实体名，测量缺失。T3-T5（特征详情/测量/面命名）为此而设，
T9（尺寸读写）与 T7（装饰特征）建立在其上。

## 决策

### 1. 面命名：模型侧 SetEntityName，AI 侧按名引用

- **决策**：`topology.list_faces` 遍历面时对**未命名**面以稳定前缀
  （Face0…FaceN，`model.SetEntityName`，宿主是 ModelDoc2 而非 Extension）
  命名；已命名实体不覆盖，前缀可配。
- **依据**：SelectByID2 按名选不中 FACE（三种名形态全 False，T5 实测）；
  面的可靠选择机制 = 遍历 + `face.Select2(append, mark)`。命名让
  mate/fillet/剖切等后续操作可引用，且跨保存重开持久。
- **代价**：面序号随特征变化可能漂移——长会话中重命名风险由「只命名
  未命名面」缓解；引用失效时 AI 重跑 list_faces 即可。

### 2. 尺寸：只读优先，写入走米制契约

- **决策**：详情（`GetSystemValue3(1,"")`）统一换算 mm 输出；写入
  （`Parameter(name).SetSystemValue3(m,1,"")`）入参 mm 内部转米，负返回码
  =拒绝。角度维度 v1 不支持（弧度语义未定）。
- **依据**：实机 GetSystemValue3 动态 dispatch 返回裸 float、typed 返回
  元组——归一化函数统一兼容；改尺寸后强制 EditRebuild3 并回读验证。

### 3. 判据：API 返回值不可靠时以特征树/回读为准

- FeatureFillet 返回值 None/int 与成败无关；EditDelete 返回 void。
- **决策**：凡 void/不可靠返回的写操作，成功判据 = 特征树差集
  （latest_feature_name 前后比）或属性回读。此模式贯穿 T7-T12。

## 后果

- AI 工作流成型：list_faces → 命名 → add_mate/apply_fillet（装配与装饰
  共用一套实体引用）；get_feature_details → dimension_set（参数化闭环）。
- 中文 SW 的本地化名（凸台-拉伸1）由「树末特征+显式 rename」规避，
  工具返回统一 ASCII 名。
- 遗留更新（N8，2026-08-30）：装配中 face 按名选择仍不可用（quirk #12）；
  但 IEntity 包装路径（`comp.GetBody() → GetFirstFace → IEntity.Select2`）
  在装配上下文可靠。tangent mate 经此路径实机验证通过（AddMate5(4) →
  「相切1」，probe_tangent_width.py）；width mate 需 4 面选择的槽/薄片
  fixture，联动 N15。
