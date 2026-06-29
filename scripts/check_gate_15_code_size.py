#!/usr/bin/env python3
"""GATE-15: 代码规模控制。

检查项：
1. 单个 Python/TypeScript/Vue 文件行数 <= 500 行
2. 单个 Python 函数行数 <= 80 行

违例处理：CI 阻断（必须修复才能合并）。
"""

import ast
import sys
from pathlib import Path

MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 80
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "pilotstd_env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".qwen",
    ".superpowers",
    "tests",
}
EXCLUDE_PREFIXES = ("whitelist",)


def _is_excluded(filepath: Path) -> bool:
    for part in filepath.parts:
        if part in EXCLUDE_DIRS:
            return True
    if filepath.name.startswith(EXCLUDE_PREFIXES):
        return True
    return False


def scan(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []

    for pattern in ("**/*.py", "**/*.ts", "**/*.vue"):
        for fpath in root.rglob(pattern):
            if _is_excluded(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except (UnicodeDecodeError, PermissionError):
                continue

            total = len(lines)
            rel = fpath.relative_to(root)
            if total > MAX_FILE_LINES:
                errors.append(f"[FILE] {rel}: {total} 行 (>{MAX_FILE_LINES})")

            # Python function check
            if fpath.suffix == ".py" and total > 10:
                try:
                    tree = ast.parse("".join(lines))
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.end_lineno is None:
                            continue
                        func_lines = node.end_lineno - node.lineno + 1
                        if func_lines > MAX_FUNCTION_LINES:
                            errors.append(f"[FUNC] {rel}:{node.name}() 有 {func_lines} 行 (>{MAX_FUNCTION_LINES})")

    warnings: list[str] = []
    return errors, warnings


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    errors, warnings = scan(root)

    print("=" * 60)
    print("GATE-15: 代码规模控制")
    print("=" * 60)

    if errors:
        print(f"\n{len(errors)} file(s) over limit:")
        for e in errors:
            print(f"  {e}")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  {w}")

    if errors:
        print(f"\nFAIL: Please fix {len(errors)} violation(s) before merging.")
        return 1

    print("\nPASS: All files within size limits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
