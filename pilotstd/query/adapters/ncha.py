# 模块：项目/查询/适配器/脚本
"""
文物保护标准查询适配器

首页: http://bz.ncha.gov.cn/portal?id=311&navId=3
API: POST http://bz.ncha.gov.cn:9005/knowledge/bzgf/find
架构类型: json_api_post
反爬: 无
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "文物保护标准"

logger = logging.getLogger(__name__)

# 日期格式列表，按常见程度排序
_DATE_FORMATS = [
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]


def _format_date(date_str: str) -> str:
    """将多种日期格式统一转换为 YYYY-MM-DD。无效值返回空字符串。"""
    if not date_str or not isinstance(date_str, str):
        return ""
    date_str = date_str.strip()
    if not date_str:
        return ""
    # 已是--格式直接返回
    if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
        return date_str
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    logger.warning("NCHA 日期解析失败: %r", date_str)
    return ""


class NCHAAdapter(BaseAdapter):
    """文物保护标准查询适配器。"""

    BASE_URL = "http://bz.ncha.gov.cn"
    API_URL = "http://bz.ncha.gov.cn:9005/knowledge/bzgf/find"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": "http://bz.ncha.gov.cn",
                "Referer": "http://bz.ncha.gov.cn/",
            },
        )

    @property
    def site_name(self) -> str:
        return "ncha"

    @property
    def site_label(self) -> str:
        return "文物保护标准"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询标准，返回全部匹配结果列表。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []
        return self._search_candidates(keyword)

    # ── 引擎层 ──

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """搜索候选项。"""
        return self._fetch_candidates(search_term)

    def _build_body(self, keyword: str) -> dict[str, Any]:
        """构建 POST 请求体。itemCode 缺失=全部标准。"""
        return {
            "pagination": {"currentPage": 1, "pageSize": 20},
            "condition": {
                "keyword": keyword,
                "standardName": "",
                "standardNum": "",
                "standardStatusCode": "",
                "standardNatureCode": "",
                "publishingDateStart": "",
                "publishingDateEnd": "",
                "executeDateStart": "",
                "executeDateEnd": "",
            },
            "sort": {"column": "publishingDate", "dir": "desc"},
        }

    def _fetch_candidates(self, keyword: str) -> list[QueryResult]:
        """POST JSON 端点获取搜索结果。"""
        body = self._build_body(keyword)
        try:
            resp = self._client.post(self.API_URL, json=body, timeout=15)
        except Exception as e:
            logger.error("NCHA 请求失败: %s", e)
            return []

        if resp.status_code != 200:
            logger.error("NCHA HTTP %d: %s", resp.status_code, resp.text[:200])
            return []

        try:
            payload = resp.json()
        except ValueError:
            logger.error("NCHA JSON 解析失败: %s", resp.text[:200])
            return []

        if payload.get("code") != 200:
            logger.debug("NCHA API code=%s msg=%s", payload.get("code"), payload.get("msg", ""))
            return []

        data = payload.get("data", {})
        rows = data.get("data", [])
        if not rows:
            return []

        total = data.get("pagination", {}).get("totalNum", 0)
        if total > len(rows):
            logger.warning("NCHA 搜索结果 %d 条超出单页 20，当前仅返回首页 %d 条", total, len(rows))

        return [self._parse_result(rec, keyword) for rec in rows]

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """将 JSON 记录映射为 QueryResult，含日期格式转换。"""
        std_no = rec.get("standardNum", "") or ""
        name = rec.get("standardName", "") or ""

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

        return QueryResult(
            standard_number=std_no,
            standard_name=name,
            status=rec.get("standardStatusName", "") or "未知",
            match_status=match_status,
            implementation_date=_format_date(rec.get("executeDate", "") or ""),
            publish_date=_format_date(rec.get("publishingDate", "") or ""),
            responsible_dept=rec.get("publishingBody", "") or "",
            hcno=rec.get("id", "") or "",
            source_site=self.site_name,
        )
