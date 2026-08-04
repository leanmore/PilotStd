#!/usr/bin/env python
# 模块：scripts/smoke_test_miit.py
"""MIIT 适配器冒烟测试 — 独立可执行。

用途：验证 MIITAdapter 在真实网络环境下正常访问 std.miit.gov.cn。
用法：python scripts/smoke_test_miit.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    """冒烟测试入口：搜索 SH/T 并验证字段完整性。"""
    from pilotstd.query.adapters.miit import MIITAdapter

    a = MIITAdapter()
    print("[1/3] 搜索 'SH/T' ...")
    results = a.query_standards("SH/T")
    if not results:
        print("FAIL 搜索返回 0 条结果")
        return 1
    print(f"  OK 返回 {len(results)} 条")

    print("[2/3] 字段完整性检查 ...")
    r = results[0]
    if not r.standard_number or not r.standard_name:
        print(f"FAIL 字段为空: number={r.standard_number} name={r.standard_name}")
        return 1
    print(f"  OK 首条: {r.standard_number} — {r.standard_name[:50]}  [{r.status}]")
    print(f"      日期: {r.publish_date} / {r.implementation_date}")

    for i, r in enumerate(results[:3]):
        print(f"  [{i + 1}] {r.standard_number} — {r.standard_name[:50]}")

    print("[3/3] 空结果检查 ...")
    empty = a.query_standards("ZZZZZ_NONEXISTENT_99999")
    if empty:
        print(f"FAIL 期望空列表，实际 {len(empty)} 条")
        return 1
    print("  OK 空结果正常")

    print("\nMIIT 冒烟测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
