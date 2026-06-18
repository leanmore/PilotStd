# pilotstd/query/adapters/hbba.py
# 行业标准信息服务平台（hbba.sacinfo.org.cn）查询适配器
# 替代 openstd 对非国标（行业标准）的查询

import logging
import re
from datetime import datetime

import requests

from ..models import QueryResult
from ..network import safe_get
from ..search_strategy import (
    _parse_result_number,
    is_adopted,
    map_status,
    match_result,
    ts_to_date,
)
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class HbbaAdapter(BaseAdapter):
    """行业标准信息服务平台查询适配器。"""

    supports_replaces_detail = True

    API_URL = "https://hbba.sacinfo.org.cn/stdQueryList"
    DETAIL_URL = "https://hbba.sacinfo.org.cn/stdDetail/{}"

    def __init__(self, session: requests.Session = None):
        self._session = session or requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://hbba.sacinfo.org.cn",
        })

    @property
    def site_name(self) -> str:
        return "hbba"

    @property
    def site_label(self) -> str:
        return "行业标准平台"

    def _search_candidates(self, search_term: str) -> list:
        """返回 API 全部候选结果。"""
        return self._post_search_candidates(search_term)

    def _post_process_result(self, result: QueryResult) -> None:
        """结果后处理：从详情页提取替代标准号。"""
        if result.hcno:
            result.replaces = self._fetch_detail_replaces(result.hcno) or ""

    def _parse_result(self, rec: dict, search_term: str = "") -> QueryResult:
        code = rec.get("code", "")
        ch_name = rec.get("chName", "")
        raw_status = rec.get("status", "")
        pk = rec.get("pk", "")

        issue_date = ts_to_date(rec.get("issueDate"))
        act_date = ts_to_date(rec.get("actDate"))

        # 状态修正：前端 JS 会将 actDate 在未来者显示为"即将实施"
        mapped = map_status(raw_status)
        if mapped == "现行" and act_date:
            try:
                act_dt = datetime.strptime(act_date, "%Y-%m-%d")
                if act_dt > datetime.now():
                    mapped = "即将实施"
            except ValueError:
                pass

        adopted = is_adopted(ch_name)

        # 用搜索目标（search_term）与 API 返回结果（code）比对，避免自比较
        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""), target.get("number", 0),
            target.get("year", 0), ch_name, code)

        return QueryResult(
            standard_number=code,
            standard_name=ch_name,
            status=mapped,
            match_status=match_status,
            implementation_date=act_date,
            publish_date=issue_date,
            responsible_dept=rec.get("chargeDept", "") or "网站无此分类",
            is_adopted=adopted,
            is_downloadable=not adopted,
            source_site=self.site_name,
            hcno=str(pk) if pk else "",
        )

    # 详情页 URL 模板
    DETAIL_URL = "https://hbba.sacinfo.org.cn/stdDetail/{}"

    def _fetch_detail_replaces(self, pk: str) -> str:
        """从详情页提取代替标准号。\"代替标准\"行中提取第一个标准号。"""
        if not pk:
            return ""
        try:
            url = self.DETAIL_URL.format(pk)
            resp = safe_get(self._session, url, self.site_name, timeout=10)
            if resp is None or resp.status_code != 200:
                return ""
            # 匹配 \"代替标准\\nSH/T 1752—2006\"
            m = re.search(
                r'代替标准\s*\n\s*([A-Z]+(?:/[A-Z]+)?\s*\d+(?:\.\d+)?\s*[—\-]\s*\d{4})',
                resp.text)
            if m:
                return m.group(1).strip()
        except Exception:
            logger.debug("hbba 替代标准解析失败", exc_info=True)
        return ""
