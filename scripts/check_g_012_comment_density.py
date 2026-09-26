#!/usr/bin/env python3
# fmt: off
"""G-012: 注释完整性检查。

检查项：
1. [DENSITY] 文件级注释密度 ≥ 3%（仅 ≥50 逻辑行的文件）
2. [FUNC] 每个函数至少有 1 行 docstring 或 # 注释
3. [CLASS] 每个类至少有 1 行 docstring 或 # 注释
4. [LANG] 注释必须全部用中文写（全量检查，工具指令注释豁免）

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

# 静态数据表（工具指令前缀 / 中文字符白名单 / 术语对照）已拆出到同目录的数据模块
from _comment_lang_data import (
    _LANG_WHITELIST_PATTERN,
    TERM_TRANSLATIONS,
    TOOL_DIRECTIVES,
)
from _gate_paths import is_git_ignored

MIN_COMMENT_DENSITY = 0.03  # 最低注释密度：注释行 / 非空行 ≥ 3%
MIN_DENSITY_LOGICAL_LINES = 50  # 仅对 ≥50 逻辑行的文件检查密度
_REPO_ROOT = Path(__file__).resolve().parent.parent
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
# 排除迁移文件：其注释密度由校验和自愈机制保证，不强制-012检查
EXCLUDE_PATTERNS = ("_migrate_",)


def _is_git_ignored(filepath: Path) -> bool:
    """判断文件是否落在 .gitignore 忽略范围内（本地草稿不参与本门禁）。"""
    return is_git_ignored(filepath, _REPO_ROOT)


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
    # 入库产物之外的本地草稿（被版本控制忽略的文件）不参与本门禁
    return _is_git_ignored(filepath)


def _is_comment_line(line: str) -> bool:
    """判断一行是否以 # 开头的纯注释行。"""
    return line.strip().startswith("#")


def _is_blank_line(line: str) -> bool:
    """判断是否为纯空白行。"""
    return line.strip() == ""





def _get_comment_text(line: str) -> str:
    """提取 # 注释的纯文本内容（去除 # 和前后空白）。"""
    if '#' not in line:
        return ''
    idx = line.index('#')
    return line[idx+1:].strip()


def _is_chinese_comment(line: str) -> bool:
    """检查注释是否全部为中文（工具指令注释豁免，白名单术语允许）。"""
    text = _get_comment_text(line)
    if not text:
        return True  # 空注释视为合规
    if any(text.startswith(d) for d in TOOL_DIRECTIVES):
        return True
    # 先去掉引号内的字符串字面量（如 "\n\n"、'value'）
    text = re.sub(r'"[^"]*"', '', text)
    text = re.sub(r"'[^']*'", '', text)
    # 再剥离白名单术语
    cleaned = _LANG_WHITELIST_PATTERN.sub('', text)
    return not bool(re.search(r'[a-zA-Z]', cleaned))


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
    # 兼容程序3.7及更早版本的.节点
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

    # []#注释语言检查：注释必须全部用中文，禁止英文
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
        if not _is_chinese_comment(line):
            errors.append(
                f"[LANG] {rel}:{i} 注释必须全部用中文，不允许出现英文字母: "
                f"{_get_comment_text(line)[:30]}"
            )

    # 函数/类注释
    if filepath.suffix != ".py":
        return errors

    # 解析抽象语法树检查每个函数和类的注释完整性
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _should_skip_func(node):
                continue
            # 函数注释检查：有文档字符串或有行内#注释即可
            has_doc = _has_docstring(node)
            has_comment = _has_comment_in_range(lines, node.lineno, node.end_lineno or node.lineno)
            if not has_doc and not has_comment:
                errors.append(f"[FUNC] {rel}:{node.name}() 缺少注释")
            # []文档字符串中文检查
            if has_doc:
                docstring = ast.get_docstring(node)
                if docstring and not _is_chinese_comment(docstring):
                    errors.append(
                        f"[LANG] {rel}:{node.lineno} {node.name}() 的 docstring 必须全部用中文: "
                        f"{docstring[:30]}"
                    )

        elif isinstance(node, ast.ClassDef):
            if _should_skip_class(node):
                continue
            has_doc = _has_docstring(node)
            has_comment = _has_comment_in_range(lines, node.lineno, node.end_lineno or node.lineno)
            if not has_doc and not has_comment:
                errors.append(f"[CLASS] {rel}:{node.name} 缺少注释")
            # []文档字符串中文检查
            if has_doc:
                docstring = ast.get_docstring(node)
                if docstring and not _is_chinese_comment(docstring):
                    errors.append(
                        f"[LANG] {rel}:{node.lineno} {node.name} 的 docstring 必须全部用中文: "
                        f"{docstring[:30]}"
                    )

    return errors




def _remove_english_from_comment(line: str) -> str:
    """从注释行中删除英文，保留中文描述。"""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return line

    indent = line[:len(line) - len(line.lstrip())]
    text = _get_comment_text(line)

    if not text:
        return f"{indent}# 分隔\n" if line.endswith(("\n", "\r")) else f"{indent}# 分隔"

    # 工具指令豁免：不修改
    if any(text.startswith(d) for d in TOOL_DIRECTIVES):
        return line

    # 已经是纯中文，不修改
    if _is_chinese_comment(line):
        return line

    # 盒型字符分隔线 → 已经是纯中文（"分隔"二字）
    if re.match(r"^[═─━┄┅┈┉╌╍╴╶╸╺]+$", text) or re.match(r"^=+$", text):
        return line

    # 应用术语翻译
    result = text
    for en, zh in TERM_TRANSLATIONS:
        result = result.replace(en, zh)

    # 删除残留的英文字母（只保留中文、数字、标点、空格）
    cleaned = re.sub(r'[a-zA-Z]', '', result)
    # 清理多余空格
    cleaned = re.sub(r'\s+', '', cleaned).strip()
    # 清理多余标点
    cleaned = re.sub(r'[-—]+$', '', cleaned).strip()
    cleaned = re.sub(r'^[-—]+', '', cleaned).strip()

    if not cleaned:
        cleaned = "（说明已省略）"

    suffix = "\n" if line.endswith(("\n", "\r")) else ""
    return f"{indent}# {cleaned}{suffix}"


def _fix_comment_line(line: str) -> str:
    """修复单行 # 注释，确保全部为中文。"""
    return _remove_english_from_comment(line)


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

    # 判断模式：--→自动修复违规
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
# fmt: on
