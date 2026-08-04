# 模块：项目/查询/适配器/脚本
"""
中国工程建设标准化协会标准查询适配器

URL: https://www.ccsn.org.cn/Zbbz/ZbbzList.aspx
技术特征: ASP.NET WebForms
搜索: GET ?KeyWord=关键词（简单 URL 参数，无需 ViewState）
分页: POST __doPostBack（需逐页提取 ViewState）
编码: GBK
"""

import logging
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "工程建设标准化"

logger = logging.getLogger(__name__)


class CCSNAdapter(BaseAdapter):
    """中国工程建设标准化协会标准查询适配器。"""

    BASE_URL = "https://www.ccsn.org.cn"
    SEARCH_URL = "https://www.ccsn.org.cn/Zbbz/ZbbzList.aspx"

    # 0确认的字段列索引:[0]序号[1]标准名称[2]标准编号[3]发布日期[4]实施日期
    COL_STANDARD_NUMBER = 2
    COL_STANDARD_NAME = 1
    COL_PUBLISH_DATE = 3
    COL_IMPLEMENT_DATE = 4

    # 空结果/错误关键词
    NO_RESULT_KEYWORDS = ["没有找到", "暂无数据", "无相关标准"]

    MAX_PAGES = 5  # 安全阀

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
                "Referer": "https://www.ccsn.org.cn/Zbbz/ZbbzList.aspx",
            },
        )

    @property
    def site_name(self) -> str:
        return "ccsn"

    @property
    def site_label(self) -> str:
        return "中国工程建设标准化协会"

    # ──提取──

    def _extract_state_from_html(self, html: str) -> tuple[Optional[str], Optional[str]]:
        """从 HTML 提取 __VIEWSTATE 和 __VIEWSTATEGENERATOR。"""
        soup = BeautifulSoup(html, "lxml")
        vs = soup.find("input", id="__VIEWSTATE")
        vsg = soup.find("input", id="__VIEWSTATEGENERATOR")
        return (
            vs.get("value") if vs else None,
            vsg.get("value") if vsg else None,
        )

    # ── 数据表定位 ──

    def _find_data_rows(self, soup: BeautifulSoup) -> list[Any]:
        """定位数据表格并返回数据行（跳过表头）。

        策略：找所有表格，筛选其中首列是纯数字序号的数据行。
        """
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            # 收集不含的行
            data_rows = [r for r in rows if not r.find("th")]
            # 检查：每行 5 列，且首列是纯数字
            valid_rows = []
            for r in data_rows:
                cols = r.find_all("td")
                if len(cols) == 5:
                    first = cols[0].text.strip()
                    if first.isdigit():
                        valid_rows.append(r)
            if len(valid_rows) >= 3:
                return valid_rows
        return []

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询工程建设标准。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        # 第1页：搜索
        try:
            resp = self._client.get(self.SEARCH_URL, params={"KeyWord": keyword}, timeout=15)
        except Exception as e:
            logger.debug(f"ccsn.org.cn GET 搜索失败: {e}")
            return []

        if resp.status_code != 200:
            return []

        html = resp.text

        # 空结果
        for kw in self.NO_RESULT_KEYWORDS:
            if kw in html:
                return []

        soup = BeautifulSoup(html, "lxml")
        rows = self._find_data_rows(soup)
        if not rows:
            return []

        all_results: list[QueryResult] = []
        for row in rows:
            r = self._parse_result(row, keyword)
            if r:
                all_results.append(r)

        # 分页：逐页获取
        for _ in range(1, self.MAX_PAGES):
            vs, vsg = self._extract_state_from_html(html)
            if not vs:
                break

            data = {
                "__EVENTTARGET": "ID_ucZbbzList$ucPager1$btnNext",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": vs,
                "__VIEWSTATEGENERATOR": vsg or "",
                "ID_ucZbbzList$txtKeyWord": keyword,
            }
            try:
                resp = self._client.post(self.SEARCH_URL, data=data, timeout=15)
            except Exception as e:
                logger.debug(f"ccsn.org.cn 分页 POST 失败: {e}")
                break

            if resp.status_code != 200:
                break

            html = resp.text
            soup = BeautifulSoup(html, "lxml")
            page_rows = self._find_data_rows(soup)
            if not page_rows:
                break

            page_results = []
            for row in page_rows:
                r = self._parse_result(row, keyword)
                if r:
                    page_results.append(r)

            if not page_results:
                break

            all_results.extend(page_results)

            # 检查是否还有下一页（结果数不足一页说明是最后一页）
            if len(page_results) < len(rows):
                break

        return all_results

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

    def _parse_result(self, row: Any, search_term: str = "") -> Optional[QueryResult]:
        """从表格行解析标准信息。"""
        cols = row.find_all("td")
        if len(cols) < 4:
            return None

        std_no = cols[self.COL_STANDARD_NUMBER].text.strip() if len(cols) > self.COL_STANDARD_NUMBER else ""
        name = cols[self.COL_STANDARD_NAME].text.strip() if len(cols) > self.COL_STANDARD_NAME else ""

        if not std_no and not name:
            return None

        pub_date = cols[self.COL_PUBLISH_DATE].text.strip() if len(cols) > self.COL_PUBLISH_DATE else ""
        imp_date = cols[self.COL_IMPLEMENT_DATE].text.strip() if len(cols) > self.COL_IMPLEMENT_DATE else ""

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
            status="未知",
            match_status=match_status,
            implementation_date=imp_date,
            publish_date=pub_date,
            responsible_dept="中国工程建设标准化协会",
            source_site=self.site_name,
        )
        return result
