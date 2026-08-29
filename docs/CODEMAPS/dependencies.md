<!-- Generated: 2026-08-28 | Files scanned: 43 .py | Token estimate: ~400 -->

# Dependencies

## Runtime (3, pinned in pyproject + requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| mcp[cli] | 1.28.1 (<1.29 pin) | FastMCP stdio server; tests touch private APIs `_tool_manager`/`_mcp_server` (upgrade risk, P2-9) |
| pywin32 | 312 | COM late binding (win32com, pythoncom, VARIANT BYREF) |
| pydantic | 2.13.4 | tool input schemas incl. AnnularRing item model ($defs) |

## External system

- **SolidWorks 2026** via COM ProgID `SldWorks.Application` (GetActiveObject attach → Dispatch launch; process probe = Toolhelp32 snapshot filtered to current session). Single STA client thread. Not version-locked (SOLIDWORKS_VERSION is advisory).
- Windows-only: kernel32/ctypes (process snapshot, ProcessIdToSessionId), junction-aware path semantics.

## Dev & tooling

pytest 9 + coverage (branch=true, fail_under=80) + pip-audit (0 known CVEs in deps, venv pip 26.2.1) · GitHub Actions ci.yml (windows-latest; activates on first remote push)

## Non-dependencies (deliberate)

No network services (stdio only), no DB, no psutil (hand-rolled snapshot), no fastmcp standalone (removed from venv 2026-08-28).

## Sibling (out of scope)

aicad/ — independent nested project (own git/venv); only output/ smoke scripts import it. Solidworks.zip 83MB in parent dir is the pre-git archive.
