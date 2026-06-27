#!/usr/bin/env python3
"""GATE-09: CHANGELOG 版本一致性检查 — CHANGELOG.md 最新版本须与 __init__.py 一致"""

import re
import sys
from pathlib import Path

from packaging.version import Version


def get_init_version() -> str:
    init_file = Path("pilotstd/__init__.py")
    if not init_file.exists():
        print("FAIL: pilotstd/__init__.py 不存在")
        return ""
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_file.read_text(encoding="utf-8"))
    if not m:
        print("FAIL: 无法从 __init__.py 读取版本号")
        return ""
    return m.group(1)


def get_changelog_latest_version() -> str:
    changelog_file = Path("CHANGELOG.md")
    if not changelog_file.exists():
        print("FAIL: CHANGELOG.md 不存在")
        return ""
    matches = re.findall(r"## v?([0-9]+\.[0-9]+\.[0-9]+)", changelog_file.read_text(encoding="utf-8"))
    if not matches:
        print("FAIL: CHANGELOG.md 中没有找到版本条目")
        return ""
    return str(max(Version(v) for v in matches))


def main() -> int:
    init_ver = get_init_version()
    cl_ver = get_changelog_latest_version()
    if not init_ver or not cl_ver:
        return 1

    if init_ver != cl_ver:
        print(f"FAIL: 版本不一致 — __init__.py={init_ver}, CHANGELOG.md={cl_ver}")
        return 1

    print(f"PASS: CHANGELOG 与 __init__.py 版本一致: v{init_ver}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
