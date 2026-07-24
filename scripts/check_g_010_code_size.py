#!/usr/bin/env python3
"""G-010: 代码规模控制（逻辑行计数）。

检查项：
1. 单个 Python/TypeScript/Vue 文件逻辑行数 <= 500 行
2. 单个 Python 函数逻辑行数 <= 80 行

逻辑行 = 排除纯注释行（#开头）、空行、纯空白行后的行数。
行内注释的代码行保留（只计代码部分）。

违例处理：CI 阻断（必须修复才能合并）。
"""

import ast
import sys
from pathlib import Path

MAX_FILE_LINES = 500  # 单文件最大逻辑行数
MAX_FUNCTION_LINES = 80  # 单个函数最大逻辑行数
# 排除目录：这些目录中的文件不参与行数统计
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
EXCLUDE_PREFIXES = ("whitelist", "probe_")


def _is_comment_or_blank(line: str) -> bool:
    """判断是否为纯注释行或空行（不应计入逻辑行）。"""
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _count_logical_lines(lines: list[str]) -> int:
    """统计逻辑行数（排除注释和空行）。"""
    return sum(1 for line in lines if not _is_comment_or_blank(line))


def _count_func_logical_lines(lines: list[str], start: int, end: int) -> int:
    """统计函数范围内的逻辑行数。start/end 为 1-based 行号。"""
    func_lines = lines[start - 1 : end]  # 转为 0-based 切片
    return _count_logical_lines(func_lines)


def _is_excluded(filepath: Path) -> bool:
    """检查文件路径是否在排除目录或前缀列表中。"""
    for part in filepath.parts:
        if part in EXCLUDE_DIRS:
            return True
    if filepath.name.startswith(EXCLUDE_PREFIXES):
        return True
    return False


def scan(root: Path) -> tuple[list[str], list[str]]:
    """扫描项目根目录下所有代码文件，检查文件级和函数级行数是否超限。

    返回 (错误列表, 警告列表)。
    """
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

            logical = _count_logical_lines(lines)
            rel = fpath.relative_to(root)
            # 检查文件逻辑行数是否超限
            if logical > MAX_FILE_LINES:
                errors.append(f"[FILE] {rel}: {logical} 逻辑行 (>{MAX_FILE_LINES})")

            # Python 文件超过 10 行时，进一步检查每个函数
            if fpath.suffix == ".py" and logical > 10:
                try:
                    tree = ast.parse("".join(lines))
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.end_lineno is None:
                            continue
                        func_logical = _count_func_logical_lines(lines, node.lineno, node.end_lineno)
                        if func_logical > MAX_FUNCTION_LINES:
                            errors.append(
                                f"[FUNC] {rel}:{node.name}() 有 {func_logical} 逻辑行 (>{MAX_FUNCTION_LINES})"
                            )

    warnings: list[str] = []
    # 当前暂无警告类型，保留扩展空间
    return errors, warnings


def main() -> int:
    """入口：执行代码规模检查并输出报告。"""
    root = Path(__file__).resolve().parent.parent
    errors, warnings = scan(root)

    print("=" * 60)
    print("G-010: 代码规模控制（逻辑行）")
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
