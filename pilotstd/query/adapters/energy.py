# 模块：项目/查询/适配器/脚本
"""
能源标准查询适配器

URL: https://114.251.111.103:18080/zxd/portal/std
AJAX: https://114.251.111.103:18080/zxd/portal/stdPage
⚠️ 纯 IP 站点，迁移风险高：IP 变更后需手动更新 BASE_URL 和 site_config
架构类型: json_api_get（Bootstrap Table AJAX JSON 加载）
"""

import logging
import re
from typing import Any

import httpx

from ..models import QueryResult
from ..search_strategy import _parse_result_number, map_status, match_result
from .base import BaseAdapter

DISPLAY_NAME = "能源标准平台"

logger = logging.getLogger(__name__)


class EnergyAdapter(BaseAdapter):
    """能源标准查询适配器。"""

    BASE_URL = "https://114.251.111.103:18080"
    API_URL = "https://114.251.111.103:18080/zxd/portal/stdPage"

    # 纯站点：显式声明+自签名证书跳过
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            verify=False,
            headers={
                "Host": "114.251.111.103:18080",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://114.251.111.103:18080/zxd/portal/std",
            },
        )

    @property
    def site_name(self) -> str:
        return "energy"

    @property
    def site_label(self) -> str:
        return "能源标准信息服务平台"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询标准，返回全部匹配结果列表。"""
        return self._search_candidates(standard_number)

    # ── 引擎层 ──

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """搜索候选项。含年份无结果时自动去年份宽搜。"""
        keyword = search_term.strip() if search_term else ""
        if not keyword:
            return []
        candidates = self._fetch_candidates(keyword)
        if candidates:
            return candidates
        # 年份回退：去除末尾-重新搜索
        m = re.search(r"-(\d{4})$", keyword)
        if m:
            no_year = keyword[: m.start()]
            logger.debug("energy 无结果，去年份宽搜: %s -> %s", keyword, no_year)
            candidates = self._fetch_candidates(no_year)
        return candidates

    def _fetch_candidates(self, keyword: str) -> list[QueryResult]:
        """GET AJAX 端点获取搜索结果，支持翻页循环。"""

        # ✅#462:翻页循环+备用域名列表
        FALLBACK_URLS = [
            "http://114.251.111.103:18080",  # IP 不变（HTTP 降级）
            "https://energy.nbse.org.cn:18080",  # 可能的域名（待验证）
        ]
        MAX_PAGES = 5  # 最大翻页数，防止无限循环
        PAGE_SIZE = 15

        all_rows: list[dict[str, Any]] = []
        total_seen: int | None = None
        limit = PAGE_SIZE

        for page in range(MAX_PAGES):
            offset = page * PAGE_SIZE
            params: dict[str, Any] = {"keyword": keyword, "tid": "0", "op": "", "limit": limit, "offset": offset}

            # ✅任务6：首页使用回退链接，翻页仅用主链接
            if page == 0:
                urls_to_try = [self.API_URL] + FALLBACK_URLS
            else:
                urls_to_try = [self.API_URL]

            resp = None
            for url in urls_to_try:
                try:
                    resp = self._client.get(url, params=params, timeout=15)
                    if resp.status_code == 200:
                        break
                except Exception:
                    continue

            if resp is None or resp.status_code != 200:
                if page == 0:
                    logger.debug("能源标准平台请求失败（含 fallback）: keyword=%r", keyword)
                else:
                    # ✅ 任务6：翻页失败返回已有数据，不静默丢弃
                    if all_rows:
                        logger.warning("energy 第%d页请求失败，返回已获取的%d条", page + 1, len(all_rows))
                    else:
                        logger.debug("energy 第%d页请求失败: keyword=%r", page + 1, keyword)
                break

            try:
                payload = resp.json()
            except ValueError:
                break

            rows = payload.get("rows", [])
            if not rows:
                break

            all_rows.extend(rows)

            # 首页确定
            if total_seen is None:
                total_seen = payload.get("total", 0)
                if total_seen <= PAGE_SIZE:
                    break  # 只有一页

            # 已拉取足够记录或已到最后一页
            if len(all_rows) >= total_seen or len(rows) < PAGE_SIZE:
                break

        if not all_rows:
            return []

        # 翻页后仍不完整的告警
        if total_seen and len(all_rows) < total_seen:
            logger.warning(
                "energy 搜索结果 %d 条超出最大翻页数 %d 页（已获取 %d/%d）",
                total_seen,
                MAX_PAGES,
                len(all_rows),
                total_seen,
            )

        return [self._parse_result(rec, keyword) for rec in all_rows]

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """将 JSON 记录映射为 QueryResult。"""
        std_no = rec.get("stdCode", "")
        name = rec.get("stdName", "")
        raw_status = rec.get("state", "")
        issue_date = rec.get("issueDate", "")
        act_date = rec.get("actDate", "")
        replaced = rec.get("replacedStd", "") or ""
        std_id = rec.get("stdId", "")

        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            name,
            std_no,
        )

        return QueryResult(
            standard_number=std_no,
            standard_name=name,
            status=map_status(raw_status),
            match_status=match_status,
            implementation_date=act_date,
            publish_date=issue_date,
            replaces=replaced,
            responsible_dept="",
            source_site=self.site_name,
            hcno=str(std_id) if std_id else "",
        )
