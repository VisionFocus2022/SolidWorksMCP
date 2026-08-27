# SolidWorksMCP 架构解析与量化评估（①+②）

**版本**: 1.0
**日期**: 2026-08-28
**审查对象**: `E:\SolidWorks 2026\SolidWorksMCP\SolidWorksMCP`（solidworks-mcp 0.3.0）
**审查档位**: 架构审查 L3（深度档：①+②+③ + 环境重建验证）｜ **SDW 定档**: 🔴 L3
**关联文档**: ③ 实施规划见 `docs/tasks-solidworksmcp-optimization.md`
**方法论**: architecture-review v2.8（测量优先 / 双源验证 / 已验证-推断强制标注 / 路径行号真实 / 完整性可见）

> **SDW 定档声明**：档位 🔴L3；确定性 低（审查前问题分布未知，需证据驱动）；影响半径 大（全面优化跨多模块；命中架构审查后果风险硬触发器 #5「无版本管理/无回滚机制」——父目录 .git 为空目录、项目根无 .git，git 命令报 not a repository，已验证）；规模 审查面约 5700 行（源码 3929 + 测试 1433 + tools 366）；可逆性 单向门成分（无 VCS），已以 `.audit-backup-20260828/` 文件级备份缓解；依据 低确定 × 大影响 → 主矩阵 L3，与用户"全面审查优化"指令一致。
> **门禁留痕（自治降级 S1/S3）**：本会话为自治运行，流程类门禁按 SDW 自治降级协议以 S1（用户显式指令"使用架构技能对项目进行全面审查优化"）放行审查与行为保持型修复；行为变更类仅规划。留痕载体 = 本文档 + ③ 文档 + 会话最终汇报。

---

## 1. 文档摘要与阅读对象

对 SolidWorksMCP（面向 SolidWorks 2026 的本地 MCP Server，Python + pywin32 COM，stdio 传输）做全量架构审查。**一句话总评（详见 §11.2）**：核心工程质量高于业余水准（STA 单线程 COM 执行、路径安全多层校验、统一响应契约、强类型输入），但项目处于"搬迁后未整备 + 无版本管理 + 质量门失效"的三重失守状态——22 个已注册工具中 2 个为特定产品的一次性专用工具（占源码 37%），测试基线红、覆盖率低于自设门槛、文档三处数字互不一致。**先止血（第一波，已完成）再演进**。

阅读对象：本项目维护者（主要）、准备扩展 MCP 工具面的开发者。不需要 SolidWorks 实机即可复核本文全部静态证据。

## 2. 系统概览

**定位**：面向 SolidWorks 2026 的本地标准 MCP Server。MCP 客户端经 stdio 调用 22 个工具（零件建模 / 设计计划 / 文件转换 / 特征树 / 基础装配 / 2 个环形灯专用工具），通过 pywin32 晚绑定 COM 驱动正在运行的 SolidWorks 实例（README 自述，工具注册数以 `grep -c "@mcp.tool"` = 22 实测为准，已验证）。

**技术栈**（每项带验证依据）：

| 项 | 值 | 依据 |
|----|----|------|
| 语言 | Python ≥3.10（实际开发/测试于 3.12） | pyproject.toml:6 `requires-python`；venv pyvenv.cfg `version = 3.12.13`（已验证） |
| MCP 框架 | 官方 SDK `mcp` 1.28.1 的 `server.fastmcp.FastMCP` | requirements.txt、server.py:11 `from mcp.server.fastmcp import FastMCP`、pip freeze `mcp==1.28.1`（已验证） |
| COM 桥 | pywin32 312（晚绑定 Dispatch/GetActiveObject） | pip freeze、app.py:111-116（已验证） |
| 校验 | pydantic ≥2.12（Field/Literal 注解驱动工具 schema） | server.py:44-54（已验证） |
| 测试 | pytest 9.1.1 + coverage 7（fail_under=80, branch=true） | pyproject.toml:38-44、pip freeze（已验证） |
| 传输 | stdio（单进程单实例） | server.py:613 `mcp.run(transport="stdio")`（已验证） |
| 平台 | Windows 专用（COM/ctypes/Win 路径语义） | app.py:38 `WinDLL("kernel32")`、security.py:35-40 commonpath 盘符处理（已验证） |

**范围声明**：父目录下的 `aicad/` 为独立项目（自带 .git 与 venv），solidworks_mcp 主包与其零代码引用（`grep -rn aicad --include=*.py solidworks_mcp/` 命中 0，已验证），**不在本次审查范围**。边界精化（完整性批判员补查）：项目内 `output/` 的两个冒烟脚本**引用了 aicad**（smoke_m5.py:2-3 `from aicad.interop.sw_features import parse_script`；extract_m5.py:5 硬编码个人缓存路径）——耦合存在于外围脚本层，主包干净；这些脚本随 P2-9 一并处理。

## 3. 整体架构（As-Built）

> 注：docs/design-solidworks-mcp.md §2.2 规划过 `tools/` 分域工具层，**实际未建**（solidworks_mcp/tools/__init__.py 仅 1 行空壳，已验证）——下图为实测 as-built 结构。

```
┌──────────────────────────────────────────────────────────────────┐
│ MCP 客户端（Claude 等）                                            │
└───────────────────────────┬──────────────────────────────────────┘
                            │ stdio (JSON-RPC, MCP 协议)
┌───────────────────────────▼──────────────────────────────────────┐
│ solidworks_mcp/server.py（619 行，22 个 @mcp.tool + 3 resource    │
│   + 1 prompt 全部集中注册；_capabilities 能力清单；统一响应契约）  │
├──────────────────────────────────────────────────────────────────┤
│ solidworks_api/（业务层，8 模块）                                  │
│  app.py        连接管理（Dispatch/GetActiveObject/进程探测）      │
│  part.py       板/箱/柱/圆孔/质量属性  ←─ design.py 复用其原语     │
│  design.py     new_part/设计计划编排/mm_to_m/平面选择(中英别名)   │
│  features.py   特征树 查/改名/抑制                                 │
│  file_io.py    打开/STEP 导入导出/STL 导出                         │
│  assembly.py   插入零部件/三型配合                                  │
│  ring_light.py     专用：9 行球形穹顶环形灯 v1（879 行）           │
│  ring_light_v3.py  专用：STEP 保形凹面盘 v3（560 行）             │
├──────────────────────────────────────────────────────────────────┤
│ utils/（横切层）                                                   │
│  com_executor.py 单 STA 线程 COM 执行器（进程级单例 + atexit）     │
│  com.py / common.py / security.py / templates.py / validation.py  │
│  config.py（env 驱动的 frozen ServerConfig）                      │
└───────────────────────────┬──────────────────────────────────────┘
                            │ pywin32 晚绑定 COM（全调用收束于
                            │ solidworks-com-sta 单线程）
┌───────────────────────────▼──────────────────────────────────────┐
│ SLDWORKS.exe（SolidWorks 2026，外部进程，用户手动启动为主）        │
└──────────────────────────────────────────────────────────────────┘
```

