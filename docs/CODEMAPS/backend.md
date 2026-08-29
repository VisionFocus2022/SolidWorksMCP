<!-- Generated: 2026-08-28 | Files scanned: 43 .py | Tool surface: 25 tools | Token estimate: ~850 -->

# MCP Tool Catalog (= "backend routes")

Call chain for every tool: `server.<tool> → _call_connected(op, launch_if_needed)
→ run_com(timeout?) → SolidWorksApp.connect → <api fn>(sw, ...) → COM` → five-field
envelope {success, data, message, warning, error{code, details}}.

## Tools (name → handler module.function)

**connect** solidworks_connect → app.connect · **query** get_active_document → app/design
· **design_capabilities** → server._capabilities (registry-derived) · **execute_plan** → design.execute_design_plan

**part** part_new / create_plate / create_box / create_cylinder / cut_round_hole → design+part
· get_mass_properties → part · **pattern** pattern_annular_layout → pattern.build_annular_layout (READ_ONLY, pure)
· part_create_annular_pattern → pattern.create_annular_pattern (cut/boss, per-ring single sketch, phase optimization vs avoid angles)

**examples (product)** part_create_ring_light → examples.ring_light (native 24-band fallback + STL/JSON side artifacts)
· part_create_ring_light_v3 → examples.ring_light_v3 (STEP-based, 48×4-quadrant bands)

**file** file_open / import_step / export_step / export_stl / file_close → file_io
(CloseDoc by title; save_changes=false discards edits — DESTRUCTIVE)

**features** features_list / feature_rename / feature_set_suppression → features
**assembly** add_component / list_components / add_mate → assembly (AddComponent4 / AddMate5, entity name × type × alias resolution)

## Resources & prompt

solidworks://capabilities | //status | //active-document; prompt solidworks_design_part_prompt

## Error codes

INVALID_PARAMETER · INVALID_OUTPUT_PATH / INVALID_SOURCE_PATH · SW_CONNECTION_FAILED ·
SW_API_ERROR · SW_SAVE_FAILED · SW_IMPORT_FAILED · SW_TIMEOUT · SW_EXECUTOR_POISONED (restart server)

## Reliability knobs

SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS (default off; timeout poisons executor → SW_EXECUTOR_POISONED until restart)

## Key files

solidworks_mcp/server.py (679, registration) · solidworks_api/pattern.py (348) ·
solidworks_api/design.py (317) · tests/test_pattern.py, test_infrastructure.py, test_hardening.py (contract+security locks)


## 2026-08-30 二期优化新增（T3-T18）

solidworks_api/topology.py（实体/面枚举+命名，SetEntityName 宿主 ModelDoc2）·
measure.py（包围盒/两点距离，GetBodyBox）·
decorations.py（圆角/倒角/抽壳，legacy 全值 API——variant 数组编组不稳）·
features.py 扩展（特征详情/尺寸读写/删除，GetSystemValue3 米制契约）·
part.py（revolve/堆叠原语 create_cylinder_on_face——顶面 GetBox 走查）·
design.py（事务性计划回滚 + rebuild_csg_plan 跨引擎契约）·
properties.py（材料/自定义属性/方程式/配置，byref VARIANT 铁律）·
drawing.py（GB 模板建图/手动三视图/InsertModelAnnotations2/导 PDF+PNG）·
assembly.py 扩展（新建装配/干涉检查/BOM/mate 6 类型）

server.py 现注册 53 tools / 3 prompts；测试基线 356 passed + 79 subtests，
覆盖率 ≥89%（红线），记忆守卫套件 test_memory_guard.py（裸 Mock 哨兵）。
契约文档：docs/csg-plan-v1.md（跨引擎 CSG v1）。
