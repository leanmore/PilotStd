# 模块：项目/查询/适配器/脚本
"""
中国标准服务网适配器

URL: https://www.cssn.net.cn/api/standards/
架构: json_api_get
认证: 无（JSL 不影响 API）
分页: GET ?page=N，用 next 字段判终
"""

import logging
from typing import Any

import httpx

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from ._shared_ssl import default_ssl_context
from .base import BaseAdapter

DISPLAY_NAME = "中国标准服务网"

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15.0


class CSSNAdapter(BaseAdapter):
    """中国标准服务网查询适配器。"""

    BASE_URL = "https://www.cssn.net.cn"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=REQUEST_TIMEOUT,
            verify=default_ssl_context(),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.cssn.net.cn/cssn/index",
            },
        )

    @property
    def site_name(self) -> str:
        return "cssn"

    @property
    def site_label(self) -> str:
        return "中国标准服务网"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询标准，支持多页翻页。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        all_results: list[QueryResult] = []
        page = kwargs.get("page", 1)
        max_pages = kwargs.get("max_pages", 1)

        for current_page in range(page, page + max_pages):
            params: dict[str, Any] = {"keyword": keyword}
            if current_page > 1:
                params["page"] = current_page

            try:
                resp = self._client.get(self.get_search_url(), params=params, timeout=REQUEST_TIMEOUT)
            except Exception as e:
                logger.error("CSSN 请求失败 (page=%d): %s", current_page, e)
                break

            if resp.status_code != 200:
                logger.error("CSSN HTTP %d (page=%d)", resp.status_code, current_page)
                break

            try:
                payload = resp.json()
            except ValueError:
                logger.error("CSSN JSON 解析失败 (page=%d)", current_page)
                break

            rows = payload.get("results", [])
            if not rows:
                break

            for row in rows:
                result = self._parse_result(row, keyword)
                if result:
                    all_results.append(result)

            # 上限告警
            count = payload.get("count", 0)
            if count >= 10000:
                logger.warning("CSSN count=%d 达到上限（固定 10000），实际结果可能更多", count)

            # 用判终
            if not payload.get("next"):
                break

        return all_results

    # ── 引擎层 ──

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        return self.query_standards(search_term, max_pages=1)

    def _parse_result(self, row: dict[str, Any], search_term: str = "") -> QueryResult:
        std_no = row.get("a100", "") or ""
        name = row.get("a298", "") or ""

        if not std_no and not name:
            return QueryResult(standard_number="", source_site=self.site_name)

        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            name,
            std_no,
        )

        result = QueryResult(
            standard_number=std_no,
            standard_name=name,
            status=row.get("a000", "") or "未知",
            match_status=match_status,
            implementation_date=row.get("a205", "") or "",
            publish_date=row.get("a101", "") or "",
            responsible_dept="",
            hcno=row.get("yf001", "") or "",
            source_site=self.site_name,
        )
        # 附加信息（非标准字段）
        result.standard_type = row.get("a104name", "") or ""  # type: ignore[attr-defined]
        result.ccs = row.get("a825name", "") or ""  # type: ignore[attr-defined]
        result.ics = row.get("a826name", "") or ""  # type: ignore[attr-defined]
        return result
