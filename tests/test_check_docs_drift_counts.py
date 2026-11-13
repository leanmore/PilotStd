"""G-052 数字声明校验（P2-07）的受控测试。

覆盖：仓库现状一致、事实变化被检出、声明缺失/数值不符被判违规。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_docs_drift.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_docs_drift", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_docs_match_code_facts():
    """当前仓库：所有 COUNT_CLAIMS 与代码事实一致（数字漂移即红）。"""
    drift = _load()
    assert drift.check_count_claims(drift.load_facts()) == []


def test_drift_detected_when_route_count_changes():
    """多一条路由 → 03/19/20 的声明必须被判 count_drift。"""
    drift = _load()
    facts = drift.load_facts()
    facts["routes"] = facts["routes"] + ["/api/__p2_07_probe__"]
    violations = drift.check_count_claims(facts)
    assert violations
    assert all(v["kind"] == "count_drift" for v in violations)
    assert any(v["file"] == "docs/onboarding/03-architecture.md" for v in violations)


def test_missing_claim_is_violation(tmp_path):
    """声明被删掉 → count_missing（不能靠删数字绕过门禁）。"""
    drift = _load()
    doc = tmp_path / "docs" / "x.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("这里没有数字声明", encoding="utf-8")
    claims = ({"doc": "docs/x.md", "pattern": r"(\d+) 张表", "label": "表数", "expected": lambda f: (1,)},)
    violations = drift.check_count_claims({}, claims=claims, root=tmp_path)
    assert [v["kind"] for v in violations] == ["count_missing"]


def test_value_mismatch_reports_line(tmp_path):
    """文档 7 ≠ 实际 8 → count_drift，并给出行号。"""
    drift = _load()
    doc = tmp_path / "docs" / "y.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("第一行\n**7 张表**\n", encoding="utf-8")
    claims = ({"doc": "docs/y.md", "pattern": r"\*\*(\d+) 张表\*\*", "label": "表数", "expected": lambda f: (8,)},)
    violations = drift.check_count_claims({}, claims=claims, root=tmp_path)
    assert [v["kind"] for v in violations] == ["count_drift"]
    assert violations[0]["line"] == 2
