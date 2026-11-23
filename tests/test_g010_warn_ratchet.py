"""tests/test_g010_warn_ratchet.py — G-010 警告档棘轮（NEW-45，2026-11-24）。

背景：G-010 只拦 >500 阻断档；>400 警告档**仅提示不阻断**。
实测 20 个文件 >400（最高 496）全部 PASS ⇒ 警告档形同虚设，
文件可以一路从 401 涨到 500 才被拦。

修法：把当前 20 个 >400 文件的实测行数登记进 `scripts/g010_warn_baseline.json`，
此后只拦「新进入警告档」与「存量行数增长」。

本测试锁住三条判据（用受控临时树，不依赖真实仓库规模）：
  1. 新文件进入 >400 档 → FAIL
  2. 存量文件行数增长 → FAIL
  3. 存量文件行数减少 → 只 WARN（可收紧基线，不阻断）
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "check_g_010_code_size.py"


def _load():
    spec = importlib.util.spec_from_file_location("g010_ratchet", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _write_big_py(path: Path, code_lines: int) -> None:
    """写出恰好 `code_lines` 行有效代码的 .py 文件（无注释/空行干扰计数）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"x{i} = {i}" for i in range(code_lines))
    path.write_text(body + "\n", encoding="utf-8")


def _patch_baseline(monkeypatch, tmp_path: Path, files: dict[str, int]) -> None:
    """把门禁的基线路径指向临时文件。"""
    baseline = tmp_path / "g010_warn_baseline.json"
    baseline.write_text(
        json.dumps({"_meta": {}, "files": files}, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(m, "WARN_BASELINE", baseline)


def test_new_file_entering_warn_tier_fails(tmp_path, monkeypatch):
    """新文件进入 >400 档且不在基线 → FAIL。"""
    _patch_baseline(monkeypatch, tmp_path, {})
    tree = tmp_path / "tree"
    _write_big_py(tree / "brand_new.py", m.WARN_FILE_LINES + 5)

    errors, _warnings = m.scan(tree)

    assert any("brand_new.py" in e and "新进入警告档" in e for e in errors), errors


def test_existing_file_growing_fails(tmp_path, monkeypatch):
    """存量文件行数增长 → FAIL。"""
    tree = tmp_path / "tree"
    _write_big_py(tree / "grown.py", m.WARN_FILE_LINES + 20)
    _patch_baseline(monkeypatch, tmp_path, {"grown.py": m.WARN_FILE_LINES + 5})

    errors, _warnings = m.scan(tree)

    assert any("grown.py" in e and "增长" in e for e in errors), errors


def test_existing_file_shrinking_only_warns(tmp_path, monkeypatch):
    """存量文件行数减少 → 只 WARN（可收紧基线，不阻断）。"""
    tree = tmp_path / "tree"
    _write_big_py(tree / "shrunk.py", m.WARN_FILE_LINES + 5)
    _patch_baseline(monkeypatch, tmp_path, {"shrunk.py": m.WARN_FILE_LINES + 20})

    errors, warnings = m.scan(tree)

    assert not any("shrunk.py" in e for e in errors), errors
    assert any("shrunk.py" in w and "STALE" in w for w in warnings), warnings


def test_unchanged_file_passes(tmp_path, monkeypatch):
    """与基线一致 → 不报错不告警。"""
    tree = tmp_path / "tree"
    _write_big_py(tree / "same.py", m.WARN_FILE_LINES + 10)
    _patch_baseline(monkeypatch, tmp_path, {"same.py": m.WARN_FILE_LINES + 10})

    errors, warnings = m.scan(tree)

    assert not any("same.py" in e for e in errors), errors
    assert not any("same.py" in w for w in warnings), warnings


def test_block_tier_still_takes_precedence(tmp_path, monkeypatch):
    """>500 阻断档仍由原逻辑处理（不被棘轮吞掉）。"""
    tree = tmp_path / "tree"
    _write_big_py(tree / "huge.py", m.MAX_FILE_LINES + 30)
    _patch_baseline(monkeypatch, tmp_path, {"huge.py": m.MAX_FILE_LINES + 30})

    errors, _warnings = m.scan(tree)

    assert any("huge.py" in e and "必须分拆" in e for e in errors), errors


def test_real_baseline_exists_and_is_consistent():
    """真实基线文件存在且条数与 _meta 自洽（防手工编辑漂移）。"""
    baseline_path = SCRIPTS / "g010_warn_baseline.json"
    assert baseline_path.exists(), "缺少 scripts/g010_warn_baseline.json"
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    files = data.get("files", {})
    assert files, "基线不应为空"
    assert data["_meta"]["file_count"] == len(files)
    # 每个登记值必须落在警告档区间内
    for rel, n in files.items():
        assert m.WARN_FILE_LINES < n <= m.MAX_FILE_LINES, f"{rel}: {n} 不在警告档区间"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
