# 模块：项目/查询/适配器/脚本
# 行业标准信息服务平台（...）查询适配器
# 替代对非国标（行业标准）的查询
# ⚠️ 修改本文件后请在本地运行国内站点端到端测试验证（见 tests/test_e2e_adapters.py，CI 不运行）

import logging
import re
from datetime import datetime
from typing import Any, Optional

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

DISPLAY_NAME = "行业标准平台"

logger = logging.getLogger(__name__)


class HbbaAdapter(BaseAdapter):
    """行业标准信息服务平台查询适配器。

    API: POST https://hbba.sacinfo.org.cn/stdQueryList
    可用请求参数: {current, size, key}
    key 为全文检索关键词（支持标准号含年份子串匹配，如 "SH/T 1752-2006"）。

    已知限制：
    - ❌ 不支持 year / stdYear / pubYear / issueDate / publishDate 独立过滤参数
    - ❌ status="" 参数无效（不同于同域 dbba API）
    - 年份过滤仅通过 key 中的年份子串实现（全字匹配，非范围过滤）
    - 不含年份的 key 会返回所有版本（如 "SH/T 1752" 返回 2006+2026）

    回退策略：
    - 首次搜索用完整标准号含年份 → 无结果时自动去年份重试（query_with_strategy 第4步）
    - 宽搜结果通过 match_result 比对区分 exact/newer/older
    """

    supports_replaces_detail = True

    API_URL = "https://hbba.sacinfo.org.cn/stdQueryList"
    DETAIL_URL = "https://hbba.sacinfo.org.cn/stdDetail/{}"

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
                "Origin": "https://hbba.sacinfo.org.cn",
            }
        )

    @property
    def site_name(self) -> str:
        return "hbba"

    @property
    def site_label(self) -> str:
        return "行业标准平台"

    def _search_candidates(self, search_term: str) -> list[Any]:
        """搜索候选项。含年份无结果时自动去年份宽搜。"""
        candidates = self._post_search_candidates(search_term)
        if candidates:
            return candidates
        # 年份回退：去除末尾-重新搜索
        m = re.search(r"-(\d{4})$", search_term)
        if m:
            no_year = search_term[: m.start()]
            logger.debug("hbba 无结果，去年份宽搜: %s -> %s", search_term, no_year)
            candidates = self._post_search_candidates(no_year)
        return candidates

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配。多候选时按年份接近度选取，而非简单取最新。"""
        candidates = self._search_candidates(search_term)
        if not candidates:
            return None
        # 精确匹配：_与_完全一致
        for c in candidates:
            if c.standard_number == search_term:
                self._post_process_result(c)
                return c  # type: ignore[no-any-return]  # 搜索结果列表元素无精确类型
        # 年份接近度优选：取与搜索词中年份最接近的候选
        target = _parse_result_number(search_term)
        target_year = target.get("year", 0)
        if target_year and len(candidates) > 1:

            def _year_dist(candidate: QueryResult) -> int:
                parsed = _parse_result_number(candidate.standard_number)
                y = parsed.get("year", 0)
                return abs(y - target_year) if y else 9999

            best = min(candidates, key=_year_dist)
            logger.debug(
                "hbba 多候选按年距选取: target_year=%d candidates=%d best=%s",
                target_year,
                len(candidates),
                best.standard_number,
            )
        else:
            best = max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")
        self._post_process_result(best)
        return best  # type: ignore[no-any-return]  # 搜索结果列表元素无精确类型

    def _post_process_result(self, result: QueryResult) -> None:
        """结果后处理：从详情页提取替代标准号。"""
        if result.hcno:
            result.replaces = self._fetch_detail_replaces(result.hcno) or ""

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        code = rec.get("code", "")
        ch_name = rec.get("chName", "")
        raw_status = rec.get("status", "")
        pk = rec.get("pk", "")

        issue_date = ts_to_date(rec.get("issueDate"))
        act_date = ts_to_date(rec.get("actDate"))

        # 状态修正：前端脚本会将在未来者显示为"即将实施"
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

    # 详情页链接模板
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
            # 匹配\"代替标准\\/1752—2006\"
            m = re.search(
                r"代替标准\s*\n\s*([A-Z]+(?:/[A-Z]+)?\s*\d+(?:\.\d+)?\s*[—\-]\s*\d{4})",
                resp.text,
            )
            if m:
                return m.group(1).strip()
        except Exception:
            logger.debug("hbba 替代标准解析失败", exc_info=True)
        return ""
