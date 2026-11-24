# 模块：项目/查询/适配器/脚本
# API Webstore（apiwebstore.org）查询适配器
# 说明：接口为 `Coveo` Search API（`POST`），需公开 `search token`（见 `TOKEN` 注释，可自动刷新）
# ⚠️ 修改本文件后请在本地运行国内/外网站点端到端测试验证（见 tests/test_e2e_adapters.py，CI 不运行）

import logging
import re
from datetime import datetime
from typing import Any

import requests

from pilotstd.core.status import Status

from ..models import QueryResult
from ..search_strategy import (
    _parse_result_number,
    match_result,
)
from .base import BaseAdapter

DISPLAY_NAME = "API标准"  # i18n-allow: 站点中文显示名（前端展示，与其它适配器同口径）

logger = logging.getLogger(__name__)

# `Coveo` 组织 `ID` 与公开 `search token`：均来自公开前端 `bundle`（`main.<hash>.js`），非用户凭据。
# `token` 轮换后适配器会自动尝试从 `bundle` 重新解析（见 `_refresh_token`）；失败则返回空并打 `warning`。
_ORG_ID = "americanpetroleuminstituteproductionafn6944o"
_API_URL = f"https://platform.cloud.coveo.com/rest/search/v2?organizationId={_ORG_ID}"
_HOMEPAGE = "https://www.apiwebstore.org/"
_JS_BUNDLE_RE = re.compile(r'src="([^"]*main\.[a-z0-9]+\.js)"')
# `Coveo` 公开 `token` 形态为 `UUID`（8-4-4-4-12，可带 ≤4 位字母前缀）；`orgId` 不匹配该形态
_TOKEN_RE = re.compile(
    r"([a-zA-Z]{0,4}[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)

# 已知类型词（与 B-6 解析修复保持同一集合口径）
_API_TYPE_WORDS = ("STD", "SPEC", "RP", "BULL", "TR", "MPMS", "PUBL", "TDB", "Q")

# `productcode` 形态：`610` / `6D` / `Q1` / `2A-WSD` / `579-1`（不含空格，纯代号）
_PRODUCT_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*$")

# Coveo status → 项目状态口径
_STATUS_MAP = {
    "Current": Status.ACTIVE.value,
    "Reaffirmed": Status.ACTIVE.value,
    "Revised": Status.ACTIVE.value,
    "Replaced": Status.SUPERSEDED.value,
    "Withdrawn": Status.WITHDRAWN.value,
}


class ApiWebstoreAdapter(BaseAdapter):
    """API Webstore 查询适配器（美国石油学会标准在线商店）。

    真实接口：Coveo Search `POST {_API_URL}`，body 为 JSON。
    - 精确检索：`aq='@productcode=="<code>" @producttype=="Standard"'`
      （实测 610/6D/5CT/579-1/2A-WSD/938-C/Q1 各 1 条）；
    - 兜底检索：`q=<原始查询>` + `@producttype=="Standard"` 过滤（去掉培训/数据表条目，1110 → 897）。

    已知限制：
    - **token 是门槛**：无 token/错 token 均 401（`NoAuthenticationException` / `InvalidTokenException`）；
    - `publisheddate` 为 `MM/DD/YYYY`，需转 ISO；无实施/废止日期、无代替关系；
    - 索引只保留每个 productcode 的最新版（历史版查询会回落为 newer）。
    """

    BASE_URL = _HOMEPAGE
    API_URL = _API_URL
    TOKEN = "xx4ad653a7-23e9-4d24-9a39-b6a0742d799d"

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Referer": self.BASE_URL,
            }
        )
        self._token = self.TOKEN

    @property
    def site_name(self) -> str:
        return "api_webstore"

    @property
    def site_label(self) -> str:
        return "API标准平台"  # i18n-allow: 站点中文标签（与 DISPLAY_NAME 同口径）

    # ── 查询构造 ──────────────────────────────────────────

    @staticmethod
    def _extract_productcode(search_term: str) -> str:
        """从标准号/查询串中提取 productcode（如 `API STD 610-2026` → `610`）。

        覆盖实测形态：`610`、`6D`、`5CT`、`Q1`、`579-1`、`2A-WSD`、`938-C`；
        联合标准 `API 579-1/ASME FFS-1` 取 `/` 前部分。
        """
        text = (search_term or "").strip().upper()
        if not text:
            return ""
        text = re.sub(r"^(API|AMERICAN\s+PETROLEUM\s+INSTITUTE)\s+", "", text)
        for word in sorted(_API_TYPE_WORDS, key=len, reverse=True):
            if text.startswith(word + " "):
                text = text[len(word) + 1 :]
                break
        # 去掉 / 之后的联合标准部分，再去掉末尾年份
        text = text.split("/")[0].strip()
        text = re.sub(r"[-–]\s*(19|20)\d{2}\s*$", "", text)
        candidate = text.strip(" :-–")
        # 自由文本（如 `centrifugal pumps`）不是 `productcode`，交由调用方走全文检索
        return candidate if _PRODUCT_CODE_RE.match(candidate) else ""

    def _build_body(self, search_term: str, start: int, count: int) -> dict[str, Any]:
        """构造 Coveo 查询体：优先 productcode 精确过滤，提取不到时回退全文查询。"""
        body: dict[str, Any] = {
            "pipeline": "API Webstore",
            "searchHub": "Webstore",
            "tab": "default",
            "locale": "en-US",
            "numberOfResults": count,
            "firstResult": start,
            "fieldsToInclude": [
                "productcode",
                "edition",
                "status",
                "producttype",
                "publisheddate",
                "type",
                "title",
                "permanentid",
                "committee",
            ],
        }
        code = self._extract_productcode(search_term)
        if code:
            body["q"] = ""
            body["aq"] = f'@productcode=="{code}" @producttype=="Standard"'
        else:
            body["q"] = search_term
            body["aq"] = '@producttype=="Standard"'
        return body

    # ── 网络 ──────────────────────────────────────────────

    def _post(self, body: dict[str, Any]) -> dict[str, Any] | None:
        """带 token 的 POST；401 时尝试刷新 token 后重试一次。返回 JSON 或 None。"""
        from ..network import safe_post

        resp = safe_post(
            self._session,
            self.API_URL,
            self.site_name,
            json=body,
            timeout=20,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if resp is not None and resp.status_code == 401 and self._refresh_token():
            resp = safe_post(
                self._session,
                self.API_URL,
                self.site_name,
                json=body,
                timeout=20,
                headers={"Authorization": f"Bearer {self._token}"},
            )
        if resp is None or resp.status_code != 200:
            if resp is not None:
                # i18n-allow: 内部运维日志
                logger.warning("api_webstore 返回 HTTP %s（token 可能已轮换）", resp.status_code)
            return None
        try:
            data = resp.json()
        except ValueError:
            # i18n-allow: 内部运维日志
            logger.warning("api_webstore 响应 JSON 解析失败（站点可能改版）", exc_info=True)
            return None
        return data if isinstance(data, dict) else None

    def _refresh_token(self) -> bool:
        """从公开前端 bundle 重新解析 Coveo search token（token 轮换后自愈）。"""
        try:
            page = self._session.get(self.BASE_URL, timeout=20)
            m = _JS_BUNDLE_RE.search(page.text or "")
            if not m:
                return False
            bundle_url = m.group(1)
            if bundle_url.startswith("/"):
                bundle_url = self.BASE_URL.rstrip("/") + bundle_url
            bundle = self._session.get(bundle_url, timeout=30)
            found = _TOKEN_RE.search(bundle.text or "")
            if not found:
                return False
            new_token = found.group(1)
            if new_token != self._token:
                # i18n-allow: 内部运维日志
                logger.info("api_webstore 已刷新 Coveo token")
                self._token = new_token
                return True
            return False
        except Exception:
            # i18n-allow: 内部运维日志
            logger.warning("api_webstore token 刷新失败（沿用旧 token）", exc_info=True)
            return False

    # ── 解析 ──────────────────────────────────────────────

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """检索并解析候选列表（`aq` 精确过滤优先，提不出代号则回退全文查询）。"""
        payload = self._post(self._build_body(search_term, 0, 10))
        if not payload:
            return []
        results = payload.get("results") or []
        if not results:
            return []
        return [self._parse_result(res, search_term) for res in results]

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """返回候选列表（与其它适配器同一约定）。"""
        return self._search_candidates(standard_number)

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        raw_value = rec.get("raw")
        raw: dict[str, Any] = raw_value if isinstance(raw_value, dict) else rec
        title = str(raw.get("title") or rec.get("title") or "")
        code = str(raw.get("productcode") or "")
        type_word = str(raw.get("type") or "").upper()

        publish_date = _iso_date(str(raw.get("publisheddate") or ""))
        year = publish_date[:4] if publish_date else ""
        standard_number = f"API {type_word} {code}-{year}".strip() if code else title.split(":")[0].strip()

        # 名称：`title` 形如 `API STD 610: Centrifugal Pumps ...`
        name = title.split(": ", 1)[1].strip() if ": " in title else title

        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            name,
            standard_number,
        )

        return QueryResult(
            standard_number=standard_number,
            standard_name=name,
            status=_STATUS_MAP.get(str(raw.get("status") or ""), Status.UNKNOWN.value),
            match_status=match_status,
            publish_date=publish_date,
            responsible_dept=str(raw.get("committee") or ""),
            source_site=self.site_name,
            hcno=str(raw.get("permanentid") or ""),
            # `API` 标准不通过 `openstd` 下载链（站点为付费商店）
            is_downloadable=False,
        )


def _iso_date(text: str) -> str:
    """把 Coveo 的 `MM/DD/YYYY` 转 ISO；无法解析时原样返回（空串保持空）。"""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        parsed = (
            datetime.strptime(text, "%m/%d/%Y")
            if "/" in text
            else datetime.strptime(text, "%Y-%m-%d")
        )
    except ValueError:
        # 非日期形态：原样返回（调用方展示原始字符串，不算吞错）
        # i18n-allow: 内部运维日志
        logger.info("api_webstore 日期字段无法解析，原样保留: %s", text)
        return text
    return parsed.strftime("%Y-%m-%d")
