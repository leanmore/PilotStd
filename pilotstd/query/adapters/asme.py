# 模块：项目/查询/适配器/脚本
# ASME（asme.org）标准查询适配器
# 说明：接口为公开商品目录 `JSON`（`GET` `/api/products`），无需登录/付费/验证码
# ⚠️ 修改本文件后请在本地运行站点端到端测试验证（见 tests/test_e2e_adapters.py，CI 不运行）

import logging
import re
from typing import Any

import requests

from pilotstd.core.status import Status

from ..models import QueryResult
from ..search_strategy import (
    _parse_result_number,
    match_result,
)
from .base import BaseAdapter

DISPLAY_NAME = "ASME标准"  # i18n-allow: 站点中文显示名（前端展示，与其它适配器同口径）

logger = logging.getLogger(__name__)

# 商品目录接口：按 `designator` 精确过滤（实测 `B16.5`/`B31.3`/`BPVC.VIII.1`/`PTC 4`/`Y14.5` 均 `total=1`）
_API_URL = "https://www.asme.org/api/products"
_ROMAN_RE = re.compile(r"^[IVX]+$")
# 末尾年份：`-2025` / `—2025`
_YEAR_SUFFIX_RE = re.compile(r"\s*[-–—]\s*(19|20)\d{2}\s*$")
# BPVC 点号写法：`BPVC.IX` / `BPVC.VIII.1` / `BPVC.II.D.M`
_BPVC_DOT_RE = re.compile(r"^BPVC\.([IVX]+)((?:\.[A-Z0-9]+)*)$")
# BPVC 文字写法（整串锚定，避免把 `BPVC.IX` 里的 `V` 误当罗马数字）：
#   `Section VIII Div.1` / `Section II Part D` / `BPVC VIII-1`
_BPVC_TEXT_RE = re.compile(
    r"^(?:BPVC\s+)?(?:Section\s+)?([IVX]+)"
    r"(?:\s*(?:Div(?:ision)?\.?|Part)\s*([A-Z0-9]+)|\s*[-–]\s*([A-Z0-9]+))?$",
    re.IGNORECASE,
)


