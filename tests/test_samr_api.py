"""test_samr_api.py — 验证 GB/HB/DB 三个 SAMR 公告列表 API 返回字段。
mock 外部 HTTP 请求，不实际访问 std.samr.gov.cn（GitHub Actions 境外 IP 被墙）。
"""

from unittest.mock import MagicMock, patch

import pytest

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

# 模拟 API 返回数据：每个端点构造一条符合条件的 row
MOCK_ROWS = {
    "GB": [{"TITLE": "国家标准公告2024年第1号", "NOTICE_DATE": "2024-01-15"}],
    "HB": [{"C_TITLE": "行业标准公告2024年第1号", "STD_COUNT": 5, "NOTICE_DATE": "2024-01-15"}],
    "DB": [{"C_TITLE": "地方标准公告2024年第1号", "STD_COUNT": 3, "NOTICE_DATE": "2024-01-15"}],
}


def _mock_response(rows):
    """构造一个模拟的 requests.Response，.json() 返回含 rows 的 dict。"""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"rows": rows, "total": len(rows)}
    return resp


@pytest.mark.parametrize(
    "name,url,expected",
    [(name, url, EXPECTED_FIELDS[name]) for name, url in ENDPOINTS.items()],
)
def test_samr_api_fields(name, url, expected):
    """验证 SAMR 列表 API 返回的 TITLE / C_TITLE / STD_COUNT 字段。"""
    with patch(
        "tests.test_samr_api.safe_raw_get",
        return_value=_mock_response(MOCK_ROWS[name]),
    ):
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
