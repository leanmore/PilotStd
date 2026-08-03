# tests/e2e/test_gongbiaoku_query_e2e.py
"""E2E test for GongBiaoKuAdapter.query_standards() — httpx + HTML parsing boundary.

Verifies:
  - Valid HTML → correctly parsed list[QueryResult]
  - Empty result set → empty list (not exception)
  - HTTP error → graceful degradation (empty list)
  - Network error → graceful degradation (empty list)
"""

from __future__ import annotations

import httpx
import pytest
import respx

from pilotstd.query.adapters.gongbiaoku import GongBiaoKuAdapter
from pilotstd.query.models import QueryResult

SEARCH_URL = "https://www.gongbiaoku.com/search"

# Mock HTML matching real selector: soup.select("ul.name-intr") + li text via _LABEL_RE
_VALID_HTML = """\
<ul class="name-intr">
  <li>标准名称：信息技术 软件测试方法</li>
  <li>标准编号：GB/T 12345-2020</li>
  <li>发布日期：2020-01-01</li>
  <li>实施日期：2020-07-01</li>
</ul>
<ul class="name-intr">
  <li>标准名称：软件工程 需求规格说明</li>
  <li>标准编号：GB/T 67890-2019</li>
  <li>发布日期：2019-06-15</li>
  <li>实施日期：2019-12-01</li>
</ul>
"""

_EMPTY_HTML = '<div class="search-results"></div>'


@pytest.fixture
def adapter():
    """Create adapter with injectable httpx.Client for respx interception."""
    client = httpx.Client()
    yield GongBiaoKuAdapter(client=client)
    client.close()


@respx.mock
def test_query_returns_parsed_results(adapter):
    """Valid HTML → list of QueryResult with correct fields."""
    route = respx.get(SEARCH_URL, params={"txt": "GB/T 12345"}).respond(
        status_code=200,
        content=_VALID_HTML.encode("utf-8"),
        headers={"content-type": "text/html; charset=utf-8"},
    )

    results = adapter.query_standards("GB/T 12345")

    assert route.called
    assert len(results) == 2
    assert all(isinstance(r, QueryResult) for r in results)
    assert results[0].standard_number == "GB/T 12345-2020"
    assert results[0].standard_name == "信息技术 软件测试方法"
    assert results[0].publish_date == "2020-01-01"
    assert results[0].implementation_date == "2020-07-01"
    assert results[0].source_site == "gongbiaoku"


@respx.mock
def test_query_empty_result_returns_empty_list(adapter):
    """Valid HTML but no ul.name-intr → empty list."""
    respx.get(SEARCH_URL, params={"txt": "NONEXISTENT-99999"}).respond(
        status_code=200,
        content=_EMPTY_HTML.encode("utf-8"),
    )

    results = adapter.query_standards("NONEXISTENT-99999")

    assert results == []


@respx.mock
def test_query_http_error_returns_empty_list(adapter):
    """Non-200 response → empty list (graceful degradation)."""
    respx.get(SEARCH_URL, params={"txt": "GB/T 12345"}).respond(status_code=503)

    results = adapter.query_standards("GB/T 12345")

    assert results == []


@respx.mock
def test_query_network_error_returns_empty_list(adapter):
    """Connection timeout → empty list, no unhandled exception."""
    respx.get(SEARCH_URL, params={"txt": "GB/T 12345"}).mock(
        side_effect=httpx.ConnectTimeout("timeout")
    )

    results = adapter.query_standards("GB/T 12345")

    assert results == []
