"""tests/test_gate_changed_files_failfast.py — 变更范围「不可知」必须 FAIL（U34 假绿修复）。

背景：G-013 / G-030 / G-031 / G-033 原先在 git 不可用、超时或命令非零退出时返回空列表，
调用方把「空」解释成「本次无变更」→ 直接 PASS。门禁在根本拿不到变更范围时假绿，且静默。

本文件锁定两条边界：
1. **不可知 → FAIL**：git 无法执行、或所有来源都非零退出，门禁必须非零退出/返回失败；
2. **为空 → 不算失败**：git 正常返回 0、输出为空（干净仓库）不得判 FAIL，
   否则每次干净提交都会被拦，门禁会被迫绕过——那是另一种假绿。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(module_name: str, filename: str):
    """以文件路径加载门禁脚本模块（scripts/ 不是包，与既有门禁测试同法）。"""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Completed:
    """subprocess.CompletedProcess 的最小替身。"""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_git(monkeypatch, *, rc: int = 128, stdout: str = "", raises: Exception | None = None) -> None:
    """把共享助手里的 subprocess.run 换成受控实现（所有门禁都经 ChangeScope 走这里）。"""
    import _gate_git

    def fake_run(args, **kwargs):  # noqa: ANN001, ANN401 - 测试替身
        if raises is not None:
            raise raises
        return _Completed(rc, stdout, "fatal: not a git repository")

    monkeypatch.setattr(_gate_git.subprocess, "run", fake_run)


# ── 1. git 无法执行（未安装 / 超时 / OSError）→ 必须 FAIL ──────────────────────


def test_changeset_unavailable_is_raised_when_git_missing(monkeypatch) -> None:
    """git 可执行文件缺失时，共享助手直接抛 ChangeSetUnavailable。"""
    import _gate_git

    _patch_git(monkeypatch, raises=FileNotFoundError("git"))
    scope = _gate_git.ChangeScope(ROOT)

    with pytest.raises(_gate_git.ChangeSetUnavailable, match="无法执行"):
        scope.query(["git", "diff", "--name-only"])


def test_g013_fails_when_git_missing(monkeypatch) -> None:
    """G-013：拿不到变更文件 → exit 2（旧行为是静默 PASS）。"""
    gate = _load("check_g_013_test_coverage", "check_g_013_test_coverage.py")
    _patch_git(monkeypatch, raises=FileNotFoundError("git"))

    with pytest.raises(SystemExit) as exc:
        gate.main()
    assert exc.value.code == 2


def test_g030_fails_when_git_missing(monkeypatch) -> None:
    """G-030：拿不到变更范围 → exit 2。"""
    gate = _load("check_g_030_tech_debt", "check_g_030_tech_debt.py")
    _patch_git(monkeypatch, raises=FileNotFoundError("git"))

    with pytest.raises(SystemExit) as exc:
        gate.main()
    assert exc.value.code == 2


def test_g031_fails_when_git_missing(monkeypatch) -> None:
    """G-031：拿不到变更范围 → main() 返回 2。"""
    gate = _load("check_g_031_docs_sync", "check_g_031_docs_sync.py")
    _patch_git(monkeypatch, raises=FileNotFoundError("git"))

    assert gate.main() == 2


def test_g033_fails_when_git_missing(monkeypatch) -> None:
    """G-033：拿不到变更范围 → validate_adr() 返回 False（CLI 即 exit 1）。"""
    gate = _load("check_g_033_adr_integrity", "check_g_033_adr_integrity.py")
    _patch_git(monkeypatch, raises=FileNotFoundError("git"))

    assert gate.validate_adr() is False


# ── 2. 所有来源都非零退出（非仓库 / 权限异常）→ 必须 FAIL ──────────────────────


def test_g013_fails_when_all_sources_error(monkeypatch) -> None:
    """G-013：git 存在但两条来源都 exit≠0 → 不可知 → exit 2。"""
    gate = _load("check_g_013_test_coverage", "check_g_013_test_coverage.py")
    _patch_git(monkeypatch, rc=128)

    with pytest.raises(SystemExit) as exc:
        gate.main()
    assert exc.value.code == 2


def test_g030_fails_when_all_sources_error(monkeypatch) -> None:
    """G-030：三条回退来源全失败 → exit 2（不能把「拿不到」当成「无变更」）。"""
    gate = _load("check_g_030_tech_debt", "check_g_030_tech_debt.py")
    _patch_git(monkeypatch, rc=128)

    with pytest.raises(SystemExit) as exc:
        gate.main()
    assert exc.value.code == 2


def test_g031_fails_when_all_sources_error(monkeypatch) -> None:
    """G-031：两个来源全失败 → 返回 2。"""
    gate = _load("check_g_031_docs_sync", "check_g_031_docs_sync.py")
    _patch_git(monkeypatch, rc=128)

    assert gate.main() == 2


def test_g033_fails_when_all_sources_error(monkeypatch) -> None:
    """G-033：三条回退来源全失败 → validate_adr() 为 False。"""
    gate = _load("check_g_033_adr_integrity", "check_g_033_adr_integrity.py")
    _patch_git(monkeypatch, rc=128)

    assert gate.validate_adr() is False


# ── 3. 反向边界：范围「为空」是合法结论，不得 FAIL ────────────────────────────


def test_empty_change_set_is_not_a_failure(monkeypatch) -> None:
    """git 正常返回 0 且输出为空 → 判定为「本次无变更」，四个门禁都放行。

    这条与上面的失败用例互为镜像：只判「空」而不判「不可知」会把干净仓库每次都拦下，
    逼使用者加豁免→又回到假绿。
    """
    _patch_git(monkeypatch, rc=0, stdout="")

    g013 = _load("check_g_013_test_coverage", "check_g_013_test_coverage.py")
    g030 = _load("check_g_030_tech_debt", "check_g_030_tech_debt.py")
    g031 = _load("check_g_031_docs_sync", "check_g_031_docs_sync.py")
    g033 = _load("check_g_033_adr_integrity", "check_g_033_adr_integrity.py")

    assert g013.get_changed_files() == []
    assert g030.get_staged_files() == []
    assert g030.get_staged_diff() == ""
    assert g031.get_changed_entries() == []
    assert g031.main() == 0
    assert g033.get_changed_files() == []

    with pytest.raises(SystemExit) as exc:
        g030.main()
    assert exc.value.code == 0


# ── 4. CLI 冒烟：作为脚本运行时 `from _gate_git import` 必须可用 ──────────────


@pytest.mark.parametrize(
    "script",
    ["check_g_030_tech_debt.py", "check_g_031_docs_sync.py"],
)
def test_cli_smoke_on_clean_repo(script: str) -> None:
    """真实仓库干净树跑 CLI → exit 0（同时验证 scripts/ 下的共享导入可用）。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
