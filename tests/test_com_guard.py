"""F1（better-harness 2026-09-06）：导入期 COM 活动机械守卫。

AGENTS.md 红线 1 要求所有 COM 调用经 run_com（utils/com_executor.py 的单
STA 线程）。solidworks_api/ 模块在函数体内使用 win32com 是合规的——工具层
会把它们交给 run_com 执行；mock 单测拦不住的失效模式是「模块导入期的
COM 活动」：它跑在任意 import 线程上，绕过 STA 线程与超时/毒化防护。

本测试用 AST 扫描 solidworks_mcp/ 全部源码，禁止在会立即执行的位置
（模块顶层语句、类体语句、装饰器、参数默认值）出现 Dispatch /
GetActiveObject / CoInitialize 等 COM 获取或初始化调用；函数体属延迟
执行，不在扫描范围（其路由由 run_com 纪律保证）。
"""
import ast
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "solidworks_mcp"

# 执行器与其 helper 拥有线程/套间生命周期的所有权。
WHITELIST = {
    "utils/com_executor.py",
    "utils/com.py",
}

# pywin32 里会获取/初始化 COM 或构造 COM 值的入口名。
COM_ENTRYPOINTS = {
    "Dispatch",
    "DispatchEx",
    "EnsureDispatch",
    "EnsureModule",
    "GetActiveObject",
    "CoInitialize",
    "CoInitializeEx",
    "CoUninitialize",
    "VARIANT",
    "new",
}


def _is_com_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in COM_ENTRYPOINTS:
            return True
        return isinstance(func, ast.Name) and func.id in COM_ENTRYPOINTS
    if isinstance(node, ast.Attribute) and node.attr in COM_ENTRYPOINTS:
        return True
    return isinstance(node, ast.Name) and node.id in COM_ENTRYPOINTS


def _hits(node: ast.AST, out: list) -> None:
    """Collect import-time COM nodes, skipping deferred function bodies."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for dec in node.decorator_list:
            _hits(dec, out)
        for default in node.args.defaults:
            _hits(default, out)
        for default in node.args.kw_defaults:
            if default is not None:
                _hits(default, out)
        return
    if isinstance(node, ast.ClassDef):
        for dec in node.decorator_list:
            _hits(dec, out)
        for base in node.bases:
            _hits(base, out)
        for kw in node.keywords:
            _hits(kw.value, out)
        for stmt in node.body:
            _hits(stmt, out)
        return
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return
    if _is_com_node(node):
        out.append(node)
    for child in ast.iter_child_nodes(node):
        _hits(child, out)


def _iter_package_files():
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        rel = path.relative_to(PACKAGE_ROOT).as_posix()
        if rel in WHITELIST or "__pycache__" in path.parts:
            continue
        yield path, rel


def _import_time_violations() -> list[str]:
    violations = []
    for path, rel in _iter_package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found = []
        for stmt in tree.body:
            _hits(stmt, found)
        for node in found:
            violations.append(f"{rel}:{node.lineno} ({type(node).__name__})")
    return violations


class TestComGuard(unittest.TestCase):
    def test_no_import_time_com_activity(self):
        violations = _import_time_violations()
        self.assertEqual(
            violations,
            [],
            "COM 获取/初始化出现在导入期位置（模块顶层/类体/装饰器/默认值），"
            "必须在函数体内并经 run_com 路由执行:\n" + "\n".join(violations),
        )

    def test_guard_detects_a_module_level_dispatch(self):
        """红绿对拍的固化副本：守卫必须能抓到顶层 Dispatch。"""
        source = 'import win32com.client\napp = win32com.client.Dispatch("SldWorks.Application")\n'
        tree = ast.parse(source)
        found = []
        for stmt in tree.body:
            _hits(stmt, found)
        self.assertTrue(any(isinstance(n, ast.Call) for n in found))
        self.assertTrue(any(isinstance(n, ast.Attribute) for n in found))


if __name__ == "__main__":
    unittest.main()
