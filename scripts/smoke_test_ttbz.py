#!/usr/bin/env python
"""团体标准平台（ttbz）适配器冒烟测试（真实网络，只读 POST 检索）。

用法：
    python scripts/smoke_test_ttbz.py

说明：
- 只发**只读 POST 检索**（站点公开查询接口），不写任何站点数据；
- 需能访问 `www.ttbz.org.cn`；适配器会先 GET `standard.html` 引导 `JSESSIONID`
  （直接 POST 会 403「访问受限」，实测 2026-11-24）；
- **按标准号检索必须用 `standardNo`**：`standardName` 是名称过滤；
- CI 不运行（与其它 `smoke_test_*.py` 同口径），本地验证用。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pilotstd.query.adapters.ttbz import TTBZAdapter  # noqa: E402

CASES = [
    ("T/BSCA", "T/BSCA"),  # 组织代号前缀（真实数据：6 条）
    ("T/CECS 2355—2026", "T/CECS 2355"),  # 真实存在的精确编号（2026-11-24 实测）
]


def main() -> int:
    """逐条检索并断言标准号前缀命中，返回退出码（0=通过）。"""
    adapter = TTBZAdapter()
    failures = 0
    for term, expect_prefix in CASES:
        results = adapter.query_standards(term)
        print(f"\n[查询] {term} -> {len(results)} 条")
        if not results:
            print("  [FAIL] 无结果（站点不可达 / 会话引导失败 / 结构变更）")
            failures += 1
            continue
        for r in results[:3]:
            print(
                f"  - {r.standard_number} | {r.standard_name[:40]} | {r.status} | "
                f"发布 {r.publish_date} | 归口 {r.responsible_dept[:20]}"
            )
        if any((r.standard_number or "").startswith(expect_prefix) for r in results):
            print(f"  [OK] 命中预期前缀「{expect_prefix}」")
        else:
            print(f"  [WARN] 未命中预期前缀「{expect_prefix}」（需人工确认）")
            failures += 1

    print(f"\n{'[OK] 冒烟通过' if failures == 0 else f'[FAIL] {failures} 项未通过'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
