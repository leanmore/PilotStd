#!/usr/bin/env python
# 模块：scripts/smoke_test_cssn.py
"""CSSN 适配器冒烟测试 — 独立可执行。

用法：python scripts/smoke_test_cssn.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    """冒烟测试入口：搜索 GB/T 19001 并验证字段完整性。"""
    from pilotstd.query.adapters.cssn import CSSNAdapter

    a = CSSNAdapter()
    print("[1/3] 搜索 'GB/T 19001' ...")
    results = a.query_standards("GB/T 19001")
    assert len(results) > 0, f"期望至少1条结果，实际 {len(results)}"
    print(f"  OK 返回 {len(results)} 条")

    print("[2/3] 字段完整性检查 ...")
    r = results[0]
    for field in ["standard_number", "standard_name", "status", "publish_date"]:
        assert hasattr(r, field), f"缺少字段: {field}"
        assert getattr(r, field), f"字段 {field} 为空"
    print(f"  OK 首条: {r.standard_number} — {r.standard_name[:50]}  [{r.status}]")
    print(f"      日期: {r.publish_date} / {r.implementation_date}")
    print(f"      类型: {getattr(r, 'standard_type', 'N/A')}")
    for i, r in enumerate(results[:3]):
        print(f"  [{i + 1}] {r.standard_number} — {r.standard_name[:50]}")

    print("[3/3] 空结果检查 ...")
    empty = a.query_standards("ZZZZZ_NONEXISTENT_99999")
    assert empty == [], f"期望空列表，实际 {empty}"
    print("  OK 空结果正常")

    print("\nCSSN 冒烟测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
