"""tests/test_check_docs_sync.py — check_docs_sync.py 的受控测试（R11-3，2026-09-27）。

背景（第五个 CI 盲区：范围取值陷阱）：CI 步骤的 `DOCS_SYNC_RANGE` 曾写成
`${{ github.event.before }}..${{ github.event.sha }}`，而 push 载荷里**没有** `event.sha`
→ 右端展开为空 → 该候选判非法 → 回退 `origin/main...HEAD`；推送到 main 时
`origin/main` 与 `HEAD` 指向同一提交、diff 恒空 → 步骤长期打印 `PASS: 无变更文件` 而空转
（run 36304263963 的步骤环境实证：`DOCS_SYNC_RANGE: 27a39d61…93..`）。

本文件锁定修复后的行为：严格模式下候选范围必须**确实含变更文件**才算命中，
空 diff 的候选继续向下回退；`--range` 硬指定不受该过滤影响。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_docs_sync.py"


def _load_module():
    """以文件路径加载脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("check_docs_sync", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _fake_git(changes: dict, resolvable: bool = True):
    """构造 _run_git 替身：rev-parse 一律可解析；diff 按范围返回预设内容。"""

    def fake(args):
        if args[:2] == ["rev-parse", "--verify"]:
            return "abc1234" if resolvable else ""
        if args and args[0] == "diff" and "--name-only" in args:
            return changes.get(args[-1], "")
        return ""

    return fake


def test_strict_mode_falls_back_when_derived_range_is_empty(mod, monkeypatch) -> None:
    """origin/main...HEAD 可解析但 diff 为空 → 回退 HEAD~1..HEAD 并据此判定。"""
    monkeypatch.setattr(mod, "_run_git", _fake_git({"HEAD~1..HEAD": "docs/technical-debt.md\n"}))
    monkeypatch.setenv("DOCS_SYNC_RANGE", "deadbeef..")
    monkeypatch.setenv("BASE_BRANCH", "main")
    rng, why = mod.resolve_range(mod.parse_args(["--strict"]))
    assert rng == "HEAD~1..HEAD", (rng, why)


def test_env_range_wins_when_both_ends_resolve_and_have_changes(mod, monkeypatch) -> None:
    """两端齐全且确有变更时，环境变量范围优先于任何回退候选。"""
    changes = {"a1b2c3..d4e5f6": "pilotstd/query/x.py\n", "HEAD~1..HEAD": "docs/x.md\n"}
    monkeypatch.setattr(mod, "_run_git", _fake_git(changes))
    monkeypatch.setenv("DOCS_SYNC_RANGE", "a1b2c3..d4e5f6")
    rng, why = mod.resolve_range(mod.parse_args(["--strict"]))
    assert rng == "a1b2c3..d4e5f6" and why == "环境变量 DOCS_SYNC_RANGE"


def test_non_strict_mode_keeps_legacy_selection(mod, monkeypatch) -> None:
    """非严格模式（本地默认）保持旧行为，不因空 diff 去抓历史提交。"""
    monkeypatch.setattr(mod, "_run_git", _fake_git({"HEAD~1..HEAD": "docs/technical-debt.md\n"}))
    monkeypatch.delenv("DOCS_SYNC_RANGE", raising=False)
    monkeypatch.setenv("BASE_BRANCH", "main")
    rng, _why = mod.resolve_range(mod.parse_args([]))
    assert rng == "origin/main...HEAD"


def test_explicit_range_is_never_filtered_out(mod, monkeypatch) -> None:
    """`--range` 为受控验证的硬指定：diff 为空也照用（其合法性由 rev-parse 判据把关）。"""
    monkeypatch.setattr(mod, "_run_git", _fake_git({}))
    monkeypatch.delenv("DOCS_SYNC_RANGE", raising=False)
    monkeypatch.delenv("BASE_BRANCH", raising=False)
    rng, why = mod.resolve_range(mod.parse_args(["--strict", "--range", "A..B"]))
    assert rng == "A..B" and why == "--range 指定"


def test_all_empty_candidates_report_explicit_reason(mod, monkeypatch) -> None:
    """全部候选为空时给出显式原因（供 main() 打印），不静默通过。"""
    monkeypatch.setattr(mod, "_run_git", _fake_git({}))
    monkeypatch.delenv("DOCS_SYNC_RANGE", raising=False)
    monkeypatch.setenv("BASE_BRANCH", "main")
    rng, why = mod.resolve_range(mod.parse_args(["--strict"]))
    assert rng is not None and "无变更" in why, (rng, why)


def test_range_has_changes_reflects_diff(mod, monkeypatch) -> None:
    monkeypatch.setattr(mod, "_run_git", _fake_git({"HEAD~1..HEAD": "docs/x.md\n"}))
    assert mod._range_has_changes("HEAD~1..HEAD") is True
    assert mod._range_has_changes("origin/main...HEAD") is False


# ── 浅克隆（check-repo-compliance.sh 曾以 --depth=1 建立浅边界 → HEAD~1 不可用） ──


def test_shallow_clone_reason_is_explicit(mod, monkeypatch) -> None:
    """浅克隆下候选全空时必须点明「历史被截断」，不得只说「该范围无变更」。"""
    monkeypatch.setattr(mod, "_run_git", _fake_git({}))
    monkeypatch.setattr(mod, "_is_shallow_clone", lambda: True)
    monkeypatch.delenv("DOCS_SYNC_RANGE", raising=False)
    monkeypatch.setenv("BASE_BRANCH", "main")
    rng, why = mod.resolve_range(mod.parse_args(["--strict"]))
    assert rng is not None and "浅克隆" in why, (rng, why)


def test_non_shallow_clone_reason_has_no_hint(mod, monkeypatch) -> None:
    monkeypatch.setattr(mod, "_run_git", _fake_git({}))
    monkeypatch.setattr(mod, "_is_shallow_clone", lambda: False)
    monkeypatch.delenv("DOCS_SYNC_RANGE", raising=False)
    monkeypatch.setenv("BASE_BRANCH", "main")
    _rng, why = mod.resolve_range(mod.parse_args(["--strict"]))
    assert "浅克隆" not in why
