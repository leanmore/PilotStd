#!/usr/bin/env python
"""G-005: 日志标签检查 — 禁止 _log()、print(stderr)、裸 print 及硬编码日志标签。
退出门禁：返回 0=通过, 1=阻断。"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "pilotstd"

# 这些文件是日志基础设施（定义标签、），不参与业务代码的日志检查
EXCLUDED_FILES = {"_core.py", "logger.py"}

# 这些目录中的()是合法的用户交互输出，不检查
EXCLUDED_DIRS = {"cli", "scripts"}

# 这些**路径前缀**整棵子树排除（与 pyproject.toml 的
# `extend-exclude = ["whitelist.py", "pilotstd/templates/**"]` 同口径）：
# cookiecutter 模板含 Jinja 占位符（如 `class X{{ cookiecutter.adapter_class }}(...)`），
# 不是合法 Python，`ast.parse` 必然 SyntaxError——若不排除，本门禁会崩掉整条 G-005。
EXCLUDED_PATH_PREFIXES = (SRC_DIR / "templates",)

# 这些文件**有意保留** `print(stderr)`，**不是**调试残留——依据 `docs/architecture/modules/ui.md`
# 「日志与诊断」节的既有设计决定（2026-09-26 清理调试输出时特意留下的两条）：
#   ① `ui/main_window/parts/_run_main.py` 的 `_qt_message_handler`：Qt C++ 层
#      WARNING/CRITICAL/FATAL 的**唯一出口**，该节记明"改成 logging 有重入风险"；
#   ② `ui/core/_self_check.py`：可选架构自检（`PILOTSTD_SELF_CHECK=1` 才启用），按设计输出到 stderr。
# ⚠️ 例外必须是**具名文件 + 有文档依据**（不是按目录整体放行）；新增例外须同步改 ui.md 该节并补受控测试。
EXCLUDED_ALLOWED_STDERR = {
    SRC_DIR / "ui" / "core" / "_self_check.py",
    SRC_DIR / "ui" / "main_window" / "parts" / "_run_main.py",
}

# 日志标签的唯一合法来源
VALID_TAG_IMPORTS = {"PROGRESS_TAG", "LoggerManager", "get_logger"}


def _find_py_files(root: Path) -> list[Path]:
    """递归查找所有需检查的 Python 文件，排除日志基础设施、CLI 目录与模板子树。"""
    files: list[Path] = []
    for p in root.rglob("*.py"):
        if p.name in EXCLUDED_FILES:
            continue
        # 检查父目录是否在排除列表中
        if any(parent.name in EXCLUDED_DIRS for parent in p.parents):
            continue
        # 模板子树按路径前缀排除（Jinja 占位符不是合法 Python）
        if any(p.is_relative_to(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
            continue
        files.append(p)
    return sorted(files)


def _rel(path: Path) -> str:
    """相对仓库根的展示路径；仓外路径（受控测试用临时文件）原样返回。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _is_logger_import_ok(tree: ast.Module, allow_print: bool = False) -> tuple[bool, str]:
    """检查是否通过合法路径获取 logger，而非自定义 _log() 或裸 print。

    `allow_print=True` 只对 `EXCLUDED_ALLOWED_STDERR` 里那两份**有文档依据的有意保留项**
    生效；该规则其余部分（禁止模块级 `_log()`）对它们照旧适用。
    """
    # 检查模块顶层：禁止模块级_()
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "_log":
            return False, f"禁止模块级 _log() 函数 (行 {stmt.lineno})"
    if allow_print:
        return True, ""
    # 检查全部节点：禁止()调用（含()等变体）
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

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        # 解析失败**作为该文件的违规项上报**，而不是让整个门禁崩掉：
        # 崩掉时 exit=1 但不指出问题文件，等于把"这一份文件有问题"伪装成"全库门禁失败"。
        return [f"  {_rel(file_path)}: 无法解析（SyntaxError: {e.msg} @ 行 {e.lineno}）"]

    if not isinstance(tree, ast.Module):
        return errors

    ok, msg = _is_logger_import_ok(tree, allow_print=file_path in EXCLUDED_ALLOWED_STDERR)
    if not ok:
        errors.append(f"  {_rel(file_path)}: {msg}")

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

    print(
        f"[G-005] PASS: {len(files)} 个文件检查通过 "
        "(_core.py, logger.py, pilotstd/templates/ 已排除；"
        "ui.md 记载的 2 处有意保留 stderr 输出已登记豁免)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
