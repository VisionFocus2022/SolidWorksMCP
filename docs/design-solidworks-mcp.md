# Design：SolidWorks MCP Server

**版本**: 1.0  
**日期**: 2026-07-17  
**关联 PRD**: `E:\SolidWorks 2026\SolidWorksMCP\docs\prd-solidworks-mcp.md`

---

## 1. 代码库探索

本项目为新建项目，无既有代码需要适配。可复用的外部能力：

- **SolidWorks 2026 COM API**: 通过 `pywin32` 的 `win32com.client.Dispatch` 调用。
- **MCP Python SDK**: 选择 `fastmcp`（更简洁）或官方 `modelcontextprotocol/python-sdk`。
- **现有 VBA 宏**: `E:\SolidWorks 2026\VBA\Verify_API_Stability.bas` 中的模板查找逻辑可复用到 Python。

---

## 2. 架构设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code (用户界面)                     │
│                  自然语言 → MCP 工具调用                      │
└───────────────────────┬─────────────────────────────────────┘
                        │ stdio / sse
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              SolidWorks MCP Server (Python)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   server.py │  │   tools/    │  │   solidworks_api/   │  │
│  │  MCP 协议层 │  │  工具注册   │  │   SolidWorks 封装   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │ pywin32 COM
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 SolidWorks 2026 Application                  │
│                         SldWorks.exe                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 组件关系

| 组件 | 职责 | 依赖 |
|------|------|------|
| `server.py` | MCP 协议入口，注册所有 tools | `fastmcp`, `tools` 包 |
| `tools/` | 每个工具一个模块，参数校验 + 业务编排 | `solidworks_api/`, `utils/` |
| `solidworks_api/` | 封装 SolidWorks COM API 调用 | `pywin32` |
| `utils/` | 公共工具：模板查找、单位转换、路径安全校验 | 无 |
| `tests/` | 单元测试和集成测试 | `pytest` |

### 2.3 数据流

1. 用户输入自然语言指令。
2. Claude Code 选择 MCP tool，发送 JSON-RPC 请求。
3. `server.py` 路由到对应 tool。
4. tool 调用 `solidworks_api/` 中的函数。
5. `solidworks_api/` 通过 pywin32 调用 SolidWorks。
6. 结果沿原路返回，Claude Code 汇总给用户。

---

## 3. 方案评估

### 方案 A：基于 `fastmcp` 的 stdio MCP Server（推荐）

**实现**: 使用 `fastmcp` 库，通过 stdio 与 Claude Code 通信。

**优点**:
- 开发简单，代码量少。
- `fastmcp` 自动处理工具注册和类型转换。
- stdio 通信稳定，无需额外端口。

**缺点**:
- 每次 Claude Code 会话启动时都需要启动 server。
- 跨进程状态管理简单，但不支持多实例并发。

**风险**: 低

### 方案 B：基于官方 `mcp` SDK 的 SSE Server

**实现**: 使用官方 `modelcontextprotocol/python-sdk`，通过 SSE（Server-Sent Events）通信。

**优点**:
- 符合官方标准，扩展性好。
- 可独立运行，支持多个客户端连接。

**缺点**:
- 配置复杂，需要处理端口、CORS、心跳等。
- 对初学者不够友好。

**风险**: 中

### 方案 C：直接 Python 脚本（非 MCP）

**实现**: 不封装成 MCP server，用户每次让 Claude Code 生成 Python 脚本并运行。

**优点**:
- 最简单，无需配置 MCP。

**缺点**:
- 不是自然语言交互，每次都要写脚本。
- 无法复用上下文，扩展性差。

**风险**: 低（但不符合用户需求）

### 最终选择：方案 A

理由：满足用户"自然语言控制 SolidWorks"的核心需求，开发成本最低，稳定性最好，最适合作为 MVP。

---

## 4. 接口与契约

### 4.1 工具命名规范

```
solidworks_<resource>_<action>
```

例如：
- `solidworks_connect_get_version`
- `solidworks_part_create_cylinder`
- `solidworks_file_import_step`
- `solidworks_assembly_add_component`

### 4.2 统一返回结构

