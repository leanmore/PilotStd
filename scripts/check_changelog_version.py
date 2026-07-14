#!/usr/bin/env python3
"""G-009: CHANGELOG 版本一致性检查 — 不一致时自动将 __init__.py 同步到 CHANGELOG 版本"""

import re
import sys
from pathlib import Path


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
    # 匹配第一个 ## vX.Y.Z 或 ## X.Y.Z
    m = re.search(r"^##\s+v?(\d+\.\d+\.\d+)", changelog_file.read_text(encoding="utf-8"), re.M)
    if not m:
        print("FAIL: CHANGELOG.md 中没有找到版本条目")
        return ""
    return m.group(1)


def update_init_version(new_version: str) -> None:
    init_file = Path("pilotstd/__init__.py")
    content = init_file.read_text(encoding="utf-8")
    new_content = re.sub(
        r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
        rf"\g<1>{new_version}\g<3>",
        content,
        count=1,
    )
    init_file.write_text(new_content, encoding="utf-8")
    print(f"已自动将 __init__.py 版本同步为 {new_version}")


def main() -> int:
    init_ver = get_init_version()
    cl_ver = get_changelog_latest_version()
    if not init_ver or not cl_ver:
        return 1

    if init_ver == cl_ver:
        print(f"PASS: CHANGELOG 与 __init__.py 版本一致: v{init_ver}")
        return 0

    print(f"版本不一致: __init__.py={init_ver}, CHANGELOG.md={cl_ver}")
    update_init_version(cl_ver)
    print(f"PASS: 已自动修复，当前版本: {cl_ver}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
