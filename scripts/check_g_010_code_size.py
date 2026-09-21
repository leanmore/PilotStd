#!/usr/bin/env python3
"""G-010: 代码规模控制（有效代码行计数，两档制 + 拆分验证）。

检查项：
1. 单个 Python/TypeScript/Vue 文件有效代码行数：
   - > 500 行：阻断（error，exit 1），并要求提供拆分证据
   - > 400 且 <= 500 行：警告（warning，仅提示，不阻断）
2. 单个 Python 函数有效代码行数 <= 80 行

有效代码行 = 排除空行、纯空白行与纯注释行后的行数。
注释剔除规则：Python 剔除 # 开头行；TypeScript 额外剔除 // 单行注释与
/* */ 块注释；Vue 额外剔除 <!-- --> HTML 注释（template 内）。
行内注释的代码行保留（只计代码部分）。

拆分验证（v2 新增）：文件 > 500 行时，阻断解除需同时满足：
  ① 存在拆分证据：同目录下存在 {文件名}/ 子目录或 {文件名}_*.py 模块文件
  ② 原文件有效代码行 <= 500
两个条件缺一不可；只要文件仍 > 500 行，errors 必被追加 → exit 1。

违例处理：仅阻断档影响 exit code；警告档输出到 stderr 不阻断。
"""

import ast
import sys
from pathlib import Path

from _gate_paths import is_git_ignored

MAX_FILE_LINES = 500  # 单文件有效代码行数上限（阻断档）
WARN_FILE_LINES = 400  # 单文件有效代码行数警告阈值（警告档）
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


def has_split_evidence(file_path: Path) -> bool:
    """检查文件是否存在拆分产物。

    两种证据（满足任一即视为已拆分）：
      1. 同目录下存在 {原文件名}/ 子目录（如 a.py → a/）
      2. 同目录下存在 {原文件名}_*.py 模块文件（如 a.py → a_impl.py）
    空模块/占位文件也视为证据——拆分质量由人工审查把关，本门禁不校验。
    """
    stem = file_path.stem
    parent = file_path.parent

    # 证据1：同目录下存在 原文件名/ 子目录
    if (parent / stem).is_dir():
        return True

    # 证据2：同目录下存在 原文件名_*.py 文件
    if any(parent.glob(f"{stem}_*.py")):
        return True

    return False


def _count_logical_lines(lines: list[str], file_suffix: str = ".py") -> int:
    """统计有效代码行数（排除空行与纯注释行）。

    - .py：剔除 # 开头行
    - .ts：额外剔除 // 单行注释与 /* */ 块注释
    - .vue：额外剔除 <!-- --> HTML 注释（模板内）
    """
    in_block_comment = False  # /* */ 跨行注释状态
    in_html_comment = False  # <!-- --> 跨行注释状态
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            continue
        if file_suffix in (".ts", ".vue"):
            if in_block_comment:
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*"):
                if "*/" not in stripped:
                    in_block_comment = True
                continue
            if stripped.startswith("//"):
                continue
        if file_suffix == ".vue":
            if in_html_comment:
                if "-->" in stripped:
                    in_html_comment = False
                continue
            if stripped.startswith("<!--"):
                if "-->" not in stripped:
                    in_html_comment = True
                continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


def _count_func_logical_lines(lines: list[str], start: int, end: int) -> int:
    """统计函数范围内的逻辑行数。start/end 为 1-based 行号。"""
    func_lines = lines[start - 1 : end]  # 转为 0-based 切片
    return _count_logical_lines(func_lines, ".py")


def _is_excluded(filepath: Path, root: Path) -> bool:
    """检查文件路径是否在排除目录、前缀列表或 .gitignore 忽略范围内。"""
    for part in filepath.parts:
        if part in EXCLUDE_DIRS:
            return True
    if filepath.name.startswith(EXCLUDE_PREFIXES):
        return True
    # 本地草稿（如 logs/）不属于入库产物，不参与代码规模判定
    return is_git_ignored(filepath, root)


def scan(root: Path) -> tuple[list[str], list[str]]:
    """扫描项目根目录下所有代码文件，检查文件级和函数级行数是否超限。

    返回 (错误列表, 警告列表)。
    """
    errors: list[str] = []
    warnings: list[str] = []

    for pattern in ("**/*.py", "**/*.ts", "**/*.vue"):
        for fpath in root.rglob(pattern):
            if _is_excluded(fpath, root):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except (UnicodeDecodeError, PermissionError):
                continue

            logical = _count_logical_lines(lines, fpath.suffix)
            rel = fpath.relative_to(root)
            # 检查文件有效代码行数：先判阻断档（>500），再判警告档（>400）
            if logical > MAX_FILE_LINES:
                errors.append(
                    f"[FILE] {rel}: {logical} 有效代码行 (>{MAX_FILE_LINES})，必须分拆"
                )
                # v2 拆分验证：阻断解除需同时满足 ①拆分证据 ②原文件 ≤500 行
                if not has_split_evidence(fpath):
                    errors.append(
                        f"  ✗ 未检测到拆分产物。请创建 {fpath.stem}/ 目录 "
                        f"或 {fpath.stem}_*.py 模块文件，并将相关逻辑迁移过去"
                    )
                else:
                    # 有证据，但原文件仍 >500 → 拆分不够彻底
                    errors.append(
                        f"  ✗ 原文件仍 {logical} 行 > {MAX_FILE_LINES}，需继续拆分至 ≤{MAX_FILE_LINES}"
                    )
            elif logical > WARN_FILE_LINES:
                warnings.append(
                    f"[FILE] {rel}: {logical} 有效代码行 (>{WARN_FILE_LINES})，文件过长需压缩"
                )

            # 程序文件超过10行时，进一步检查每个函数
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

    return errors, warnings


def main() -> int:
    """入口：执行代码规模检查并输出报告。"""
    root = Path(__file__).resolve().parent.parent
    errors, warnings = scan(root)

    print("=" * 60)
    print("G-010: 代码规模控制（有效代码行，两档制）")
    print("=" * 60)

    if errors:
        print(f"\n{len(errors)} file(s) over limit:")
        for e in errors:
            print(f"  {e}")

    if warnings:
        # 警告档输出到 stderr，不影响退出码
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)

    if errors:
        print(f"\nFAIL: Please fix {len(errors)} violation(s) before merging.")
        return 1

    print("\nPASS: All files within size limits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
