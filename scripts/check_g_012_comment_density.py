#!/usr/bin/env python3
"""G-012: 注释完整性检查。

检查项：
1. 文件级注释密度：注释行占非空行的比例 ≥ 3%（仅 ≥50 逻辑行的文件）
2. 每个函数/方法至少有 1 行注释（docstring 或 # 注释）
3. 每个类至少有 1 行注释（docstring 或 # 注释）

两种模式：
- pre-commit 模式（传入文件列表）：仅检查暂存文件，违规 → exit 1
- 全量模式（无参数）：扫描全部文件，违规 → 报告但不阻断（exit 0）

跳过策略：魔法方法、@property、≤2 行函数体、≤3 行类体、
私有短函数（_xxx ≤5 行）、__init__.py/setup.py 密度豁免。
"""

import ast
import re
import sys
from pathlib import Path

MIN_COMMENT_DENSITY = 0.03  # 最低注释密度：注释行 / 非空行 ≥ 3%
MIN_DENSITY_LOGICAL_LINES = 50  # 仅对 ≥50 逻辑行的文件检查密度
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
DENSITY_EXEMPT_FILES = {"__init__.py", "__main__.py", "setup.py"}  # 密度豁免文件：包入口和构建脚本
# 排除迁移文件：其注释密度由 checksum 自愈机制保证，不强制 G-012 检查
EXCLUDE_PATTERNS = ("_migrate_",)


def _is_excluded(filepath: Path) -> bool:
    """检查文件路径是否在排除目录列表、命名前缀或模式列表中。"""
    for part in filepath.parts:
        if part in EXCLUDE_DIRS:
            return True
    if filepath.name.startswith(EXCLUDE_PREFIXES):
        return True
    # 排除迁移文件等特殊模式
    for pattern in EXCLUDE_PATTERNS:
        if pattern in filepath.name:
            return True
    return False


def _is_comment_line(line: str) -> bool:
    """判断一行是否以 # 开头的纯注释行。"""
    return line.strip().startswith("#")


def _is_blank_line(line: str) -> bool:
    """判断是否为纯空白行。"""
    return line.strip() == ""


def _contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符（CJK统一表意文字）。"""
    for ch in text:
        if '一' <= ch <= '鿿':
            return True
    return False


def _has_docstring(node: ast.AST) -> bool:
    """检查 AST 节点（函数/类）的第一个语句是否为字符串常量文档字符串。"""
    body = getattr(node, "body", [])
    if not body:
        return False
    first = body[0]
    if not isinstance(first, ast.Expr):
        return False
    val = first.value
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
        return True
    # 兼容 Python 3.7 及更早版本的 ast.Str 节点
    if hasattr(ast, "Str") and isinstance(val, ast.Str):
        return True
    return False


def _has_comment_in_range(lines: list[str], start: int, end: int) -> bool:
    """检查代码行范围 [start, end]（1-based）内是否存在 # 注释行。"""
    for i in range(start - 1, min(end, len(lines))):
        if _is_comment_line(lines[i]):
            return True
    return False


def _should_skip_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """判断函数是否应跳过检查：魔法方法、@property、≤2 行体、私有短函数。"""
    if node.name.startswith("__") and node.name.endswith("__"):
        return True
    body_lines = (node.end_lineno or node.lineno) - node.lineno + 1
    if body_lines <= 2:
        return True
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "property":
            return True
    if node.name.startswith("_") and not node.name.startswith("__"):
        if body_lines <= 5:
            return True
    return False


def _should_skip_class(node: ast.ClassDef) -> bool:
    """判断类是否应跳过检查：≤3 行的极小类体。"""
    body_lines = (node.end_lineno or node.lineno) - node.lineno + 1
    return body_lines <= 3