每个工具返回一个 JSON 对象：

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功",
  "warning": null
}
```

失败时：

```json
{
  "success": false,
  "data": null,
  "message": "具体错误原因",
  "warning": null
}
```

### 4.3 错误契约

| 错误码 | 含义 | 示例 |
|--------|------|------|
| `SW_NOT_RUNNING` | SolidWorks 未运行 | 用户未启动 SolidWorks |
| `SW_API_ERROR` | COM API 调用失败 | 模板不存在、特征创建失败 |
| `INVALID_PARAMETER` | 参数不合法 | 直径为负数、路径为空 |
| `FILE_ALREADY_EXISTS` | 文件已存在，需要确认 | 保存路径冲突 |
| `OPERATION_CANCELLED` | 用户取消操作 | 确认弹窗选择否 |
| `TIMEOUT` | 操作超时 | SolidWorks 响应过慢 |

### 4.4 核心工具列表（第一期）

| 工具名 | 功能 | 关键参数 |
|--------|------|---------|
| `solidworks_connect` | 连接 SolidWorks 并返回版本 | 无 |
| `solidworks_part_create_cylinder` | 创建圆柱体 | diameter, height, save_path（可选） |
| `solidworks_part_create_box` | 创建立方体 | width, depth, height |
| `solidworks_file_open` | 打开文件 | file_path |
| `solidworks_file_import_step` | 导入 STEP | file_path |
| `solidworks_file_export_step` | 导出 STEP | file_path, overwrite_confirm |
| `solidworks_part_get_mass_properties` | 获取质量属性 | 无 |
| `solidworks_part_get_features` | 获取特征树 | 无 |
| `solidworks_feature_rename` | 重命名特征 | old_name, new_name |
| `solidworks_feature_set_suppression` | 抑制/解除抑制 | feature_name, suppressed |
| `solidworks_assembly_add_component` | 装配体插入零件 | file_path, x, y, z |

---

## 5. 数据模型

### 5.1 内部状态

```python
class SolidWorksAppState:
    app: Any  # SldWorks.SldWorks COM 对象
    connected: bool
    version: str
```

### 5.2 配置模型

```python
class ServerConfig:
    solidworks_version: str = "2026"
    template_search_paths: List[str]
    confirm_destructive: bool = True  # 始终为 True（严格确认模式）
```

### 5.3 工具参数模型（Pydantic）

```python
class CreateCylinderParams(BaseModel):
    diameter: float = Field(gt=0, description="圆柱直径，单位 mm")
    height: float = Field(gt=0, description="圆柱高度，单位 mm")
    save_path: Optional[str] = None
```

---

## 6. 安全设计

### 6.1 确认机制

- 所有 `save_path` 指向已存在文件时，工具返回 `FILE_ALREADY_EXISTS`，不执行覆盖。
- Claude Code 需要再次调用工具并传入 `overwrite_confirm=True` 才能覆盖。
- 删除特征、删除文件等操作需要显式 `confirm=True` 参数。

### 6.2 路径安全

- 所有路径通过 `os.path.abspath` 规范化。
- 拒绝包含 `..` 的相对路径，防止目录遍历。
- 只允许操作 `E:\SolidWorks 2026\` 及其子目录（可通过配置放宽）。

### 6.3 API 安全

- 不在工具中暴露任何密码、密钥、许可证信息。
- 所有异常返回给用户时，不泄露内部堆栈（仅返回 message）。

---

## 7. 性能设计

- 工具调用默认超时 30 秒。
- 文件导入/导出等可能耗时操作超时 120 秒。
- 所有工具调用串行化，避免 SolidWorks COM API 并发问题。
- 对频繁读取的模型属性做本地缓存（如特征列表）。

---

## 8. 文件变更清单

| 文件/目录 | 类型 | 说明 |
|----------|------|------|
| `E:\SolidWorks 2026\SolidWorksMCP\pyproject.toml` | 新增 | 项目依赖与配置 |
| `E:\SolidWorks 2026\SolidWorksMCP\requirements.txt` | 新增 | 运行时依赖 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\server.py` | 新增 | MCP server 入口 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\__init__.py` | 新增 | 包初始化 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\solidworks_api\__init__.py` | 新增 | API 包初始化 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\solidworks_api\app.py` | 新增 | SolidWorks 连接管理 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\solidworks_api\part.py` | 新增 | 零件操作 API |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\solidworks_api\assembly.py` | 新增 | 装配体操作 API |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\solidworks_api\drawing.py` | 新增 | 工程图操作 API |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\solidworks_api\file_io.py` | 新增 | 文件导入导出 API |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\solidworks_api\features.py` | 新增 | 特征树操作 API |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\tools\__init__.py` | 新增 | 工具包初始化 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\tools\connect.py` | 新增 | 连接类工具 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\tools\part.py` | 新增 | 零件类工具 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\tools\file_io.py` | 新增 | 文件类工具 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\tools\features.py` | 新增 | 特征类工具 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\utils\__init__.py` | 新增 | 工具包初始化 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\utils\templates.py` | 新增 | 模板路径查找 |
| `E:\SolidWorks 2026\SolidWorksMCP\solidworks_mcp\utils\security.py` | 新增 | 路径安全校验 |
| `E:\SolidWorks 2026\SolidWorksMCP\tests\test_app.py` | 新增 | 连接测试 |
| `E:\SolidWorks 2026\SolidWorksMCP\tests\test_utils.py` | 新增 | 工具函数测试 |
| `E:\SolidWorks 2026\SolidWorksMCP\README.md` | 新增 | 使用说明 |
| `E:\SolidWorks 2026\SolidWorksMCP\claude_mcp_config.json` | 新增 | Claude Code MCP 配置示例 |

---

## 9. 向后兼容与迁移

本项目为新建项目，无向后兼容问题。后续若升级工具签名，需保持旧版本兼容或提供迁移说明。

---

## 10. 门禁记录

- [✅] 探索门禁已通过
- [✅] PRD 门禁已通过
- [ ] Design 门禁待确认
