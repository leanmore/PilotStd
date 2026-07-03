#!/usr/bin/env python3
"""从 commit message 自动计算语义化版本号，读写 VERSION 文件。"""

import os
import re
from pathlib import Path

VERSION_FILE = Path(__file__).parent.parent / "VERSION"


def get_current_version() -> str:
    return VERSION_FILE.read_text().strip()


def write_version(version: str) -> None:
    VERSION_FILE.write_text(version + "\n")


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
    msgs_str = os.environ.get("COMMIT_MSGS", "")
    commit_msgs = [msg.strip() for msg in msgs_str.split("\n") if msg.strip()]
    current = get_current_version()
    new_version = bump_version(current, commit_msgs)
    if new_version:
        write_version(new_version)
        print(new_version)
    else:
        print(current)