分层判定：**两层半**（MCP 协议层 server.py / 业务层 solidworks_api / 横切 utils），无循环依赖（import 关系单向：server→api→utils→config，ring_light→design+part，已验证）。分层清晰度良好；但协议层同时承担了原规划给 tools/ 层的注册职责（见缺点 P1-3/P2-5）。

## 4. 关键机制剖析

### 4.1 COM STA 单线程执行器（核心可靠性机制）
[com_executor.py](../solidworks_mcp/utils/com_executor.py)：进程级单例 `ComExecutor`，daemon 工作线程 `solidworks-com-sta` 内 `pythoncom.CoInitialize()` 后循环取队列执行；所有 SolidWorks 调用经 `run_com()` 收束到该线程，天然消除 COM 并发问题（server.py README 亦自述此约束）。测试 `test_calls_share_one_com_thread` 验证同线程语义（已验证）。`atexit` 注册 `shutdown()`（2 秒 join 上限）。**边界**：`future.result()` 无超时参数（com_executor.py:62）——设计文档 §7 承诺的 30s/120s 工具超时**从未实现**（已验证：全仓无 timeout 相关调用），SW 弹模态框时整个 server 无限阻塞（→ 缺点 P1-1）。

### 4.2 路径安全（多层校验，但存在结构性缺口）
[security.py](../solidworks_mcp/utils/security.py)：`normalize_path`（expanduser+abspath+realpath 解析符号链接/junction）→ `is_path_allowed`（commonpath + normcase，ValueError 防混合盘符，fail-closed）→ `validate_path`（存在性/父目录）→ `validate_extension`（白名单，ADS/尾点等畸形路径被挡）→ `check_overwrite_confirm`。README 安全规则与实现基本一致（已验证）。**对抗验证发现三个结构性缺口（安全反驳 agent + 主会话机理复核）**：
1. **校验-落盘不一致**：校验用规范化路径，但所有落盘 sink（SaveAs3/open/write_text）用的是用户**原始字符串**（file_io.py:191,221、design.py:87、part.py:132,189、ring_light.py:748,816-818、ring_light_v3.py:512,528，已验证）。
2. **词法折叠穿越条件**：`abspath` 先于 `realpath` 执行（security.py:21-22），`E:\R\link\..\out.sldprt` 中的 `link\..` 被词法消解，junction 对 realpath 不可见 → 校验通过；而 Windows 对象管理器逐组件解析时 `..` 作用于 junction **目标**目录 → 实际落在 root 外。折叠顺序已实测复现（abspath 输出即无 link 段）；OS 侧语义为既定 Windows 行为（推断，依据对象管理器解析规则）。前置条件：root 内存在外指 junction/符号链接（OneDrive 目录、手工 junction 常见）→ 组合为 P1-7。
3. **TOCTOU 分钟级窗口**：校验（ring_light.py:802 / design.py:282-287）与保存（748 / 359 行）之间隔着全部建模 COM 调用，窗口内父目录换 junction 或目标文件新建可同时击穿包含性与覆盖确认（已验证窗口存在，利用难度高）。
另：ring_light 系派生副产物（.generated.stl / .layout.json）不经 overwrite_confirm 静默覆盖，且**先于主保存落盘**——主保存失败副产物已写入（ring_light.py:815-821、ring_light_v3.py:528-529，已验证 → P1-6）；无环境变量时默认 allowed_root = `parents[2]`（config.py:42，已验证 → P2-3，传递包含 aicad 与整个兄弟工作区）。

### 4.3 连接管理与进程探测
[app.py](../solidworks_mcp/solidworks_api/app.py)：优先 `GetActiveObject` 附着运行实例；失败则用 ctypes Toolhelp32 快照自实现 SLDWORKS.exe 进程探测（app.py:18-62，避免 psutil 依赖，**该函数测试覆盖为 0**，coverage 表 Missing 20-62，已验证）；`launch_if_needed` 三态（True/False/None→env 默认 False）控制 Dispatch 启动；连接后 `RevisionNumber` 探活，缓存失效自动降级 disconnect。进程级单例 `_sw_app`。
**对抗验证驳倒了"无误判"假设（安全反驳 agent）**：快照是**全系统全 会话**的、仅按进程名匹配——其他用户/会话的 SLDWORKS.exe、僵尸或正在退出的进程都会令 `already_running=True`（app.py:113），随后照常 `Dispatch`（app.py:116），本会话无已注册类对象时会拉起新实例，即 `should_launch=False` 下也可能非预期启动；用户正在启动 SW 的窗口期（进程在、COM 类未注册）存在双实例竞态；冷启动 Dispatch/Visible/RevisionNumber 均无超时，可阻塞数分钟且占死唯一 STA 线程（→ P1-8）。另：`SOLIDWORKS_MCP_SOLIDWORKS_VERSION` 实为装饰性——仅用于错误文案（app.py:137）与 capabilities 展示，实际连接用版本无关 ProgID + RevisionNumber 校验（完整性批判员，已验证 → P2-6）。

