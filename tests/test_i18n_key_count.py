"""check_i18n_key_count.py 单元测试 — 覆盖边界场景确保脚本可靠性。

测试策略：通过临时目录模拟 locale 文件结构，monkeypatch LOCALE_DIR 后调用 main()，
检查返回值与 stdout 输出验证行为。

静态场景使用 tests/fixtures/i18n/ 目录下的预置 JSON 文件；
动态场景（阈值边界）使用 monkeypatch + 运行时生成的数据。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# 将 scripts/ 加入搜索路径
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_i18n_key_count.py"
if SCRIPT.exists():
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_i18n_key_count", str(SCRIPT))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
else:
    pytest.skip("scripts/check_i18n_key_count.py not found", allow_module_level=True)

# ── fixtures 根目录 ──
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "i18n"


# ═══════════════════════════════════════════════════════════════
# 静态场景：使用预置 fixtures
# ═══════════════════════════════════════════════════════════════


def test_all_aligned_passes(monkeypatch, capsys):
    """三个文件完全对齐 → 返回值 0，输出 PASS。"""
    monkeypatch.setattr(mod, "LOCALE_DIR", FIXTURES / "aligned")
    rc = mod.main()
    assert rc == 0
    assert "PASS" in capsys.readouterr().out


def test_missing_key_fails(monkeypatch, capsys):
    """zh-CN 缺少 en.json 中存在的顶层 key → 返回值 1。"""
    monkeypatch.setattr(mod, "LOCALE_DIR", FIXTURES / "missing_key")
    rc = mod.main()
    assert rc == 1
    assert "error" in capsys.readouterr().out.lower()


def test_unique_key_warns(monkeypatch, capsys):
    """某文件有独有 key → 输出 warning，且因另一文件缺失该 key 而 exit 1。"""
    monkeypatch.setattr(mod, "LOCALE_DIR", FIXTURES / "unique_key")
    rc = mod.main()
    assert rc == 1
    captured = capsys.readouterr().out
    assert "extra_only" in captured


def test_nested_keys_not_misreported(monkeypatch, capsys):
    """同名 key 在不同层级（如 nav.pending vs home.pending）不应被误报。

    脚本只比较顶层 key，嵌套 key 的差异不影响对齐检查。
    """
    monkeypatch.setattr(mod, "LOCALE_DIR", FIXTURES / "nested_keys")
    rc = mod.main()
    assert rc == 0
    assert "PASS" in capsys.readouterr().out


def test_deeply_nested_key_drift_is_detected(monkeypatch, capsys):
    """v1.1.0 语义升级：深层**键**漂移现在要报错（旧版只比顶层，会放过这种漂移）。

    fixture `deep_nesting`：en = settings.x/settings.y，zh-CN = settings.a.b.c ——
    顶层 key 都是 settings，旧版判 PASS；叶子路径不一致，新版必须判 FAIL。
    """
    monkeypatch.setattr(mod, "LOCALE_DIR", FIXTURES / "deep_nesting")
    rc = mod.main()
    assert rc == 1
    assert "叶子 key" in capsys.readouterr().out


def test_deeply_nested_value_diff_passes(tmp_path, monkeypatch, capsys):
    """深层**取值**不同（叶子路径一致）不算漂移，仍应 PASS。"""
    d = make_locales(
        tmp_path,
        {
            "en.json": {"settings": {"a": {"b": "B"}}},
            "zh-CN.json": {"settings": {"a": {"b": "甲"}}},
        },
    )
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    assert mod.main() == 0
    assert "PASS" in capsys.readouterr().out


def test_leaf_drift_with_aligned_top_level_fails(tmp_path, monkeypatch, capsys):
    """顶层完全一致、只有叶子缺失 → 必须 FAIL（真实案例：zh-CN 曾缺 nav.archive）。"""
    d = make_locales(
        tmp_path,
        {
            "en.json": {"nav": {"home": "Home", "archive": "Archive"}},
            "zh-CN.json": {"nav": {"home": "首页"}},
        },
    )
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    rc = mod.main()
    assert rc == 1
    assert "nav.archive" in capsys.readouterr().out


def test_empty_object_counts_as_leaf(tmp_path, monkeypatch, capsys):
    """空对象 `{}` 记为一个叶子：一侧有、一侧没有 → FAIL（避免空壳 key 被漏掉）。"""
    d = make_locales(
        tmp_path,
        {"en.json": {"nav": {"home": "Home"}, "stub": {}}, "zh-CN.json": {"nav": {"home": "首页"}}},
    )
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    # 顶层缺 key 已经会 FAIL；这里断言叶子检查同样把它算出来
    assert mod.main() == 1
    assert "stub" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════
# 动态场景：运行时生成临时数据
# ═══════════════════════════════════════════════════════════════


def write_locale(tmp: Path, name: str, data: dict) -> Path:
    """在临时目录写入一个 locale JSON 文件。"""
    p = tmp / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def make_locales(tmp: Path, files: dict[str, dict]) -> Path:
    """批量写入多个 locale 文件，返回目录路径。"""
    d = tmp / "locales"
    d.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        write_locale(d, name, data)
    return d


def test_single_file_passes(tmp_path, monkeypatch, capsys):
    """单文件场景 — 无对齐问题，应通过。"""
    d = make_locales(tmp_path, {"en.json": {"nav": {"home": "Home"}}})
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    rc = mod.main()
    assert rc == 0
    assert "PASS" in capsys.readouterr().out


def test_empty_locale_dir(tmp_path, monkeypatch, capsys):
    """locale 目录为空 → 返回值 0，输出 warning。"""
    d = tmp_path / "locales"
    d.mkdir()
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    rc = mod.main()
    assert rc == 0
    captured = capsys.readouterr().out
    assert "warning" in captured.lower() or "No locale" in captured


def test_missing_directory(tmp_path, monkeypatch):
    """locale 目录不存在 → sys.exit(1)。"""
    monkeypatch.setattr(mod, "LOCALE_DIR", tmp_path / "nonexistent")
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1


def test_invalid_json(tmp_path, monkeypatch):
    """locale 文件含非法 JSON → sys.exit(1)。"""
    d = tmp_path / "locales"
    d.mkdir()
    (d / "bad.json").write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1


def test_warn_threshold(tmp_path, monkeypatch, capsys):
    """key 数 >= WARN_THRESHOLD → 输出 ::warning，返回值 0（仅警告不阻断）。"""
    monkeypatch.setattr(mod, "WARN_THRESHOLD", 2)
    monkeypatch.setattr(mod, "FAIL_THRESHOLD", 99)
    d = make_locales(tmp_path, {"en.json": {f"k{i}": {} for i in range(3)}})
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    rc = mod.main()
    assert rc == 0
    assert "warning" in capsys.readouterr().out


def test_fail_threshold(tmp_path, monkeypatch, capsys):
    """key 数 >= FAIL_THRESHOLD → 返回值 1。"""
    monkeypatch.setattr(mod, "WARN_THRESHOLD", 1)
    monkeypatch.setattr(mod, "FAIL_THRESHOLD", 2)
    d = make_locales(tmp_path, {"en.json": {f"k{i}": {} for i in range(3)}})
    monkeypatch.setattr(mod, "LOCALE_DIR", d)
    rc = mod.main()
    assert rc == 1
    assert "error" in capsys.readouterr().out
