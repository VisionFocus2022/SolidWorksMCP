# -*- coding: utf-8 -*-
"""N57 批次 B：frozen exe 实机 COM 附着验证（MCP stdio 全链）。

frozen exe（80 工具）起 MCP stdio 会话，驱动真实 SW：
connect(真附着) → part_new → create_box(60,40,10) → get_bounding_box → 断言。
验证点：frozen 进程内 COM Dispatch、模板发现、gen_py typed 缓存首生成路径。
退出码 0 = 全链 PASS。
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "SolidWorksMCPServer" / "SolidWorksMCPServer.exe"
TIMEOUT_S = 180.0  # COM 首调用含 gen_py 生成，放宽


def _reader(proc, out):
    for line in proc.stdout:
        out.put(line.decode("utf-8", "replace"))
    out.put("")


def _rpc(proc, out, payload, wait_id):
    proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
    proc.stdin.flush()
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            line = out.get(timeout=deadline - time.monotonic())
        except queue.Empty:
            break
        if not line:
            raise RuntimeError("server closed stdout")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == wait_id:
            return msg
    raise RuntimeError(f"no response id={wait_id} in {TIMEOUT_S}s")


def call(proc, out, next_id, name, args):
    resp = _rpc(proc, out, {
        "jsonrpc": "2.0", "id": next_id, "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }, wait_id=next_id)
    result = resp.get("result") or {}
    text = (result.get("content") or [{}])[0].get("text", "")
    return json.loads(text) if text.startswith("{") else {"raw": text}


def main() -> int:
    assert EXE.is_file(), f"exe missing: {EXE}"
    t0 = time.monotonic()
    proc = subprocess.Popen(
        [str(EXE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, cwd=str(EXE.parent),
    )
    out: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=_reader, args=(proc, out), daemon=True).start()

    init = _rpc(proc, out, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "frozen-real-sw", "version": "0"}},
    }, wait_id=1)
    print(f"handshake {time.monotonic()-t0:.1f}s", flush=True)
    assert init.get("result", {}).get("serverInfo")
    proc.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode("utf-8"))
    proc.stdin.flush()

    c = call(proc, out, 2, "solidworks_connect", {"launch_if_needed": False})
    print(f"connect: success={c.get('success')} version={(c.get('data') or {}).get('version')}", flush=True)
    assert c.get("success") is True

    c = call(proc, out, 3, "solidworks_part_new", {})
    print(f"part_new: success={c.get('success')}", flush=True)
    assert c.get("success") is True

    c = call(proc, out, 4, "solidworks_part_create_box",
             {"width": 60, "depth": 40, "height": 10})
    print(f"create_box: success={c.get('success')}", flush=True)
    assert c.get("success") is True

    c = call(proc, out, 5, "solidworks_get_bounding_box", {})
    dims = (c.get("data") or {}).get("size_mm")
    print(f"bbox: {dims} ({time.monotonic()-t0:.1f}s total)", flush=True)
    assert dims and all(abs(dims[i] - [60, 40, 10][i]) <= 0.5 for i in range(3)), dims

    c = call(proc, out, 6, "solidworks_file_close", {"save": False})
    print(f"close: success={c.get('success')}", flush=True)
    proc.stdin.close()
    proc.wait(timeout=15)
    print("BATCH B PASS: frozen exe -> real SW COM full chain", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
