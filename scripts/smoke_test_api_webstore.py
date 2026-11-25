#!/usr/bin/env python
"""API Webstore 适配器冒烟测试（真实网络，只读 POST 检索）。

用法：
    python scripts/smoke_test_api_webstore.py

说明：
- 只发**只读 POST 搜索**（Coveo Search API），不写任何站点数据；
- 需能访问 `platform.cloud.coveo.com`；
- **token 轮换检测**：若返回 401 且自动刷新失败，本脚本会失败——说明需要更新 token；
- CI 不运行（与其它 `smoke_test_*.py` 同口径），本地验证用。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pilotstd.query.adapters.api_webstore import ApiWebstoreAdapter  # noqa: E402

CASES = [
    ("API STD 610-2026", "610"),
    ("API SPEC 6D-2021", "6D"),
    ("API RP 2A-WSD", "2A-WSD"),
]


def main() -> int:
    """逐条检索预设编号并断言 productcode 命中，返回退出码（0=通过）。"""
    adapter = ApiWebstoreAdapter()
    failures = 0
    for term, expect_code in CASES:
        results = adapter.query_standards(term)
        print(f"\n[查询] {term} -> {len(results)} 条")
        if not results:
            print("  [FAIL] 无结果（站点不可达 / token 失效 / 结构变更）")
            failures += 1
            continue
        for r in results[:3]:
            print(
                f"  - {r.standard_number} | {r.standard_name[:60]} | {r.status} | "
                f"发布 {r.publish_date} | 归口 {r.responsible_dept[:40]}"
            )
        if any(expect_code in (r.standard_number or "") for r in results):
            print(f"  [OK] 命中预期代号「{expect_code}」")
        else:
            print(f"  [WARN] 未命中预期代号「{expect_code}」（需人工确认）")
            failures += 1

    print(f"\n{'[OK] 冒烟通过' if failures == 0 else f'[FAIL] {failures} 项未通过'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
