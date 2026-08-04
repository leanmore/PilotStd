# 模块：pilotstd/query/adapters/tdpress.py
"""
铁路标准查询适配器

URL: https://biaozhun.tdpress.com/#/
API: GET /front/queryFomePage（站点拼写确为 Fome，非 Form）
架构类型: json_api_get（jQuery EasyUI JSON 接口）
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "铁路标准平台"

logger = logging.getLogger(__name__)

# 铁路标准平台数据源时区为 CST (UTC+8)，显式指定避免容器 UTC 环境日期偏移
CST = timezone(timedelta(hours=8))


def _safe_ts_to_date(ms_timestamp: Any) -> str:
    """毫秒时间戳安全转换为 YYYY-MM-DD（CST 时区），无效值返回空字符串。"""
    if ms_timestamp is None or not isinstance(ms_timestamp, (int, float)):
        return ""
    try:
        return datetime.fromtimestamp(ms_timestamp / 1000, tz=CST).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return ""


def _map_status(raw: str) -> str:
    """TRUE/FALSE 字符串映射为中文状态，未知值保留原值并告警。"""
    mapping = {"TRUE": "现行", "FALSE": "废止"}
    result = mapping.get(raw.upper() if raw else "", raw)
    if result == raw and raw not in ("TRUE", "FALSE", ""):
        logger.warning("TDPress unknown status value: %r", raw)
    return result


class TDPressAdapter(BaseAdapter):
    """铁路标准查询适配器。"""

    BASE_URL = "https://biaozhun.tdpress.com"
    API_URL = "https://biaozhun.tdpress.com/front/queryFomePage"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://biaozhun.tdpress.com/",
            },
        )

    @property
    def site_name(self) -> str:
        return "tdpress"

    @property
    def site_label(self) -> str:
        return "铁路标准信息服务平台"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询标准，返回全部匹配结果列表。"""
        return self._search_candidates(standard_number)

    # ── 引擎层 ──

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """搜索候选项。"""
        keyword = search_term.strip() if search_term else ""
        if not keyword:
            return []
        return self._fetch_candidates(keyword)

    def _fetch_candidates(self, keyword: str) -> list[QueryResult]:
        """GET AJAX 端点获取搜索结果。"""
        params: dict[str, Any] = {
            "page": "1",
            "rows": "20",
            "queryKey": keyword,
            "soleLogo": "tlbz",
        }
        try:
            resp = self._client.get(self.API_URL, params=params, timeout=15)
        except Exception as e:
            logger.error("tdpress 请求失败: %s", e)
            return []

        if resp.status_code != 200:
            logger.error("tdpress HTTP %d: %s", resp.status_code, resp.text[:200])
            return []

        try:
            payload = resp.json()
        except ValueError:
            logger.error("tdpress JSON 解析失败: %s", resp.text[:200])
            return []

        rows = payload.get("rows", [])
        if not rows:
            return []

        return [self._parse_result(rec, keyword) for rec in rows]

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """将 JSON 记录映射为 QueryResult，含时间戳转换和状态映射。"""
        std_no = rec.get("standardNumber", "") or ""
        name = rec.get("standardName", "") or ""
        raw_status = rec.get("standardStatus", "") or ""

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
            status=_map_status(raw_status),
            match_status=match_status,
            implementation_date=_safe_ts_to_date(rec.get("implementDate")),
            publish_date=_safe_ts_to_date(rec.get("publicationDate")),
            replaces=rec.get("replaceStandard", "") or "",
            responsible_dept=rec.get("supervisorDept", "") or "",
            hcno=rec.get("standardFilingNum", "") or "",
            source_site=self.site_name,
        )