### 4.4 ring_light 双版本几何引擎（领域专用机制）
v1（ring_light.py）：纯 Python 几何计算（球面 9 行布局 `_best_phase` 避开 4 个安装孔方位角、72 边形环体三角剖分、LED 穹顶网格）→ 输出 ASCII STL + 布局 JSON 副产物；SolidWorks 原生路径因 FeatureRevolve2 晚绑定被拒而降级为 24 同心环带近似（warning 自述，ring_light.py:771-776）。v3（ring_light_v3.py）：以 STEP 源件为基体，`_layout_row_angles` 在 0.05° 分辨率允许弧上做避开安装孔/辐条的行布局优化（7200 采样 × 候选偏移评分），48 四象限盲切带逼近凹球面。**两版本常量大量重复**（DEFAULT_ROW_COUNTS、_linspace、SW 常量），v1 内含 42 行不可达死代码（→ P1-4/P1-5/P2-1）。几何契约由测试固化（225 LED、球半径 44mm、30-60° 角域等，test_ring_light*.py，已验证）。

## 5. 启动链与生命周期

```
MCP客户端 ──spawn──> python -m solidworks_mcp.server
  │ import server → _configure_logging()（import 期副作用，→ P2-2）
  │            → 构建 FastMCP、注册 22 工具/3 资源/1 prompt（装饰器期）
  ▼
main() → mcp.run(stdio) ──请求──> @mcp.tool 函数
  │  _call_connected(op) → run_com(invoke)  [入 STA 队列]
  │    invoke: get_solidworks_app().connect() → 探活/附着/按需启动
  │    → op(sw) → 业务模块 → COM 调用（全部在 sta 线程）
  ▼
响应（success/data/message/warning/error 五段结构，error 含稳定 code）
  ▼
进程退出 → atexit → ComExecutor.shutdown()（≤2s join，daemon 兜底）
```

单位约定：工具层毫米 → COM 层米（`mm_to_m` 或内联 `/1000.0`，两种写法并存，→ P1-5）。

## 6. 核心组件职责表

| 组件 | 层 | 职责 | 关键符号 | 证据 |
|------|----|------|----------|------|
| server.py | 协议 | 22 工具/3 资源/1 prompt 注册、注解四分类、能力清单 | `_call_connected`、READ_ONLY/STATE_CHANGE/DESTRUCTIVE/IDEMPOTENT_WRITE | server.py:69-92（已验证） |
| app.py | 业务 | 连接/探活/进程探测/单例 | `SolidWorksApp.connect/status/disconnect` | app.py:65-183（已验证） |
| part.py | 业务 | 基本体建模原语（板=箱别名、柱、质量属性） | `create_box/create_cylinder/get_mass_properties` | part.py:96-244（已验证） |
| design.py | 业务 | new_part、圆孔切割、设计计划编排、mm_to_m | `execute_design_plan`（首错即停语义） | design.py:268-366（已验证） |
| features.py | 业务 | 特征树枚举/改名/抑制 | `get_features/rename_feature/set_feature_suppression` | features.py（已验证） |
| file_io.py | 业务 | OpenDoc6/SaveAs3 封装、错误码人性化 | `_format_load_error`（2097152→3DInterconnect 提示） | file_io.py:67-75（已验证） |
| assembly.py | 业务 | AddComponent4/AddMate5、实体名多候选选择 | `select_entity`（类型×别名×@装配体名组合） | assembly.py:146-190（已验证） |
| ring_light(_v3).py | 业务(专用) | 环形灯几何引擎+原生建模 | `build_*_layout` 纯函数（可离线测试） | §4.4（已验证） |
| utils/security.py | 横切 | 路径安全五连校验 | `validate_output_file` | §4.2（已验证） |
| utils/com_executor.py | 横切 | STA 串行化 | `run_com` | §4.1（已验证） |
| utils/templates.py | 横切 | 模板发现（config 优先 + 7/5/3 候选硬编码） | `get_part_template` | templates.py:16-38（已验证） |

## 7. 领域专用章节：COM 集成约定

- **晚绑定适配**：`call_or_value`（com.py）统一处理 pywin32 对属性/方法暴露差异（CDispatch 判别）。全仓未用 makepy 早绑定——SW 常量全部手工镜像（5 处重复定义，→ P1-5）。
- **选面三策略**：FeatureByName→Select2 → SelectByID2("PLANE") → 别名表（中/英文基准面名，design.py:24-28、assembly.py:27-34）。
- **BYREF VARIANT**：OpenDoc6 错误/警告出参、AddMate5 错误出参用 `VT_BYREF|VT_I4` VARIANT（file_io.py:60-64、assembly.py:192-194）。
- **测量**：质量属性直接返回 SI 单位（m³/m²/kg/m）不自换单位，README 声明一致（part.py:225-239，已验证）。

## 8. 配置体系

环境变量驱动（config.py `get_config()` 每次调用现读，frozen dataclass）：ALLOWED_ROOT（默认 parents[2]）、AUTO_START（默认 false）、SOLIDWORKS_VERSION（默认 "2026"）、三个模板路径覆盖、LOG_PATH。`.mcp.json` 为客户端侧配置（指向解释器 + env 注入）。**注意**：utils/security.py:16 的 `DEFAULT_ALLOWED_ROOT` 在 import 期冻结一次（→ P2-3）。当前 .mcp.json 内路径指向旧机器位置（→ P0-2）。

## 9. 日志/诊断/可靠性

RotatingFileHandler（2MB×3，UTF-8）默认落项目根 solidworks_mcp.log；OSError 降级 StreamHandler（server.py:95-111）。业务层异常统一 `logger.exception` + 结构化 error_response（不含堆栈，仅 exception_type）。**实证问题**：import 期配置日志导致测试运行把 mock 堆栈写入运行日志（solidworks_mcp.log 尾部实证，已验证 → P2-2）；ring_light_v3.py 无 logger（错误只进响应）。运行产物：output/ 内 7-21 的实机验证遗留件（含 4 个 ~$ SW 锁文件，提示当时有文档未正常关闭）。

## 10. 关键架构特性总结

