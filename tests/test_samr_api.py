"""test_samr_api.py — 验证 GB/HB/DB 三个 SAMR 公告列表 API 返回字段。
仅用于本地测试，不修改任何业务代码。
"""

import sys

import pytest

# 复用项目请求层
sys.path.insert(0, ".")
from pilotstd.query.network import safe_raw_get

ENDPOINTS = {
    "GB": "https://std.samr.gov.cn/noc/search/nocGBPage",
    "HB": "https://std.samr.gov.cn/noc/search/nocHBPage",
    "DB": "https://std.samr.gov.cn/noc/search/nocDBPage",
}

# 每个端点预期的字段存在性
EXPECTED_FIELDS = {
    "GB": {"TITLE": True, "C_TITLE": False, "STD_COUNT": False},
    "HB": {"TITLE": False, "C_TITLE": True, "STD_COUNT": True},
    "DB": {"TITLE": False, "C_TITLE": True, "STD_COUNT": True},
}


@pytest.mark.parametrize("name,url,expected", [(name, url, EXPECTED_FIELDS[name]) for name, url in ENDPOINTS.items()])
def test_samr_api_fields(name, url, expected):
    """验证 SAMR 列表 API 返回的 TITLE / C_TITLE / STD_COUNT 字段。"""
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

    assert resp is not None, f"{name}: safe_raw_get returned None"
    assert resp.status_code == 200, f"{name}: HTTP {resp.status_code}"

    data = resp.json()
    rows = data.get("rows", [])
    assert len(rows) > 0, f"{name}: no rows in response"

    first = rows[0]
    for field, should_exist in expected.items():
        actual = field in first
        assert actual == should_exist, (
            f"{name}: {field} expected={'EXISTS' if should_exist else 'MISSING'}, "
            f"got={'EXISTS' if actual else 'MISSING'}"
        )
