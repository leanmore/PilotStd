# pilotstd/query/adapters/mee.py
"""
生态环境部标准查询适配器

URL: https://www.mee.gov.cn/ywgz/fgbz/bz/bzfb/
搜索 API: https://www.mee.gov.cn/was5/web/search
参数: channelid=270514 (标准发布栏目), searchword=关键词, page=页码

注意：
- 搜索结果由 JS 动态加载，适配器直接调用后端 WAS5 API。
- 返回 HTML 片段，使用 BeautifulSoup + lxml 解析。
- 编码为 UTF-8。
- 仅处理分类为"法规标准"的条目，过滤新闻和互动交流。
- 标准号从 h2/p 文本中用正则提取，格式为 {前缀} {序号}-{年份}。
"""

import logging
import re
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "生态环境部"

logger = logging.getLogger(__name__)

# 标准号提取正则：前缀 + 空格 + 序号 + 连接符 + 年份
# 前缀示例：GB/T, GB, HJ, HJ/T, DBxx/T, DBxx
# 序号可选带部分号（如 43871.1），连接符可能是 - — –
_STD_NO_RE = re.compile(
    r"(GB\s*/\s*[TZ]|HJ\s*/\s*T|DB\d{2}\s*/\s*T|GB|HJ|DB\d{2})"
    r"\s+"
    r"(\d+(?:\.\d+)?)"
    r"\s*[—\-–]\s*"
    r"(\d{2,4})",
    re.IGNORECASE,
)

# 有效标准分类
_VALID_CATEGORY = "法规标准"


class MEEAdapter(BaseAdapter):
    """生态环境部标准查询适配器。"""

    SEARCH_API = "https://www.mee.gov.cn/was5/web/search"
    # channelid=270514 对应"标准发布"栏目，若未来改版需从首页JS中提取新值
    CHANNEL_ID = "270514"

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.mee.gov.cn/searchnew/",
            }
        )

    @property
    def site_name(self) -> str:
        return "mee"

    @property
    def site_label(self) -> str:
        return "生态环境部标准"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询生态环境标准，返回全部匹配结果列表。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        params: dict[str, Any] = {
            "channelid": self.CHANNEL_ID,
            "searchword": keyword,
            "page": kwargs.get("pageNo", 1),
            "orderby": "relevance",
        }
        # 可选参数透传
        for key in ("searchscope", "timestart", "timeend", "period", "chnls", "andsen"):
            if key in kwargs:
                params[key] = kwargs[key]

        try:
            resp = self._session.get(self.SEARCH_API, params=params, timeout=15)
        except Exception as e:
            logger.debug(f"mee.gov.cn API 请求失败: {e}")
            return []

        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # 查找结果项（ul#list2 下的 li.li）
        items = soup.select("ul#list2 li.li")
        if not items:
            return []

        results: list[QueryResult] = []
        for item in items:
            result = self._parse_result(item, keyword)
            if result:
                results.append(result)

        return results

    # ── 引擎层 ──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配（精确匹配优先，否则返回最新）。"""
        candidates = self.query_standards(search_term)
        if not candidates:
            return None
        for c in candidates:
            if c.standard_number == search_term:
                return c
        # 返回发布日期最新的候选
        best = max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")
        return best

    def _parse_result(self, item: Any, search_term: str = "") -> Optional[QueryResult]:
        """从 BeautifulSoup Tag 解析标准信息。"""
        # 1. 检查分类：仅处理"法规标准"
        cat_em = item.select_one("em.fl.ll_gjjs_list_title")
        category = cat_em.text.strip() if cat_em else ""
        if category != _VALID_CATEGORY:
            return None

        # 2. 提取 h2 文本（去掉分类前缀）
        h2 = item.select_one("h2.h2")
        h2_text = h2.get_text(" ", strip=True) if h2 else ""
        if category and h2_text.startswith(category):
            h2_text = h2_text[len(category) :].strip()

        # 3. 提取 p 文本，合并后用正则提取标准号
        p_tag = item.select_one("p.p")
        p_text = p_tag.get_text(" ", strip=True) if p_tag else ""
        full_text = h2_text + " " + p_text

        m = _STD_NO_RE.search(full_text)
        if not m:
            return None

        prefix = re.sub(r"\s+", "", m.group(1))
        std_no = f"{prefix} {m.group(2)}-{m.group(3)}"

        # 4. 标准名称取 h2 文本（不含分类前缀）
        std_name = h2_text

        # 5. 提取实施日期
        span = item.select_one("span.span")
        implement_date = span.text.strip() if span else ""

        # 6. 匹配状态
        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            std_name,
            std_no,
        )

        result = QueryResult(
            standard_number=std_no,
            standard_name=std_name,
            status="未知",
            match_status=match_status,
            implementation_date=implement_date,
            publish_date="",
            responsible_dept="生态环境部",
            source_site=self.site_name,
        )
        return result

    # ── 详情页补充（Q22-03 待实现）──

    def _fetch_detail_status(self, detail_url: str) -> str:
        """从详情页提取标准状态（Q22-03 待办）。

        当前列表页不提供状态字段，返回 "未知"。
        后续迭代需：请求 detail_url → 解析详情页 DOM → 提取状态文本。
        """
        return "未知"
