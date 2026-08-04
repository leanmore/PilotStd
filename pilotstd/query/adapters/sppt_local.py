# 模块：项目/查询/适配器/_脚本
"""
食品安全地方标准数据检索平台适配器（8087）

URL: https://sppt.cfsa.net.cn:8087/db
数据格式: SSR HTML 内嵌 Vue.js dataList JSON
搜索: POST task=index&keyword=X&accessData=df
分页: pageIndex 参数被服务端忽略，仅返回首页
SSL: 自签名证书（verify=False）
"""

import json
import logging
import re
from typing import Any, Optional

import httpx
import urllib3

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "食品安全地标"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# 提取正则（3种模式，按置信度降序）
_DATALIST_PATTERNS = [
    re.compile(r"dataList\s*:\s*(\[.*?\])\s*,\s*\w+\s*:", re.DOTALL),  # Vue data()
    re.compile(r"dataList\s*:\s*(\[.*?\])\s*[,}]", re.DOTALL),  # 宽松匹配
    re.compile(r"dataList\s*=\s*(\[.*?\])\s*;", re.DOTALL),  # 赋值语句
]


class SPPTLocalAdapter(BaseAdapter):
    """食品安全地方标准查询适配器（8087）。
    仅适用于食品安全地方标准，国标请使用 SPPTAdapter（8086）。
    """

    SEARCH_URL = "https://sppt.cfsa.net.cn:8087/db"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            verify=False,  # 自签名 SSL
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://sppt.cfsa.net.cn:8087/db",
            },
        )

    @property
    def site_name(self) -> str:
        return "sppt_local"

    @property
    def site_label(self) -> str:
        return "食品安全地方标准"

    # ──提取──

    def _extract_datalist(self, html: str) -> list[dict[str, Any]]:
        """从 SSR HTML 提取 Vue dataList JSON 数组（3 种正则降级）。"""
        for pattern in _DATALIST_PATTERNS:
            match = pattern.search(html)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    continue
        logger.debug("SPPT Local: dataList extraction failed with all patterns")
        return []

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询食品安全地方标准。
        注意：分页不可用，仅返回首页结果（≤6 条）。
        """
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        data: dict[str, Any] = {
            "task": "index",
            "accessData": "df",
            "keyword": keyword,
            "tabActive": "1",
        }

        try:
            resp = self._client.post(self.SEARCH_URL, data=data, timeout=15)
        except Exception as e:
            logger.debug(f"sppt.cfsa.net.cn:8087 POST 失败: {e}")
            return []

        if resp.status_code != 200:
            return []

        # 会话过期检测
        if "重新登录" in resp.text or "会话过期" in resp.text:
            logger.debug("SPPT Local: session expired")
            return []

        data_list = self._extract_datalist(resp.text)
        if not data_list:
            return []

        # ✅#462:服务端忽略分页，仅返回首页（≤6条），添加告警
        max_first_page = len(data_list)
        logger.warning(
            "SPPT Local 仅返回首页 %d 条结果（服务端忽略 pageIndex 参数），关键词 %r 的结果可能不完整",
            max_first_page,
            keyword,
        )

        results: list[QueryResult] = []
        for row in data_list:
            r = self._parse_result(row, keyword)
            if r:
                results.append(r)

        return results

    # ── 引擎层 ──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配。"""
        candidates = self.query_standards(search_term)
        if not candidates:
            return None
        for c in candidates:
            if c.standard_number == search_term:
                return c
        return max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")

    def _parse_result(self, row: dict[str, Any], search_term: str = "") -> Optional[QueryResult]:
        """从 dataList 行解析标准信息。"""
        std_no = (row.get("standard_code") or "").strip()
        name = (row.get("title") or "").strip()

        if not std_no:
            return None

        province = (row.get("province") or "").strip()
        # 省份后缀：直辖市用"市"，其余用"省"
        municipalities = {"北京", "上海", "天津", "重庆"}
        if province in municipalities:
            dept = f"{province}市"
        elif province:
            dept = f"{province}省"
        else:
            dept = "未知省份"

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
            status="现行",
            match_status=match_status,
            implementation_date="",
            publish_date="",
            responsible_dept=dept,
            source_site=self.site_name,
        )
        return result
