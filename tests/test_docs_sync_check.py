"""tests/test_docs_sync_check.py — docs_sync_check.py 的受控测试（T-16，2026-09-27）。

背景：该脚本的 8 条触发规则曾因 `_match_trigger_rules` 用**字典字面量**做 arity 分派而**全部失效**——
`{3: fn(a,b,c), 2: fn(a,b), 1: fn(a)}.get(n)` 会先求值三个调用，参数个数不符者抛 TypeError 被 except 吞掉，
于是规则从未触发过；同时脚本只读暂存区（CI 全新检出恒为空）且恒 `return 0`。
本文件锁定修复后的行为：arity 分派、范围切分、严格模式开关。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "docs_sync_check.py"


def _load_module():
    """以文件路径加载脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("docs_sync_check", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import pytest


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# ── arity 分派（回归守卫：修复前所有规则都会抛 TypeError 而失效） ──


def test_all_trigger_rules_are_callable_without_typeerror(mod, capsys) -> None:
    """8 条规则都要能被正确 arity 调用；不得出现"规则异常"提示。"""
    changed = [("M", "web/src/App.vue"), ("M", "pilotstd/core/x.py"), ("A", "tests/test_new.py")]
    mod._match_trigger_rules(changed, "diff-body", "feat: something")
    out = capsys.readouterr().out
    assert "规则「" not in out, f"有规则抛异常（arity 分派回归）: {out}"


def test_source_and_commit_message_rules_fire(mod, capsys) -> None:
    """源码变更 + feat: 提交 → 应触发 STATUS.md 与 CHANGELOG.md 两条规则。"""
    changed = [("M", "web/src/App.vue")]
    deduped = mod._match_trigger_rules(changed, "", "feat: add thing")
    docs = {doc for _tn, doc, _s, _r in deduped}
    assert "CHANGELOG.md" in docs
    assert "STATUS.md" in docs


def test_in_repo_flag_distinguishes_blocking_targets(mod) -> None:
    """feat:/fix: → CHANGELOG.md 为 in_repo=True（严格模式判定对象）；STATUS.md 为 False。"""
    deduped = mod._match_trigger_rules([("M", "web/src/App.vue")], "", "fix: bug")
    flags = {doc: in_repo for _tn, doc, _s, in_repo in deduped}
    assert flags.get("CHANGELOG.md") is True
    assert flags.get("STATUS.md") is False


def test_doc_already_changed_is_skipped(mod) -> None:
    """目标文档已与本次变更同批更新 → 不再要求（按 basename 判定）。"""
    changed = [("M", "web/src/App.vue"), ("M", "CHANGELOG.md")]
    deduped = mod._match_trigger_rules(changed, "", "feat: add thing")
    assert "CHANGELOG.md" not in {doc for _tn, doc, _s, _r in deduped}


# ── 参数解析与范围切分 ──


def test_parse_args(mod) -> None:
    assert mod._parse_args([]) == {"range": None, "base": None, "strict": False, "strict_block": False}
    assert mod._parse_args(["--range", "A..B"])["range"] == "A..B"
    assert mod._parse_args(["--base", "main"])["base"] == "main"
    opts = mod._parse_args(["--strict"])
    assert opts["strict"] is True and opts["strict_block"] is False
    opts = mod._parse_args(["--strict-block"])
    assert opts["strict"] is True and opts["strict_block"] is True


def test_split_range_handles_two_and_three_dots(mod) -> None:
    assert mod._split_range("a..b") == ("a", "b")
    assert mod._split_range("a...b") == ("a", "b")
    assert mod._split_range("") == ("", "")


def test_invalid_ranges_are_rejected(mod) -> None:
    assert mod._range_is_valid("") is False
    assert mod._range_is_valid("HEAD") is False
    # 全 0 SHA（GitHub 新分支/首次推送的 before）必须判无效
    assert mod._range_is_valid("0000000000000000000000000000000000000000..HEAD") is False


def test_help_exits_zero(mod) -> None:
    with pytest.raises(SystemExit) as exc:
        mod._parse_args(["--help"])
    assert exc.value.code == 0
