#!/usr/bin/env python3
"""G-029: UI 变更时检查 GUI 测试是否同步更新。

2026-10-17 体检 D-7 的两处修正：

1. **范围取值**：原实现用 `git diff origin/main..HEAD`，而本仓库以直推 main 为主——
   推送时 `origin/main` 已被推进到本次 tip ⇒ 范围恒空 ⇒ 打印"无变更文件 PASS"（假绿）。
   现优先读 `G029_RANGE`（CI 传 `before..sha`，与 T-27 的 `COMPLIANCE_RANGE` 同手法），
   回退 `origin/<base>...HEAD`（三点=merge-base）与 `HEAD~1..HEAD`；**显式范围若为 0 文件
   直接 FAIL**，绝不静默通过。

2. **映射收敛**：原 4 组前缀（parser / query.adapters / scan / ui）与 G-013 大幅重叠；
   G-013 在 2026-10-17 修好 `pilotstd/` 识别后已覆盖这些目录。原映射要求"精确测试文件名"
   （tests/test_parser.py、tests/test_adapters.py），实测 2/2 假阳性——改动方实际写的是
   `test_exact_matcher.py` 等按功能命名的测试。故 G-029 只保留 **UI**（G-013 唯一未覆盖的
   目录），其余交给 G-013，避免同一文件被两套规则各判一次。
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")  # CI 中可通过环境变量指定对比分支
RANGE_ENV = "G029_RANGE"  # CI 传入 `<before>..<sha>`；与 T-27 同手法

# 变更路径前缀 → 必须同时变更的测试路径（任一匹配即可）
# 只保留 UI：其余目录由 G-013 的"tests/ 下任一测试变更"覆盖（见模块 docstring 第 2 点）
COVERAGE_MAP: list[tuple[list[str], list[str]]] = [
    (
        ["pilotstd/ui/"],
        ["tests/gui/", "tests/test_ui", "tests/test_windows_tray"],
    ),
]


def _diff(range_spec: str) -> list[str] | None:
    """执行 `git diff --name-only <range>`；git 失败返回 None（与"0 个文件"区分）。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", range_spec],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            cwd=str(ROOT),
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [f for f in result.stdout.strip().splitlines() if f]


def _is_zero_before(range_spec: str) -> bool:
    """`before` 全零（新分支/强制推送）时显式范围无意义，应回退。"""
    left = range_spec.split("..")[0].strip()
    return bool(left) and set(left) <= {"0"}


def get_changed_files() -> list[str] | None:
    """返回变更文件列表；显式范围为空时返回 None（调用方判 FAIL）。"""
    explicit = os.environ.get(RANGE_ENV, "").strip()
    if explicit and ".." in explicit and not _is_zero_before(explicit):
        files = _diff(explicit)
        return files or None

    for spec in (f"origin/{BASE_BRANCH}...HEAD", "HEAD~1..HEAD"):
        files = _diff(spec)
        if files:
            return files
    return []


def matches_any(path: str, prefixes: list[str]) -> bool:
    """判断文件路径是否匹配任意一个前缀。"""
    return any(path.startswith(p) for p in prefixes)


def main() -> int:
    """入口：检查 UI 变更是否同步更新了对应测试文件。"""
    changed = get_changed_files()
    if changed is None:
        print(
            f"[G-029] FAIL: 显式范围 {RANGE_ENV} 内 0 个变更文件，拒绝静默通过"
            "（检查 before/sha 取值是否为空或全零）"
        )
        return 1
    if not changed:
        print("[G-029] PASS: 无变更文件")
        return 0

    failures: list[str] = []
    for src_prefixes, test_prefixes in COVERAGE_MAP:
        changed_src = [f for f in changed if matches_any(f, src_prefixes)]
        if not changed_src:
            continue
        if [f for f in changed if matches_any(f, test_prefixes)]:
            print(f"[G-029] OK: UI 变更已有测试同步 — {', '.join(changed_src)}")
            continue
        failures.append(
            f"  ❌ UI 变更未同步测试:\n"
            f"     变更文件: {', '.join(changed_src)}\n"
            f"     期望同步更新: {', '.join(test_prefixes)}"
        )

    if failures:
        print(f"[G-029] FAIL: {len(failures)} 项变更缺少测试同步")
        for f in failures:
            print(f)
        return 1

    print("[G-029] PASS: 所有变更已同步测试")
    return 0


if __name__ == "__main__":
    sys.exit(main())
