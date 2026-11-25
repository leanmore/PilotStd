#!/usr/bin/env python3
"""重庆标准信息平台适配器冒烟测试（真实网络，只读检索）。

用法：
    python scripts/smoke_test_cqis.py

说明：
- 只发**只读 POST 检索**（`/LocalStandard/GetDB50ShareList`），不写任何站点数据；
- 站点仅 HTTP，需能访问 `db.cqis.cn`；
- CI 不运行（与其它 `smoke_test_*.py` 同口径），本地验证用。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pilotstd.query.adapters.cqis import CqisAdapter  # noqa: E402

CASES = [
    ("DB50/T 950", "荣昌卤鹅"),  # 现行 + 废止两代
    ("DB50/T 2087", "脑电图"),  # 纯数字段
]


def main() -> int:
    """逐条检索预设标准号并断言命中预期关键词，返回退出码（0=通过）。"""
    adapter = CqisAdapter()
    failures = 0
    for term, expect_in_name in CASES:
        results = adapter.query_standards(term)
        print(f"\n[查询] {term} → {len(results)} 条")
        if not results:
            print("  [FAIL] 无结果（站点不可达或结构变更）")
            failures += 1
            continue
        for r in results[:3]:
            print(
                f"  - {r.standard_number} | {r.standard_name} | {r.status} | "
                f"发布 {r.publish_date} | 实施 {r.implementation_date} | 代替 {r.replaces or '-'}"
            )
        if any(expect_in_name in (r.standard_name or "") for r in results):
            print(f"  [OK] 命中预期关键词「{expect_in_name}」")
        else:
            print(f"  [WARN] 未命中预期关键词「{expect_in_name}」（需人工确认）")
            failures += 1

    print(f"\n{'[OK] 冒烟通过' if failures == 0 else f'[FAIL] {failures} 项未通过'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
