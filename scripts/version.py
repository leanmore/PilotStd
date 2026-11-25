#!/usr/bin/env python3
"""从 commit message 自动计算语义化版本号。"""

import os
import re
from pathlib import Path

VERSION_FILE = Path(__file__).parent.parent / "VERSION"


def get_base_version() -> str:
    """优先从环境变量获取基准版本（用于跨端对齐），否则读取本地 VERSION 文件。"""
    base = os.environ.get("BASE_VERSION")
    if base:
        return base.strip()
    return VERSION_FILE.read_text().strip()


def bump_version(version: str, commit_messages: list[str]) -> str | None:
    """根据 commit 规范计算新版本号。"""
    major, minor, patch = map(int, version.split("."))

    # 剥离-8（+），防止/前缀被吞导致版本号不升
    cleaned = [msg.removeprefix("\ufeff") for msg in commit_messages]

    # 基础设施类 scope（CI/文档/测试/构建/运维脚本）不触发行版本 bump —— 与
    # `scripts/check_version_bump.py` 的 INFRA_SCOPES 保持同一口径，否则会出现
    # 「version job 想 bump、门禁豁免不 bump」的互相矛盾（main 实测：feat(ops) 让发布停摆）。
    infra = re.compile(r"^(@ )?(feat|fix)\((ci|docs|test|build|ops)\):")
    cleaned = [msg for msg in cleaned if not infra.match(msg)]

    has_breaking = any("BREAKING CHANGE:" in msg for msg in cleaned)
    # 兼容'@'前缀（残留）和标准格式
    has_feat = any(re.search(r"^(@ )?feat(\(.+\))?:", msg) for msg in cleaned)
    has_fix = any(re.search(r"^(@ )?fix(\(.+\))?:", msg) for msg in cleaned)

    if has_breaking:
        return f"{major + 1}.0.0"
    elif has_feat:
        return f"{major}.{minor + 1}.0"
    elif has_fix:
        return f"{major}.{minor}.{patch + 1}"
    else:
        return None


if __name__ == "__main__":
    # 1.获取信息
    msgs_str = os.environ.get("COMMIT_MSGS", "")
    # 持续集成用|分隔（版本控制不支持多行），本地用换行
    separator = "|" if "|" in msgs_str else "\n"
    commit_msgs = [msg.strip() for msg in msgs_str.split(separator) if msg.strip()]

    # 2. 获取基准版本并计算
    current = get_base_version()
    new_version = bump_version(current, commit_msgs)

    # 3.如果有新版本，打印到标准输出供持续集成捕获；如果没有，静默退出
    if new_version:
        print(new_version)
