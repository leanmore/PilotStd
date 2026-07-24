# pilotstd/query/adapters/jtst.py
"""
交通运输部标准查询适配器

URL: https://jtst.mot.gov.cn/search/std?q=关键词
搜索 API: /search/stdPage?tid=&q=关键词&op= （iframe 内嵌 HTML）
结果总数: 7000+ 条（GB + JT + JTG 已发布标准及标准计划）

注意：
- 搜索结果通过 iframe 加载 HTML 片段，不是表格而是卡片式布局。
- 卡片选择器: .panel.panel-default.post
- 标准号在 span.en-code 中；计划编号直接在 a 标签文本中。
- 无状态/发布日期等独立列，需从卡片内多个区域提取。
"""

import logging
import re
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

logger = logging.getLogger(__name__)

# 结果总数提取正则
_TOTAL_COUNT_RE = re.compile(r"(\d+)\s*条")


class JTSTAdapter(BaseAdapter):
    """交通运输部标准查询适配器。"""

    SEARCH_URL = "https://jtst.mot.gov.cn/search/stdPage"

    # 结果卡片选择器
    CARD_SELECTOR = ".panel.panel-default.post"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://jtst.mot.gov.cn/search/std?q=",
            },
        )

    @property
    def site_name(self) -> str:
        return "jtst"

    @property
    def site_label(self) -> str:
        return "交通运输部标准"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询交通标准，返回全部匹配结果列表。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        params: dict[str, Any] = {
            "tid": "",
            "q": keyword,
            "op": "",
        }

        try:
            resp = self._client.get(self.SEARCH_URL, params=params, timeout=15)
        except Exception as e:
            logger.debug(f"jtst.mot.gov.cn 请求失败: {e}")
            return []

        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # 空结果检测
        total_span = soup.select_one(".nums span")
        if total_span:
            total_text = total_span.text.strip()
            if total_text == "0":
                return []

        cards = soup.select(self.CARD_SELECTOR)
        if not cards:
            return []

        results: list[QueryResult] = []
        for card in cards:
            result = self._parse_result(card, keyword)
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
        best = max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")
        return best

    def _parse_result(self, card: Any, search_term: str = "") -> Optional[QueryResult]:
        """从 BeautifulSoup 卡片解析标准信息。"""
        # 1. 标准号（已发布标准有 .en-code，计划直接在 a 文本中）
        en_code = card.select_one(".en-code")
        if en_code:
            std_no = en_code.text.strip()
        else:
            # 计划编号：a 标签直接文本的第一个非空行
            a_tag = card.select_one(".post-head a")
            if a_tag:
                # lxml 可能合并多行为单个 NavigableString，按行分割取第一段
                raw = "".join(c for c in a_tag.children if isinstance(c, str))
                lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
                std_no = lines[0] if lines else a_tag.get_text(" ", strip=True)
            else:
                return None

        if not std_no:
            return None

        # 2. 标准名称：a 标签中去除标准号后的文本
        name = ""
        a_tag = card.select_one(".post-head a")
        if a_tag:
            full_text = a_tag.get_text(" ", strip=True)
            # 去掉开头的标准号部分
            name = full_text[len(std_no) :].strip()

        # 3. 状态
        status_el = card.select_one(".s-status.label")
        status_text = status_el.text.strip() if status_el else ""
        status_map = {"现行": "现行", "即将实施": "即将实施", "废止": "废止", "已废止": "废止", "现行有效": "现行"}
        status = status_map.get(status_text, status_text) if status_text else "未知"

        # 4. 日期（第一个 time 是发布日期，第二个是实施日期）
        time_tags = card.select(".panel-footer time.post-date")
        publish_date = time_tags[0].text.strip() if len(time_tags) > 0 else ""
        implement_date = time_tags[1].text.strip() if len(time_tags) > 1 else ""

        # 5. 匹配状态
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
            implementation_date=implement_date,
            publish_date=publish_date,
            responsible_dept="交通运输部",
            source_site=self.site_name,
        )
        return result
