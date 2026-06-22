# pilotstd/query/adapters/iso_gov.py
# 全国标准信息公共服务平台 — ISO/IEC 国际标准查询适配器
# API: std.samr.gov.cn/gj/search/gjPage

import logging
import re
from typing import Any

import requests

from ..models import QueryResult
from ..network import safe_get
from ..search_strategy import _parse_result_number, map_status, match_result
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class IsoGovAdapter(BaseAdapter):
    """ISO/IEC 国际标准查询适配器。

    API: GET https://std.samr.gov.cn/gj/search/gjPage?searchText=...
    搜索入口: std.samr.gov.cn/gj/std?key=xxx
    """

    SEARCH_URL = "https://std.samr.gov.cn/gj/search/gjPage"
    SEARCH_PAGE = "https://std.samr.gov.cn/gj/std"

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    @property
    def site_name(self) -> str:
        return "iso_gov"

    @property
    def site_label(self) -> str:
        return "国际标准平台"

    # _search 继承自 BaseAdapter（基类实现已覆盖：_search_candidates → 精确匹配 → 取最新）

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """返回 API 全部候选结果，供 base 层统一打分。"""
        if not any(kw in search_term.upper() for kw in ("ISO", "IEC")):
            return []

        clean_term = re.sub(r"[-—:]\s*\d{4}", "", search_term).strip()

        safe_get(
            self._session,
            self.SEARCH_PAGE,
            self.site_name,
            params={"key": clean_term},
            timeout=10,
        )

        self._session.headers["Referer"] = self.SEARCH_PAGE

        params = {
            "searchText": clean_term,
            "pageNumber": 1,
            "pageSize": 10,
        }
        resp = safe_get(
            self._session, self.SEARCH_URL, self.site_name, params=params, timeout=15
        )
        if resp is None or resp.status_code != 200:
            return []

        try:
            payload = resp.json()
        except ValueError:
            return []

        rows = payload.get("rows", [])
        if not rows:
            return []

        return [self._parse_result(row, search_term) for row in rows]

    def _parse_result(self, row: dict[str, Any], search_term: str = "") -> QueryResult:
        # 使用无 HTML 标签的字段
        std_no = self._clean_std_no(row.get("STANDARD_NO", ""))
        en_name = row.get("ENGLISH_NAME", "")
        state_raw = row.get("STATE", "")
        circ_date = row.get("CIRCULATION_DATE", "")
        std_status = row.get("STANDARD_STATUS", "")

        # 状态判定
        status = map_status(state_raw)
        if std_status == "WITHDRAWN" and status not in ("废止",):
            status = "废止"

        # ISO 采标判定：名称含 "adoption" → 是国内采标版本，不可下载
        is_adopted = "adoption" in en_name.lower()

        # 用搜索目标（search_term）与 API 返回结果（std_no）比对，避免自比较
        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            en_name,
            std_no,
        )

        return QueryResult(
            standard_number=std_no,
            standard_name=en_name,
            status=status,
            match_status=match_status,
            implementation_date="",
            publish_date=circ_date,
            abolition_date="网站无此分类",
            responsible_dept=row.get("PUBLISH_UNIT", "") or "网站无此分类",
            is_adopted=is_adopted,
            is_downloadable=not is_adopted,
            source_site=self.site_name,
            hcno=row.get("id", ""),
        )

    @staticmethod
    def _clean_std_no(text: str) -> str:
        """去除 HTML 高亮标签 <sacinfo>...</sacinfo>。"""
        if not text:
            return ""
        return re.sub(r"</?sacinfo>", "", text)
