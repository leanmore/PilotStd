# 模块：项目/查询/适配器/脚本
# 安徽标准化信息服务平台适配器(://...)
# 分隔
# 说明：接口://查询
# 参数:(1=国标/2=行标/3=地标/4=国际/5=团标),(标准号),,
# 免鉴权、免、免令牌——最简单的一类站点
# 字段模糊匹配(%%)，搜索结果需客户端按标准号精确过滤
# 覆盖范围:/行业/地方/国际/团体~230万条

import logging
from typing import Any, Optional

import requests

from ..models import QueryResult
from ..network import CHROME_UA, safe_request
from .base import BaseAdapter

DISPLAY_NAME = "安徽标准"

logger = logging.getLogger(__name__)

# 搜索端点
SEARCH_URL = "https://bzxx.ahbz.org.cn/standard/query"

# 字段映射
_STATUS_MAP = {
    "A": "现行",
    "W": "作废",
}


class AhbzAdapter(BaseAdapter):
    """安徽标准化信息服务平台适配器。
    免费、免鉴权、全国范围标准数据库。
    """

    @property
    def site_name(self) -> str:
        return "ahbz"

    @property
    def site_label(self) -> str:
        return "安徽标准平台"

    # ── 公共查询接口 ──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """BaseAdapter 要求实现的基础搜索。委托 _search_single。"""
        session = requests.Session()
        session.headers["User-Agent"] = CHROME_UA
        return self._search_single(search_term, session)

    def _search_single(self, standard_number: str, session: requests.Session) -> QueryResult:
        """搜索单个标准号，在模糊匹配结果中过滤精确匹配。"""
        # 从标准号提取+
        std_type = self._get_type(standard_number)
        if std_type is None:
            return QueryResult(
                standard_number=standard_number,
                error_message=f"无法识别标准类型: {standard_number}",
                source_site=self.site_name,
            )

        code = self._normalize_code(standard_number)

        # 请求接口—使用全文检索（同网页搜索框），非字段模糊匹配
        # 参数对空格敏感（"接口6852000"→0行），不限格式
        payload = {"type": std_type, "keyWord": code, "size": 20, "page": 1}
        resp = safe_request(session, "POST", SEARCH_URL, self.site_name, timeout=15, json=payload)
        if resp is None:
            return QueryResult(
                standard_number=standard_number,
                error_message="网络请求失败",
                source_site=self.site_name,
            )

        try:
            data = resp.json()
        except ValueError:
            return QueryResult(
                standard_number=standard_number,
                error_message="响应解析失败",
                source_site=self.site_name,
            )

        if data.get("code") != "0":
            return QueryResult(
                standard_number=standard_number,
                error_message=f"API返回错误: {data.get('message', '未知')}",
                source_site=self.site_name,
            )

        rows = data.get("data", {}).get("rows", [])
        if not rows:
            return QueryResult(
                standard_number=standard_number,
                error_message="未找到",
                source_site=self.site_name,
            )

        # 结构化匹配：用解析双方，按(,,,,)比对
        match = self._match_structured(standard_number, rows)

        if not match:
            return QueryResult(
                standard_number=standard_number,
                error_message="未找到精确匹配",
                source_site=self.site_name,
            )

        # 构造，补提闲置字段
        return QueryResult(
            standard_number=match.get("code", standard_number),
            standard_name=match.get("csName") or match.get("egName") or "",
            status=_STATUS_MAP.get(match.get("status", ""), ""),
            replaces=match.get("replaceSd") or "",
            abolition_date=match.get("expiryDate") or "",
            implementation_date=self._normalize_date(match.get("executeDate", "")),
            source_site=self.site_name,
            match_status="exact",
            is_adopted=False,
            is_downloadable=True,
        )

    @staticmethod
    def _match_structured(target_num: str, rows: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """结构化匹配：用 StandardParser 解析双方 code，比对数段+前后缀。"""
        from ...organizer.industry_lookup import build_code_mapping
        from ...scan.parser import StandardParser

        parser = StandardParser(build_code_mapping())
        target = parser.parse(target_num + ".pdf")
        if not target:
            return None

        for row in rows:
            row_code = row.get("code", "")
            candidate = parser.parse(row_code + ".pdf")
            if not candidate:
                continue
            if (
                candidate.logical_code == target.logical_code
                and candidate.number == target.number
                and candidate.year == target.year
                and candidate.num_prefix == target.num_prefix
                and candidate.num_suffix == target.num_suffix
            ):
                return row
        return None

    # ── 类型推断 ──

    _TYPE_MAP = {
        "gb": 1,
        "industry": 2,
        "db": 3,
        "iso_iec": 4,
        "foreign": 4,
        "group": 5,
    }

    @staticmethod
    def _get_type(std_num: str) -> Optional[int]:
        """从标准号推断 ahbz API type 编号。委托 classify_std_code()。"""
        from ...core.std_utils import classify_std_code

        code = std_num.split()[0].upper() if " " in std_num else std_num.split("/")[0].upper()
        # 团体标准无空格格式（如/待定-2020）拆分后只剩""，直接返回类型
        if code == "T" or code.startswith("T/"):
            return AhbzAdapter._TYPE_MAP["group"]
        cat = classify_std_code(code)
        return AhbzAdapter._TYPE_MAP.get(cat)  # enterprise → None

    @staticmethod
    def _normalize_code(std_num: str) -> str:
        """简化标准号用于搜索——取code+序号部分，不去掉T后缀。"""
        return std_num.strip()

    @staticmethod
    def _normalize_date(raw: str) -> str:
        """将执行日期格式化为YYYY-MM-DD。原始格式如'20270401'或'2027-04-01'。"""
        if not raw:
            return ""
        raw = raw.strip()
        if len(raw) == 8:
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw
