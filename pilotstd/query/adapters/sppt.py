# 模块：项目/查询/适配器/脚本
"""
食品安全国家标准数据检索平台适配器

URL: https://sppt.cfsa.net.cn:8086/db
API: GET /db?task=indexSearch&accessData=gj&keyword=关键词
响应: JSON 数组（混合公告 TABLENAME=1 和标准 TABLENAME=2）
SSL: 自签名证书（verify=False）
"""

import logging
from typing import Any, Optional

import httpx
import urllib3

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

DISPLAY_NAME = "食品安全国标"

# 抑制自签名证书警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class SPPTAdapter(BaseAdapter):
    """食品安全国家标准查询适配器。
    仅适用于食品安全国家标准（8086），地方标准请使用 SPPTLocalAdapter。
    """

    SEARCH_URL = "https://sppt.cfsa.net.cn:8086/db"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            verify=False,  # 自签名 SSL 证书
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://sppt.cfsa.net.cn:8086/db",
            },
        )

    @property
    def site_name(self) -> str:
        return "sppt"

    @property
    def site_label(self) -> str:
        return "食品安全国家标准"

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询食品安全国家标准。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        params: dict[str, Any] = {
            "task": "indexSearch",
            "accessData": "gj",  # 国标
            "keyword": keyword,
            "isLength": kwargs.get("isLength", 50),
            "num_tn": kwargs.get("num_tn", 1),
        }

        try:
            resp = self._client.get(self.SEARCH_URL, params=params, timeout=15)
        except Exception as e:
            logger.debug(f"sppt.cfsa.net.cn API 请求失败: {e}")
            return []

        if resp.status_code != 200:
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        # 仅保留标准条目（表=2,非空），过滤公告（表=1）
        results: list[QueryResult] = []
        for row in data:
            result = self._parse_result(row, keyword)
            if result:
                results.append(result)

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
        """从 JSON 行解析标准信息，过滤公告条目。"""
        # 过滤公告（为或表不为2）
        std_no = (row.get("CODE") or "").strip()
        if not std_no:
            return None

        name = (row.get("TITLE") or "").strip()
        pub_date = (row.get("PDATE") or "").strip()
        imp_date = (row.get("SSRQ") or "").strip()

        # 状态：此接口不返回状态字段，默认"现行"
        status = "现行" if pub_date else "未知"

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
            implementation_date=imp_date,
            publish_date=pub_date,
            responsible_dept="国家卫生健康委员会",
            source_site=self.site_name,
        )
        return result
