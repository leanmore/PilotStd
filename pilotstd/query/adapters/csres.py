# 模块：项目/查询/适配器/脚本
# 工标网查询适配器（.）
# 逐页逐行搜索，标准编号精确比对后才返回

import logging
import re
import threading
import time as _time
from typing import Any, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from ..models import QueryResult
from ..network import safe_get
from ..search_strategy import is_adopted, map_status
from .base import BaseAdapter

DISPLAY_NAME = "工标网"

logger = logging.getLogger(__name__)

# 冷却时长（秒）：被工标网拒绝访问后强制冷却 24 小时
COOLDOWN_ON_REJECT = 86_400


class CsresAdapter(BaseAdapter):
    """工标网（csres.com）标准查询适配器。

    注意：工标网仅支持 HTTP（80端口），HTTPS被拒绝。
    未注册用户限制访问200页，超限后需等待或注册。
    """

    supports_replaces_detail = True

    _http_warned = False  # HTTP 明文风险只提示一次
    # 本地冷却标记（秒级时间戳）——多线程竞态下___冷却和
    # ___之间存在时间窗口，用锁保护。
    _local_cooldown_until: float = 0.0
    _cool_lock = threading.Lock()

    def __init__(self, session: requests.Session | None = None):
        """初始化工标网适配器，注入 requests session 并设置请求头。"""
        self._session = session or requests.Session()
        if not CsresAdapter._http_warned:
            logger.info("csres.com 不支持 HTTPS，查询内容可能被网络中间人窃听")
            CsresAdapter._http_warned = True
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )
        self._rotator = None

    def set_rotator(self, rotator: Any) -> None:
        """注入站点轮转器实例，用于冷却时联动通知 rotator。"""
        self._rotator = rotator

    def _is_locally_cooled(self) -> bool:
        """检查本地冷却标记（类级别，跨实例生效）。"""
        with CsresAdapter._cool_lock:
            return _time.time() < CsresAdapter._local_cooldown_until

    @classmethod
    def _set_local_cooldown(cls, seconds: int = 86_400) -> None:
        """设置本地冷却标记（类级别，跨实例立即生效，线程安全）。"""
        with cls._cool_lock:
            if _time.time() >= cls._local_cooldown_until:
                cls._local_cooldown_until = _time.time() + seconds

    @property
    def site_name(self) -> str:
        return "csres"

    @property
    def site_label(self) -> str:
        return "工标网"

    # ──覆盖：多页搜索+详情页─────────────────────

    def _search_candidates(self, search_term: str) -> list[Any]:
        """工标网翻页搜索，返回多页所有候选结果。"""
        return self._search_multi_page(search_term, max_pages=3)

    def _post_process_result(self, result: QueryResult) -> None:
        """从详情页提取替代关系。"""
        detail_url = getattr(result, "_csres_detail_url", "")
        if detail_url:
            result.replaces = self._fetch_detail_replaces(detail_url)

    def _search_multi_page(self, search_term: str, max_pages: int = 3) -> list[Any]:
        """用搜索词查询工标网，翻 max_pages 页，返回所有有效候选结果列表。"""
        # 本地冷却检查：多线程竞态下第一时间拦截
        if self._is_locally_cooled():
            return []
        base_url = self.get_search_url().format(quote(search_term))
        total_pages = 1
        candidates = []

        for page in range(1, max_pages + 1):
            url = f"{base_url}&page={page}" if page > 1 else base_url
            resp = safe_get(self._session, url, self.site_name, timeout=15)
            if resp is None:
                break
            # 响应返回后二次检查：其他线程可能已在请求期间触发冷却
            if self._is_locally_cooled():
                break
            resp.encoding = "gbk"

            # 检测被拒：302→//.或页面内容为错误页
            if resp.status_code != 200 or "noright" in resp.url or "noright" in resp.text[:200].lower():
                logger.warning("工标网拒绝访问，自动冷却站点(24h)")
                self._set_local_cooldown(COOLDOWN_ON_REJECT)
                if self._rotator:
                    self._rotator.force_cooldown(self.site_name, COOLDOWN_ON_REJECT)
                break

            if resp.status_code != 200:
                break

            html = resp.text
            if page == 1:
                total_pages = self._parse_total_pages(html)
                if total_pages == 0:
                    break

            page_candidates = self._find_all_matches_in_page(html)
            candidates.extend(page_candidates)

            if page >= total_pages or page >= max_pages:
                break

        if not candidates:
            logger.debug(f"搜索词 '{search_term}' 未找到匹配")
        return candidates

    # ──网页解析────────────────────────────────────────────

    @staticmethod
    def _parse_total_pages(html: str) -> int:
        """从工标网搜索结果页 HTML 中解析总页数，0 表示无结果或解析失败。"""
        m = re.search(r"共找到(\d+)条", html)
        if not m or int(m.group(1)) == 0:
            return 0
        m = re.search(r"共(\d+)页", html)
        return int(m.group(1)) if m else 1

    _DETAIL_BASE = "http://www.csres.com"

    def _find_all_matches_in_page(self, html: str) -> list[Any]:
        """在单页 HTML 中解析所有有效标准编号行，返回 QueryResult 列表。"""
        soup = BeautifulSoup(html, "lxml")

        result_table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if rows and "标准编号" in rows[0].get_text(strip=True):
                result_table = t
                break
        if result_table is None and len(soup.find_all("table")) >= 7:
            result_table = soup.find_all("table")[6]
        if result_table is None:
            return []

        candidates = []
        for row in result_table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            found_number = cells[0].get_text(strip=True)
            if not re.match(r"[A-Z]+", found_number):
                continue
            # 提取详情页
            detail_url = ""
            a_tag = cells[0].find("a")
            if a_tag:
                href: str = a_tag.get("href", "") or ""  # type: ignore[assignment]  # BeautifulSoup get 返回值类型不精确
                if href.startswith("/detail/"):
                    detail_url = self._DETAIL_BASE + href
            candidates.append(self._parse_result(found_number, cells, detail_url))
        return candidates

    def _parse_result(self, found_number: str, cells: Any, detail_url: str = "") -> QueryResult:
        """从表格行构建 QueryResult。"""
        std_name = cells[1].get_text(strip=True)
        dept = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        impl_date = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        status_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""

        result = QueryResult(
            standard_number=found_number,
            standard_name=std_name,
            status=map_status(status_text),
            implementation_date=impl_date,
            publish_date="网站无此分类",
            responsible_dept=dept or "网站无此分类",
            is_adopted=is_adopted(std_name),
            is_downloadable=not is_adopted(std_name),
            source_site=self.site_name,
        )
        # 暂存详情页链接，由查询__择机提取
        result._csres_detail_url = detail_url  # type: ignore[attr-defined]
        return result

    def _fetch_detail_replaces(self, detail_url: str) -> str:
        """从工标网详情页提取替代标准号。\"替代情况\"字段中\"被X代替\"。"""
        if not detail_url:
            return ""
        try:
            resp = safe_get(self._session, detail_url, self.site_name, timeout=10)
            if resp is None or resp.status_code != 200:
                return ""
            resp.encoding = "gbk"
            # 匹配\"被/713.2-2023代替\"
            m = re.search(
                r"被\s*([A-Z]+(?:/[A-Z]+)?\s*\d+(?:\.\d+)?\s*[—\-:]\s*\d{4})\s*代替",
                resp.text,
            )
            if m:
                return m.group(1).strip()
        except Exception:
            logger.debug("csres 替代标准解析失败", exc_info=True)
        return ""

    def fetch_replaces_detail(self, result: Any) -> str:
        """classifier 调用的统一接口：从 csres 详情页提取替代关系。"""
        detail_url = getattr(result, "_csres_detail_url", "")
        if detail_url and hasattr(self, "_fetch_detail_replaces"):
            return self._fetch_detail_replaces(detail_url) or ""
        return ""

    # ── 基础接口（供其他模块调用）────────────────────────────

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """简化版搜索（不比对标准编号），供 query_single / query_batch 使用。"""
        if self._is_locally_cooled():
            return QueryResult(
                standard_number=search_term,
                error_message="站点冷却中",
                source_site=self.site_name,
            )
        base_url = self.get_search_url().format(quote(search_term))
        resp = safe_get(self._session, base_url, self.site_name, timeout=15)
        if resp is None:
            return QueryResult(
                standard_number=search_term,
                error_message="网络错误",
                source_site=self.site_name,
            )
        # 响应返回后二次检查：其他线程可能已在请求期间触发冷却
        if self._is_locally_cooled():
            return QueryResult(
                standard_number=search_term,
                error_message="站点冷却中",
                source_site=self.site_name,
            )
        resp.encoding = "gbk"
        if resp.status_code != 200 or "noright" in resp.url:
            self._set_local_cooldown(COOLDOWN_ON_REJECT)
            if self._rotator:
                self._rotator.force_cooldown(self.site_name, COOLDOWN_ON_REJECT)
            return QueryResult(
                standard_number=search_term,
                error_message="工标网拒绝访问",
                source_site=self.site_name,
            )
        # 返回第一个格式有效的标准号行
        html = resp.text
        soup = BeautifulSoup(html, "lxml")
        result_table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if rows and "标准编号" in rows[0].get_text(strip=True):
                result_table = t
                break
        if result_table is None and len(soup.find_all("table")) >= 7:
            result_table = soup.find_all("table")[6]
        if result_table is None:
            return None
        for row in result_table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            found = cells[0].get_text(strip=True)
            if not re.match(r"[A-Z]+", found):
                continue
            return self._parse_result(found, cells)
        return None