- 单 STA 线程收束全部 COM 调用，并发模型极简且正确（已验证）
- 五段统一响应 + 稳定错误码 + 四类工具注解，MCP 契约工整（已验证）
- 路径安全五层校验 + 覆盖确认，破坏性操作有闸门（已验证）
- 几何纯函数与 COM 操作分离，专用算法可离线回归（已验证）
- 22 工具集中注册于单文件，能力清单手维护（→ P2-5）
- 无超时、无版本管理、一次性专用工具占 37%（→ P1-1/P0-1/P1-4）

## 11. 量化评估与优化方案

### 11.1 实测指标表（§7 阈值定级；复核状态见对抗验证记录）

| 指标 | 实测值 | 测量方式 | 定级 | 复核状态 |
|------|--------|----------|------|----------|
| 源码文件数 / LOC | 20 / 3929 | find+wc（排除 pycache） | 正常 | 重验一致（事实核查员独立重测） |
| 单文件最大 LOC | 879（ring_light.py） | wc -l | 🟡P2（300-1000 带） | 重验一致 |
| Top3 大文件 | 879 / 619 / 560 | wc -l | — | 重验一致 |
| 测试 LOC / 文件数 | 1433 / 13 | find+wc | — | 重验一致 |
| 测试/源码比 | 0.365 | 算术 | 正常（>0.3） | 算术推断 |
| 注册工具数 vs 测试断言 vs README | 22 / 21 / 20 | grep -c；pytest 输出 | 🔴 红基线 | 已验证（pytest 实跑 1 failed） |
| pytest | 119P / 1F / 1S | 实跑 9.32s | 🔴 | 已验证 |
| 覆盖率（fail_under=80） | 63% | coverage 实跑 | 🟠P1（自设门失败；通用阈值 >60 属正常带，校准说明：项目自定 80 更严，且缺口 72% 来自两个 ring_light 模块） | 已验证 |
| ring_light / v3 覆盖率 | 25% / 45% | coverage 表 | 🟠P1 | 已验证 |
| except Exception 密度 | 26 处 ≈ 6.6/千行 | grep | 🟡P2 带，**语义校准**：全量通读确认 26 处均转结构化响应且绝大多数 logger.exception，无吞异常、无空 catch、无裸 except → 语义定级正常 | 已验证（全量通读） |
| TODO/FIXME/print/密钥 | 0 / 0 / 0 | grep | 正常 | 已验证 |
| 直接依赖数 | 3（mcp/pywin32/pydantic） | requirements | 正常 | 已验证 |
| 已知 CVE（项目依赖） | 0 | pip-audit | 正常（注：审计环境 venv 内自带 pip 24.3.1 有 7 个 PYSEC，属环境问题非声明依赖） | 已验证 |
| 重复代码 | 手工识别 6 组约 150-200 行 | 人工比对 | 🟠P1（推断·估算，jscpd 未安装；组目：get_features×2、_linspace×2、SW常量×5、平面选择×3、FeatureExtrusion2 参数表×3、_error_variants×2） | 推断 |
| 版本管理 | 无（父 .git 空目录，git 报错） | ls/cat/git | 🔴P0（硬触发器#5） | 已验证 |
| 可运行性 | venv 损坏（pyvenv.cfg 指向 C:\Users\one\...）+ .mcp.json 指向不存在路径 | cat/实跑 | 🔴P0 | 已验证 |
| 不可达死代码 | ring_light.py:824-865（42 行） | Read | 🟡P2 | 已验证 |

### 11.2 一句话总评
**内核精良、躯壳失守**：业务与横切层代码质量在水准之上，但"无版本管理 + 搬迁未整备 + 质量门失效（测试红/覆盖不足/文档漂移）"使任何演进都在裸奔；环形灯专用代码占了三分之一躯体，通用服务器的边界已被侵蚀。

### 11.3 优点（带证据；经对抗复核修正后表述）
1. STA 单线程 COM 执行器：**串行化与套间管理正确**（CoInitialize 在工作线程、atexit 关停、重入守卫、同线程语义有测试锁定，com_executor.py + test_server.py:75-80，已验证）——但缺挂死防护（→ P1-1），"设计正确"以此为限（对抗修正）。
2. 路径安全多层校验框架：realpath+commonpath+normcase+白名单+覆盖确认的**骨架成立且 fail-closed**（已验证）——但存在校验-落盘不一致等结构性缺口（→ P1-7），"无穿越"不成立（对抗修正）。
3. 统一五段响应契约 + 异常不泄堆栈（已验证）——但错误码覆盖不全：约半数 error_response 省略 code 落入默认 OPERATION_FAILED，design 承诺的 TIMEOUT/SW_NOT_RUNNING 从未作为 code 发出（对抗修正 → P2-7）。
4. pydantic 注解驱动输入校验：**标量参数完整**（PositiveMM/FiniteMM/枚举）且测试断言 schema 特征（server.py:44-54 + test_server.py:39-48，已验证）——聚合参数（List[Dict[str,Any]]/List[int]）无 item 级 schema 约束，靠下游手工校验兜底（对抗修正）。
5. 工具注解四分类语义（READ_ONLY/STATE_CHANGE/DESTRUCTIVE/IDEMPOTENT_WRITE），客户端可据此做安全提示（server.py:69-92，已验证）。
6. 中英文本地化兼容（基准面别名、模板候选含中文名）（design.py:24-28、templates.py，已验证）——同时构成 SW 界面语言耦合（见 S 视角备注）。
7. 几何纯函数与 COM 副作用分离，专用算法可离线全参回归（ring_light 系 build_* + 对应测试，已验证）。
8. 依赖极简（3 个运行时依赖）且 mcp 有上界锁定；项目声明依赖 0 CVE（pip-audit，已验证）——venv 内另有未声明的 fastmcp 3.4.4 残留（→ P0-2/P2-4）。

### 11.4 缺点（对照 §7 阈值；格式 **P{0,1,2}-N**）

