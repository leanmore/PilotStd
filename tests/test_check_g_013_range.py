"""tests/test_check_g_013_range.py — G-013 `--range` 模式（CI 形态）契约。

背景：G-013 原先只读暂存区，`.husky/pre-commit` 之外（`--no-verify`、直推 main、换机器）
完全失守。本文件锁四件事：
1. `--range BASE...HEAD` 能按范围取变更文件，且**新旧内容取自 base/head**（不是 HEAD vs 工作区，
   否则 CI 里恒等 ⇒ 永远无变更，等于假绿）；
2. 生产文件变了但没动测试 → FAIL，错误信息含文件路径；
3. 生产文件与测试都变了 → PASS；范围为空 → PASS；
4. 范围不可知（ref 不存在 / git 不可用）→ exit 2；格式错误 → exit 2；本地模式语义不变。
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "check_g_013_test_coverage.py"


def _load():
    """以文件路径加载门禁模块（scripts/ 不是包，与既有门禁测试同法）。"""
    spec = importlib.util.spec_from_file_location("check_g_013_test_coverage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    """在临时仓库里执行 git（显式身份，避免依赖全局 user.name/email）。"""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "gate-test",
        "GIT_AUTHOR_EMAIL": "gate@test.local",
        "GIT_COMMITTER_NAME": "gate-test",
        "GIT_COMMITTER_EMAIL": "gate@test.local",
    }
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """三连提交的临时仓库：
    ① 基线（foo.py 一个稳定函数）
    ② 只改生产代码（新增公开函数、未动测试）→ 应 FAIL
    ③ 生产代码 + 测试一起改 → 应 PASS
    """
    _git(tmp_path, "init")
    (tmp_path / "pilotstd" / "manager").mkdir(parents=True)
    (tmp_path / "pilotstd" / "manager" / "foo.py").write_text(
        "def stable_api():\n    return 1\n", encoding="utf-8"
    )
    _commit(tmp_path, "chore: baseline")

    (tmp_path / "pilotstd" / "manager" / "foo.py").write_text(
        "def stable_api():\n    return 1\n\n\ndef new_api():\n    return 2\n", encoding="utf-8"
    )
    _commit(tmp_path, "fix: 生产代码变更但没带测试")

    (tmp_path / "pilotstd" / "manager" / "foo.py").write_text(
        "def stable_api():\n    return 1\n\n\ndef new_api():\n    return 3\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_foo.py").write_text(
        "def test_new_api():\n    assert 3 == 3\n", encoding="utf-8"
    )
    _commit(tmp_path, "test: 补测试")
    return tmp_path


def _run(monkeypatch, gate, repo: Path, argv: list[str]) -> int:
    """在临时仓库里跑 gate.main()，返回 SystemExit.code。"""
    monkeypatch.setattr(gate, "ROOT", repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["check_g_013_test_coverage.py", *argv])
    with pytest.raises(SystemExit) as exc:
        gate.main()
    return int(exc.value.code)


def test_range_prod_change_without_test_fails(repo, monkeypatch, capsys) -> None:
    """② 只改生产代码、未带测试 → exit 1，且报错含文件路径。"""
    gate = _load()
    # ② 是「只改生产代码」的那次提交；③ 已补测试，故范围取 HEAD~2..HEAD~1
    code = _run(monkeypatch, gate, repo, ["--range", "HEAD~2..HEAD~1", "--no-commit-msg"])

    captured = capsys.readouterr()
    assert code == 1
    assert "[TEST-BLOCK]" in captured.err
    assert "pilotstd/manager/foo.py" in captured.err


def test_range_prod_and_test_change_passes(repo, monkeypatch, capsys) -> None:
    """③ 生产代码 + 测试同批变更 → exit 0。"""
    gate = _load()
    code = _run(monkeypatch, gate, repo, ["--range", "HEAD~1..HEAD", "--no-commit-msg"])

    assert code == 0
    assert "[PASS]" in capsys.readouterr().out


def test_range_uses_base_side_content(repo, monkeypatch) -> None:
    """range 模式的旧内容是 base 侧快照：HEAD~2..HEAD~1 要比的是 ①→②，而不是 HEAD vs 工作区。"""
    gate = _load()
    monkeypatch.setattr(gate, "ROOT", repo)
    monkeypatch.chdir(repo)

    base = gate.resolve_range_base("HEAD~2", "HEAD~1")
    changed = gate.get_changed_files_for_range(base, "HEAD~1")

    assert "pilotstd/manager/foo.py" in changed
    # 基线侧不含 new_api，head 侧含 ⇒ 证明内容确实按 ref 取，而非读工作区
    assert "new_api" not in gate.get_content_at("pilotstd/manager/foo.py", base)
    assert "new_api" in gate.get_content_at("pilotstd/manager/foo.py", "HEAD~1")


def test_empty_range_passes(repo, monkeypatch, capsys) -> None:
    """范围为空（HEAD == HEAD）→ PASS，与本地「无暂存变更」语义一致。"""
    gate = _load()
    code = _run(monkeypatch, gate, repo, ["--range", "HEAD..HEAD", "--no-commit-msg"])

    assert code == 0
    assert "0 个业务文件" in capsys.readouterr().out


def test_range_missing_arg_exits_2(repo, monkeypatch) -> None:
    """`--range` 后面没参数 → exit 2（明确报错，不猜）。"""
    gate = _load()
    assert _run(monkeypatch, gate, repo, ["--range"]) == 2


def test_range_bad_format_exits_2(repo, monkeypatch) -> None:
    """不带 `..` 的 `--range` → exit 2。"""
    gate = _load()
    assert _run(monkeypatch, gate, repo, ["--range", "main"]) == 2


def test_range_unknown_ref_exits_2(repo, monkeypatch) -> None:
    """ref 不存在 → 范围不可知 → exit 2（不是静默 PASS）。"""
    gate = _load()
    assert _run(monkeypatch, gate, repo, ["--range", "nosuchref..HEAD"]) == 2


def test_git_missing_exits_2(repo, monkeypatch) -> None:
    """git 不可用 → 范围不可知 → exit 2。"""
    import _gate_git

    def _boom(*_a, **_k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(_gate_git.subprocess, "run", _boom)
    gate = _load()
    assert _run(monkeypatch, gate, repo, ["--range", "HEAD~1..HEAD"]) == 2


def test_legacy_local_mode_unchanged(repo, monkeypatch, capsys) -> None:
    """保留原语义：不带 --range 时仍读暂存区；干净树 → PASS。"""
    gate = _load()
    code = _run(monkeypatch, gate, repo, ["--no-commit-msg"])

    assert code == 0
    assert "0 个业务文件" in capsys.readouterr().out
