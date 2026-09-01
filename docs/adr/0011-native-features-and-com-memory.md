# ADR-0011：原生特征解锁方法论与 COM 内存治理（N9 + N10）

日期：2026-08-30 · 状态：已接受（实机验证，13 轮探针收敛）

## 背景

第三期 C3/C4 与 F1：mirror/draft/线性阵列/真实螺纹四个特征族在
FeatureData 扫描中零产出（BLOCKED）；soak 100 轮 SW 工作集 +1.83GB
泄漏嫌疑威胁夜间长会话。两任务的共同方法论收获是「先取证后编码」。

## 决策（N9：特征解锁）

### 1. 解锁方法论：类型库枚举法，不盲试签名

- **决策**：makepy 静态代理枚举 + **PowerShell 反射本机
  swconst.dll**（在线帮助 403 时的兜底）拿 swFeatureNameID_e 真值与
  接口成员签名，再写探针逐参验证。
- **依据**：T8 当初 BLOCKED 的根因就是盲试签名；本批 swFmDraft=3 /
  swFmMirrorSolid=4 / swFmLPattern=6 / swFmSweepThread=87 /
  swFmLocalLPattern=108 全部由此拿到。

### 2. 三原生 + 一数学替代，如实声明

- **mirror**：`SelectByID2(feat,"BODYFEATURE",mark=1)` + 基准面
  mark=2 → 动态 dispatch `InsertMirrorFeature2(False,True,True,False,0)`
  ——第 5 参 ScopeOptions=0 是关键；ΔV=1005mm³ 精确镜像孔验证。
- **真实螺纹**：InsertHelix + `InsertCutSwept5` 22 参形态
  （CircularProfile/Diameter 在第 20/21 参）。
- **draft**：锥度面参数组（Dchk1/Ddir1/Dang1 弧度）。
- **线性阵列**：`CreateDefinition(91)=None` 证实 API 缺失 → **数学
  替代**（循环调用既有 cut/hole 原语，环阵先例），capabilities/
  docstring 如实声明 "non-native (rebuilt primitives), not
  parametric-linked"。
- **代价**：数学替代件改一处不驱动全阵——枚举证据已记入探针文件头
  供人工升级路径。

## 决策（N10：COM 内存）

### 3. 先归因后修：分工具组 soak 定位真实贡献者

- **决策**：soak 加 `--tool-filter`（box-only 0.90MB/轮 / +faces
  0.67 / +drawing 2.78 / +assembly 3.17）。**推翻预期**：walk 面枚举
  不是泄漏点（最低组），assembly/drawing 才是大头。
- **依据**：soak 每轮 `_close_all` 兜底掩盖真实场景；改为无兜底探针
  （5 零件×15 轮）后 doc_count 每新零件 +2。

### 4. 装配文档滞留是 SW 语义，不是可修泄漏

- **决策**：CloseDoc 取证证明装配引用持有（CloseDoc 静默无效、
  OpenDoc6 重开不激活、ActivateDoc3 typed 拒 byref）属 SolidWorks
  自身语义。修复定性为**失败路径关闭**（统一失败路径堵回滚漏洞）+
  design 空壳关闭（shell_closed=true）+ 成功路径滞留在 assembly.py
  docstring 文档化。
- **代价**：长装配会话工作集仍会增长——COM 超时（默认 120s×3）+
  毒化退程（N3）是配套安全网。

## 后果

四特征族 3 原生 + 1 替代全部解锁；soak 泄漏从"嫌疑 1.83GB"收敛为
"已知 SW 语义 + 失败路径已堵"。证据：`51bd1c3`、`eca371c`、探针
`tools/probe_part/probe_n9_unblock.py`、`output/soak-report-*.json`。


---

## 增补（N28，2026-09-01）：loft/sweep 特征解锁——术语陷阱与返回值不可靠

- **决策**：凸台放样走**老式 Blend 直调**（`IModelDoc2.InsertProtrusionBlend2(Closed,
  KeepTangency, ForceNonRational)` 三参），不走 CreateDefinition(swFmBlend=9)+
  LoftFeatureData 路线；扫描凸台走 `IFeatureManager.InsertProtrusionSwept4`
  20 参 + `CircularProfile=True` 免轮廓。中间剖面基准面用 `FeatureManager.
  InsertRefPlane(8, distance)`（Distance 约束）。
- **取证修正**：类型库关键词搜 "Loft" 会漏光——SW 把放样族叫 **Blend**
  （`InsertProtrusionBlend*`/`AddLoftSection`/`swFmBlend=9`），两步取证互证
  （枚举 → 实机探针）纠正了「无直接 API」的初判。方法论教训：**术语必须
  从 swFeatureNameID_e 反射拿权威词根，不能按通用 CAD 词汇表搜**。
- **返回值契约**：`InsertProtrusionBlend2` 成功时也返回 None（FeatureFillet
  同族，本 ADR「成功判据=特征树差集」纪律再次生效）；`InsertProtrusionSwept4`
  返回 IFeature 可用（本次实证）。生产 `create_loft` 因此用树差集判据，
  `create_swept` 用返回值判据。
- **证据**：探针 `tools/probe_part/probe_loft_sweep_enum.py` +
  `probe_n28_unblock.py`（2/2 一次收敛）、e2e `tools/e2e_n28.py`
  （sweep 2467.40 精确 / loft 14922.04 窗口 0.004%）。