- **P0-1 无版本管理（阻塞一切演进的偏态级风险）**：项目根无 .git；父目录 .git 为空目录（无 HEAD/对象）；git 命令 fatal: not a git repository（实测，已验证，事实核查员独立重验一致）。架构审查后果风险硬触发器 #5 命中。放大效应：无回滚、无历史、无协作、优化只能靠手工备份（本审查以 .audit-backup-20260828/ 临时缓解；根治=第二波动作 8）。环境元数据声称"是 git 仓库"亦不实（完整性批判员证伪，以 git 实测为准）。
- **P0-2 运行与验证环境断裂（搬迁后未整备 + 依赖漂移）**：venv/pyvenv.cfg home 指向 C:\Users\one\.cache\codex-runtimes\...（原机器 Codex 运行时，本机不存在，venv 不可用，142MB 死重）；venv 内**残留未声明的 fastmcp 3.4.4 / fastmcp_slim 3.4.4**（与 mcp-1.28.1 并存；7-17 用 fastmcp → 7-21 切官方 mcp SDK 后未清理，server_test.log 的 gofastmcp.com banner 互证，完整性批判员双源印证）；.mcp.json 与 README 路径指向 E:\机械设计\Solidworks\...（旧位置，README:36"当前机器可直接使用"已自反）；tests/test_ring_light.py:99 硬编码旧绝对路径 → 1 skip；solidworks_mcp.log 堆栈全为旧机器路径且文件为 GBK 编码（历史 handler 未指定编码所致，现行已修 server.py:103，已验证）。后果：本机按文档无法启动 server、无法跑测试（本审查以独立 venv 重建验证可恢复性）。
- **P1-1 COM 调用无超时 + 单线程队列放大（可靠性关键路径）**：com_executor.py:62 `future.result()` 无超时；队列无界（:21）；design §7 承诺 30s/120s 未实现（全仓 grep timeout 唯一命中是 shutdown 的 join(2.0)，已验证）。后果经对抗强化：一旦某调用挂死（SW 模态框、许可证弹窗、超大文件打开），**队列中全部后续 COM 请求排队等待，22 个工具整体瘫痪**（单线程放大效应）；缓和事实：SW 忙碌时多数调用快速抛 RPC_E_CALL_REJECTED 被 catch 链结构化返回，非必然挂死（对抗修正，表述由"无限期阻塞"校准为"挂死场景永久阻塞"）。退出路径：shutdown 仅 join 2 秒，在途调用被 daemon 硬杀、CoUninitialize 不执行（完整性批判员补强）。
- **P1-2 质量门失效（红基线 + 覆盖不足 + 套件失跑）**：pytest 1 failed（21≠22）；coverage 63% < fail_under 80；缺口集中于 ring_light.py 25%（316 语句未覆盖，COM 建模路径无测试）、ring_light_v3.py 45%、app.py 进程探测函数 0 覆盖（coverage 表 Missing 20-62，已验证）。衍生推断：test_server.py:22 断言 21 而实际 22，意味着**测试套件自 ring_light_v3（7-22 14:35）注册以来从未完整跑过**（资深工程师，依据时间线+失败必然性）。无 CI 使红测试未拦截合入。
- **P1-3 文档-配置-打包三层漂移（无 as-built 真相源）**：README 工具数 20（:9）且工具清单（:96-103）漏列 2 个 ring_light 工具 vs 实际 22；design 文档的 tools/ 分域层/fastmcp 选型/超时承诺/错误码表均未随实现更新；docs/tasks T2/T11 仍写"fastmcp"；egg-info/SOURCES.txt 缺 ring_light 系文件（7-21 快照落后于 7-22 工作，editable 安装下无害）；无 ADR 记录两次搬迁与 fastmcp→mcp SDK 切换（pyvenv.cfg command 字段、日志路径、design 文档路径、venv 残留四源交叉印证，已验证）。
- **P1-4 一次性业务侵入通用服务器（边界侵蚀）**：ring_light.py+v3 = 1439 行占源码 36.6%（算术）。产品绑定实锤：v3 自述 "MV-LRSS-H-80-W STEP/DXF"（v3:203）；安装孔 PCD56/74、孔径 3.0/3.65、线缆盒 22×16×42 硬编码且不在工具签名（ring_light.py:36-39,172-175）；STL solid 名硬编码 "ring_light_9row_21_29_mm"（:423）；**v3 布局完全忽略 STEP 源实际几何**（v3:508 只传 row_counts 一个参数，资深工程师）。定性修正（对抗）：v1（从零生成）与 v3（改造 STEP 源）是**不同输入模型**而非冗余副本；"试错残留"仅适用于 v1 已死的 STL 导入路径。
- **P1-5 重复代码 10 组（对抗复核后较初判扩容，估算 200+ 行）**：get_features×2（part.py:247 生产死代码，仅测试引用）；_linspace×2；swDocPART 等常量×5 文件（另有 swDocASSEMBLY 等未计）；平面选择近似实现×**4**（part.py:47、design.py:43、ring_light.py:455+542 两个）；FeatureExtrusion2 23 参表×3（part.py:89、ring_light.py:616、v3:342）；FeatureCut3 参表×3（design.py:217、ring_light.py:584、v3:332）；mm→m 双轨（design.py:31 有 mm_to_m 而 part.py:120-121 手写 /1000.0）；_latest_feature_name×2；_error_variants×2（file_io/ring_light_v3）；未使用 import os ×2（ring_light.py:8、v3:7）（全部 grep/Read 已验证存在性；行数为估算）。
- **P1-6 派生文件静默覆盖（安全边界缺口）**：ring_light.py:815-820 写 .generated.stl/.layout.json、v3:528-529 写 .layout.json 均不经 overwrite_confirm，同名既有文件被静默截断覆盖；**且先于主保存执行**——SLDPRT 最终保存失败时副产物已落盘（安全反驳员加重情节，已验证）。
- **P1-7 路径校验-落盘不一致 + 词法折叠穿越条件（安全 agent 修正产物）**：§4.2 三缺口——sink 用原始字符串（6+ 处）、abspath 先于 realpath 的折叠缺陷（root 内存在外指 junction 时可无竞态穿越且绕过覆盖确认）、TOCTOU 分钟级窗口。机理复核：折叠顺序已实测；穿越成立依赖前置 junction 条件，故定 P1 而非 P0。另 env 模板路径完全绕过 allowed_root（templates.py:53-68，NEW-3，运维配置面）。
- **P1-8 auto-start 进程探测误判与竞态（安全 agent 驳倒产物）**：§4.3——全系统快照按名匹配，其他会话/僵尸进程误判为已运行 → should_launch=False 下仍可能意外拉起新实例；启动窗口期双实例竞态；冷启动 Dispatch 无超时可占死唯一 STA 线程数分钟（已验证代码路径）。
- **P1-9 输出与参数自相矛盾（正确性缺陷，资深工程师新发现）**：ring_light.py:760 特征名硬编码 "LED_MARKERS_225_DOME_HEIGHT"、:770 消息硬编码 "225 LED markers"，而 :762 data 用的是动态 total_led_count——用户自定义 row_counts 后，几何正确但特征名/消息仍宣称 225；v3:547 warning 同病硬编码 "204 ... 21 ..."（已验证）。
- **P2-1 死代码与误导性桩函数**：ring_light.py:824-865 不可达（821 无条件 return，42 行；swOpenDocOptions_Silent 常量仅死代码引用）；ring_light_v3.py:349 `_band_crosses_mount_zone` 恒 True——**定性修正（对抗）**：被 test_ring_light_v3.py:71-76 有意固化为保守设计（全部环带走四象限切割以保十字筋），quadrants=(None,) 整圆快路径是预留优化分支而非疏忽；但函数名与实现语义不符，启用快路径需同步改测试。
- **P2-2 日志初始化 import 期副作用 + 历史编码**：server.py:114 模块级 `_configure_logging()`，测试导入即污染运行日志（log 实证 134 条 ERROR，绝大多数为"未连接即调用"级联，真实建模失败仅 3 条——完整性批判员模式分析）；RotatingFileHandler 打开失败回退 StreamHandler→stderr（stdio 场景可被客户端收集，轻微）；ring_light_v3.py 无 logger。
- **P2-3 allowed_root 默认边界过宽 + import 期冻结**：无 env 时默认 parents[2]（当前机器上传递包含 aicad、skills、整个兄弟工作区）；DEFAULT_ALLOWED_ROOT 在 security.py:16 冻结而 get_config 不缓存——同进程内其他配置动态、allowed_root 静态的不一致（安全 agent 补强）；读写实际限于 CAD 扩展白名单（精化：任意代码覆盖不可达）。
- **P2-4 仓库卫生**：egg-info 在树内且 SOURCES 陈旧；.coverage/3 个日志/output 产物混根；4 个 ~$ SW 锁文件残留（Jul 21，无 CloseDoc 的物证）；pyproject 声明 MIT 但无 LICENSE；requirements.txt 与 pyproject 双源且不含 dev 依赖；venv 残留 fastmcp（已验证）。
- **P2-5 多处独立维护同一清单（机制性漂移风险）**：工具清单存在三处独立维护点——实际注册（22）、_capabilities 列表、README、测试断言。**归因修正（对抗）**：_capabilities 当前 22/22 同步，本次 20/21/22 漂移发生在 README 与测试，不在 capabilities；但"多处人肉同步"机制是漂移温床（本次实证）。
- **P2-6 版本配置装饰性 + 模板路径硬耦合**：SOLIDWORKS_MCP_SOLIDWORKS_VERSION 仅用于文案与展示（连接实为版本无关 ProgID，已验证）；真正的版本耦合在 templates.py:16-38 的 ProgramData\SolidWorks\SolidWorks 2026\ 硬编码候选（有 config 覆盖与 Program Files 兜底，故 P2）。
- **P2-7 错误契约执行不彻底**：约半数 error_response 省略 code 落默认 OPERATION_FAILED（features/part/file_io/assembly/design 多处，资深工程师逐点列举）；design 承诺的 TIMEOUT/SW_NOT_RUNNING 错误码从未实现；多数模块把 str(exc) 拼进返回 message（com_error 内部码元组、本地路径可入响应；README"不返回完整堆栈"字面为真但弱于其暗示，安全 agent 修正）。
- **P2-8 SolidWorks 文档生命周期未管理（完整性批判员新发现）**：全包无 CloseDoc/QuitDoc 调用（grep 唯一命中是关草图函数）——文档只开不关，锁文件残留为物证；长会话内存增长无界（S12 视角实证落点）。
- **P2-9 测试与脚本的脆弱耦合（完整性批判员新发现）**：测试依赖 MCP SDK 私有 API（mcp._tool_manager/_resource_manager/_prompt_manager/_mcp_server，test_server.py:19-27），SDK 升级即碎（与 mcp<1.29 钉版互为因果）；output/ 冒烟脚本 import aicad（smoke_m5.py:2-3）并硬编码个人缓存路径（extract_m5.py:5）；tools/ 探针含主包缺失的 LoadFile4 导入兜底逻辑（inspect_step_geometry.py:40-54）——知识困在探针里未回流主包。

