#!/usr/bin/env python
# 模块：scripts/smoke_test_tdpress.py
"""tdpress 适配器冒烟测试 — 独立可执行。

用途：验证 TDPressAdapter 在真实网络环境下正常访问 biaozhun.tdpress.com。
用法：python scripts/smoke_test_tdpress.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from pilotstd.query.adapters.tdpress import TDPressAdapter

    a = TDPressAdapter()
    print("[1/3] 搜索 'TB' ...")
    results = a.query_standards("TB")
    assert len(results) > 0, f"期望至少1条结果，实际 {len(results)}"
    print(f"  OK 返回 {len(results)} 条")

    print("[2/3] 字段完整性检查 ...")
    r = results[0]
    for field in ["standard_number", "standard_name", "status", "implementation_date"]:
        assert hasattr(r, field), f"缺少字段: {field}"
        assert getattr(r, field) or field == "implementation_date", f"字段 {field} 为空"
    print(f"  OK 首条: {r.standard_number} {r.standard_name} [{r.status}]")

    # 展示前3条核心信息
    for i, r in enumerate(results[:3]):
        print(f"  [{i + 1}] {r.standard_number} — {r.standard_name[:50]}  [{r.status}]")

    print("[3/3] 空结果检查 ...")
    empty = a.query_standards("ZZZZZ_NONEXISTENT_99999")
    assert empty == [], f"期望空列表，实际 {empty}"
    print("  OK 空结果正常")

    print("\ntdpress 冒烟测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
