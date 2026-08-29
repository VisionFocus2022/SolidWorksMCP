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
