#!/usr/bin/env python3
"""G-031: 文档同步检查。

检查本次 PR 变更的核心模块是否同步更新了对应文档。
- 目标文档存在但未同步更新 → 阻断（exit 1）
- 目标文档不存在 → 告警但不阻断
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")

# 映射规则: (源路径前缀, 目标文档路径, 阻断模式)
# 阻断模式: "block" = 文档存在时阻断, "warn" = 仅告警
DOC_SYNC_MAP: list[tuple[str, str, str]] = [
    ("pilotstd/core/parser.py", "docs/architecture/modules/parser.md", "block"),
    ("pilotstd/query/adapters/", "docs/architecture/modules/query.md", "block"),
    ("pilotstd/core/_scan.py", "docs/architecture/modules/scan.md", "block"),
    ("pilotstd/ui/main_window.py", "docs/architecture/modules/ui.md", "block"),
    ("pilotstd/manager/", "docs/architecture/modules/manager.md", "block"),
    ("scripts/", "docs/governance/gates.md", "block"),
    (".github/workflows/", "docs/governance/gates.md", "block"),
    ("docs/governance/", "docs/governance/README.md", "block"),
    ("docs/architecture/decisions/", "docs/governance/README.md", "block"),
]


def get_changed_files() -> list[str]:
    """返回本次 PR 相对于 base branch 变更的文件列表。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{BASE_BRANCH}..HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(ROOT),
        )
    except subprocess.CalledProcessError:
        print(f"[G-031] WARN: 无法获取 diff (base={BASE_BRANCH})，跳过检查")
        return []
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def main() -> int:
    changed = get_changed_files()
    if not changed:
        print("[G-031] PASS: 无变更文件")
        return 0

    changed_set = {f.replace("\\", "/") for f in changed}

    failures: list[str] = []
    warnings: list[str] = []

    for src_prefix, doc_path, mode in DOC_SYNC_MAP:
        # 检查是否有变更文件匹配源路径
        matched = [f for f in changed_set if f.startswith(src_prefix)]
        if not matched:
            continue

        # 检查目标文档是否在变更列表中
        doc_changed = doc_path in changed_set

        if doc_changed:
            print(f"[G-031] OK: {src_prefix} → {doc_path} 已同步更新")
            continue

        # 文档未被修改 — 检查文档是否存在
        doc_full = ROOT / doc_path
        if doc_full.exists():
            failures.append(
                f"[G-031] FAIL: {src_prefix} 已变更，但 {doc_path} 未同步更新"
            )
        else:
            msg = f"[G-031] WARN: {src_prefix} 已变更，但 {doc_path} 不存在（目标文档待创建）"
            if mode == "warn":
                warnings.append(msg)
            else:
                failures.append(msg)

    # 汇总
    for w in warnings:
        print(f"  {w}")

    if failures:
        print(f"\n{len(failures)} 项文档同步失败:")
        for f in failures:
            print(f"  {f}")
        print(f"\nFAIL: 请同步更新上述文档后再提交。")
        return 1

    if warnings:
        print(f"\n{len(warnings)} 项告警（不阻断）")

    print("PASS: 文档同步检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
