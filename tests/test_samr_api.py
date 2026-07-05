"""test_samr_api.py — 验证 GB/HB/DB 三个 SAMR 公告列表 API 返回字段。
仅用于本地测试，不修改任何业务代码。
"""

import sys

# 复用项目请求层
sys.path.insert(0, ".")
from pilotstd.query.network import safe_raw_get

ENDPOINTS = {
    "GB (国标)": "https://std.samr.gov.cn/noc/search/nocGBPage",
    "HB (行标)": "https://std.samr.gov.cn/noc/search/nocHBPage",
    "DB (地标)": "https://std.samr.gov.cn/noc/search/nocDBPage",
}

FIELDS_TO_CHECK = ["TITLE", "C_TITLE", "STD_COUNT"]


def test_endpoint(name: str, url: str) -> dict:
    """请求列表 API，返回第一条数据的字段分析结果。"""
    print(f"\n{'=' * 60}")
    print(f"  测试端点: {name}")
    print(f"  URL: {url}")
    print(f"{'=' * 60}")

    resp = safe_raw_get(
        url,
        site_name="test_samr_api",
        timeout=30,
        params={
            "pageNumber": 1,
            "pageSize": 1,
            "sortName": "NOTICE_DATE",
            "sortOrder": "desc",
        },
    )

    if resp is None:
        print("  [FAIL] safe_raw_get returned None")
        return {}

    if resp.status_code != 200:
        print(f"  [FAIL] HTTP {resp.status_code}")
        print(f"  响应体前 500 字符: {resp.text[:500]}")
        return {}

    try:
        data = resp.json()
    except Exception as e:
        print(f"  [FAIL] JSON parse error: {e}")
        print(f"  响应体前 500 字符: {resp.text[:500]}")
        return {}

    rows = data.get("rows", [])
    total = data.get("total", "?")
    print(f"  total: {total}, 返回行数: {len(rows)}")

    if not rows:
        print("  ⚠️ 无数据行")
        return {}

    # 第一条数据的字段分析
    first = rows[0]
    print("\n  第一条数据的所有字段:")
    for k, v in first.items():
        val_str = str(v)[:100] if v is not None else "None"
        print(f"    {k}: {val_str}")

    print("\n  Target fields:")
    result = {}
    for field in FIELDS_TO_CHECK:
        exists = field in first
        value = first.get(field, "KEY_NOT_FOUND")
        if exists:
            print(f"    [EXISTS] {field} = {str(value)[:120]}")
        else:
            print(f"    [MISSING] {field}")
        result[field] = {"exists": exists, "value": value if exists else None}

    return result


def main():
    print("SAMR 公告列表 API 字段验证测试")
    print(f"检查字段: {FIELDS_TO_CHECK}")
    print()

    summary = {}
    for name, url in ENDPOINTS.items():
        result = test_endpoint(name, url)
        summary[name] = result

    # 汇总
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")
    for name, fields in summary.items():
        print(f"\n  {name}:")
        for field, info in fields.items():
            status = "[OK]" if info["exists"] else "[MISSING]"
            val = str(info["value"])[:60] if info["value"] else "-"
            print(f"    {status} {field}: {val}")


if __name__ == "__main__":
    main()
