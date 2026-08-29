<!-- Generated: 2026-08-28 | Files scanned: 43 .py | Token estimate: ~300 -->

# Data & State

No database. All state is process-local or file-based.

## Process state

| State | Owner | Notes |
|-------|-------|-------|
| COM connection (cached app object) | app.SolidWorksApp singleton `_sw_app` | RevisionNumber health-check; stale → auto-disconnect |
| STA worker thread + queue | com_executor.ComExecutor `_executor` | poisoned flag after timeout; restart = process restart |

## File artifacts (all under allowed_root)

- CAD: .sldprt (write), .step/.stp/.stl (export), .step/.iges/.x_t/... (read, 3DInterconnect)
- Derived side artifacts: `<name>.generated.stl` + `<name>.layout.json` (ring_light v1), `<name>.layout.json` (v3)
- Scratch: output/ (gitignored — validation artifacts + smoke scripts that import aicad/)
- Logging: solidworks_mcp.log at project root (RotatingFileHandler 2MB×3, utf-8, configured in main() not import)

## Configuration (env, read at call time; ServerConfig frozen per call)

| Var | Default | Effect |
|-----|---------|--------|
| SOLIDWORKS_MCP_ALLOWED_ROOT | project dir (narrowed 2026-08-28) | root of all file IO |
| SOLIDWORKS_MCP_AUTO_START | false | launch SW on connect if null |
| SOLIDWORKS_MCP_SOLIDWORKS_VERSION | 2026 | error text + ProgramData template paths (connection itself uses version-independent ProgID) |
| SOLIDWORKS_MCP_{PART,ASSEMBLY,DRAWING}_TEMPLATE | – | override template lookup |
| SOLIDWORKS_MCP_LOG_PATH | project/solidworks_mcp.log | |
| SOLIDWORKS_MCP_COM_TIMEOUT_SECONDS | 0 (off) | COM call timeout; poison on expiry |

Client-side: .mcp.json (interpreter path + env). Packaging: pyproject.toml (coverage fail_under=80).
