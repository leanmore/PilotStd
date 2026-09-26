# 模块：项目/查询/适配器/脚本
"""
工标库 (gongbiaoku.com) 适配器

URL: https://www.gongbiaoku.com/search?txt=关键词
数据结构: 多个 <ul class="name-intr">，每个含 4 个 <li>（名称/编号/发布日期/实施日期）
"""

import logging
import re
import time
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from ._shared_ssl import default_ssl_context
from .base import BaseAdapter

DISPLAY_NAME = "工标库"

logger = logging.getLogger(__name__)

# 字段标签匹配正则（兼容全角/半角冒号）
_LABEL_RE = re.compile(r"^(标准名称|标准编号|发布日期|实施日期)[：:\s]*(.+)$")


class GongBiaoKuAdapter(BaseAdapter):
    """工标库查询适配器。"""

    BASE_URL = "https://www.gongbiaoku.com"

    # 默认校验的站点复用进程级共享 SSL context（见 _shared_ssl），避免各自重新加载证书包
    def __init__(self, client: httpx.Client | None = None):
        self._log_window_start = 0.0
        self._log_count = 0
        self._client = client or httpx.Client(
            timeout=15.0,
            verify=default_ssl_context(),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.gongbiaoku.com/",
            },
        )

    @property
    def site_name(self) -> str:
        return "gongbiaoku"

    @property
    def site_label(self) -> str:
        return "工标库"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询标准，返回全部匹配结果列表。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        params: dict[str, Any] = {"txt": keyword}

        try:
            resp = self._client.get(self.get_search_url(), params=params, timeout=15)
        except Exception as e:
            logger.debug(f"gongbiaoku.com 请求失败: {e}")
            return []

        if resp.status_code != 200:
            self._log_non_200(resp)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        uls = soup.select("ul.name-intr")
        if not uls:
            return []

        results: list[QueryResult] = []
        for ul in uls:
            result = self._parse_ul(ul, keyword)
            if result:
                results.append(result)

        return results

    def _log_non_200(self, resp: httpx.Response) -> None:
        """采样记录非 200 响应（每分钟最多 5 条），避免反爬时刷屏。"""
        now = time.monotonic()
        if now - self._log_window_start >= 60.0:
            self._log_window_start = now
            self._log_count = 0
        if self._log_count >= 5:
            return
        self._log_count += 1
        location = resp.headers.get("Location", "")
        try:
            snippet = resp.text[:200]
        except Exception:
            snippet = "(body 解码失败)"
        logger.warning(
            "gongbiaoku 非200响应: status=%d location=%s body=%s",
            resp.status_code,
            location,
            snippet,
        )

    # ── 引擎层 ──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配。"""
        candidates = self.query_standards(search_term)
        if not candidates:
            return None
        for c in candidates:
            if c.standard_number == search_term:
                return c
        return candidates[0]

    def _parse_ul(self, ul: Any, search_term: str = "") -> Optional[QueryResult]:
        """从 <ul class=\"name-intr\"> 的 4 个 <li> 解析标准信息。"""
        values: dict[str, str] = {}
        for li in ul.find_all("li"):
            text = li.get_text(strip=True)
            m = _LABEL_RE.match(text)
            if m:
                values[m.group(1)] = m.group(2).strip()

        std_no = values.get("标准编号", "")
        name = values.get("标准名称", "")
        publish_date = values.get("发布日期", "")
        implement_date = values.get("实施日期", "")

        if not std_no and not name:
            return None

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
            status="现行",  # 页面不提供状态字段
            match_status=match_status,
            implementation_date=implement_date,
            publish_date=publish_date,
            responsible_dept="",
            source_site=self.site_name,
        )
        return result
