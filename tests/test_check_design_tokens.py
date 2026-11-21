"""G-055 设计令牌门禁的受控测试（反证）。

覆盖任务包要求的五类行为：
  1. 新增 hex 颜色 → 阻断；
  2. 新增固定像素视觉值 → 阻断；
  3. 新增内联 style 高度 → 阻断（白名单也必须占基线名额）；
  4. 基线内 B 类 / C 类存量 → 不误报；
  5. 基线条目数量减少 → 只提示过期（不阻断、不自动改基线）。

每个用例都在临时树里跑，不触碰真实仓库的 baseline。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 门禁脚本与审计脚本同在 scripts/，测试通过 sys.path 注入复用同一套分类
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_design_tokens as gate  # noqa: E402


def write_tree(tmp_path: Path, css: str = "", template: str = '<div class="a" />') -> Path:
    """构造一棵最小 web/src 树：一个 .vue（含 style 块与模板）+ 一份 style.css 令牌定义。"""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    # 令牌定义：让 --danger / --space-8 等被识别为"已定义"，否则会被判成 D 类缺陷
    (src / "style.css").write_text(
        ":root {\n  --danger: #ef4444;\n  --text: #475569;\n  --space-8: 8px;\n}\n",
        encoding="utf-8",
    )
    (src / "Comp.vue").write_text(
        f"<template>{template}</template>\n<style scoped>\n{css}\n</style>\n",
        encoding="utf-8",
    )
    return src


def write_baseline(path: Path, entries: list[dict]) -> Path:
    """写一份最小基线：entries 形如 {"file","prop","value","count"}。"""
    groups = [{"id": "test-group", "class": "C", "reason": "测试用", "entries": entries}]
    path.write_text(
        json.dumps({"version": 1, "gate": "G-055", "groups": groups}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_new_hex_color_is_blocked(tmp_path: Path) -> None:
    """新增 hex 颜色（A 类：可映射到 --danger）必须阻断，并给出建议令牌。"""
    src = write_tree(tmp_path, css=".a { color: #ef4444; }")
    baseline = write_baseline(tmp_path / "baseline.json", [])

    violations, stale = gate.check(src, baseline)

    assert stale == []
    assert len(violations) == 1
    assert "A 类" in violations[0] and "--danger" in violations[0]


def test_new_fixed_px_visual_is_blocked(tmp_path: Path) -> None:
    """新增固定像素字号（A 类：--font-size-13）必须阻断。"""
    src = write_tree(tmp_path, css=".a { font-size: 13px; }")
    baseline = write_baseline(tmp_path / "baseline.json", [])

    violations, _ = gate.check(src, baseline)

    assert len(violations) == 1
    assert "--font-size-13" in violations[0]


def test_new_inline_height_is_blocked(tmp_path: Path) -> None:
    """新增内联 style 高度（B 类、基线外）必须阻断。"""
    src = write_tree(tmp_path, css=".a { display: flex; }", template='<div style="height: 20px" />')
    baseline = write_baseline(tmp_path / "baseline.json", [])

    violations, _ = gate.check(src, baseline)

    assert len(violations) == 1
    assert "height: 20px" in violations[0]


def test_c_class_var_fallback_not_reported(tmp_path: Path) -> None:
    """C 类存量（var() fallback）在基线内时不得误报。"""
    css = ".a { color: var(--danger, #e74c3c); }"
    src = write_tree(tmp_path, css=css)
    baseline = write_baseline(
        tmp_path / "baseline.json",
        [{"file": "Comp.vue", "prop": "color", "value": "var(--danger, #e74c3c)", "count": 1}],
    )

    violations, stale = gate.check(src, baseline)

    assert violations == [] and stale == []


def test_baseline_b_entry_not_reported(tmp_path: Path) -> None:
    """B 类存量在基线内时不得误报。"""
    src = write_tree(tmp_path, css=".a { height: 20px; }")
    baseline = write_baseline(
        tmp_path / "baseline.json",
        [{"file": "Comp.vue", "prop": "height", "value": "20px", "count": 1}],
    )

    violations, stale = gate.check(src, baseline)

    assert violations == [] and stale == []


def test_inline_whitelist_requires_baseline_entry(tmp_path: Path) -> None:
    """内联白名单不是"免检"：没有基线名额时依然阻断。

    真实仓库的 2 条内联白名单在 baseline 里各占 1 个 count，因此这里验证的是
    "白名单也走同一套计数"这一性质。
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "style.css").write_text(":root { --text: #475569; }\n", encoding="utf-8")
    (src / "views").mkdir()
    (src / "views" / "PendingView.vue").write_text(
        '<template><div style="height: 20px" /></template>\n<style scoped>\n\n</style>\n',
        encoding="utf-8",
    )
    baseline = write_baseline(tmp_path / "baseline.json", [])

    violations, _ = gate.check(src, baseline)

    assert len(violations) == 1
    assert "PendingView.vue" in violations[0]


def test_same_value_beyond_baseline_count_blocked(tmp_path: Path) -> None:
    """同一文件同属性同值出现次数超过基线次数必须阻断（新增即超限）。"""
    src = write_tree(tmp_path, css=".a { height: 20px; }\n.b { height: 20px; }")
    baseline = write_baseline(
        tmp_path / "baseline.json",
        [{"file": "Comp.vue", "prop": "height", "value": "20px", "count": 1}],
    )

    violations, _ = gate.check(src, baseline)

    assert len(violations) == 1
    assert "当前第 2 次" in violations[0]


def test_stale_baseline_only_warns(tmp_path: Path) -> None:
    """基线条目数量减少时只提示过期，不阻断，且脚本不修改基线文件。"""
    src = write_tree(tmp_path, css=".a { display: flex; }")
    baseline = write_baseline(
        tmp_path / "baseline.json",
        [{"file": "Comp.vue", "prop": "height", "value": "20px", "count": 2}],
    )
    before = baseline.read_text(encoding="utf-8")

    violations, stale = gate.check(src, baseline)

    assert violations == []
    assert len(stale) == 1 and "基线 2 次 / 当前 0 次" in stale[0]
    assert baseline.read_text(encoding="utf-8") == before


def test_cli_exit_code_on_violation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI 在发现新增 A 类硬编码时退出码必须为 1。"""
    src = write_tree(tmp_path, css=".a { font-size: 13px; }")
    baseline = write_baseline(tmp_path / "baseline.json", [])
    monkeypatch.setattr(sys, "argv", ["check_design_tokens.py", "--root", str(src), "--baseline", str(baseline)])

    assert gate.main() == 1
