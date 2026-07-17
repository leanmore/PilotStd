#!/usr/bin/env python3
"""G-029: 核心模块变更时检查对应测试文件是否同步更新。

仅检查本次 PR 中变更的文件（diff 对 base branch），不追溯历史。
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")  # CI 中可通过环境变量指定对比分支

# 变更路径前缀 → 必须同时变更的测试路径（任一匹配即可）
COVERAGE_MAP: list[tuple[list[str], list[str]]] = [
    (
        ["pilotstd/scan/parser/", "pilotstd/core/std_utils.py"],
        ["tests/test_scanner.py", "tests/test_parser.py"],
    ),
    (
        ["pilotstd/query/adapters/"],
        ["tests/test_adapters.py", "tests/test_query.py"],
    ),
    (
        [
            "pilotstd/ui/core/handlers/_scan.py",
            "pilotstd/scan/scanner.py",
            "pilotstd/ui/workers/scan.py",
        ],
        ["tests/test_scan.py", "tests/test_scanner.py"],
    ),
    (
        [
            "pilotstd/ui/main_window/",
            "pilotstd/ui/core/handlers/_query_summary.py",
            "pilotstd/ui/core/handlers/_query.py",
        ],
        ["tests/gui/"],
    ),
]


def get_changed_files() -> list[str]:
    """返回本次 PR 中相对于 base branch 变更的文件列表。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{BASE_BRANCH}..HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(ROOT),
        )
    except subprocess.CalledProcessError:
        print(f"[G-029] WARN: 无法获取 diff (base={BASE_BRANCH})，跳过检查")
        return []
    return [f for f in result.stdout.strip().split("\n") if f]


def matches_any(path: str, prefixes: list[str]) -> bool:
    """判断文件路径是否匹配任意一个前缀。"""
    return any(path.startswith(p) for p in prefixes)


def main() -> int:
    """入口：检查核心模块变更是否同步更新了对应测试文件。"""
    changed = get_changed_files()
    if not changed:
        print("[G-029] PASS: 无变更文件")
        return 0

    failures: list[str] = []
    for src_prefixes, test_prefixes in COVERAGE_MAP:
        # 筛选出匹配前缀的变更源文件
        changed_src = [f for f in changed if matches_any(f, src_prefixes)]
        if not changed_src:
            continue
        changed_tests = [f for f in changed if matches_any(f, test_prefixes)]
        if changed_tests:
            print(f"[G-029] OK: 核心模块变更已有测试同步 — {', '.join(changed_src)}")
            continue
        failures.append(
            f"  ❌ 核心模块变更未同步测试:\n"
            f"     变更文件: {', '.join(changed_src)}\n"
            f"     期望同步更新: {', '.join(test_prefixes)}"
        )

    if failures:
        print(f"[G-029] FAIL: {len(failures)} 项核心模块变更缺少测试同步")
        for f in failures:
            print(f)
        return 1

    print("[G-029] PASS: 所有核心模块变更已同步测试")
    return 0


if __name__ == "__main__":
    sys.exit(main())
