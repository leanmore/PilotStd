#!/usr/bin/env python3
"""从 commit message 自动计算语义化版本号。

优先读取环境变量 BASE_VERSION（CI 通过 git tag 注入），
降级读 VERSION 文件。commit 信息直接从 git log 读取。
"""

import os
import re
import subprocess
from pathlib import Path

VERSION_FILE = Path(__file__).parent.parent / "VERSION"


def get_current_version() -> str:
    """优先 BASE_VERSION 环境变量，降级 VERSION 文件。"""
    base = os.environ.get("BASE_VERSION", "").strip()
    if base:
        return base
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "0.0.0"


def get_commit_messages() -> list[str]:
    """从 git log 读取自上次 tag 以来的所有 commit message。"""
    try:
        last_tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        result = subprocess.check_output(
            ["git", "log", f"{last_tag}..HEAD", "--format=%s"],
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [msg.strip() for msg in result.split("\n") if msg.strip()]


def bump_version(version: str, commit_messages: list[str]) -> str | None:
    major, minor, patch = map(int, version.split("."))

    has_breaking = any("BREAKING CHANGE:" in msg for msg in commit_messages)
    has_feat = any(re.search(r"^feat(\(.+\))?:", msg) for msg in commit_messages)
    has_fix = any(re.search(r"^fix(\(.+\))?:", msg) for msg in commit_messages)

    if has_breaking:
        return f"{major + 1}.0.0"
    elif has_feat:
        return f"{major}.{minor + 1}.0"
    elif has_fix:
        return f"{major}.{minor}.{patch + 1}"
    else:
        return None


if __name__ == "__main__":
    current = get_current_version()
    commit_msgs = get_commit_messages()
    new_version = bump_version(current, commit_msgs)
    if new_version:
        print(new_version)
    else:
        print(current)
