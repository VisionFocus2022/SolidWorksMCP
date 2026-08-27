# ADR-0001：所有 SolidWorks COM 调用收束到单一 STA 线程

- **状态**：已接受（2026-07 实施，2026-08-28 记录）
- **背景**：SolidWorks 的 COM 接口是单线程套间（STA）语义；pywin32 从多线程并发调用会引发 RPC 错误与不可复现的崩溃。MCP server 的工具回调可能来自框架线程池。
- **决策**：进程级单例 `ComExecutor`（[utils/com_executor.py](../solidworks_mcp/utils/com_executor.py)）持有一个名为 `solidworks-com-sta` 的 daemon 工作线程，线程内 `CoInitialize` 后循环消费任务队列；`run_com()` 是唯一入口。缓存连接与全部 `SolidWorksApp` 状态只在该线程内触碰。
- **后果**：并发模型极简（天然串行、无锁）；代价是**任一 COM 调用挂死会瘫痪全部工具**（无超时，见 ADR-0005 待办）；关停时在途调用被 daemon 硬杀。测试以 `test_calls_share_one_com_thread` 锁定同线程契约。
- **替代方案**：每请求一线程（COM 套间爆炸）、每文档一线程（SolidWorks 不支持）、主线程调用（阻塞 stdio 事件循环）——均被否决。

# ADR-0002：COM 晚绑定 + 手工镜像常量，不使用 makepy 早绑定

- **状态**：已接受
- **背景**：pywin32 可用 makepy 生成早绑定包装获得常量与类型，但生成物绑定 SolidWorks 版本且部署复杂。
- **决策**：全程 `Dispatch`/`GetActiveObject` 晚绑定；用到的 SW 枚举常量手工镜像，**集中存放于 [solidworks_api/constants.py](../solidworks_mcp/solidworks_api/constants.py)**（2026-08-28 前曾分散在 5+ 个文件，已收敛）。pywin32 属性/方法暴露差异由 `call_or_value` 统一适配。
- **后果**：零部署依赖、跨 SW 小版本稳健；代价是无 IDE 常量提示、参数个数错误只能在运行期暴露（由 FakeModel 双打测试兜底）。`_band_crosses_mount_zone` 恒 True 期间观察到的 FeatureRevolve2 晚绑定被拒现象即源于此，v1 因此降级为 24 环带近似。

# ADR-0003：产品专用工具物理隔离到 examples 子包

- **状态**：已接受（2026-08-28，用户裁决"子包隔离+保留工具"）
- **背景**：ring_light v1/v3 是 MV-LRSS-H-80-W 环形灯产品的一次性设计工具（1439 行、占源码 37%），与通用建模工具混在 `solidworks_api/` 里侵蚀了分层边界。
- **决策**：两个模块迁至 [solidworks_mcp/examples/](../solidworks_mcp/examples/)；server 继续注册全部 22 个工具（**行为零变化**）；包 docstring 声明边界——新的通用能力进 `solidworks_api`，一次性产品案例进 `examples`。
- **后果**：未来若要注销这两个工具，只需删 server.py 的两行 import 与两个注册函数；反向（迁回）同样便宜。备选方案（删除 v1 / 完全移出并注销 / 维持原位）见架构审查文档 §11.4 P1-4。

# ADR-0004：路径校验采用逐组件解析，禁止跨链接的词法折叠

- **状态**：已接受（2026-08-28）
- **背景**：原 `normalize_path` 先 `abspath`（内含 normpath 词法折叠）再 `realpath`。当允许根内存在外指 junction 时，`root\link\..\out` 被折叠成 `root\out`（校验通过），而文件系统按对象管理器语义经链接解析到根外——校验与实际落盘位置发散（审查 P1-7）。且历史上校验用规范化路径、落盘 sink 用原始字符串，进一步扩大缺口。
- **决策**：[security.py](../solidworks_mcp/utils/security.py) 的 `normalize_path` 逐组件解析：每个**存在**的组件经 `realpath`（`_getfinalpathname`，OS 语义）规范化，`..` 只对**已规范化的前缀**做 pop，绝不词法折叠；全部 COM sink（SaveAs3/OpenDoc6/LoadFile4）与派生文件写入改用规范化路径（响应中仍回显调用方原始路径）。
- **后果**：真实 junction 回归测试（mklink /J 构造）锁定该行为——旧实现在该测试上失败。已知的残余窗口：校验与写盘之间的 TOCTOU（分钟级，需攻击者能在此窗口改写父目录），留待后续收紧；`realpath` 对 UNC/`\\?\` 前缀的极端形态未全覆盖测试。

# ADR-0005：能力清单从注册表派生（含遗留待办）

- **状态**：已接受（2026-08-28）
- **决策**：`_capabilities()["tools"]` 由 `mcp._tool_manager.list_tools()` 派生，替代 22 项手维护清单；契约测试断言**列表相等**（含顺序）。历史上 README(20)/test(21)/实际(22) 三重漂移即源于多处人肉同步。
- **遗留待办**（三波，需实机 PoC 或远端）：①COM 调用超时与挂死检测（`run_com` 无超时参数，SW 模态框即全服务瘫痪——审查 P1-1，含 design 文档承诺未兑现）；②auto-start 进程探测收紧（Toolhelp32 快照全系统按名匹配，跨会话/僵尸进程会误判，审查 P1-8）；③CloseDoc/文档生命周期策略（当前只开不关，审查 P2-8）；④CI 流水线（pytest+coverage≥80+pip-audit）。
