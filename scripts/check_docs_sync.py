#!/usr/bin/env python3
"""文档同步门禁：核心模块变更时检查对应架构文档是否同步更新。

仅检查本次 PR 中变更的文件（diff 对 base branch），不追溯历史。
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")

# 核心模块变更 → 必须同步更新的架构文档
DOC_COVERAGE_MAP: dict[str, str] = {
    "pilotstd/core/": "docs/architecture/modules/core.md",
    "pilotstd/query/": "docs/architecture/modules/query.md",
    "pilotstd/scan/": "docs/architecture/modules/scan.md",
    "pilotstd/ui/": "docs/architecture/modules/ui.md",
    "pilotstd/manager/": "docs/architecture/modules/manager.md",
}


def get_changed_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{BASE_BRANCH}..HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(ROOT),
        )
    except subprocess.CalledProcessError:
        print("[docs-compliance] WARN: 无法获取 diff，跳过检查")
        return []
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def main() -> int:
    changed = get_changed_files()
    if not changed:
        print("[docs-compliance] PASS: 无变更文件")
        return 0

    failures: list[str] = []
    for src_prefix, doc_path in DOC_COVERAGE_MAP.items():
        changed_src = [f for f in changed if f.startswith(src_prefix)]
        if not changed_src:
            continue
        doc_changed = any(f == doc_path for f in changed)
        if doc_changed:
            print(f"[docs-compliance] OK: {src_prefix} 变更已同步文档 {doc_path}")
            continue
        doc_exists = (ROOT / doc_path).exists()
        if doc_exists:
            failures.append(
                f"  ❌ {src_prefix} 模块变更但未更新 {doc_path}\n"
                f"     变更文件: {', '.join(changed_src[:3])}"
                + (f" ...共{len(changed_src)}个" if len(changed_src) > 3 else "")
            )
        else:
            failures.append(f"  ❌ {src_prefix} 模块缺少架构文档 {doc_path}\n     请先创建 {doc_path} 再合入")

    if failures:
        print(f"[docs-compliance] FAIL: {len(failures)} 项文档未同步")
        for f in failures:
            print(f)
        return 1

    print("[docs-compliance] PASS: 所有核心模块变更已同步文档")
    return 0


if __name__ == "__main__":
    sys.exit(main())
