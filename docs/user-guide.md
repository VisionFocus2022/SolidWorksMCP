# SolidWorksMCP 用户指南 v1（N49，2026-09-10）

> 面向**最终用户**的安装与首跑文档。开发者向的架构/扩展文档见 `docs/architecture-review-solidworksmcp.md` 与 `AGENTS.md`。
> 安装形态裁决（D5，2026-09-10）：**frozen onedir 为主分发形态**（依据 `docs/packaging-frozen-report.md`），源码+venv 为开发者形态保留。

## 1. 系统要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（64 位）——SolidWorks COM 自动化仅 Windows |
| SolidWorks | SolidWorks 2026（正版安装；服务以 COM 连接运行中的 SolidWorks，不替代许可） |
| MCP 客户端 | 任意支持 stdio MCP 的客户端（Claude Desktop / Claude Code / Cursor / 自研客户端等） |
| Python | **仅源码形态需要**（3.12+）；frozen 形态无需 Python |

## 2. 安装

### 形态 A：frozen 分发包（推荐——零 Python）

1. 拿到分发包（onedir zip，约 ≤25MB 压缩/47MB 解压），解压到任意**固定路径**，例如 `C:\Tools\SolidWorksMCPServer\`。
2. 目录内应有 `SolidWorksMCPServer.exe` 与 `_internal\` 支撑树——两者必须同目录，整目录一起分发。
3. 启动**SolidWorks**（frozen 不替你开 SW；见 §4 AUTO_START）。
4. 按 §3 配置客户端后即可使用。

> 构建 frozen 包（开发者）：`venv\Scripts\python.exe -m pip install pyinstaller && venv\Scripts\python.exe tools\build_frozen.py`，验收用 `tools\smoke_frozen.py`。

### 形态 B：源码 + venv（开发者形态）

```powershell
git clone <repo> && cd SolidWorksMCP
python -m venv venv
venv\Scripts\python.exe -m pip install -e .
```

## 3. 客户端配置（.mcp.json）

**形态 A（frozen）**——command 直接指向 exe，无需 args：

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "C:\\Tools\\SolidWorksMCPServer\\SolidWorksMCPServer.exe",
      "env": {
        "SOLIDWORKS_MCP_ALLOWED_ROOT": "D:\\CAD_Work",
        "SOLIDWORKS_MCP_SOLIDWORKS_VERSION": "2026"
      }
    }
  }
}
```

**形态 B（源码）**：

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "E:\\path\\to\\SolidWorksMCP\\venv\\Scripts\\python.exe",
      "args": ["-m", "solidworks_mcp.server"],
      "env": {
        "SOLIDWORKS_MCP_ALLOWED_ROOT": "D:\\CAD_Work",
        "SOLIDWORKS_MCP_SOLIDWORKS_VERSION": "2026"
      }
    }
  }
}
```

## 4. 环境变量

全部前缀 `SOLIDWORKS_MCP_`，不设均有安全默认：

| 变量 | 默认 | 说明 |
|---|---|---|
| `ALLOWED_ROOT` | 项目根（frozen 下=exe 所在目录上级） | **文件沙箱根**：open/save/export/import 的所有路径必须在它之下；跨项目使用务必显式设宽（如 `D:\CAD_Work`） |
| `AUTO_START` | `false` | `true` 时 connect 工具可拉起未运行的 SolidWorks 进程 |
| `SOLIDWORKS_VERSION` | `2026` | 用于模板目录定位与 COM ProgID 探测；装机版本不同时改这里 |
| `PART_TEMPLATE` / `ASSEMBLY_TEMPLATE` / `DRAWING_TEMPLATE` | 自动发现 | 显式指定模板绝对路径；不设时按 §5 顺序自动找 |
| `LOG_PATH` | 项目根（frozen 下=exe 旁）`solidworks_mcp.log` | 滚动日志（排查首选） |
| `COM_TIMEOUT_SECONDS` | `120` | 单次 COM 调用超时秒数；大装配/复杂重建可调大 |
| `POISONED_EXIT` | `false` | COM 执行器毒化时的行为：`false`=返回结构化错误+重启指引；`true`=进程直接退出，交给客户端监督者自动重启（推荐配自动重启的客户端） |
| `PRODUCT_TOOLS` | 空 | 追加产品级工具（如 `ring_light`），工具数 79→81 |

## 5. 模板自动发现顺序（不设 TEMPLATE 变量时）

1. `C:\ProgramData\SolidWorks\SolidWorks <版本>\templates\` 下按 `gb_part.prtdot`（国标）→ `Part.prtdot` → `零件.prtdot`（中文版）序查找（装配/图纸同构：`gb_assembly/Assembly/装配体`、`gb_a4p/Drawing/工程图`）；
2. 找不到则回退 `C:\Program Files\...\lang\english|chinese-simplified\` 安装目录默认模板；
3. 仍找不到：新建文档工具会返回结构化错误——此时显式设对应 `*_TEMPLATE` 变量。

## 6. 首跑验证清单（4 步，全部走客户端对话）

| 步 | 对客户端说 | 期望 |
|---|---|---|
| 1 | 「连接 SolidWorks」 | `solidworks_connect` 成功返回版本/活动文档状态（SW 必须已开，或 AUTO_START=true） |
| 2 | 「新建一个 60×40×10 的盒子」 | `part_new` + `part_create_box` 成功，返回特征/体积信息 |
| 3 | 「测量它的包围盒」 | `get_bounding_box` 返回 [60, 40, 10]（±0.5mm 公差内） |
| 4 | 「导出 STEP 到 <ALLOWED_ROOT 下某路径>」 | `file_export_step` 生成文件且返回路径；写 ALLOWED_ROOT 之外会**被拒绝**（这是安全特性，不是故障） |

四步全过=安装健康。更多玩法见 `examples/INDEX.md`（22 张按域组织的可贴示例卡）。

## 7. 故障排查

| 症状 | 原因 → 处置 |
|---|---|
| connect 报「Could not connect」 | SW 未运行（先开 SW，或设 `AUTO_START=true`）；或版本号不对（改 `SOLIDWORKS_VERSION`） |
| 工具调用一直超时 | 复杂模型重建慢 → 调大 `COM_TIMEOUT_SECONDS`；看 `LOG_PATH` 日志定位 |
| 所有工具报「执行器已毒化」 | COM 线程卡死不可进程内恢复 → 重启 MCP 会话/服务器进程；长期方案 `POISONED_EXIT=true` + 客户端自动重启 |
| 路径被拒「outside allowed root」 | 目标路径不在沙箱内 → 设宽 `ALLOWED_ROOT`（路径分隔用 `\\`） |
| 新建文档报模板错误 | 模板未被发现 → 显式设 `*_TEMPLATE`（§5） |
| 首次 COM 调用慢数秒 | typed COM 缓存（gen_py）首生成，仅一次；缓存被系统清理后会自动重建 |
| 中文乱码/文件名异常 | 保持路径纯 ASCII 重试并把现象贴给维护者（已知中文控制台编码坑） |

## 8. 安全边界（必读）

- **文件沙箱**：一切文件读写限制在 `ALLOWED_ROOT` 内，默认不越界。
- **COM 隔离**：所有 SolidWorks 调用经带超时的受控线程执行，单调用超时不拖死整个服务。
- **无网络面**：server 仅 stdio 本地通信，不监听端口。
