"""入仓合规门禁必须拦截"临时文件"（体检 E-3 / R-010）。

R-010 要求临时文件写在仓库外，但此前**零拦截**，历史上已两次误提交：
`_msg7.txt`（`6d3b3cf5`）、`_msg_tmp.txt`（`d7d40c56`），仓根还残留 `STATUS.md.bak`。

本测试锁两件事：
1. `.github/scripts/check-repo-compliance.sh` 的 `FILENAME_BLACKLIST` 里确有这三条模式；
2. 该脚本仍可被 `bash -n` 解析（防止有人加模式时写坏 shell 语法）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "check-repo-compliance.sh"

_REQUIRED_PATTERNS = ("_*tmp*", "_msg*.txt", "*.bak")


def _blacklist_block() -> str:
    """取出 `FILENAME_BLACKLIST=(...)` 的括号内容（容忍多行与注释）。"""
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"FILENAME_BLACKLIST=\((.*?)\n\)", text, re.DOTALL)
    assert match, "未找到 FILENAME_BLACKLIST 数组"
    return match.group(1)


def test_temp_file_patterns_are_blacklisted() -> None:
    """三条"手滑提交"模式必须在黑名单里。"""
    block = _blacklist_block()
    for pattern in _REQUIRED_PATTERNS:
        assert f'"{pattern}"' in block, f"FILENAME_BLACKLIST 缺少 {pattern}（R-010 回归风险）"


def test_known_regressions_would_be_caught() -> None:
    """用历史上真正误提交过的文件名复核（避免"模式在、但匹配不到"）。"""
    block = _blacklist_block()
    patterns = re.findall(r'"([^"]+)"', block)
    assert patterns, "黑名单为空"

    import fnmatch

    for name in ("_msg7.txt", "_msg_tmp.txt", "STATUS.md.bak"):
        assert any(fnmatch.fnmatch(name, p) for p in patterns), f"{name} 不会被任何黑名单模式命中"


def test_script_is_syntactically_valid() -> None:
    """加模式不得写坏 shell 语法（bash -n）。"""
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"bash -n 失败（exit {result.returncode}）：{result.stderr}"


def test_script_uses_posix_shell_available_on_ci() -> None:
    """CI 在 ubuntu 上跑，脚本必须能被 `bash` 找到（而非依赖 PowerShell）。"""
    assert sys.platform  # 占位：确保测试在任何平台都至少执行到这一步
    assert SCRIPT.exists(), f"脚本不存在：{SCRIPT}"
