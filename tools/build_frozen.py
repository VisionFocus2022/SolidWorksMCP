# -*- coding: utf-8 -*-
"""N48: build the SolidWorksMCP server into a frozen onedir bundle.

Run from the repo root with the project venv (PyInstaller is a
build-machine-only tool — deliberately NOT in pyproject so the CI
pip-audit surface stays unchanged; install with
``venv/Scripts/python.exe -m pip install pyinstaller``).

Usage:
    venv\\Scripts\\python.exe tools\\build_frozen.py
Output:
    dist/SolidWorksMCPServer/SolidWorksMCPServer.exe   (+ support tree)
Follow up with tools/smoke_frozen.py against the built exe.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "SolidWorksMCPServer"


def main() -> int:
    args = [
        "--name", NAME,
        "--onedir",
        "--console",
        "--noconfirm",
        "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build" / "pyinstaller"),
        # The entry script resolves the package from the repo root.
        "--paths", str(ROOT),
        str(ROOT / "solidworks_mcp" / "server.py"),
    ]
    print("pyinstaller", " ".join(args))
    proc = subprocess.run(
        [sys.executable, "-m", "PyInstaller", *args],
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        return proc.returncode
    exe = ROOT / "dist" / NAME / f"{NAME}.exe"
    print(f"\nOK: {exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
