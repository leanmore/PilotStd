# 模块：项目/查询/适配器/脚本
# 全国团体标准信息平台（..）查询适配器
# 说明：接口:://.../-代理////
# 响应数据的.包含标准列表

import logging
from typing import Any, Optional

import requests

from ..models import QueryResult
from ..network import safe_post
from ..search_strategy import (
    _parse_result_number,
    match_result,
)
from .base import BaseAdapter

DISPLAY_NAME = "团体标准平台"

logger = logging.getLogger(__name__)


class TTBZAdapter(BaseAdapter):
    """全国团体标准信息平台查询适配器。

    API: POST /cms-proxy/ms/portal/standardInfo/getPortalStandardList
    请求参数: pageNo, pageSize, standardName（核心），organName/publishDateBegin 等可选。
    返回 data.rows（非 records），每条含 standardNo/standardTitleCn 等字段。

    已知限制：
    - 不支持 status 独立过滤参数
    - standardTitleEn 和 standardField 以动态属性挂载（QueryResult 无对应字段）
    """

    API_URL = "https://www.ttbz.org.cn/cms-proxy/ms/portal/standardInfo/getPortalStandardList"

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
                "Referer": "https://www.ttbz.org.cn/standard.html",
            }
        )

    @property
    def site_name(self) -> str:
        return "ttbz"

    @property
    def site_label(self) -> str:
        return "全国团体标准信息平台"

    # ── 指令层：公开接口，返回列表 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询团体标准，返回全部匹配结果列表。

        Args:
            standard_number: 标准号（如 "T/CAS 123-2024"）或关键词（如 "团体标准"）
            **kwargs: 可选过滤参数 — organName, publishDateBegin, publishDateEnd,
                      standardField, pageNo, pageSize

        Returns:
            list[QueryResult]: 查询结果列表。网络异常/解析失败/空结果均返回空列表。
        """
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        data: dict[str, Any] = {
            "pageNo": kwargs.pop("pageNo", 1),
            "pageSize": kwargs.pop("pageSize", 20),
            "standardName": keyword,
        }
        # 透传额外过滤参数
        for key in (
            "organName",
            "publishDateBegin",
            "publishDateEnd",
            "standardField",
            "implementDateBegin",
            "implementDateEnd",
            "standardType",
        ):
            if key in kwargs:
                data[key] = kwargs.pop(key)

        # 显式传递，确保模拟能检测到（.在模拟下不会自动合并）
        try:
            resp = safe_post(
                self._session,
                self.API_URL,
                self.site_name,
                data=data,
                timeout=15,
                headers=dict(self._session.headers),
            )
        except Exception:
            logger.debug("ttbz 网络请求异常", exc_info=True)
            return []
        if resp is None or resp.status_code != 200:
            return []

        try:
            payload = resp.json()
        except ValueError:
            logger.debug("ttbz JSON 解析失败", exc_info=True)
            return []

        rows = payload.get("data", {}).get("rows", [])
        if not rows:
            return []

        return [self._parse_result(rec, keyword) for rec in rows]

    # ──引擎层：融入渐进搜索体系──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配。多候选时选 standard_number 精确匹配或最新发布者。"""
        candidates = self.query_standards(search_term)
        if not candidates:
            return None
        # 精确匹配
        for c in candidates:
            if c.standard_number == search_term:
                return c
        # 取最新发布
        best = max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")
        return best

    def _build_search_data(self, search_term: str) -> dict[str, Any]:
        """构建搜索请求 form data。BaseAdapter 兼容接口。"""
        return {"pageNo": 1, "pageSize": 15, "standardName": search_term}

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """将 API 返回的单条 JSON 映射为 QueryResult。

        动态属性说明（QueryResult 无对应字段，以动态属性挂载）：
        - result.standard_name_en: str — 英文名称，来源 rec["standardTitleEn"]
        - result.field: str — 标准领域，来源 rec["standardField"]
        """
        code = rec.get("standardNo", "")
        ch_name = rec.get("standardTitleCn", "")
        en_name = rec.get("standardTitleEn", "")
        raw_status = rec.get("standardStatusName", "")
        field = rec.get("standardField", "")
        unique_id = rec.get("standardUniqueId", "")
        organ_name = rec.get("organName", "")

        publish_date = rec.get("publishDate", "") or ""
        implement_date = rec.get("implementDate", "") or ""

        # 状态映射：仅对明确的几个值做归一化，其余原样保留
        status_map = {"现行": "现行", "即将实施": "即将实施", "废止": "废止"}
        mapped = status_map.get(raw_status, raw_status) if raw_status else "未知"

        # 匹配状态
        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            ch_name,
            code,
        )

        result = QueryResult(
            standard_number=code,
            standard_name=ch_name,
            status=mapped,
            match_status=match_status,
            implementation_date=implement_date,
            publish_date=publish_date,
            responsible_dept=organ_name,
            source_site=self.site_name,
            hcno=unique_id,
        )
        # 动态属性：无对应字段，以动态属性承载
        result.standard_name_en = en_name  # type: ignore[attr-defined]
        result.field = field  # type: ignore[attr-defined]
        return result
