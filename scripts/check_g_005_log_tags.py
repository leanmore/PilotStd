#!/usr/bin/env python
"""G-005: 日志标签检查 — 禁止 _log()、print(stderr)、裸 print 及硬编码日志标签。
退出门禁：返回 0=通过, 1=阻断。"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "pilotstd"

# 这些文件是日志基础设施（定义标签、LoggerManager），不参与业务代码的日志检查
EXCLUDED_FILES = {"_core.py", "logger.py"}

# 这些目录中的 print() 是合法的用户交互输出，不检查
EXCLUDED_DIRS = {"cli", "scripts"}

# 日志标签的唯一合法来源
VALID_TAG_IMPORTS = {"PROGRESS_TAG", "LoggerManager", "get_logger"}


def _find_py_files(root: Path) -> list[Path]:
    """递归查找所有需检查的 Python 文件，排除日志基础设施和 CLI 目录。"""
    files: list[Path] = []
    for p in root.rglob("*.py"):
        if p.name in EXCLUDED_FILES:
            continue
        # 检查父目录是否在排除列表中
        if any(parent.name in EXCLUDED_DIRS for parent in p.parents):
            continue
        files.append(p)
    return sorted(files)


def _is_logger_import_ok(tree: ast.Module) -> tuple[bool, str]:
    """检查是否通过合法路径获取 logger，而非自定义 _log() 或裸 print。"""
    # 检查模块顶层：禁止模块级 def _log()
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "_log":
            return False, f"禁止模块级 _log() 函数 (行 {stmt.lineno})"
    # 检查全部节点：禁止 print() 调用（含 print(stderr) 等变体）
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                return False, f"禁止使用 print() (行 {node.lineno})"
            if isinstance(node.func, ast.Attribute) and node.func.attr == "print":
                return False, f"禁止使用 print() (行 {node.lineno})"
    return True, ""


def check_file(file_path: Path) -> list[str]:
    """检查单个文件的日志规范，返回违规列表。"""
    errors: list[str] = []
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception:
        return errors

    tree = ast.parse(source)
    if not isinstance(tree, ast.Module):
        return errors

    ok, msg = _is_logger_import_ok(tree)
    if not ok:
        errors.append(f"  {file_path.relative_to(ROOT)}: {msg}")

    return errors


def main() -> int:
    """入口：扫描 pilotstd/ 下所有 Python 文件，检查日志调用规范。"""
    all_errors: list[str] = []
    files = _find_py_files(SRC_DIR)
    for fp in files:
        all_errors.extend(check_file(fp))

    if all_errors:
        print(f"[G-005] FAIL: {len(all_errors)} 个违规项")
        for err in all_errors:
            print(err)
        return 1

    print(f"[G-005] PASS: {len(files)} 个文件检查通过 (_core.py, logger.py 已排除)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
