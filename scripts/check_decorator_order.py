#!/usr/bin/env python3
"""SEC-001 防回潮：AST 静态检查 @require_role 装饰器顺序。

正确顺序（@require_role 在内层，紧贴函数）：
    @router.get("/path")
    @require_role("admin")
    def handler(request: Request, ...):

违规（@require_role 在外层，导致 FastAPI 注册未包裹的原函数，鉴权失效）：
    @require_role("admin")
    @router.get("/path")
    def handler(...):
"""

import ast
import sys
from pathlib import Path

SCAN_DIRS = ["docker/api"]
ROUTER_METHODS = {"get", "post", "put", "delete", "patch"}


def _decorator_name(dec: ast.expr) -> str | None:
    """提取装饰器名称：'require_role' 或 'router.get' 等。"""
    func = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        prefix = func.value.id if isinstance(func.value, ast.Name) else ""
        return f"{prefix}.{func.attr}" if prefix else func.attr
    return None


def check_file(filepath: str) -> list[str]:
    """检查单个文件，返回违规列表。"""
    errors: list[str] = []
    try:
        source = Path(filepath).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [f"{filepath}: SyntaxError: {e}"]

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        router_idx: int | None = None
        require_idx: int | None = None
        for i, dec in enumerate(node.decorator_list):
            name = _decorator_name(dec) or ""
            if name == "require_role":
                require_idx = i
            elif "." in name and name.rsplit(".", 1)[1] in ROUTER_METHODS:
                router_idx = i

        # 装饰器列表下标 0 = 最外层。require_role 必须在 router 内层（下标更大）
        if require_idx is not None and router_idx is not None and require_idx < router_idx:
            errors.append(
                f"{filepath}:{node.lineno}: @require_role must be inside @router.xxx "
                f"(closer to function def), currently outside causes auth bypass"
            )
    return errors


def main() -> int:
    """扫描 SCAN_DIRS 下所有 .py 文件，汇总装饰器顺序违规并返回退出码。

    返回 0 表示全部通过，1 表示存在违规（供 pre-commit hook 阻断提交）。
    """
    all_errors: list[str] = []
    # 遍历每个扫描目录下的 .py 文件，聚合所有违规
    for scan_dir in SCAN_DIRS:
        d = Path(scan_dir)
        if not d.exists():
            print(f"Directory not found: {scan_dir}", file=sys.stderr)
            continue
        for py_file in sorted(d.glob("*.py")):
            all_errors.extend(check_file(str(py_file)))

    # 存在违规则输出详情并返回非零退出码（阻断 pre-commit）
    if all_errors:
        print("\nSEC-001 decorator order violations:\n", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    print("SEC-001 check passed: all decorator orders correct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
