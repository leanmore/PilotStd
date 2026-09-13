#!/usr/bin/env python3
"""能力矩阵与代码同步检查（入库文档门禁）。

背景：`docs/governance/capabilities_registry.md` 是**入库**文档，由
`scripts/generate_capabilities.py` 扫描代码生成；AGENTS.md 第七节要求
修改架构/ADR/pilotstd/core/docker-api/治理文档时重跑生成器并一并提交。
此前没有任何门禁核对"入库的能力矩阵是否与入库的代码一致"（G-032 只看它是否新鲜）。

做法：重新生成一次，与当前（入库）内容比对，忽略生成时间戳行；
有实质差异即判定不同步，提示作者本地重跑生成器并一并提交。
检查结束后把文件还原，保证 CI 工作区不残留改动。

放置位置：本检查针对**入库文档**，故由 CI 执行（docs 生成属本地行为，
本地生成后用本脚本可自查，但门禁挂在 CI）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "docs" / "governance" / "capabilities_registry.md"
GENERATOR = ROOT / "scripts" / "generate_capabilities.py"
AUTO_HEADER_PREFIX = "<!-- AUTO-GENERATED"
# 生成物里带时间戳的还有"生成时间"行，同样必须剔除，否则每次重生成都必然差异
GENERATED_AT_PREFIX = "> 生成时间："


def _normalize(text: str) -> str:
    """剔除生成时间戳行后归一化，避免时间戳导致必然差异。"""
    kept = [
        line
        for line in text.splitlines()
        if not line.startswith(AUTO_HEADER_PREFIX) and not line.startswith(GENERATED_AT_PREFIX)
    ]
    return "\n".join(kept).strip()


def main() -> int:
    """入口：重生成 → 比对 → 还原 → 输出结论。"""
    if not REGISTRY.exists():
        print(f"[capabilities-sync] FAIL: 缺少入库文档 {REGISTRY.relative_to(ROOT)}")
        return 1

    before = REGISTRY.read_text(encoding="utf-8")

    try:
        subprocess.run([sys.executable, str(GENERATOR)], check=True, cwd=str(ROOT))
    except subprocess.CalledProcessError as e:
        print(f"[capabilities-sync] FAIL: 生成器执行失败 ({e})")
        return 1

    after = REGISTRY.read_text(encoding="utf-8")
    REGISTRY.write_text(before, encoding="utf-8")  # 还原，避免 CI 工作区残留改动

    if _normalize(before) == _normalize(after):
        print("[capabilities-sync] PASS: 能力矩阵与代码一致")
        return 0

    print(
        "[capabilities-sync] FAIL: docs/governance/capabilities_registry.md 与代码不同步。\n"
        "  修复：本地执行 `python scripts/generate_capabilities.py`，"
        "将 capabilities_registry.md 一并提交（AGENTS.md 第七节）。"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
