# 模块：项目/查询/适配器/365脚本
# 南京标准公共服务平台查询适配器（365.新站，2026-05-25上线）
# 会话管理/签名/请求重试已提取至_365_脚本

import logging
import re
from typing import Any, Optional

import requests

from ..models import QueryResult
from ..network import safe_get
from ..search_strategy import match_result
from ._njbz365_session_manager import Njz365SessionManager
from .base import BaseAdapter

DISPLAY_NAME = "南京标准网"

logger = logging.getLogger(__name__)


class Njbz365Adapter(BaseAdapter):
    """南京标准公共服务平台查询适配器。

    会话管理由 Njz365SessionManager 提供；本类负责搜索/匹配/替代标准提取。
    """

    supports_replaces_detail = True

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )
        self._session_mgr = Njz365SessionManager(self._session)

    @property
    def site_name(self) -> str:
        return "njbz365"

    @property
    def site_label(self) -> str:
        return "南京标准公共服务平台"

    # 详情页链接模板
    DETAIL_URL = "https://www.njbz365.cn/details/{}"

    def _search(
        self,
        search_term: str,
        target_code: str = "",
        target_number: int = 0,
        target_year: int = 0,
    ) -> Optional[QueryResult]:
        """单结果兼容接口。target 为空时从 search_term 自动解析。"""
        if not target_code:
            parsed = _parse_result_number(search_term)
            target_code = parsed.get("code", "")
            target_number = parsed.get("number", 0)
            target_year = parsed.get("year", 0)
        candidates = self._search_candidates(search_term, target_code, target_number, target_year)
        return candidates[0] if candidates else None

    def _search_candidates(
        self,
        search_term: str,
        target_code: str = "",
        target_number: int = 0,
        target_year: int = 0,
    ) -> list[QueryResult]:
        """返回 API 全部候选结果（最多 limit 条），供 base 层统一打分。"""
        data = self._do_request(search_term)
        if data is None:
            return []

        # 从_自动解析标准编号字段
        items = data.get("data", {}).get("datalist", [])
        if not items:
            return []

        parsed_target = _parse_result_number(search_term)
        match_code = parsed_target.get("code", "") or target_code
        match_number = parsed_target.get("number", 0) or target_number
        match_year = parsed_target.get("year", 0) or target_year

        status_map = {"现行": "现行", "未生效": "即将实施", "废止": "废止"}
        results = []
        for item in items:
            bzbh = item.get("bzbh", "")
            bzmc = item.get("bzmc", "")
            bzzt = item.get("bzzt", "")
            bzid = item.get("bzid", "")
            cybz = item.get("cybz", "")
            is_adopted = bool(cybz)
            status = status_map.get(bzzt, bzzt)

            matched, match_status = match_result(match_code, match_number, match_year, bzmc, bzbh)

            results.append(
                QueryResult(
                    standard_number=bzbh,
                    standard_name=bzmc,
                    status=status,
                    match_status=match_status,
                    source_site=self.site_name,
                    hcno=bzid,
                    is_adopted=is_adopted,
                    is_downloadable=not is_adopted,
                    publish_date=item.get("fbrq", ""),
                    implementation_date=item.get("ssrq", ""),
                )
            )
        return results

    def _fetch_replaces(self, bzid: str, bzbh: str) -> str:
        """从详情页获取替代标准号。"""
        if not bzid:
            return ""
        try:
            url = self.DETAIL_URL.format(bzid)
            resp = safe_get(
                self._session,
                url,
                self.site_name,
                params={"bzbh": bzbh, "bzid": bzid},
                timeout=10,
            )
            if resp is None or resp.status_code != 200:
                return ""
            m = re.search(
                r"被如下标准代替：\s*([A-Z]+(?:/[A-Z]+)?\s*\d+(?:\.\d+)?\s*[—\-:]\s*\d{4})",
                resp.text,
            )
            if m:
                return m.group(1).strip()
        except Exception:
            logger.debug("njbz365 替代标准解析失败", exc_info=True)
        return ""

    def _post_process_result(self, result: QueryResult) -> None:
        """结果后处理：从详情页提取替代标准号。"""
        if result.hcno:
            result.replaces = self._fetch_replaces(result.hcno, result.standard_number)

    def fetch_replaces_detail(self, result: Any) -> str:
        """classifier 调用的统一接口：从查询结果提取替代关系。"""
        if hasattr(self, "_fetch_replaces") and result.hcno:
            return self._fetch_replaces(result.hcno, result.standard_number) or ""
        return ""

    # 会话管理代理（委托365，供外部测试访问）

    def _do_request(self, search_term: str):
        return self._session_mgr._do_request(search_term)

    def _refresh_csrf(self) -> None:
        self._session_mgr._refresh_csrf()


def _parse_result_number(standard_number: str) -> dict[str, Any]:
    """从标准编号字符串解析代号、顺序号、年份、部分号。委托公用解析器。"""
    from ...core.std_utils import parse_std_number

    r = parse_std_number(standard_number)
    return r if r else {"code": "", "number": 0, "part": None, "year": 0}
