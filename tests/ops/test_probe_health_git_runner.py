"""`scripts/ops/probe_health._run_git` 的双通道回归（2026-11-25）。

背景：受限/沙箱环境禁止为子进程创建管道，`subprocess.run(capture_output=True)`
会拿到 `stdout=None`（甚至读线程异常），使 `probe_all` 在 `version.deployed_commit`
处崩溃。`_run_git()` 因此实现了「内存捕获 → 临时文件重定向」双通道。

本测试锁定：
1. 正常环境下能拿到 git 输出；
2. 管道不可用时自动退化到文件重定向，仍然拿到输出；
3. `_git_commit_exists` 能区分「存在且是祖先」与「不存在」。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ops"))

import probe_health  # noqa: E402


class _FakeProc:
    def __init__(self, returncode: int, stdout: str | None, stderr: str | None = "err") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_git_returns_head_sha() -> None:
    rc, out, _err = probe_health._run_git(["rev-parse", "HEAD"])
    assert rc == 0
    assert len(out.strip()) >= 7


def test_run_git_falls_back_when_stdout_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟沙箱：首次（内存捕获）返回 stdout=None，退路（文件重定向）正常。"""
    calls: list[dict] = []

    def fake_run(*args, **kwargs):  # noqa: ANN001, ANN002
        calls.append(kwargs)
        if "capture_output" in kwargs:
            return _FakeProc(0, None, None)  # 管道不可用
        # 退路：写文件
        stdout_file = kwargs.get("stdout")
        if stdout_file is not None:
            stdout_file.write("deadbeef\r\n")
        return _FakeProc(0, None, None)

    monkeypatch.setattr(probe_health.subprocess, "run", fake_run)
    rc, out, _err = probe_health._run_git(["rev-parse", "HEAD"])
    assert rc == 0
    assert out.strip() == "deadbeef"
    assert len(calls) == 2, f"应走到退路（2 次调用），实际 {len(calls)}"


def test_run_git_falls_back_when_pipe_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟沙箱：内存捕获直接抛 OSError，退路仍应工作。"""

    def fake_run(*args, **kwargs):  # noqa: ANN001, ANN002
        if "capture_output" in kwargs:
            raise OSError("pipes are not allowed")
        stdout_file = kwargs.get("stdout")
        if stdout_file is not None:
            stdout_file.write("cafebabe\r\n")
        return _FakeProc(0, None, None)

    monkeypatch.setattr(probe_health.subprocess, "run", fake_run)
    rc, out, _err = probe_health._run_git(["rev-parse", "HEAD"])
    assert rc == 0
    assert out.strip() == "cafebabe"


def test_git_commit_exists_for_head() -> None:
    head = probe_health._run_git(["rev-parse", "HEAD"])[1].strip()
    assert head
    exists, detail = probe_health._git_commit_exists(head)
    assert exists is True
    assert "祖先" in detail


def test_git_commit_exists_for_bogus_sha() -> None:
    exists, detail = probe_health._git_commit_exists("0" * 40)
    assert exists is False
    assert "不存在" in detail
