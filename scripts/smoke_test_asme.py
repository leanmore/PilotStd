#!/usr/bin/env python
"""ASME 适配器冒烟测试（真实网络，只读 GET）。

用法：
    python scripts/smoke_test_asme.py

说明：
- 只发**只读 GET**（`/api/products` 商品目录），不写任何站点数据；
- 需能访问 `www.asme.org`；
- CI 不运行（与其它 `smoke_test_*.py` 同口径），本地验证用。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pilotstd.query.adapters.asme import AsmeAdapter  # noqa: E402

CASES = [
    ("ASME B16.5-2025", "B16.5"),
    ("ASME BPVC Section VIII Div.1-2025", "BPVC.VIII.1"),
    ("ASME PTC 4-2013", "PTC 4"),
    ("ASME Y14.5-2018", "Y14.5"),
]


def main() -> int:
    """逐条检索预设编号并断言 designator 命中，返回退出码（0=通过）。"""
    adapter = AsmeAdapter()
    failures = 0
    for term, expect_designator in CASES:
        results = adapter.query_standards(term)
        print(f"\n[查询] {term} -> {len(results)} 条")
        if not results:
            print("  [FAIL] 无结果（站点不可达 / 结构变更）")
            failures += 1
            continue
        for r in results[:3]:
            print(
                f"  - {r.standard_number} | {r.standard_name[:60]} | {r.status} | "
                f"年份 {r.publish_date} | 商品号 {r.hcno}"
            )
        if any(expect_designator in (r.standard_number or "") for r in results):
            print(f"  [OK] 命中预期 designator「{expect_designator}」")
        else:
            print(f"  [WARN] 未命中预期 designator「{expect_designator}」（需人工确认）")
            failures += 1

    print(f"\n{'[OK] 冒烟通过' if failures == 0 else f'[FAIL] {failures} 项未通过'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