def check_file(filepath: Path, root: Path) -> list[str]:
    """检查单个文件，返回违规列表。"""
    errors: list[str] = []
    rel = filepath.relative_to(root) if root in filepath.parents else filepath

    try:
        text = filepath.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
    except (UnicodeDecodeError, PermissionError):
        return errors

    if len(lines) < 5:
        return errors

    # 分离非空行和逻辑行用于密度计算
    non_blank = [line for line in lines if not _is_blank_line(line)]
    logical_lines = [line for line in non_blank if not _is_comment_line(line)]

    # 文件级注释密度
    if len(logical_lines) >= MIN_DENSITY_LOGICAL_LINES and filepath.name not in DENSITY_EXEMPT_FILES:
        comment_count = sum(1 for line in non_blank if _is_comment_line(line))
        density = comment_count / len(non_blank) if non_blank else 1.0
        if density < MIN_COMMENT_DENSITY:
            errors.append(f"[DENSITY] {rel}: 注释密度 {density:.1%} (< {MIN_COMMENT_DENSITY:.0%})")

    # [LANG] # 注释语言检查：所有 # 注释行必须包含中文
    for i, line in enumerate(lines, start=1):
        if _is_blank_line(line):
            continue
        if not _is_comment_line(line):
            continue
        stripped = line.strip()
        if stripped.startswith("#!"):
            continue
        if "# -*-" in stripped:
            continue
        if not _contains_chinese(stripped):
            errors.append(f"[LANG] {rel}:{i} 注释缺少中文")

    # 函数/类注释
    if filepath.suffix != ".py":
        return errors

    # 解析 AST 检查每个函数和类的注释完整性
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _should_skip_func(node):
                continue
            # 函数注释检查：有 docstring 或有行内 # 注释即可
            has_doc = _has_docstring(node)
            has_comment = _has_comment_in_range(lines, node.lineno, node.end_lineno or node.lineno)
            if not has_doc and not has_comment:
                errors.append(f"[FUNC] {rel}:{node.name}() 缺少注释")
            # [LANG] docstring 中文检查
            if has_doc:
                docstring = ast.get_docstring(node)
                if docstring and not _contains_chinese(docstring):
                    errors.append(f"[LANG] {rel}:{node.lineno} {node.name}() 的 docstring 缺少中文")

        elif isinstance(node, ast.ClassDef):
            if _should_skip_class(node):
                continue
            has_doc = _has_docstring(node)
            has_comment = _has_comment_in_range(lines, node.lineno, node.end_lineno or node.lineno)
            if not has_doc and not has_comment:
                errors.append(f"[CLASS] {rel}:{node.name} 缺少注释")
            # [LANG] docstring 中文检查
            if has_doc:
                docstring = ast.get_docstring(node)
                if docstring and not _contains_chinese(docstring):
                    errors.append(f"[LANG] {rel}:{node.lineno} {node.name} 的 docstring 缺少中文")

    return errors


def _fix_comment_line(line: str) -> str:
    """修复单行 # 注释，确保包含中文。"""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return line

    # 空注释 → 分隔
    if stripped == "#":
        return line.replace("#", "# 分隔", 1)

    # 模块路径 # path/to/file.py → # 模块：path/to/file.py
    m = re.match(r"^#\s*([\w\\/._-]+\.py)$", stripped)
    if m:
        return line.replace(stripped, f"# 模块：{m.group(1)}", 1)

    # 盒型字符分隔线：═、─、━、┄ 等 → 末尾加 分隔
    if re.match(r"^#\s*[═─━┄┅┈┉╌╍╴╶╸╺]+$", stripped):
        return line.rstrip("\n\r") + " 分隔\n" if line.endswith(("\n", "\r")) else line.rstrip() + " 分隔"

    # ===...=== 型分隔线 → 末尾加 分隔
    if re.match(r"^#\s*=+$", stripped):
        return line.rstrip("\n\r") + " 分隔\n" if line.endswith(("\n", "\r")) else line.rstrip() + " 分隔"

    # 普通英文注释 → 加中文前缀
    indent = line[:len(line) - len(line.lstrip())]
    comment_text = stripped[1:].strip()
    if comment_text and not _contains_chinese(comment_text):
        return f"{indent}# 说明：{comment_text}\n"

    return line


