"""G-029 的范围取值与 UI 映射（体检 D-7，2026-10-17）。

原缺陷：`git diff origin/main..HEAD` 在直推 main 时恒空 ⇒ 打印"无变更文件 PASS"。
修复后：显式 `G029_RANGE`（before..sha）优先；`before` 全零回退；
显式范围 0 文件 ⇒ FAIL（不再静默通过）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_029_test_coverage.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_g_029_test_coverage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


def test_zero_before_detected() -> None:
    assert gate._is_zero_before("0000000000..abc") is True
    assert gate._is_zero_before("abc..def") is False


def test_explicit_empty_range_fails(monkeypatch) -> None:
    """显式范围 0 文件时必须返回 None（调用方判 FAIL），不得当成"无变更"。"""
    monkeypatch.setenv("G029_RANGE", "abc..def")
    monkeypatch.setattr(gate, "_diff", lambda _spec: [])
    assert gate.get_changed_files() is None
    monkeypatch.setattr(gate, "_diff", lambda _spec: ["pilotstd/ui/x.py"])
    assert gate.get_changed_files() == ["pilotstd/ui/x.py"]


def test_zero_before_falls_back(monkeypatch) -> None:
    """新分支 before 全零 ⇒ 忽略显式范围，回退到 origin/base...HEAD。"""
    monkeypatch.setenv("G029_RANGE", "0000..abc")
    calls: list[str] = []

    def fake_diff(spec: str) -> list[str]:
        calls.append(spec)
        return ["pilotstd/ui/x.py"] if "origin/" in spec else []

    monkeypatch.setattr(gate, "_diff", fake_diff)
    assert gate.get_changed_files() == ["pilotstd/ui/x.py"]
    assert "origin/" in calls[0]


def test_ui_mapping_covers_tests_gui_and_test_ui() -> None:
    src, tests = gate.COVERAGE_MAP[0]
    assert src == ["pilotstd/ui/"]
    assert "tests/gui/" in tests
    assert any(t.startswith("tests/test_ui") for t in tests)
