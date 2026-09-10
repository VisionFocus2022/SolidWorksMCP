# Frozen 打包实测报告（N48，2026-09-10）

> **TLDR**：PyInstaller 6.22.2 onedir 打包**一次成功**——47MB 分发树、0.6 秒完成 MCP 握手、
> **79 工具与计数锁逐位一致**、无 SW 时 connect 诚实失败。**D5 裁决建议：frozen onedir 可行且成本极低，
> 采纳为主分发形态**（裁决正条目见 product-vision §D5，N49 落笔）。

## 1. 构建（可复现）

```bash
# 构建机一次性准备（不进 pyproject——CI pip-audit 面零变化）
venv\Scripts\python.exe -m pip install pyinstaller   # 实测 6.22.2
venv\Scripts\python.exe tools\build_frozen.py        # ~16s
venv\Scripts\python.exe tools\smoke_frozen.py        # 验收
```

- 入口：`solidworks_mcp/server.py`（`main()` → FastMCP stdio）。
- 参数：onedir + console；产物 `dist/SolidWorksMCPServer/`。

## 2. 实测数字

| 项 | 值 |
|---|---|
| 构建耗时 | ~16s（clean build） |
| 分发树大小 | **47MB**（exe 10MB + `_internal` 37MB；zip 后预计 ≤25MB） |
| 握手延迟 | **0.6s**（exe 冷启动→initialize 应答） |
| 工具注册 | **79**（与 5 处测试断言钉死的默认口径逐位一致） |
| 诚实失败 | connect（SW 未运行）返回结构化 JSON 错误（`success:false` + 指引信息），协议通道不崩 |

## 3. 坑清单（全部未触发——依赖面极简的红利）

- **pywin32**：`pythoncom`/`win32com.client` 模块级导入，PyInstaller 内置 hook 全覆盖，**零额外配置**。
- **pydantic v2 / mcp SDK**：无 hidden imports 需求（分析器全量跟随）。
- **ezdxf 数据钩子**（vision 遗留观察项）：主仓**不依赖 ezdxf**（那是 aicad 的 DXF 依赖）——观察项对主仓 N/A，aicad 侧打包时再验。
- **gen_py typed 缓存**：运行时生成于 `%TEMP%\gen_py`（机器级、易失可重建，quirks#30）——frozen 不受影响；**SW 实机联动路径（typed wrapper 首生成）留 e2e 观察项**（需 SW 开机窗口，N49 后随 e2e 批补）。

## 4. 限制与注意（诚实披露）

- 本 smoke 在**有 SW 2026 + 有 Python 构建机的同机**跑——模拟「无源码」而非「无依赖装机」；
  真·裸机（无 SW 版本探测、防病毒误报率、路径空格）属 N49 安装器验证范围。
- onedir 首启 0.6s——onefile（解压到临时目录）会更慢且杀软误报率高，**不测**（反目标）。
- `mcp[cli]` 的 cli extras（typer/rich）未被打进（未被 import 跟随）——体积红利。

## 5. D5 裁决（2026-09-10 落笔，N49）

**裁决：frozen onedir 采纳为分发包主形态**（product-vision §D5 已同步）。

| 形态 | 结论 |
|---|---|
| **frozen onedir** | ✅ 主形态：实测全过、构建 16s、47MB、维护面=构建脚本一个 |
| 源码+bootstrap 脚本 | 保留为开发者形态（venv+README 即现状） |
| 容器 | 否决：目标用户=Windows+SolidWorks 桌面工位，COM 无容器路径 |

后续（安装器 UI / 许可激活）= G9 尾项，按 product-vision 路线另行立项。