class AsmeAdapter(BaseAdapter):
    """ASME 标准查询适配器。

    接口：`GET https://www.asme.org/api/products?type=Codes-Standards&fullDesignator=<designator>`
    返回 `results[]`（含 `Title`/`FullDesignator`/`DesignatorYear`/`ProductCode`/`ProductURL`）。

    已知限制：
    - **无 status 字段**：状态按「请求年份 vs 返回 DesignatorYear」推断——
      同版→现行；请求更旧版（API 只索引最新版）→被代替；无年份→现行；
    - `PublishDate` 恒为 `0001-01-01`（不可用），`publish_date` 用 `DesignatorYear`；
    - 无实施/废止日期、无代替关系字段；
    - designator 需归一化：`Section VIII Div.1` → `BPVC.VIII.1`（见 `_normalize_designator`）。
    """

    BASE_URL = "https://www.asme.org"
    API_URL = _API_URL

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Referer": self.BASE_URL + "/codes-standards",
            }
        )

    @property
    def site_name(self) -> str:
        return "asme"

    @property
    def site_label(self) -> str:
        return "ASME标准平台"  # i18n-allow: 站点中文标签（与 DISPLAY_NAME 同口径）

    # ── `designator` 归一化 ──────────────────────────────

    @staticmethod
    def _normalize_designator(search_term: str) -> str:
        """把标准号归一化为 ASME 商品目录的 `fullDesignator`。

        覆盖（实测可命中的形态）：
        - `ASME B16.5-2025` → `B16.5`
        - `ASME BPVC.VIII.1-2025` → `BPVC.VIII.1`
        - `ASME BPVC Section VIII Div.1-2021` → `BPVC.VIII.1`
        - `ASME BPVC Section II Part D` → `BPVC.II.D`
        - `ASME PTC 4-2013` → `PTC 4`
        - `ASME Y14.5-2018` → `Y14.5`
        """
        text = (search_term or "").strip()
        if not text:
            return ""
        text = re.sub(r"^ASME\s*", "", text, flags=re.IGNORECASE)
        text = _YEAR_SUFFIX_RE.sub("", text).strip()
        upper = text.upper()

        # 1) 已是点号写法：BPVC.VIII.1 / BPVC.II.D.M
        if _BPVC_DOT_RE.match(upper):
            return upper

        # 2) 文字写法：Section VIII Div.1 / Section II Part D / BPVC VIII-1
        if "BPVC" in upper or "SECTION" in upper or re.match(r"^[IVX]+\b", upper):
            m = _BPVC_TEXT_RE.match(upper)
            if m:
                roman = m.group(1)
                tail = m.group(2) or m.group(3)
                if _ROMAN_RE.match(roman):
                    designator = f"BPVC.{roman}"
                    if tail:
                        designator += f".{tail}"
                    return designator

        # 3) 其它：原样返回（`PTC 4`/`B16.5`/`CSD-1`/`A112.18.1/CSA B125.1`）
        return re.sub(r"\s+", " ", text).strip()

    # ── 网络 ──────────────────────────────────────────────

    def _fetch(self, designator: str) -> list[dict[str, Any]]:
        """按 designator 拉取商品目录条目；失败返回空列表。"""
        params: dict[str, str | int] = {
            "type": "Codes-Standards",
            "page": 1,
            "perPage": 10,
            "fullDesignator": designator,
        }
        try:
            resp = self._session.get(self.API_URL, params=params, timeout=20)
        except Exception:
            # i18n-allow: 内部运维日志
            logger.warning("asme 商品目录请求异常（designator=%s）", designator, exc_info=True)
            return []
        if resp.status_code != 200:
            # i18n-allow: 内部运维日志
            logger.warning("asme 返回 HTTP %s（designator=%s）", resp.status_code, designator)
            return []
        try:
            payload = resp.json()
        except ValueError:
            # i18n-allow: 内部运维日志
            logger.warning("asme 响应 JSON 解析失败（站点可能改版）", exc_info=True)
            return []
        results = payload.get("results") if isinstance(payload, dict) else None
        return results if isinstance(results, list) else []

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """检索候选：先按归一化 designator 精确查；BPVC 分部查不到时补 `.C`/`.M` 尝试。"""
        designator = self._normalize_designator(search_term)
        if not designator:
            return []
        rows = self._fetch(designator)
        if not rows and designator.startswith("BPVC.") and designator.count(".") == 2:
            # 例：`BPVC.II.D` 在目录中细分为 `BPVC.II.D.C`（Customary）/`BPVC.II.D.M`（Metric）
            for suffix in (".C", ".M"):
                rows = self._fetch(designator + suffix)
                if rows:
                    designator = designator + suffix
                    break
        return [self._parse_result(row, search_term) for row in rows]

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """返回候选列表（与其它适配器同一约定）。"""
        return self._search_candidates(standard_number)

    # ── 解析 ──────────────────────────────────────────────

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        designator = str(rec.get("FullDesignator") or "")
        year_raw = rec.get("DesignatorYear")
        year = int(year_raw) if isinstance(year_raw, (int, str)) and str(year_raw).isdigit() else 0
        title = str(rec.get("Title") or "")

        standard_number = f"ASME {designator}-{year}" if year else f"ASME {designator}"
        name = title.split(" - ", 1)[1].strip() if " - " in title else title

        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            name,
            standard_number,
        )

        requested_year = int(target.get("year") or 0) if target else 0
        status = Status.ACTIVE.value
        if requested_year and year and requested_year < year:
            # 目录只索引最新版：请求更旧版本 → 该版已被代替
            status = Status.SUPERSEDED.value

        return QueryResult(
            standard_number=standard_number,
            standard_name=name,
            status=status,
            match_status=match_status,
            publish_date=str(year) if year else "",
            source_site=self.site_name,
            hcno=str(rec.get("ProductCode") or ""),
            # `ASME` 标准为付费商品，不走 `openstd` 下载链
            is_downloadable=False,
        )
