#!/usr/bin/env python3
"""
相对导入有效性检查工具

扫描 pilotstd/ 下所有 Python 文件，找出所有相对导入语句，
验证其解析目标在当前包结构中是否真实存在。

用法:
    python scripts/check_relative_imports.py
    python scripts/check_relative_imports.py --warn-undefined-names  # 额外检查导入名是否在目标模块中定义

依赖: 仅 Python 3.10+ 标准库 (ast, pathlib)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # d:/PilotStd
SCAN_DIR = PROJECT_ROOT / "pilotstd"

# GBK 终端兼容输出
_OUT = print


def _out(*args, **kwargs):
    """跨编码安全输出。"""
    kwargs.pop("file", None)
    try:
        _OUT(*args, **kwargs)
    except UnicodeEncodeError:
        # GBK 等窄编码终端 fallback：替换非 ASCII 字符
        text = " ".join(str(a) for a in args)
        safe = text.encode("ascii", errors="replace").decode("ascii")
        _OUT(safe, **kwargs)


# ── 核心逻辑 ──────────────────────────────────────────────────────


def _resolve_name(name: str, package: str, level: int) -> str:
    """CPython importlib._resolve_name 的纯 Python 实现。"""
    if level <= 0:
        raise ValueError("level must be > 0")
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        raise ValueError("attempted relative import beyond top-level package")
    base = bits[0]
    return f"{base}.{name}" if name else base


def get_package_name(file_path: Path, scan_root: Path) -> str | None:
    """获取文件所属的完整包名（如 'pilotstd.ui.main_window.parts'）。

    从 scan_root 向下检查每层是否有 __init__.py，直到文件的父目录。
    如果文件不在任何包内，返回 None。
    """
    try:
        rel = file_path.resolve().parent.relative_to(scan_root.resolve())
    except ValueError:
        return None

    init_dirs: list[str] = []
    current = scan_root
    for part in rel.parts:
        current = current / part
        if (current / "__init__").with_suffix(".py").exists():
            init_dirs.append(part)
        else:
            break

    if not init_dirs:
        return scan_root.name

    return scan_root.name + "." + ".".join(init_dirs)


def module_to_path(module_name: str, scan_root: Path) -> list[Path]:
    """将绝对模块名转为可能存在的文件路径列表（按优先级排序）。

    返回候选项:
      1. <package>/<module>.py
      2. <package>/<module>/__init__.py

    返回扫描根目录内的路径，全部相对于 scan_root。
    """
    # 处理顶层包自身（module_name 就是 "pilotstd"）
    if module_name == scan_root.name:
        return [scan_root / "__init__.py"]

    # 去掉顶层包名前缀
    prefix = scan_root.name + "."
    if module_name.startswith(prefix):
        rel_module = module_name[len(prefix) :]
    else:
        rel_module = module_name

    parts = rel_module.split(".")
    base = scan_root.joinpath(*parts)
    return [base.with_suffix(".py"), base / "__init__.py"]


def format_import_statement(node: ast.ImportFrom) -> str:
    """将 AST 节点还原为导入语句字符串。"""
    dots = "." * node.level
    names = ", ".join(f"{alias.name} as {alias.asname}" if alias.asname else alias.name for alias in node.names)
    module = f"{dots}{node.module or ''}"
    return f"from {module} import {names}"


def is_inside_try(root: ast.Module, target_node: ast.ImportFrom) -> bool:
    """判断 ImportFrom 节点是否在 try/except 块内。"""
    for node in ast.walk(root):
        if isinstance(node, ast.Try):
            # 检查 try 体内的语句是否包含目标节点的行号范围
            start_line = node.lineno
            # TryStar 也用 end_lineno
            end_line = getattr(node, "end_lineno", start_line)
            if start_line <= target_node.lineno <= end_line:
                return True
            for handler in node.handlers:
                h_start = handler.lineno
                h_end = getattr(handler, "end_lineno", h_start)
                if h_start <= target_node.lineno <= h_end:
                    return True
    return False


def collect_relative_imports(
    file_path: Path,
) -> list[tuple[int, ast.ImportFrom, str, bool]]:
    """收集文件中所有相对导入。

    返回 (行号, AST节点, 导入语句字符串, 是否在 try 块内) 列表。
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print(
            f"  [WARN] 语法解析失败: {file_path.relative_to(PROJECT_ROOT)}: {e}",
            file=sys.stderr,
        )
        return []

    results: list[tuple[int, ast.ImportFrom, str, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
            stmt = format_import_statement(node)
            guarded = is_inside_try(tree, node)
            results.append((node.lineno, node, stmt, guarded))
    return results


def check_import(
    node: ast.ImportFrom,
    file_path: Path,
    scan_root: Path,
) -> tuple[str, list[Path]] | None:
    """检查相对导入是否能解析到已存在的目标。

    返回 (错误描述或绝对模块名, 候选路径列表) 如果解析失败，否则返回 None。

    处理两种模式：
    - `from ...module import name` (module 非空): 直接解析目标模块，检查 .py 或 __init__.py
    - `from ... import name` (module 为空): 解析到锚点包，然后检查 name 是否为该包的子模块
    """
    pkg = get_package_name(file_path, scan_root)
    if pkg is None:
        return ("<文件不在包内>", [])

    module = node.module or ""
    imported_names = [a.name for a in node.names]
    try:
        abs_module = _resolve_name(module, pkg, node.level)
    except ValueError as e:
        return (f"<{e}>", [])

    # ── 模式 A: `from ...module import name` ──
    if module:
        candidates = module_to_path(abs_module, scan_root)
        if any(cp.exists() for cp in candidates):
            return None
        return (abs_module, candidates)

    # ── 模式 B: `from ... import name` ──
    # abs_module 是锚点包名（如 "pilotstd" 或 "pilotstd.ui.main_window.parts"）
    # imported_names 是导入的名称列表（如 core, MainWindow）
    # 找到锚点包目录：锚点包的 __init__.py 所在目录
    anchor_pkg_dir: Path | None = None
    for cp in module_to_path(abs_module, scan_root):
        if cp.name == "__init__.py" and cp.exists():
            anchor_pkg_dir = cp.parent
            break
    if anchor_pkg_dir is None:
        init_candidates = module_to_path(abs_module, scan_root)
        return (f"{abs_module} (<init>.py 不存在)", init_candidates)

    # 对每个导入的名称，检查它是否是锚点包下的子模块/文件 或 __init__.py 中定义的属性
    missing_submodules = []
    anchor_init = anchor_pkg_dir / "__init__.py"
    defined_in_init = get_defined_names(anchor_init) if anchor_init.exists() else set()
    for name in imported_names:
        sub_py = anchor_pkg_dir / f"{name}.py"
        sub_pkg = anchor_pkg_dir / name / "__init__.py"
        if sub_py.exists() or sub_pkg.exists() or name in defined_in_init:
            continue
        missing_submodules.append(name)

    if missing_submodules:
        candidates = [anchor_pkg_dir / f"{n}.py" for n in missing_submodules]
        return (f"{abs_module} (缺少: {', '.join(missing_submodules)})", candidates)

    return None


# ── 可选: 检查导入的名称是否在目标模块中定义 ──────────────────────


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
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def check_imported_names(
    node: ast.ImportFrom,
    resolved_path: Path,
) -> list[str]:
    """检查从目标模块导入的名称是否存在（仅顶层）。

    返回未找到的名称列表，全部找到返回空列表。
    """
    imported_names = [alias.name for alias in node.names]
    if not imported_names:
        return []

    target_path = resolved_path if resolved_path.suffix == ".py" else resolved_path / "__init__.py"
    if not target_path.exists():
        return []

    defined = get_defined_names(target_path)
    return [name for name in imported_names if name not in defined and name != "*"]


def _categorize_issues(
    reports: list[tuple[Path, int, str, str, list[Path], bool]],
) -> list[tuple[str, list[tuple[Path, int, str, str]]]]:
    """将失效导入分类并给出修复建议。"""
    cat: dict[str, list[tuple[Path, int, str, str]]] = {
        "handlers: ...X 应改为 ....X": [],  # 3点点到 ui.X，实际在 pilotstd.X
        "handlers: ..X 应改为 ...X": [],  # 2点点到 core.X，实际在 ui.X
        "handlers: ....X 应改为 ...X": [],  # 4点点到 top-level，实际在 ui.X
        "parts: .MainWindow 应改为 ..MainWindow": [],
        "other": [],
    }

    for file_path, lineno, stmt, abs_module, _candidates, _guarded in reports:
        rel = file_path.relative_to(PROJECT_ROOT)
        parts_parts = file_path.parts
        is_handler = "handlers" in parts_parts and "ui" in parts_parts and "core" in parts_parts

        # 注意顺序：4 点要先匹配（因为其前缀包含 3 点）
        if is_handler and stmt.startswith("from ...."):
            cat["handlers: ....X 应改为 ...X"].append(
                (rel, lineno, stmt, "改用 from ...X (themes 在 pilotstd.ui.themes)")
            )
        elif is_handler and stmt.startswith("from ..") and not stmt.startswith("from ..."):
            # 说明：from ..X → 2 dots
            cat["handlers: ..X 应改为 ...X"].append(
                (rel, lineno, stmt, "改用 from ...X (目标在 pilotstd.ui.X, 不在 pilotstd.ui.core.X)")
            )
        elif is_handler and stmt.startswith("from ..."):
            # 3 dots — 确保不是 4 dots (已在上面处理)
            if not stmt.startswith("from ...."):
                cat["handlers: ...X 应改为 ....X"].append(
                    (rel, lineno, stmt, "改用 from ....X (目标在 pilotstd.X, 不在 pilotstd.ui.X)")
                )
        elif "parts" in parts_parts and "_run_main.py" in str(file_path):
            cat["parts: .MainWindow 应改为 ..MainWindow"].append(
                (rel, lineno, stmt, "改用 from .. import MainWindow (MainWindow 定义在父包)")
            )
        else:
            cat["other"].append((rel, lineno, stmt, abs_module))

    return [(k, v) for k, v in cat.items() if v]


def _print_report(total_valid: int, total_invalid: int, reports: list) -> None:
    """打印检查报告。"""
    sep = "=" * 60
    _out(sep)
    _out("  相对导入检查报告")
    _out(sep)

    if not reports:
        _out("")
        _out("  [OK] 无失效导入，全部通过。")
        _out(sep)
        return

    unguarded = [r for r in reports if not r[5]]
    guarded_list = [r for r in reports if r[5]]

    if unguarded:
        _out("")
        _out("  --- 未保护的失效导入（需修复）---")
        for file_path, lineno, stmt, abs_module, candidates, _ in unguarded:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            _out(f"  文件: {rel_path}:{lineno}")
            _out(f"    导入: {stmt}")
            _out(f"    解析: {abs_module}")
            for cp in candidates:
                try:
                    cp_rel = cp.relative_to(PROJECT_ROOT)
                except ValueError:
                    cp_rel = cp
                marker = "[OK]" if cp.exists() else "[MISSING]"
                _out(f"    候选: {marker} {cp_rel}")
            _out("")

    if guarded_list:
        _out("")
        _out("  --- try/except 保护的失效导入（可能是有意为之）---")
        for file_path, lineno, stmt, abs_module, candidates, _ in guarded_list:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            _out(f"  文件: {rel_path}:{lineno}")
            _out(f"    导入: {stmt}")
            _out(f"    解析: {abs_module}")
            for cp in candidates:
                try:
                    cp_rel = cp.relative_to(PROJECT_ROOT)
                except ValueError:
                    cp_rel = cp
                marker = "[OK]" if cp.exists() else "[MISSING]"
                _out(f"    候选: {marker} {cp_rel}")
            _out("")

    _out(sep)
    _out(f"  总计: {total_invalid} 个失效（其中 {len(guarded_list)} 个受 try/except 保护）, {total_valid} 个有效")
    _out(sep)

    if unguarded:
        _out("")
        _out("  --- 分类汇总与修复建议 ---")
        categories = _categorize_issues(unguarded)
        for title, items in categories:
            _out(f"  [{title}] {len(items)} 处")
            for rel_path, lineno, stmt, suggestion in items[:5]:
                _out(f"    {rel_path}:{lineno}  {stmt}")
                _out(f"      -> {suggestion}")
            if len(items) > 5:
                _out(f"    ... 还有 {len(items) - 5} 处相似导入")
            _out("")
    _out(sep)


def _check_undefined_names(py_files: list[Path]) -> None:
    """检查导入的名称是否在目标模块中定义（--warn-undefined-names 模式）。"""
    sep = "=" * 60
    _out("")
    _out(sep)
    _out("  导入名称未定义检查")
    _out(sep)
    _out()

    found_undefined = False
    for file_path in py_files:
        pkg = get_package_name(file_path, SCAN_DIR)
        if pkg is None:
            continue
        imports = collect_relative_imports(file_path)
        for lineno, node, stmt, _guarded in imports:
            result = check_import(node, file_path, SCAN_DIR)
            if result is not None:
                continue
            module = node.module or ""
            try:
                abs_module = _resolve_name(module, pkg, node.level)
            except ValueError:
                continue

            candidates = module_to_path(abs_module, SCAN_DIR)
            target_file = next((c for c in candidates if c.exists()), None)
            if target_file is None:
                continue

            undefined = check_imported_names(node, target_file)
            if undefined:
                rel_path = file_path.relative_to(PROJECT_ROOT)
                _out(f"  文件: {rel_path}:{lineno}")
                _out(f"    导入: {stmt}")
                _out(f"    目标: {target_file.relative_to(PROJECT_ROOT)}")
                _out(f"    未定义: {', '.join(undefined)}")
                _out()
                found_undefined = True

    if not found_undefined:
        _out("  [OK] 所有导入名称均能在目标模块中找到。")
    _out(sep)


def main() -> None:
    """入口：扫描 pilotstd/ 下所有 Python 文件，验证相对导入有效性。"""
    warn_names = "--warn-undefined-names" in sys.argv

    py_files = sorted(p for p in SCAN_DIR.rglob("*.py") if "__pycache__" not in p.parts)

    total_valid = 0
    total_invalid = 0
    reports: list[tuple[Path, int, str, str, list[Path], bool]] = []

    for file_path in py_files:
        imports = collect_relative_imports(file_path)
        for lineno, node, stmt, guarded in imports:
            result = check_import(node, file_path, SCAN_DIR)
            if result is None:
                total_valid += 1
            else:
                abs_module, candidates = result
                total_invalid += 1
                reports.append((file_path, lineno, stmt, abs_module, candidates, guarded))

    _print_report(total_valid, total_invalid, reports)

    if warn_names:
        _check_undefined_names(py_files)

    sys.exit(1 if any(not r[5] for r in reports) else 0)


if __name__ == "__main__":
    main()
