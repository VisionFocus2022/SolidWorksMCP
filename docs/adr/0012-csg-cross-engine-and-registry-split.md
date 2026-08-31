# ADR-0012：CSG 跨引擎契约与 server 分域注册（N11 + N14）

日期：2026-08-30 · 状态：已接受（双仓闭环）

## 背景

第三期 A3/A4/A5：server.py 1494 行 69 工具单文件、每工具 8-12 行
同构样板；产品专用工具（ring_light）混入通用面；CSG 导出器已实现
但未接路由（双引擎桥只通一半）。

## 决策（N11：CSG 跨引擎）

### 1. 契约 v1：aicad 脚本 → 4-op CSG JSON → SW 重建 → 体积互证

- **决策**：aicad 侧把脚本产物序列化为 CSG 契约 v1（box/cylinder/
  hole/cut_hole 4-op，含 name/through/at.z 堆叠语义）；主仓
  `solidworks_csg_rebuild` 按契约重建实体；验收 = 跨引擎往返体积
  互证 + 三件套（aicad 产物 / CSG JSON / SW 重建件）单脚本断言。
- **依据**：AI 在双引擎间迁移设计时需要无损中转格式；自由脚本无法
  跨引擎复现，受限 4-op 可以。
- **代价**：v1 只覆盖 4 op——装饰/阵列等后续按需扩契约版本。

## 决策（N14：分域注册）

### 2. server.py 收缩为门面，工具按域落 registry/

- **决策**：`registry/` 10 文件（base.py 共享类型/annotations/执行
  件 + 8 个域模块 + `register_all`）；server.py 1494→215 行，只留
  FastMCP 实例 / 3 resources / stdio 入口 + 全量 re-export（69 工具
  + 5 prompt + base 辅助名）。
- **依据**：~35 处 `server.*` 引用（tests/tools）靠 re-export 零改动；
  N19 错误码审计证明错误面随之收敛到 base.py 单文件。
- **代价**：re-export 段撑起 215 行纯声明（无逻辑，可接受）；新工具
  落 registry 域模块而非 server.py——AGENTS.md 已指路。

### 3. 产品工具 env 门控，不进默认面

- **决策**：ring_light 等产品工具仅在 `SOLIDWORKS_MCP_PRODUCT_TOOLS`
  列出时注册（默认 69 → 开启后 71），`test_default_subprocess_registers_
  69_tools` 钉死默认面。
- **依据**：通用工具面是 AI 的能力契约（capabilities 单一事实源，
  N2）——产品专用件混入会污染能力声明。

## 后果

双引擎往返闭环成立（三件套验收脚本入库）；server 结构与 69 工具
计数均有测试钉死。证据：`40708d2` + aicad `90c6a5a`（CSG）、
`17048c8`（分域注册）。
