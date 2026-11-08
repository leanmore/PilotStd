# tests/test_scripts_fail_loud_batch2.py — U34 E-fix-scripts 批 2
"""锁定「git 取不到 ≠ 无变更」「continue 跳过必须留痕」「G-013 内容取空不得退化成 PASS」。

覆盖：
- 1.2 `check_module_doc_mappings` / `docs_sync_check`：git 失败 → `[WARN]` + **exit 2**；
- E3 `check_g_010_code_size`：读文件失败 + continue → `[WARN]`；
- D-17 `ast.unparse` 失败 → `[WARN]`，且不污染 `has_io`；
- D-18 `get_content_at` git 不可用 → `None`（与「ref 中无此文件 → ''」区分），`_load_pair` → exit 2。
"""

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str, filename: str):
    """以文件路径加载脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ── 1.2 git 失败 → WARN + exit 2 ────────────────────────────────────────


def test_module_doc_mappings_exits_2_when_git_unavailable(capsys) -> None:
    """git 取不到 → 不能当"无变更"，必须 exit 2。"""
    mod = _load("check_module_doc_mappings_t", "check_module_doc_mappings.py")
    mod._run_git = lambda args: None  # 模拟 git 失败
    with pytest.raises(SystemExit) as exc:
        mod.get_changed_files("HEAD~1..HEAD")
    assert exc.value.code == 2
    assert "[WARN]" in capsys.readouterr().err


def test_docs_sync_diff_or_exit_exits_2(capsys) -> None:
    """docs_sync_check 的 diff 查询失败 → exit 2。"""
    mod = _load("docs_sync_check_t", "docs_sync_check.py")
    mod._run_git = lambda args: None
    with pytest.raises(SystemExit) as exc:
        mod._diff_or_exit(["diff", "--cached", "--name-status"])
    assert exc.value.code == 2
    assert "[WARN]" in capsys.readouterr().err


# ── E3 读文件失败 + continue → WARN ────────────────────────────────────


def test_code_size_warns_on_undecodable_file(tmp_path, capsys) -> None:
    """非 UTF-8 文件被跳过，但必须 [WARN]（否则规模门禁静默漏检）。"""
    mod = _load("check_g_010_t", "check_g_010_code_size.py")
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"\xff\xfe\x00not utf8")
    mod.scan(tmp_path)
    err = capsys.readouterr().err
    assert "[WARN]" in err and "bad.py" in err


# ── D-17 ast.unparse 失败不污染 has_io ─────────────────────────────────


def test_unparse_failure_keeps_has_io_consistent(monkeypatch, capsys) -> None:
    """单个调用 unparse 失败 → 只少判该调用，不影响其他调用的 has_io。"""
    mod = _load("check_g_013_t", "check_g_013_test_coverage.py")
    src = (
        "def f():\n"
        "    requests.get('u')\n"
        "    obj.boom()\n"
    )
    tree = ast.parse(src)
    real_unparse = ast.unparse

    def fake_unparse(node):
        if isinstance(node, ast.Attribute) and node.attr == "boom":
            raise ValueError("simulated unparse failure")
        return real_unparse(node)

    monkeypatch.setattr(ast, "unparse", fake_unparse)
    apis = mod._extract_api_signatures(tree)
    # requests.get 命中 IO_PATTERN；boom() 失败只影响它自己
    assert apis["f"]["has_io"] is True
    assert "[WARN]" in capsys.readouterr().err


# ── D-18 get_content_at：git 不可用 → None（≠ 文件不存在 ''） ──────────


def test_get_content_at_returns_none_when_git_unavailable(monkeypatch, capsys) -> None:
    """git 超时/不可用 → None；不得与"文件不存在 → ''"混同。"""
    mod = _load("check_g_013_t2", "check_g_013_test_coverage.py")

    def boom(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(mod.subprocess, "run", boom)
    assert mod.get_content_at("x.py", "HEAD") is None
    assert "[WARN]" in capsys.readouterr().err


def test_load_pair_exits_2_when_git_unavailable(monkeypatch, capsys) -> None:
    """基线内容取不到 → 范围不可知 → exit 2（而不是跳过该文件后 PASS）。"""
    mod = _load("check_g_013_t3", "check_g_013_test_coverage.py")
    monkeypatch.setattr(mod, "get_content_at", lambda f, r: None)
    with pytest.raises(SystemExit) as exc:
        mod._load_pair("pilotstd/x.py", "BASE", "HEAD", [])
    assert exc.value.code == 2
    assert "[WARN]" in capsys.readouterr().err
