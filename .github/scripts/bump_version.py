#!/usr/bin/env python3
"""
从 commit message 前缀自动计算下一个语义化版本号。

用法:
    python scripts/bump_version.py "feat: 新增下载适配器"
    # → 0.5.0

    python scripts/bump_version.py "fix: 修复缓存过期问题"
    # → 0.4.2

    python scripts/bump_version.py "chore: 更新依赖"
    # → 0.4.1  (不变)

CI 用 --github 输出 GitHub Actions set-output 格式。
"""

import argparse
import re
import sys
from pathlib import Path

# 项目根目录（脚本在 .github/scripts/ 下）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INIT_PATH = PROJECT_ROOT / "pilotstd" / "__init__.py"

# 升 Minor 的提交类型（新功能）
MINOR_PREFIXES = ("feat:", "feat(", "feature:", "feature(")

# 升 Patch 的提交类型（修复）
PATCH_PREFIXES = ("fix:", "fix(", "bugfix:", "bugfix(", "hotfix:", "hotfix(")

# 不升版本的提交类型
SKIP_PREFIXES = (
    "chore:", "chore(",
    "refactor:", "refactor(",
    "docs:", "docs(",
    "test:", "test(",
    "style:", "style(",
    "ci:", "ci(",
    "build:", "build(",
    "perf:", "perf(",
    "revert:", "revert(",
)


def read_current_version():
    # type: () -> str
    """从最新 git tag 读取当前版本，回退到 __init__.py。

    优先使用 git tag（代表已发布的版本），避免人工手动改了 __init__.py
    但未打 tag 导致 CI 重复 bump。
    """
    import subprocess
    result = subprocess.run(
        ["git", "tag", "--sort=-creatordate"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if result.returncode == 0:
        for tag in result.stdout.strip().split("\n"):
            tag = tag.strip()
            # 只取正式版 tag（vX.Y.Z），跳过 dev 后缀
            if re.match(r'^v\d+\.\d+\.\d+$', tag):
                return tag.lstrip("v")

    # 回退：从 __init__.py 读取
    content = INIT_PATH.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not m:
        print("::error::无法获取当前版本号（无 git tag 且 __init__.py 无 __version__）",
              file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def parse_version(version: str) -> tuple[int, int, int]:
    """解析 MAJOR.MINOR.PATCH 字符串为整数三元组。"""
    # 剥离前导 v 和 -dev 后缀
    v = version.lstrip("v").split("-")[0]
    parts = v.split(".")
    if len(parts) != 3:
        print(f"::error::版本号格式错误（需为 X.Y.Z）: {version}", file=sys.stderr)
        sys.exit(1)
    return int(parts[0]), int(parts[1]), int(parts[2])


def classify_commit(msg: str) -> str:
    """
    根据提交信息前缀判断升级类型。

    返回: "minor" | "patch" | "none"
    """
    msg_lower = msg.strip().lower()

    for prefix in MINOR_PREFIXES:
        if msg_lower.startswith(prefix):
            return "minor"

    for prefix in PATCH_PREFIXES:
        if msg_lower.startswith(prefix):
            return "patch"

    # 未知前缀也按 patch 处理（保守策略：有改动就升修订号）
    for prefix in SKIP_PREFIXES:
        if msg_lower.startswith(prefix):
            return "none"

    # 无法识别的前缀 → 升 patch（保守）
    return "patch"


def bump_version(current: str, bump_type: str) -> str:
    """
    根据升级类型计算新版本号。

    bump_type: "minor" → X.Y+1.0, "patch" → X.Y.Z+1, "none" → 不变
    """
    major, minor, patch = parse_version(current)

    if bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    # bump_type == "none": 不变

    return f"{major}.{minor}.{patch}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据 commit message 前缀自动计算下一个语义化版本号"
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="提交信息（不传则从最新 git commit 读取）",
    )
    parser.add_argument(
        "--github",
        action="store_true",
        help="输出 GitHub Actions set-output 格式（key=value 行）",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="就地更新 pilotstd/__init__.py 中的 __version__",
    )
    args = parser.parse_args()

    # 获取提交信息
    if args.message:
        msg = args.message
    else:
        import subprocess
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            print(f"::error::git log 失败: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        msg = result.stdout.strip()
        if not msg:
            print("::error::无法获取最新提交信息", file=sys.stderr)
            sys.exit(1)

    # 计算版本号
    current = read_current_version()
    bump_type = classify_commit(msg)
    new_version = bump_version(current, bump_type)

    # 就地更新 __init__.py（CI 用）
    if args.update and bump_type != "none" and new_version != current:
        content = INIT_PATH.read_text(encoding="utf-8")
        updated = re.sub(
            r'__version__\s*=\s*"[^"]*"',
            f'__version__ = "{new_version}"',
            content,
        )
        INIT_PATH.write_text(updated, encoding="utf-8")
        print(f"已更新 {INIT_PATH}: {current} → {new_version}", file=sys.stderr)

    if args.github:
        # GitHub Actions set-output 格式
        print(f"current_version={current}")
        print(f"new_version={new_version}")
        print(f"bump_type={bump_type}")
        print(f"version=v{new_version}")
        # 是否实际发生了版本变更
        bumped = "true" if current != new_version else "false"
        print(f"bumped={bumped}")
    else:
        if bump_type == "none":
            print(f"{current}  (不变 — {msg[:60]})")
        else:
            print(f"{current} → {new_version}  ({bump_type} — {msg[:60]})")


if __name__ == "__main__":
    main()
