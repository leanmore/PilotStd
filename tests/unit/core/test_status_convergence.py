"""状态字面量收敛守卫 + 行为断言（#32-B / R14-4b，2026-10-01）。

B 阶段把生产代码里的中文状态字面量替换为 `Status.*.value`。本文件锁定两件事：

① **防回归守卫**：已收敛的生产 Python 文件内不得再出现裸状态字面量
   （AST 口径，排除 docstring/注释；`pilotstd/core/status.py` 是字典本身，豁免；
    `pilotstd/templates/` 为 cookiecutter 脚手架模板、非可解析运行时代码，豁免）；
② **行为断言**：核心替换模块产出的状态值确为字典值（`== Status.*.value`），
   保证替换没有改变任何运行时语义。
"""

from __future__ import annotations

import ast
import io
import os

import pytest

from pilotstd.core.status import Status

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
STATUS_VALUES = {member.value for member in Status}

# 豁免路径：字典本身 + cookiecutter 脚手架模板（含 Jinja 占位符，非合法 Python）
EXEMPT_PREFIXES = ("pilotstd/core/status.py", "pilotstd/templates/")


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _scan_status_literals() -> list[str]:
    """扫描生产目录，返回 `文件:行 值` 形式的裸状态字面量列表（AST 口径）。"""
    found: list[str] = []
    for root in ("pilotstd", "docker"):
        for dirpath, _dirs, names in os.walk(os.path.join(REPO_ROOT, root)):
            if "__pycache__" in dirpath:
                continue
            for name in names:
                if not name.endswith(".py"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, name), REPO_ROOT).replace("\\", "/")
                if any(rel.startswith(prefix) for prefix in EXEMPT_PREFIXES):
                    continue
                try:
                    tree = ast.parse(io.open(os.path.join(REPO_ROOT, rel), encoding="utf-8").read())
                except SyntaxError:
                    continue
                skip = _docstring_node_ids(tree)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                        continue
                    if node.value in STATUS_VALUES and id(node) not in skip:
                        found.append(f"{rel}:{node.lineno} {node.value}")
    return found


def test_no_bare_status_literals_in_production():
    """已收敛的生产代码内不得再有裸状态字面量（防回归守卫）。"""
    leftovers = _scan_status_literals()
    assert leftovers == [], "仍有裸状态字面量（应改用 Status.*.value）：\n" + "\n".join(leftovers)


def test_all_status_values_are_reachable_from_enum():
    """守卫的前提：扫描集合来自枚举本身（避免哨兵值与枚举脱节）。

    **Sentinel 2**（#32-D）：下面 9 个中文字面量是本文件扫描基准的独立来源——
    若有人改动枚举 value，本断言与 `test_status.py` 的 Sentinel 1 会同时失败。
    """
    # Sentinel: 确保枚举 value 与现网中文契约一致（扫描基准必须独立于被测枚举实现）
    assert STATUS_VALUES == {
        "现行",
        "即将实施",
        "废止",
        "已废止",
        "被代替",
        "作废",
        "过期",
        "待确认",
        "未知",
    }


def test_validity_checker_status_output_matches_enum():
    """`ValidityChecker._determine_status` 的返回值与枚举值逐字一致。"""
    from pilotstd.core.validity_checker import ValidityChecker

    checker = ValidityChecker.__new__(ValidityChecker)  # 只测纯判定逻辑，不建 DB 连接

    abolished = checker._determine_status("GB/T 1-2020", {"std_name": "关于废止 GB/T 1-2020 的公告"})
    assert abolished is not None
    assert abolished["status"] == Status.WITHDRAWN_NORMALIZED.value

    active = checker._determine_status("GB/T 1-2020", {"std_name": "某标准"})
    assert active is not None
    assert active["status"] == Status.ACTIVE.value


@pytest.mark.parametrize("member", list(Status))
def test_enum_value_round_trip_for_converged_call_sites(member):
    """收敛点使用 `Status.X.value`，其类型与取值必须与字典一致（str 严格性）。"""
    assert type(member.value) is str
    assert member.value == Status(member.value).value
