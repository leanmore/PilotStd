# 模块：项目/查询/适配器/脚本
# 地方标准信息服务平台（...）查询适配器
# 覆盖全国各省/市地方标准（数据库标准）的查询

import logging
from datetime import datetime
from typing import Any

import requests

from ..models import QueryResult
from ..search_strategy import (
    _parse_result_number,
    is_adopted,
    map_status,
    match_result,
    ts_to_date,
)
from .base import BaseAdapter

DISPLAY_NAME = "地方标准"

logger = logging.getLogger(__name__)


class DbbaAdapter(BaseAdapter):
    """地方标准信息服务平台查询适配器。

    搜索入口: dbba.sacinfo.org.cn/stdList
    API 入口: dbba.sacinfo.org.cn/stdQueryList (POST, form-urlencoded)
    详情入口: dbba.sacinfo.org.cn/stdDetail/{pk}

    覆盖全国各省/市地方标准（DB11, DB35/T, DB3501/T 等）。
    """

    API_URL = "https://dbba.sacinfo.org.cn/stdQueryList"
    DETAIL_URL = "https://dbba.sacinfo.org.cn/stdDetail/{}"

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://dbba.sacinfo.org.cn",
            }
        )

    @property
    def site_name(self) -> str:
        return "dbba"

    @property
    def site_label(self) -> str:
        return "地方标准平台"

    def _build_search_data(self, search_term: str) -> dict[str, Any]:
        """地方标准 API 需要 status 参数避免遗漏已废止标准。"""
        data = super()._build_search_data(search_term)
        data["status"] = ""
        return data

    def _search_candidates(self, search_term: str) -> list[Any]:
        """返回 API 全部候选结果。"""
        return self._post_search_candidates(search_term)

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        code = rec.get("code", "")
        ch_name = rec.get("chName", "")
        raw_status = rec.get("status", "")
        pk = rec.get("pk", "")

        issue_date = ts_to_date(rec.get("issueDate"))
        act_date = ts_to_date(rec.get("actDate"))

        # 状态修正：在未来→即将实施
        mapped = map_status(raw_status)
        if mapped == "现行" and act_date:
            try:
                act_dt = datetime.strptime(act_date, "%Y-%m-%d")
                if act_dt > datetime.now():
                    mapped = "即将实施"
            except ValueError:
                pass

        adopted = is_adopted(ch_name)

        # 用搜索目标（_）与接口返回结果（）比对，避免自比较
        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            ch_name,
            code,
        )

        # 代替标准：接口直接返回，无需查详情页
        replaces = rec.get("reviseStdCodes", "") or ""

        return QueryResult(
            standard_number=code,
            standard_name=ch_name,
            status=mapped,
            match_status=match_status,
            implementation_date=act_date,
            publish_date=issue_date,
            responsible_dept=rec.get("chargeDept", "") or "",
            is_adopted=adopted,
            is_downloadable=False,  # DB 标准无法通过 openstd 下载
            source_site=self.site_name,
            hcno=str(pk) if pk else "",
            replaces=replaces,
        )
