"""PR 路径 CI 配置的回归测试（2026-11-21 两处既有缺陷的守护）。

锁住两条结论，谁改回去这里就红：
  1. `G029_RANGE` 必须同时覆盖 push（`github.event.before`）与 PR
     （`pull_request.base.sha` / `pull_request.head.sha`）—— 只写 before 时，
     PR 事件下范围退化为 `..<sha>`，G-029 会判"0 变更文件"直接失败；
  2. `deep-gate.yml` 必须安装 pytest —— `check_all.sh --deep` 的
     `run_gate_selftests` 依赖它，缺失即 `No module named pytest`。

另外锁住 G-029 脚本自身的"拒绝静默通过"行为：显式范围为空时必须以非 0 退出，
避免有人以后把它改成"0 文件也 PASS"，让同类配置缺陷重新变成假绿。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
DEEP_GATE_YML = ROOT / ".github" / "workflows" / "deep-gate.yml"
G029 = ROOT / "scripts" / "check_g_029_test_coverage.py"


def test_g029_range_covers_push_and_pull_request() -> None:
    """G-029 的范围表达式必须对 push 与 PR 两种事件都取到非空左端。"""
    text = CI_YML.read_text(encoding="utf-8")
    line = next(lin for lin in text.splitlines() if "G029_RANGE:" in lin)

    assert "github.event.before" in line, "push 事件仍需用 before"
    assert "github.event.pull_request.base.sha" in line, "PR 事件需回落到 base.sha"
    assert "github.event.pull_request.head.sha" in line, "PR 事件右端应为 head.sha"


def test_deep_gate_installs_pytest() -> None:
    """deep-gate 的依赖安装行必须包含 pytest（--deep 的受控测试自查需要）。"""
    text = DEEP_GATE_YML.read_text(encoding="utf-8")
    install_block = text.split("Install dependencies", 1)[1].split("Run Deep Gate", 1)[0]

    assert "pip install" in install_block
    assert "pytest" in install_block.replace("pytest-xdist", ""), "必须安装 pytest 本体"


def test_g029_refuses_silent_pass_on_empty_range() -> None:
    """显式范围为空时 G-029 必须非 0 退出（拒绝静默通过）。"""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    env = dict(os.environ, G029_RANGE=f"..{head}")

    # 必须显式指定 utf-8：Windows 默认按 GBK 解码子进程输出，脚本的 UTF-8 中文会解码失败，
    # 导致 stdout 变 None（本地实测），与 CI（Linux）行为不一致。
    proc = subprocess.run([sys.executable, str(G029)], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")

    assert proc.returncode != 0, "空范围不应通过"
    output = (proc.stdout or "") + (proc.stderr or "")
    assert "0 个变更文件" in output, "应给出 0 变更文件的明确原因"
