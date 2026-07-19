# tests/mocks/mock_http.py — HTTP mock 基础设施
"""使用 responses 库 mock HTTP 请求，预置常见 API 响应模板。

用法:
    import responses
    from tests.mocks.mock_http import mock_njbz365, mock_std_gov, ANNOUNCEMENT_HTML

    @responses.activate
    def test_something():
        mock_njbz365()
        # ... 发起请求的代码 ...
"""

from __future__ import annotations

from typing import Any

import responses as _responses

# ── 公告页面 HTML 模板 ──────────────────────────────────────────

ANNOUNCEMENT_HTML = """<!DOCTYPE html>
<html><body>
<table>
<tr><th>序号</th><th>std_code</th><th>std_name</th><th>publish_date</th></tr>
<tr><td>1</td><td>GB/T 1.1-2020</td><td>标准化工作导则 第1部分</td><td>2020-03-31</td></tr>
<tr><td>2</td><td>GB/T 19000-2016</td><td>质量管理体系 基础和术语</td><td>2016-12-30</td></tr>
</table>
</body></html>"""

# ── njbz365 API 响应 ────────────────────────────────────────────

NJBZ365_SEARCH_RESPONSE: dict[str, Any] = {
    "code": "0",
    "msg": "成功",
    "data": {
        "datalist": [
            {
                "bzbh": "GB/T 1.1-2020",
                "bzmc": "标准化工作导则 第1部分：标准化文件的结构和起草规则",
                "bzzt": "现行",
                "bzid": "abc123",
                "cybz": "",
                "fbrq": "2020-03-31",
                "ssrq": "2020-10-01",
            }
        ],
        "total": 1,
    },
}


def mock_njbz365_search(results: list[dict[str, Any]] | None = None, total: int | None = None) -> None:
    """注册 njbz365 搜索 API mock 响应。"""
    data = dict(NJBZ365_SEARCH_RESPONSE)
    if results is not None:
        data["data"] = {"datalist": results, "total": total or len(results)}
    _responses.add(
        _responses.POST,
        "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
        json=data,
        status=200,
    )


def mock_njbz365_empty() -> None:
    """注册 njbz365 空结果响应。"""
    data = {"code": "0", "msg": "成功", "data": {"datalist": [], "total": 0}}
    _responses.add(
        _responses.POST,
        "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
        json=data,
        status=200,
    )


# ── 公告 API 响应 ───────────────────────────────────────────────

ANNOUNCEMENT_LIST_RESPONSE: dict[str, Any] = {
    "rows": [
        {
            "PID": "pid001",
            "CODE": "2024-001",
            "TITLE": "国家标准公告2024年第1号",
            "NOTICE_DATE": "2024-01-15",
            "STD_COUNT": "2",
        },
        {
            "PID": "pid002",
            "CODE": "2024-002",
            "TITLE": "国家标准公告2024年第2号",
            "NOTICE_DATE": "2024-02-20",
            "STD_COUNT": "1",
        },
    ],
    "total": 2,
}


def mock_announcement_list(response: dict[str, Any] | None = None) -> None:
    """注册公告列表 API mock 响应。"""
    data = response or ANNOUNCEMENT_LIST_RESPONSE
    _responses.add(
        _responses.GET,
        _responses.matchers.query_param_matcher({"pageNumber": "1"}),  # type: ignore[arg-type]
        json=data,
        status=200,
    )


# ── 通用 GET mock ──────────────────────────────────────────────


def mock_get(url: str, body: str = "", status: int = 200, content_type: str = "text/html") -> None:
    """注册一个通用 GET mock。"""
    _responses.add(
        _responses.GET,
        url,
        body=body,
        status=status,
        content_type=content_type,
    )


def mock_get_json(url: str, data: dict[str, Any], status: int = 200) -> None:
    """注册一个返回 JSON 的 GET mock。"""
    _responses.add(
        _responses.GET,
        url,
        json=data,
        status=status,
    )