### 11.5 改进路线（三波 × ROI，详见 ③ 实施规划）

- 🚑 **第一波 止血（低风险，本次已执行）**：修红测试 21→22+集合相等断言；删 42 行死代码及孤儿常量/未用 import；消 get_features 重复；修 .mcp.json/README/测试的旧机器路径；重建 venv（顺带清除 fastmcp 残留）；日志初始化移入 main()；补 LICENSE。→ 恢复"可运行、可验证、文档对齐"。
- 🔧 **第二波 可测化+解耦（中风险，待裁决）**：git init + 首提交（回滚网，一切前提）；抽 constants/geometry 消 10 组重复；capabilities 从注册表派生（P2-5 机制性根治）；ring_light v1/v3 去留裁决与隔离；补测试回 80%（含进程探测/关停分支）；design 文档对账 + ADR；修 P1-9 输出自相矛盾（动态计数进特征名/消息）；测试解耦 SDK 私有 API（P2-9）。
- 🚀 **第三波 现代化（高风险，需 PoC）**：COM 超时与挂死检测（poisoned executor 快速失败，P1-1）；路径校验-落盘一致性修复（sink 改用规范化路径 + realpath 先行排序，P1-7）；auto-start 探测收紧（会话过滤/启动窗口退避，P1-8）；CI（pytest+coverage+pip-audit）；ring_light 参数化为通用环形阵列；模板发现版本参数化；文档关闭策略（P2-8）；错误码补全（P2-7）。

