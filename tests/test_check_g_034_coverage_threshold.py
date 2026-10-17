"""G-034 覆盖率门禁的解析与阈值来源（体检 A-3 / B-1，2026-10-17）。

回归两点：
1. 原正则只认 `行覆盖率: 85.2%`，而生成器的真实输出是**表格行** `| 行覆盖率 | **62.5%** |`
   ⇒ 永不匹配 ⇒ 门禁恒报"无法解析"。
2. 原阈值在本脚本硬编码 80.0，与 `pyproject.toml` 的 `fail_under`、CI 的 `--cov-fail-under`
   构成**四套口径**（51/45/58/80）⇒ 改为读 pyproject 作唯一权威。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_034_coverage_threshold.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_g_034_coverage_threshold", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


def test_parse_coverage_reads_generated_table_row() -> None:
    """生成器的真实输出是表格行 ⇒ 必须能解析出 62.5（这是被修掉的假红）。"""
    text = "| 指标 | 数值 |\n|---|---|\n| 行覆盖率 | **62.5%** |\n"
    assert gate.parse_coverage(text) == 62.5


def test_parse_coverage_still_accepts_colon_form() -> None:
    """旧的冒号写法仍要兼容（不得因修表格行而打破既有报告）。"""
    assert gate.parse_coverage("行覆盖率: 85.2%\n") == 85.2
    assert gate.parse_coverage("TOTAL 26356 1000 65%\n") == 65.0


def test_parse_coverage_returns_none_for_missing_data() -> None:
    """真没有数据时仍返回 None（不得"什么都能过"）。"""
    assert gate.parse_coverage("本报告只有一句说明，没有覆盖率数字。\n") is None


def test_threshold_comes_from_pyproject(tmp_path: Path) -> None:
    """阈值单一来源：从 pyproject 的 `fail_under` 读，而不是脚本内硬编码。"""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.coverage.report]\nfail_under = 77\n', encoding="utf-8")
    assert gate.resolve_threshold(pyproject) == 77.0


def test_threshold_falls_back_when_unreadable(tmp_path: Path) -> None:
    """pyproject 读不到/无该键时退回兜底值（不得抛）。"""
    missing = tmp_path / "nope.toml"
    assert gate.resolve_threshold(missing) == gate.FALLBACK_THRESHOLD
    empty = tmp_path / "empty.toml"
    empty.write_text("[tool.coverage]\n", encoding="utf-8")
    assert gate.resolve_threshold(empty) == gate.FALLBACK_THRESHOLD
