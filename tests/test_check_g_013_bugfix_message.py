"""G-013 规则 0 的消息来源（2026-10-17，体检 D-6 相邻缺陷）。

实测缺陷：`get_commit_message()` 原先优先读 `.git/COMMIT_EDITMSG`，而 pre-commit
阶段 git **尚未写入本次消息**，该文件仍是上一条提交的留言 ⇒ 一条纯 docs 提交被
前一条 `fix(gate):` 拦住（假阻断）。修复后：

1. pre-commit 传 `--no-commit-msg`，只跑规则 1（业务代码 → 测试联动）；
2. commit-msg 传 `--commit-msg-file "$1" --bugfix-only`，用**本次**消息跑规则 0。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_013_test_coverage.py"


def _load():
    # 脚本用 `from _gate_git import ...`（同目录模块），单独跑本文件时需把 scripts/ 入路径
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("check_g_013_test_coverage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()
DOCS_ONLY = ["docs/index.md"]


def test_fix_message_without_test_change_blocks() -> None:
    """提交消息含 fix 且没改测试 ⇒ 规则 0 阻断。"""
    result = gate.run_check(changed_files=DOCS_ONLY, commit_msg="fix(gate): x\n", bugfix_only=True)
    assert result["passed"] is False
    assert any("[TEST-BLOCK]" in e for e in result["errors"])


def test_fix_message_with_test_change_passes() -> None:
    result = gate.run_check(
        changed_files=[*DOCS_ONLY, "tests/test_x.py"],
        commit_msg="fix(gate): x\n",
        bugfix_only=True,
    )
    assert result["passed"] is True


def test_no_commit_msg_skips_rule_zero() -> None:
    """pre-commit 传 --no-commit-msg 时不得因上一条 fix 消息中断。"""
    result = gate.run_check(changed_files=DOCS_ONLY, commit_msg="fix(gate): 上一条\n", check_bugfix=False)
    assert result["passed"] is True


def test_docs_message_does_not_trigger_bugfix_rule() -> None:
    """``T-43``/``docs`` 等正文不得被误判为 fix（单词边界）。"""
    result = gate.run_check(
        changed_files=DOCS_ONLY,
        commit_msg="docs(debt): 回写 T-43 状态与 C-6\n",
        bugfix_only=True,
    )
    assert result["passed"] is True


def test_filename_containing_test_is_not_a_test_change() -> None:
    """`scripts/check_g_013_test_coverage.py` 文件名含 test，但它不是测试文件。"""
    result = gate.run_check(
        changed_files=["scripts/check_g_013_test_coverage.py"],
        commit_msg="fix(gate): 修规则 0\n",
        bugfix_only=True,
    )
    assert result["passed"] is False
    assert gate.is_test_file("tests/test_x.py") is True
    assert gate.is_test_file("scripts/check_g_013_test_coverage.py") is False


def test_commit_message_read_failure_warns(tmp_path, capsys) -> None:
    """读消息失败 → 返回空串但 stderr 留 WARN（静默空消息会让规则 0 失效）。"""
    missing = tmp_path / "no_such_msg_file"
    assert gate.get_commit_message(str(missing)) == ""
    err = capsys.readouterr().err
    assert "[WARN]" in err
    assert "commit message" in err