### 11.6 决策者建议
1. **若只做一件事：落 git**（第二波动作 8）——它是其余一切优化的回滚前提；在此之前任何大改都是赌博。
2. **绞杀者而非重写**：内核（executor/security/契约）质量值得保留，演进按"先测试网后动刀"推进，不推倒重来。
3. **给专用代码划边界**：ring_light 属"产品案例"不属"通用能力"，物理隔离（examples/ 或独立包）后核心 server 回归通用定位——这是防止 server.py 继续膨胀为"通用工具+私货集合"的结构性决策。

## 12. 附录

### A. 模块速查
源码 20 文件 3929 行（utils 336 / api 3593 含 ring_light 1439 / server 619 / config 52 / 包初始化 6）；tests 13 文件 1433 行；tools/ 4 个诊断脚本 366 行（inspect_step_geometry 115 等，未纳入包）；output/ 2 个冒烟脚本 105 行 + 实机验证产物。

### B. 配置目录
`.mcp.json`（客户端）、环境变量 7 个（§8）、pyproject.toml（依赖/pytest/coverage）。

### C. 术语
STA（单线程套间，COM 并发模型）；晚绑定（IDispatch 动态调用，对应 makepy 早绑定）；3DInterconnect（SW 中性 CAD 格式直开特性，file_io 错误码 2097152 提示关联）；overwrite_confirm（覆盖确认闸门参数）。

### D. 覆盖矩阵（18 视角 + 扩展）

| 视角 | 状态 | 已查 ✓ | 关键发现（证据或不适原因） |
|------|------|--------|---------------------------|
| C1 架构合理性 | 必查 | ✓ | 两层半无循环依赖（已验证）；P1-4/P2-5 |
| C2 可维护性 | 必查 | ✓ | P1-5 重复 6 组；P2-1 死代码；P2-4 卫生 |
| C3 可靠性 | 必查 | ✓ | P1-1 无超时；异常处理语义健康（26 处全量通读） |
| C4 可测试性 | 必查 | ✓ | P1-2 红基线+63%；mock 模式成熟可扩展 |
| C5 可运维性 | 必查 | ✓ | P2-2 日志污染；配置 env 驱动良好；无健康检查端点（stdio 单机场景可接受） |
| C6 安全性 | 必查 | ✓ | **P1-7 校验-落盘不一致/折叠穿越/TOCTOU**；**P1-8 auto-start 误判**；P1-6 派生文件覆盖；P2-3 root 边界（读写限于 CAD 扩展）；无密钥；STL/STEP 解析攻击面在威胁模型内（恶意文件→SW 崩溃→单线程 DoS） |
| S1 性能伸缩 | 适用 | ✓ | 几何计算毫秒级（7200 采样评分，推断：复杂度分析）；单实例串行定位，无伸缩需求 |
| S2 数据持久化 | 不适用 | ✓ | 无 DB；文件即输出（路径校验已覆盖该面） |
| S3 并发 | 适用 | ✓ | STA 串行化设计性消除竞态（已验证）；无锁需求 |
| S4 API 契约 | 适用 | ✓ | 五段响应+输出 schema 有测试；错误码覆盖不全（P2-7）；测试钉住 SDK 私有 API（P2-9）；mcp<1.29 上界钉版 vs 生态演进需策略 |
| S5 依赖健康 | 适用 | ✓ | 3 依赖有界锁定；声明依赖 0 CVE（pip-audit）；**venv 实装漂移**（fastmcp 3.4.4 残留，P0-2 证据） |
| S6 灾备 | 不适用 | ✓ | 本地单机开发工具，无 SLA；文件操作有覆盖确认闸门 |
| S7 合规隐私 | 不适用 | ✓ | 无 PII/监管数据；建议补 LICENSE 落实声明（P2-4） |
| S8 可观测深化 | 不适用 | ✓ | 单进程本地工具，基础日志已备；trace/metrics 无场景 |
| S9 i18n/a11y | 不适用 | ✓ | 无 UI；中英文平面名/模板兼容反而是加分项 |
| S10 演进/ADR | 适用 | ✓ | P1-3：无 ADR；两次搬迁无记录（三方证据交叉印证） |
| S11 构建链 | 适用 | ✓ | P0-2：venv 断裂；无 CI（→ 第三波动作 14）；pip install -e 可复现（egg-info 在树） |
| S12 资源泄漏/生命周期 | 适用 | ✓ | COM 引用经 disconnect 置空；executor atexit 2s join+daemon 兜底（在途调用被硬杀，CoUninitialize 不执行，与 P1-1 同源）；**无 CloseDoc/QuitDoc，文档只开不关**（P2-8，锁文件物证）；日志 ERROR 模式已分析（未连接级联为主） |
| **扩展 E-1 搬迁可移植性** | 适用（新增） | ✓ | 硬编码绝对路径 4 处（README/.mcp.json/test_ring_light:99/venv pyvenv.cfg），P0-2 主证据 |
| **扩展 E-2 实机验证缺位** | 适用（新增） | ✓ | 全部 COM 行为仅 mock 证据；7-21 后无实机回归记录（output/ 遗件为最后实机痕迹） |

### E. 完整性批判记录（§6.4 九问，经完整性批判员独立复核补强）

