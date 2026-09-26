"""tests/test_check_no_conflict_markers.py — G-039 冲突标记门禁的受控测试。

覆盖：正常文件通过 / 冲突块被检出 / 孤立标记被检出 / Markdown Setext 下划线不误伤 /
白名单夹具通过 / 自带标记的临时文件在 CLI 下返回非 0。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_no_conflict_markers.py"

# 标记用拼接构造：本测试文件因此不含字面量（否则会被本门禁判违规）
LT = "<" * 7
GT = ">" * 7
EQ = "=" * 7


def _load_module():
    """以文件路径加载门禁脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("check_no_conflict_markers", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    """加载后的门禁模块。"""
    return _load_module()


def test_clean_file_passes(gate, tmp_path: Path) -> None:
    """普通文本文件不含标记 → 无违规。"""
    f = tmp_path / "clean.txt"
    f.write_text("hello\nworld\n", encoding="utf-8")
    assert gate.find_violations(f) == []


def test_conflict_block_is_detected(gate, tmp_path: Path) -> None:
    """完整冲突块 → 三行标记（<、=、>）全部命中。"""
    f = tmp_path / "conflicted.txt"
    f.write_text(f"a\n{LT} HEAD\nours\n{EQ}\ntheirs\n{GT} branch\nb\n", encoding="utf-8")
    hits = gate.find_violations(f)
    assert [h[0] for h in hits] == [2, 4, 6], hits


def test_lone_marker_is_detected(gate, tmp_path: Path) -> None:
    """孤立标记（残缺残留）也要判违规。"""
    f = tmp_path / "lone.txt"
    f.write_text(f"a\n{LT} HEAD\nb\n", encoding="utf-8")
    assert [h[0] for h in gate.find_violations(f)] == [2]
    f2 = tmp_path / "lone2.txt"
    f2.write_text(f"a\n{GT} branch\nb\n", encoding="utf-8")
    assert [h[0] for h in gate.find_violations(f2)] == [2]


def test_markdown_setext_underline_not_flagged(gate, tmp_path: Path) -> None:
    """`=======` 作 Markdown Setext 标题下划线时不误伤（不成块即合法）。"""
    f = tmp_path / "doc.md"
    f.write_text(f"标题\n{EQ}\n\n正文\n", encoding="utf-8")
    assert gate.find_violations(f) == []


def test_whitelisted_fixture_passes(gate, tmp_path: Path) -> None:
    """白名单夹具（用于测试本门禁自身）即使含标记也跳过。"""
    f = tmp_path / "conflict-marker-fixture.txt"
    f.write_text(f"{LT} HEAD\n{EQ}\n{GT} x\n", encoding="utf-8")
    assert gate.WHITELIST_NAME_SUFFIXES == ("conflict-marker-fixture.txt",)
    assert gate.find_violations(f) == []


def test_cli_fails_on_conflict_and_passes_when_clean(gate, tmp_path: Path, capsys) -> None:
    """CLI 语义：有标记 → 1，无标记 → 0。"""
    bad = tmp_path / "bad.txt"
    bad.write_text(f"{LT} HEAD\nours\n{EQ}\ntheirs\n{GT} branch\n", encoding="utf-8")
    assert gate.main([str(bad)]) == 1
    assert "[MARKER]" in capsys.readouterr().out

    good = tmp_path / "good.txt"
    good.write_text("clean\n", encoding="utf-8")
    assert gate.main([str(good)]) == 0


def test_gate_script_itself_is_clean(gate) -> None:
    """门禁脚本自身用拼接构造标记 → 自扫描必须通过（否则它自己就会被拦）。"""
    assert gate.find_violations(SCRIPT) == []


def test_binary_and_missing_files_are_skipped(gate, tmp_path: Path) -> None:
    """二进制/不可读文件跳过，不抛异常。"""
    f = tmp_path / "blob.bin"
    f.write_bytes(b"\xff\xfe\x00\x01" + LT.encode() + b"\n")
    assert gate.find_violations(f) == []
    assert gate.find_violations(tmp_path / "not-exists.txt") == []
