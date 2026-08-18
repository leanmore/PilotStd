#!/usr/bin/env python3
"""G-015 相对导入有效性检查（门禁脚本）。

扫描 pilotstd、docker、web/src 下的所有 Python 文件，验证每条相对导入
的解析目标在当前包结构中真实存在。

判定规则：
- 目标存在（模块文件、初始化文件或命名空间目录）→ 通过
- 目标不存在且导入未受 try/except 保护 → 阻断（退出码 1）
- 目标不存在但导入位于 try/except 块内 → 仅警告（可能是有意的可选依赖回退）

docker 目录无初始化文件，按命名空间包处理：包名取扫描根目录名加相对路径。
仅使用标准库，无第三方依赖。
"""

import ast
import io
import sys
from pathlib import Path

# Windows 控制台默认编码无法输出部分字符，统一改用 UTF-8 输出
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 配置 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = ("pilotstd", "docker", "web/src")


# ── 包名与目标解析工具 ────────────────────────────────
def _package_name(file_path: Path, scan_root: Path) -> str:
    """计算文件所属包名，兼容无初始化文件的命名空间包。"""
    rel = file_path.parent.relative_to(scan_root)
    return ".".join([scan_root.name, *rel.parts])


def _resolve_module(module: str, package: str, level: int) -> str:
    """按层级解析相对导入为绝对模块名，语义与标准导入一致。"""
    bits = package.split(".")
    if level > len(bits):
        raise ValueError("attempted relative import beyond top-level package")
    base = ".".join(bits[: len(bits) - (level - 1)])
    return f"{base}.{module}" if module else base


def _module_paths(module: str, scan_root: Path) -> list[Path]:
    """将绝对模块名映射为扫描根目录下的候选路径列表。"""
    prefix = scan_root.name + "."
    rel = module[len(prefix) :] if module.startswith(prefix) else module
    parts = rel.split(".")
    base = scan_root.joinpath(*parts)
    return [base.with_suffix(".py"), base / "__init__.py", base]


def _module_exists(module: str, scan_root: Path) -> bool:
    """判断绝对模块名是否存在于扫描根目录（含命名空间目录）。"""
    return any(p.exists() for p in _module_paths(module, scan_root))


def _name_exists(package: str, name: str, scan_root: Path) -> bool:
    """判断 from . import name 的 name 是否可解析为子模块或包内定义。"""
    rel_parts = package.split(".")[1:]  # 去掉扫描根目录名前缀
    pkg_dir = scan_root.joinpath(*rel_parts)
    for candidate in (pkg_dir / f"{name}.py", pkg_dir / name / "__init__.py", pkg_dir / name):
        if candidate.exists():
            return True
    init_file = pkg_dir / "__init__.py"
    if init_file.exists():
        try:
            tree = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
        except (SyntaxError, UnicodeDecodeError):
            return False
        defined = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Import):
                defined.update(a.asname or a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                defined.update(a.asname or a.name for a in node.names)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        defined.add(t.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    defined.add(node.target.id)
        if name in defined:
            return True
    return False


def _is_inside_try(root: ast.Module, target_node: ast.ImportFrom) -> bool:
    """判断导入语句是否位于 try/except 块内（有意的回退导入）。"""
    for node in ast.walk(root):
        if not isinstance(node, ast.Try):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        if start <= target_node.lineno <= end:
            return True
        for handler in node.handlers:
            h_start = handler.lineno
            h_end = getattr(handler, "end_lineno", h_start)
            if h_start <= target_node.lineno <= h_end:
                return True
    return False


def _format_statement(node: ast.ImportFrom) -> str:
    """将导入节点还原为语句文本，便于报告展示。"""
    dots = "." * node.level
    names = ", ".join(a.name if not a.asname else f"{a.name} as {a.asname}" for a in node.names)
    return f"from {dots}{node.module or ''} import {names}"


# ── 单文件检查 ────────────────────────────────────────
def check_file(file_path: Path, scan_root: Path) -> tuple[int, int, list[tuple[int, str, str, bool]]]:
    """检查单个文件的相对导入，返回有效数、无效数与违规明细。"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(f"  [WARN] 解析失败: {file_path.relative_to(PROJECT_ROOT)}: {exc}")
        return 0, 0, []

    package = _package_name(file_path, scan_root)
    valid = 0
    invalid = 0
    violations: list[tuple[int, str, str, bool]] = []
    for node in ast.walk(tree):
        # 仅处理显式相对导入（level > 0）
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        guarded = _is_inside_try(tree, node)
        stmt = _format_statement(node)
        try:
            abs_module = _resolve_module(node.module or "", package, node.level)
        except ValueError as exc:
            # 相对层级超过包深度，属确定性的代码错误
            invalid += 1
            violations.append((node.lineno, stmt, f"层级越界: {exc}", guarded))
            continue

        if node.module:
            # 带模块名的相对导入，直接校验目标模块是否存在
            if _module_exists(abs_module, scan_root):
                valid += 1
            else:
                invalid += 1
                violations.append((node.lineno, stmt, f"目标模块不存在: {abs_module}", guarded))
        else:
            # from . import x 形式：逐名校验子模块或包内定义
            missing = [n.name for n in node.names if not _name_exists(abs_module, n.name, scan_root)]
            if missing:
                invalid += 1
                violations.append((node.lineno, stmt, f"缺少子模块: {', '.join(missing)}", guarded))
            else:
                valid += 1
    return valid, invalid, violations


# ── 入口 ──────────────────────────────────────────────
def main() -> int:
    """入口：扫描全部扫描根目录，输出报告并返回退出码。"""
    total_valid = 0
    total_invalid = 0
    violations: list[tuple[Path, int, str, str, bool]] = []
    for root_name in SCAN_ROOTS:
        scan_root = PROJECT_ROOT / root_name
        if not scan_root.is_dir():
            continue
        for py_file in sorted(scan_root.rglob("*.py")):
            if "__pycache__" in py_file.parts or "templates" in py_file.parts:
                # 排除缓存与 Jinja2/cookiecutter 模板（{{ }} 占位符非合法语法）
                continue
            valid, invalid, items = check_file(py_file, scan_root)
            total_valid += valid
            total_invalid += invalid
            for lineno, stmt, reason, guarded in items:
                violations.append((py_file, lineno, stmt, reason, guarded))

    print("G-015 相对导入有效性检查")
    print(f"  有效: {total_valid}  无效: {total_invalid}")
    blocked = 0
    for file_path, lineno, stmt, reason, guarded in violations:
        tag = "警告" if guarded else "阻断"
        if not guarded:
            blocked += 1
        print(f"  [{tag}] {file_path.relative_to(PROJECT_ROOT)}:{lineno} {stmt}")
        print(f"        {reason}")

    if blocked:
        print(f"\n❌ G-015 失败: {blocked} 处未受保护的无效相对导入")
        return 1
    if violations:
        print(f"\n⚠️  G-015 通过（{len(violations) - blocked} 处受保护警告）")
    else:
        print("\n✅ G-015 通过：所有相对导入均可解析")
    return 0


if __name__ == "__main__":
    sys.exit(main())
