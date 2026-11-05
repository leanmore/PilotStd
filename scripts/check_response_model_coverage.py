#!/usr/bin/env python3
"""B 组护栏：所有 /api 路由必须声明 response_model（流式/文件响应显式豁免）。

用 AST 静态扫描，避免在 CI 的 repo-compliance 作业里 import 整个应用（该作业不装运行依赖）。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "docker" / "api", ROOT / "docker"]
METHODS = {"get", "post", "put", "delete", "patch"}

# 这些端点成功响应是 Response/FileResponse/StreamingResponse，没有 JSON 模型可校验。
# 维护规则：新增流式/文件端点（如备份下载）时必须同步加入本清单，否则 G-0 契约检查会误报。
# 扫描方式为 AST 静态分析，不导入 FastAPI 运行依赖。
ALLOWLIST = {
    "/api/notification/callback/wechat",
    "/api/notification/callback/{channel}",
    "/api/export/standards",
    "/api/admin/logs/app",
    "/api/backgrounds/{filename}",
    "/api/backup/download/{name}",
}


def _decorator_path(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """返回该函数上第一个 HTTP 路由装饰器的路径；不是路由则 None。"""
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        if isinstance(func, ast.Attribute) and func.attr in METHODS and dec.args:
            arg = dec.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
    return None


def missing_response_models() -> list[tuple[str, str]]:
    """静态扫描所有受管目录，返回 (方法, 路径) 缺少 response_model 的项。"""
    missing: list[tuple[str, str]] = []
    for directory in SCAN_DIRS:
        for path in sorted(directory.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                route = _decorator_path(node)
                if not route or not route.startswith("/api"):
                    continue
                if route in ALLOWLIST:
                    continue
                for dec in node.decorator_list:
                    if not isinstance(dec, ast.Call):
                        continue
                    func = dec.func
                    if not (isinstance(func, ast.Attribute) and func.attr in METHODS):
                        continue
                    if any(kw.arg == "response_model" for kw in dec.keywords):
                        break
                else:
                    missing.append((node.name, route))
    return missing


def main() -> int:
    """执行静态检查，失败时打印缺失项。"""
    missing = missing_response_models()
    if missing:
        for func, route in missing:
            print(f"[FAIL] {func} {route} 缺少 response_model")
        return 1
    print("PASS: 所有 /api 路由均声明 response_model（5 个流式/文件端点豁免）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
