"""D-19：run_batch_tests 不得再使用 shell=True（列表参数 + 文件重定向）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "run_batch_tests.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_batch_tests_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


batch_runner = _load()


def test_build_cmd_returns_list_without_redirection() -> None:
    cmd = batch_runner._build_cmd({"files": ["tests/a.py", "tests/b.py"], "gui": True})
    assert isinstance(cmd, list)
    assert cmd[0] == (sys.executable or "python")
    assert "tests/a.py" in cmd and "tests/b.py" in cmd
    assert "--timeout=15" in cmd
    joined = " ".join(cmd)
    assert ">" not in joined
    assert "set CI" not in joined


def test_build_cmd_timeout_variants() -> None:
    assert "--timeout=30" in batch_runner._build_cmd({"files": [], "independent": True})
    assert "--timeout=15" not in batch_runner._build_cmd({"files": []})


def test_build_env_sets_ci(monkeypatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    assert batch_runner._build_env({"env_ci": True})["CI"] == "1"
    assert "CI" not in batch_runner._build_env({})


def test_source_has_no_shell_true() -> None:
    assert "shell=True" not in SCRIPT.read_text(encoding="utf-8")