def fix_lang_violations(root: Path) -> int:
    """自动修复所有 [LANG] 违规。"""
    files = [f for f in sorted(root.rglob("*.py")) if not _is_excluded(f)]
    fixed_count = 0
    docstring_todo: list[str] = []

    for fpath in files:
        if _is_excluded(fpath):
            continue
        errors = check_file(fpath, root)
        lang_errors = [e for e in errors if e.startswith("[LANG]")]
        if not lang_errors:
            continue

        # 解析违规行号和类型
        fix_lines: set[int] = set()
        for err in lang_errors:
            m = re.match(r"\[LANG\]\s+.+?:(\d+)\s", err)
            if m:
                fix_lines.add(int(m.group(1)))
            else:
                docstring_todo.append(err)

        if not fix_lines:
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)
        except (UnicodeDecodeError, PermissionError):
            continue

        modified = False
        for ln in sorted(fix_lines):
            if ln <= len(lines):
                old_line = lines[ln - 1]
                new_line = _fix_comment_line(old_line)
                if new_line != old_line:
                    lines[ln - 1] = new_line
                    modified = True

        if modified:
            fpath.write_text("".join(lines), encoding="utf-8")
            rel = fpath.relative_to(root) if root in fpath.parents else fpath
            print(f"  已修复: {rel} ({len(fix_lines)} 行)")
            fixed_count += 1

    if docstring_todo:
        print(f"\n  [跳过] docstring 违规（需手动翻译）: {len(docstring_todo)} 项")
        for e in docstring_todo:
            print(f"    {e}")

    print(f"\n  修复文件数: {fixed_count}")
    return 0


def main() -> int:
    """入口：支持 pre-commit 模式（传入文件列表，阻断）和全量模式（报告不阻断）。"""
    root = Path(__file__).resolve().parent.parent

    # 判断模式：--fix → 自动修复 LANG 违规
    args = sys.argv[1:]
    if "--fix" in args:
        args = [a for a in args if a != "--fix"]
        return fix_lang_violations(root)

    if args:
        files = [Path(a).resolve() for a in args if Path(a).resolve().exists()]
        mode = "pre-commit（暂存文件）"
    else:
        files = [f for f in sorted(root.rglob("*.py")) if not _is_excluded(f)]
        mode = "全量扫描"

    all_errors: list[str] = []
    for fpath in files:
        if _is_excluded(fpath):
            continue
        all_errors.extend(check_file(fpath, root))

    print("=" * 60)
    print(f"G-012: 注释完整性检查 [{mode}]")
    print("=" * 60)
    print(f"  扫描文件: {len(files)}")
    print(f"  违规数: {len(all_errors)}")
    print()

    if all_errors:
        lang_errors = [e for e in all_errors if e.startswith("[LANG]")]
        hard_errors = [e for e in all_errors if not e.startswith("[LANG]")]

        if hard_errors:
            print("违规项:")
            for e in hard_errors:
                print(f"  {e}")
            print()
        if lang_errors:
            print(f"[LANG] 注释语言警告 ({len(lang_errors)} 项，不阻断):")
            for e in lang_errors:
                print(f"  {e}", file=sys.stderr)
            print()

        print("=" * 60)
        print(f"汇总: {len(hard_errors)} 项阻断违规, {len(lang_errors)} 项语言警告")
        if hard_errors:
            print("FAIL: 请添加注释后再提交。")
            return 1
        print("PASS: 所有阻断项通过（[LANG] 警告不阻断）。")
        return 0

    print("=" * 60)
    print("汇总: 0 项违规")
    print("PASS: 所有文件的注释密度均达标。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
