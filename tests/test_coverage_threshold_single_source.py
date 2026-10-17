"""覆盖率阈值单一来源（体检 B-1，2026-10-17）。

历史问题：`pyproject.toml` 的 `fail_under`（51）、CI `test-backend` 的
`--cov-fail-under=45`、CI GUI 的 `--fail-under=58`、旧 `gates.md` 的 80 并存；
G-034 脚本与 `generate_coverage_report.py` 各自硬编码一套，报告里甚至写死 "≥80%"。
本测试锁住：两处消费者必须共用 `scripts/_coverage_threshold.py` 的同一个函数，
且该函数读的就是 pyproject 的 `fail_under`。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
GATE = SCRIPTS / "check_g_034_coverage_threshold.py"
GENERATOR = SCRIPTS / "generate_coverage_report.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # 生成器内部 import 需要能命中自身模块名
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(SCRIPTS))
# 用规范模块名加载：门禁与生成器内部 `from _coverage_threshold import ...` 必须命中同一对象
helper = _load("_coverage_threshold", SCRIPTS / "_coverage_threshold.py")
gate = _load("check_g_034_coverage_threshold", GATE)
generator = _load("generate_coverage_report", GENERATOR)


def test_gate_and_generator_share_one_resolver() -> None:
    """两个消费者必须是同一函数，而不是各自复制一份解析逻辑。"""
    assert gate.resolve_threshold is helper.resolve_threshold
    assert generator.resolve_threshold is helper.resolve_threshold


def test_threshold_equals_pyproject_fail_under() -> None:
    """权威值来自 pyproject 的 `fail_under`，不得再从别处取值。"""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"^\s*fail_under\s*=\s*([\d.]+)", text, re.MULTILINE)
    assert match, "pyproject.toml 缺少 fail_under，阈值将退化为兜底值"
    assert helper.resolve_threshold() == float(match.group(1))
