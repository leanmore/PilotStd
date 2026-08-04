# 模块：pilotstd/query/adapters/miit.py
"""
工信部行业标准适配器

API: POST /kjsStandproject/front/zxd/stand/queryFullDisclosureStandards
架构: json_api_post_form
返回限制: 最多 15 条，无分页
⚠️ 参数拼写: stadardNum（站点源码缺字母 n）
"""

import logging
from typing import Any

import httpx

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "工信部行业标准"

logger = logging.getLogger(__name__)


class MIITAdapter(BaseAdapter):
    """工信部行业标准查询适配器。"""

    BASE_URL = "https://std.miit.gov.cn"
    API_URL = "https://std.miit.gov.cn/kjsStandproject/front/zxd/stand/queryFullDisclosureStandards"

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
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": "https://std.miit.gov.cn/",
            },
        )

    @property
    def site_name(self) -> str:
        return "miit"

    @property
    def site_label(self) -> str:
        return "工信部行业标准"

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

    def _fetch_candidates(self, keyword: str) -> list[QueryResult]:
        """POST form-urlencoded 获取搜索结果。"""
        body = {
            "stadardNum": keyword,
            "siZbzname": "",
            "userCode": "游客",
            "sourceType": "more",
            "piHyid": "",
            "hyName": "",
            "userId": "",
        }
        try:
            resp = self._client.post(self.API_URL, data=body, timeout=15)
        except Exception as e:
            logger.error("MIIT 请求失败: %s", e)
            return []

        if resp.status_code != 200:
            logger.error("MIIT HTTP %d: %s", resp.status_code, resp.text[:200])
            return []

        try:
            payload = resp.json()
        except ValueError:
            logger.error("MIIT JSON 解析失败: %s", resp.text[:200])
            return []

        if payload.get("code") != 0:
            logger.debug("MIIT API code=%s", payload.get("code"))
            return []

        rows = payload.get("data", [])
        if not rows:
            return []

        # 15 条截断告警
        if len(rows) >= 15:
            logger.warning(
                "MIIT API 返回 %d 条结果（达到上限），搜索词 %r 可能存在结果截断",
                len(rows),
                keyword,
            )
            # ✅ 任务5：为每条结果附加截断标记，透传至前端
            for rec in rows:
                rec["_truncated"] = True
                rec["_truncated_message"] = f"结果可能不完整，共{len(rows)}条仅展示前15条"

        return [self._parse_result(rec, keyword) for rec in rows]

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """将 form-urlencoded 响应记录映射为 QueryResult。"""
        std_no = rec.get("bpiBzno", "") or ""
        name = rec.get("piProjectname", "") or ""

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

        # ✅ #46 P2: 尝试从响应中提取真实状态字段，替代硬编码"现行"
        raw_status = rec.get("bpiBzstatus") or rec.get("standardStatus") or rec.get("status") or ""

        return QueryResult(
            standard_number=std_no,
            standard_name=name,
            status=raw_status if raw_status else "现行",  # 兜底仍用"现行"
            match_status=match_status,
            implementation_date=rec.get("bpiJysstime", "") or "",
            publish_date=rec.get("createTime", "") or "",
            responsible_dept="",
            hcno="",
            source_site=self.site_name,
        )
