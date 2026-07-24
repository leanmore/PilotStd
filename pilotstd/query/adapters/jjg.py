# pilotstd/query/adapters/jjg.py
"""
国家计量技术规范全文公开系统适配器

URL: https://jjg.spc.org.cn/resmea/view/index
API: GET /api/standard/search/page?keyword=关键词&pageNum=页码&pageSize=条数
响应: JSON {total, rows[{code, title, status, publishDate, implementDate}]}
"""

import logging
from typing import Any, Optional

import httpx

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "计量技术规范"

logger = logging.getLogger(__name__)


class JJGAdapter(BaseAdapter):
    """国家计量技术规范查询适配器。"""

    BASE_URL = "https://jjg.spc.org.cn"
    API_URL = "https://jjg.spc.org.cn/resmea/api/standard/search/page"
    PAGE_SIZE = 20
    MAX_PAGES = 20

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://jjg.spc.org.cn/resmea/view/index",
            },
        )

    @property
    def site_name(self) -> str:
        return "jjg"

    @property
    def site_label(self) -> str:
        return "国家计量技术规范"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询计量技术规范，返回全部匹配结果列表。"""
        # 注意：keyword 参数是 URL query string，服务端大小写敏感
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        max_pages = min(kwargs.get("max_pages", self.MAX_PAGES), self.MAX_PAGES)
        page_size = kwargs.get("pageSize", self.PAGE_SIZE)
        all_results: list[QueryResult] = []

        for page in range(1, max_pages + 1):
            params: dict[str, Any] = {
                "keyword": keyword,
                "pageNum": page,
                "pageSize": page_size,
            }
            try:
                resp = self._client.get(self.API_URL, params=params, timeout=15)
            except Exception as e:
                logger.debug(f"jjg.spc.org.cn API 请求失败: {e}")
                break

            if resp.status_code != 200:
                break

            try:
                data = resp.json()
            except Exception:
                break

            rows = data.get("rows", [])
            if not rows:
                break

            for row in rows:
                r = self._parse_result(row, keyword)
                if r:
                    all_results.append(r)

            # 终止条件：返回行数不足一页，或已取满 total
            total = data.get("total", 0)
            if len(all_results) >= total:
                break

        return all_results

    # ── 引擎层 ──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配。"""
        candidates = self.query_standards(search_term, max_pages=1)
        if not candidates:
            return None
        for c in candidates:
            if c.standard_number == search_term:
                return c
        return max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")

    def _parse_result(self, row: dict[str, Any], search_term: str = "") -> Optional[QueryResult]:
        """从 JSON 行解析标准信息。"""
        std_no = (row.get("code") or "").strip()
        name = (row.get("title") or "").strip()

        if not std_no and not name:
            return None

        status_text = (row.get("status") or "").strip()
        status_map = {"现行": "现行", "现行有效": "现行", "即将实施": "即将实施", "废止": "废止", "已废止": "废止"}
        status = status_map.get(status_text, status_text) if status_text else "未知"

        pub_date = (row.get("publishDate") or "").strip()
        imp_date = (row.get("implementDate") or "").strip()

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
            status=status,
            match_status=match_status,
            implementation_date=imp_date,
            publish_date=pub_date,
            responsible_dept="国家市场监督管理总局",
            source_site=self.site_name,
        )
        return result