1. **最关键风险面？** 无版本管理 + 环境断裂 + 单线程无超时挂死（P0-1/P0-2/P1-1）——已作为最高优先级覆盖（批判员排序与主审一致）。
2. **没打开过的文件？** 补查了 7 处（tools/inspect_step_geometry 全文、output/ 两脚本全文、test_assembly 前 80 行、prd/tasks skim、egg-info/SOURCES.txt）——有意外发现：output 脚本引用 aicad 与个人路径（→P2-9）、探针含主包缺失的 LoadFile4 兜底（→P2-9）、egg-info 陈旧（→P1-3）。主包 20/20 全量通读（已验证）。
3. **外部边界？** MCP stdio 仅两次手动冒烟证据；编码边界：源码全 UTF-8（含中文文件），**历史日志为 GBK**（现行 handler 已修，→P0-2 附注）；Windows 路径边界已深挖（→P1-7）。
4. **默认成立的非功能需求？** 几何计算经复杂度分析有界（_best_phase 每行 ≤10,440 次比较；_layout_row_angles 每行 ~5.8 万次三角函数、offset 候选有硬上限 240——批判员逐函数核算）：亚秒级为**推断**，无计时测试做第二证据（已标注）。
5. **运行产物异常信号？** 134 条 ERROR 模式分析：两轮"未连接即调用"级联（各 15+ 条同毫秒）+ 3 条真实建模失败（create_box 1、cut_round_hole 2）——已解释；server_test.log 乱码 = fastmcp 3.4.4 UTF-8 banner 过 GBK 控制台 + venv 残留 dist-info 双源互证 fastmcp→mcp SDK 切换史；server_test2.log 与之除时间戳外逐字节相同（两次连续手动冒烟）；~$ 锁文件 = 无 CloseDoc 的直接物证（→P2-8）。
6. **错误路径/生命周期？** com_executor 全文补查（无界队列/daemon 硬杀/重入内联）；OpenDoc6 错误路径已覆盖，缺口是"Silent 下仍弹模态框→挂起"（与 P1-1 叠加）——已查。
7. **文档自相矛盾？** README:36"当前机器可直接使用"自反；工具数三重矛盾；tasks 文档 fastmcp 措辞；egg-info SOURCES 落后——已列 P1-3/P2-5。
8. **单源证据？** 计数类已双源（事实核查员 14/14 重验一致 + .pytest_cache nodeids/lastfailed 交叉）；"git 已诊断"曾依赖会话元数据、被批判员以 git 实测证伪后以实测为准；覆盖率经二次运行一致；重复行数仍为估算（已标注）。
9. **领域特有视角？** 已加 E-1 搬迁可移植性、E-2 实机验证缺位；批判员建议的九视角经映射：版本控制（P0-1）、COM 生命周期（P1-1/P2-8）、三层漂移（P1-3）、环境一致性（P0-2）、SW 会话资源（P2-8）、本地化耦合（S 矩阵备注）、SDK 私有 API（P2-9）、文件边界宽度（P2-3）、范围边界（§2 范围声明精化）——全部落位，无遗留"待补"。

### F. 对抗验证记录（Phase 4 多 agent，L3 四员面板）

| 反驳员 | 任务 | 裁决摘要 |
|--------|------|----------|
| 事实核查员 | 14 条关键数字独立重测 | **14 存活 / 0 修正 / 0 驳倒**（.pipcache 精化为"单目录 141MB/387 文件"）；关键数字全部获独立第二源 |
| 资深工程师 | 8 条架构论断反驳 | 5 存活（A1/A2/A3/A4/A7）；1 定性修正（A5 后半：恒 True 为测试固化的保守设计）；1 归因修正（A6：_capabilities 当前同步，漂移在 README/test——本报告 P2-5 已改写）；1 部分驳倒（A8：错误码分层/pydantic 完整两项表扬降级，并**新发现 P1-9 输出自相矛盾**）；A2/A4 反被强化（单线程队列放大、重复清单扩容至 10 组） |
| 安全反驳者 | 6 条安全结论反驳 | S1 修正（→**P1-7** 三缺口）；S2 修正（str(exc) 入 message→P2-7）；S3 存活（加重：副产物先于主保存落盘）；S4 存活（精化边界）；S5 存活（补 config 不缓存的不一致）；**S6 被驳倒（→P1-8）**；另 NEW-3 模板 env 绕过（并入 P1-7）、NEW-4 信息披露（P2 级，并入 P2-3） |
| 完整性批判员 | 九问查漏 | 补查 7 文件 + 日志全量模式分析 + venv dist-info 取证；新发现：venv fastmcp 残留（并 P0-2）、无 CloseDoc（→P2-8）、output/aicad 耦合与探针知识孤岛（→P2-9）、egg-info 陈旧（并 P1-3）、SOLIDWORKS_VERSION 装饰性（并 P2-6）、SDK 私有 API 依赖（并 P2-9） |

**主会话复核**：P1-7 折叠顺序已实测复现（abspath 输出即无 link 段）；P2-1 定性修正此前已由测试阅读独立得出（与反驳员结论互证）。对抗面板改变了 3 处定级/归因、新增 3 条 P1 与 3 条 P2——本报告以修正后版本为准。

---

## 验证范围与局限

- **未做**：未在 SolidWorks 实机运行任何工具（全部 COM 行为结论来自源码通读 + mock 测试）；未反汇编/未调用真实 SW API 文档比对参数语义（FeatureCut3/AddMate5 等 20+ 参调用的参数正确性依赖既有测试与 7-21 实机验证遗件佐证，标注推断）；未审查 aicad/ 本体（范围外；output/ 脚本对其的引用已记录，见 §2 范围声明）；未装 jscpd（重复行数为人工估算）；未创建真实 junction 做 P1-7 端到端穿越 PoC（折叠顺序已实测，OS 侧解析为既定行为推断）。
- **已做**：主包 20 源文件全量通读；pytest/coverage/pip-audit 实跑（两轮一致）；venv 重建实证可恢复性；LOC/计数类指标全部工具实测并经独立 agent 重验（14/14 一致）；关键架构论断四源交叉（源码+测试+文档+运行产物）+ 四员对抗面板（1 条驳倒、4 条修正/定性改写、6 条新发现并入）。
- **审查足迹声明**：本审查在工作区写入了 `.venv-audit/`（临时验证环境）、覆盖了根 `.coverage`（测试数据，可再生）、`.audit-backup-20260828/`（回滚备份）——均为可再生/临时产物，收尾时清理或声明保留。
- **诚实声明**：本文降低误判概率，不保证零误判；单工具测量可能出错（对抗复核记录为二次验证痕迹，含 1 处归因错误被纠正的实例）。
