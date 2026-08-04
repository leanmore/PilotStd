#!/usr/bin/env python3
"""
批量修复 pilotstd/ 中所有失效相对导入。

用法:
    python scripts/fix_relative_imports.py
    python scripts/fix_relative_imports.py --dry-run  # 预览不修改
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIR = PROJECT_ROOT / "pilotstd"


# ── 复用检查逻辑 ──


def _resolve_name(name: str, package: str, level: int) -> str:
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        raise ValueError("beyond top-level package")
    return f"{bits[0]}.{name}" if name else bits[0]


def get_package_name(file_path: Path) -> str | None:
    """获取文件所属的完整包名，通过检查 __init__.py 链确定。"""
    try:
        rel = file_path.resolve().parent.relative_to(SCAN_DIR.resolve())
    except ValueError:
        return None
    init_dirs: list[str] = []
    current = SCAN_DIR
    for part in rel.parts:
        current = current / part
        if (current / "__init__").with_suffix(".py").exists():
            init_dirs.append(part)
        else:
            break
    if not init_dirs:
        return SCAN_DIR.name
    return SCAN_DIR.name + "." + ".".join(init_dirs)


def module_to_path(module_name: str) -> list[Path]:
    """将绝对模块名转为可能的文件路径列表（.py 优先，__init__.py 次之）。"""
    if module_name == SCAN_DIR.name:
        return [SCAN_DIR / "__init__.py"]
    prefix = SCAN_DIR.name + "."
    rel_module = module_name[len(prefix) :] if module_name.startswith(prefix) else module_name
    parts = rel_module.split(".")
    base = SCAN_DIR.joinpath(*parts)
    return [base.with_suffix(".py"), base / "__init__.py"]


def get_defined_names(file_path: Path) -> set[str]:
    """解析 .py 文件，返回顶层定义的名称集合。"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except (SyntaxError, OSError):
        return set()
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def check_level(file_path: Path, module: str, level: int, imported_names: list[str]) -> bool:
    """Return True if this level resolves to an existing target.

    检查两方面：
    - 非空 module：目标 .py 或 __init__.py 存在
    - 空 module（from . import Name）：Name 是锚点包的子模块 或 在 __init__.py 中定义
    """
    pkg = get_package_name(file_path)
    if pkg is None:
        return False
    try:
        abs_mod = _resolve_name(module, pkg, level)
    except ValueError:
        return False

    if module:
        return any(p.exists() for p in module_to_path(abs_mod))

    # ...—检查是否为子模块或____脚本属性
    for cp in module_to_path(abs_mod):
        if cp.name == "__init__.py" and cp.exists():
            pkg_dir = cp.parent
            # 检查子模块
            for name in imported_names:
                sub_py = pkg_dir / f"{name}.py"
                sub_pkg = pkg_dir / name / "__init__.py"
                if sub_py.exists() or sub_pkg.exists():
                    continue
                # 检查____脚本属性
                defined = get_defined_names(cp)
                if name not in defined:
                    return False
            return True
    return False


def format_import_stmt(level: int, module: str, names: list[tuple[str, str | None]]) -> str:
    """重构 import 语句字符串。"""
    dots = "." * level
    mod_part = f"{dots}{module}" if module else dots
    name_parts = []
    for name, alias in names:
        name_parts.append(f"{name} as {alias}" if alias else name)
    return f"from {mod_part} import {', '.join(name_parts)}"


# ── 修复逻辑 ──

Fix = tuple[Path, int, str, str]  # file, lineno, old_line_stripped, new_line_stripped


def collect_fixes(dry_run: bool) -> list[Fix]:
    """扫描所有 .py 文件，收集需要修复的导入。"""
    py_files = sorted(p for p in SCAN_DIR.rglob("*.py") if "__pycache__" not in p.parts)
    fixes: list[Fix] = []

    for file_path in py_files:
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue

        lines = source.splitlines(keepends=True)
        pkg = get_package_name(file_path)
        if pkg is None:
            continue

        # 倒序处理以保持行号不变
        for node in reversed(list(ast.walk(tree))):
            if not isinstance(node, ast.ImportFrom) or not node.level or node.level <= 0:
                continue

            module = node.module or ""
            names = [(a.name, a.asname) for a in node.names]
            current_level = node.level

            # 未损坏 — 跳过
            if check_level(file_path, module, current_level, [n for n, _ in names]):
                continue

            # 尝试 [1, 5] 范围内所有候选层级
            best_level: int | None = None
            for candidate in range(1, 6):
                if candidate == current_level:
                    continue
                if check_level(file_path, module, candidate, [n for n, _ in names]):
                    best_level = candidate
                    break

            if best_level is None:
                rel = file_path.relative_to(PROJECT_ROOT)
                print(f"  [SKIP] {rel}:{node.lineno} — 无有效级别: {format_import_stmt(current_level, module, names)}")
                continue

            # 构造旧行和新行文本
            old_stmt = format_import_stmt(current_level, module, names)
            new_stmt = format_import_stmt(best_level, module, names)

            # 在源码中定位行
            lineno = node.lineno - 1  # 0-indexed
            # 在行内替换语句（处理缩进）
            new_line = lines[lineno].replace(old_stmt, new_stmt, 1)

            if dry_run:
                rel = file_path.relative_to(PROJECT_ROOT)
                pad = " " * 4
                print(f"  {rel}:{node.lineno}")
                print(f"{pad}- {old_stmt}")
                print(f"{pad}+ {new_stmt}")
            else:
                lines[lineno] = new_line

            fixes.append((file_path, node.lineno, old_stmt, new_stmt))

        # 如果此文件有修复则写回
        had_fix = any(f[0] == file_path for f in fixes)
        if not dry_run and had_fix:
            file_path.write_text("".join(lines), encoding="utf-8")

    return fixes


def main() -> None:
    """入口：扫描并修复失效的相对导入语句，支持 --dry-run 预览模式。"""
    dry_run = "--dry-run" in sys.argv
    mode = "（预览模式，不修改）" if dry_run else ""
    sep = "=" * 60

    print(sep)
    print(f"  批量修复相对导入 {mode}")
    print(sep)
    print()

    fixes = collect_fixes(dry_run)

    print()
    print(sep)
    if dry_run:
        print(f"  预览完成：发现 {len(fixes)} 处需修复的导入")
        print("  去掉 --dry-run 执行实际修改")
    else:
        print(f"  已修复 {len(fixes)} 处失效导入")
        print("  请运行 python scripts/check_relative_imports.py 验证")
    print(sep)


if __name__ == "__main__":
    main()
