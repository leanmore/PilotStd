# 模块：项目/查询/适配器/脚本
# 全国团体标准信息平台（..）查询适配器
# 说明：接口:://.../-代理////
# 响应数据的.包含标准列表

import logging
from typing import Any, Optional

import requests

from pilotstd.core.status import Status

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

    # 最大翻页数：`standardNo` 是前缀/模糊过滤，目标通常在首页；仍可能落在后续页
    MAX_PAGES = 3
    PAGE_SIZE = 20

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session_ready = False
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

        self._ensure_session()
        # 注意：`standardName` 是**名称**过滤，用标准号搜索会返回 0 条（实测 2026-11-24）。
        # 按标准号检索必须用 `standardNo`（站点前端 `params.standardNo`，前缀/模糊匹配）。
        page_size = int(kwargs.pop("pageSize", self.PAGE_SIZE))
        first_page = int(kwargs.pop("pageNo", 1))
        collected: list[QueryResult] = []
        for offset in range(self.MAX_PAGES):
            data: dict[str, Any] = {
                "pageNo": first_page + offset,
                "pageSize": page_size,
                "standardNo": keyword,
            }
            # 透传额外过滤参数（站点支持的字段，见 `standard.html` 的 `params` 构造）
            for key in (
                "organName",
                "organCode",
                "standardName",
                "standardTitleEn",
                "standardStatus",
                "publishDateBegin",
                "publishDateEnd",
                "implementDateBegin",
                "implementDateEnd",
                "searchKey",
            ):
                if key in kwargs:
                    data[key] = kwargs.pop(key)
            rows, total = self._fetch_page(data)
            if not rows:
                break
            collected.extend(self._parse_result(rec, keyword) for rec in rows)
            # 已拿到精确匹配、或已到末页 → 停止翻页
            if any(r.match_status == "exact" for r in collected):
                break
            if len(collected) >= total:
                break
        return collected

    def _ensure_session(self) -> None:
        """建立 JSESSIONID：直接 POST 接口会返回 403「访问受限」（实测），需先访问标准页。"""
        if self._session_ready:
            return
        try:
            self._session.get("https://www.ttbz.org.cn/standard.html", timeout=15)
        except Exception:
            # i18n-allow: 内部运维日志
            logger.warning("ttbz 会话引导失败（后续请求可能被拒）", exc_info=True)
        self._session_ready = True

    def _fetch_page(self, data: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        """请求一页并返回 `(rows, total)`；失败返回空。"""
        try:
            resp = safe_post(
                self._session,
                self.get_search_url(),
                self.site_name,
                data=data,
                timeout=15,
                headers=dict(self._session.headers),
            )
        except Exception:
            # 保持 DEBUG：safe_post 在重试耗尽 / HTTP>=400 时已打过 warning，此处只兜意外异常，
            # 再打 WARNING 会与上游重复告警（见 tests/query/adapters/test_adapter_log_levels.py）。
            logger.debug("ttbz 网络请求异常（pageNo=%s）", data.get("pageNo"), exc_info=True)
            return [], 0
        if resp is None or resp.status_code != 200:
            return [], 0
        try:
            payload = resp.json()
        except ValueError:
            # i18n-allow: 内部运维日志
            logger.warning("ttbz 响应 JSON 解析失败（站点可能改版），本次返回空结果", exc_info=True)
            return [], 0
        body = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(body, dict):
            return [], 0
        rows = body.get("rows") or []
        total = int(body.get("total") or 0)
        return rows if isinstance(rows, list) else [], total


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
        """构建搜索请求 form data（BaseAdapter 兼容接口）。

        **必须用 `standardNo`**：`standardName` 是名称过滤，用标准号会返回 0 条（实测）。
        """
        return {"pageNo": 1, "pageSize": self.PAGE_SIZE, "standardNo": search_term}

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """将 API 返回的单条 JSON 映射为 QueryResult。

        映射口径（真实响应字段，见 tests/fixtures/ttbz_sample.json）：
        - 标准号/名称/状态/发布/实施/废止日期/归口团体/站点唯一 ID 直接映射；
        - 英文名称与领域以动态属性挂载（QueryResult 无对应字段）；
        - **无「代替标准」字段**：接口不返回，故 `replaces` 恒为空（不臆造）。
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
        # 废止日期（2026-11-24 补：真实响应含 `abolishDate`，此前未映射）
        abolish_date = rec.get("abolishDate", "") or ""

        # 状态映射：仅对明确的几个值做归一化，其余原样保留
        status_map = {
            Status.ACTIVE.value: Status.ACTIVE.value,
            Status.UPCOMING.value: Status.UPCOMING.value,
            Status.WITHDRAWN.value: Status.WITHDRAWN.value,
        }
        mapped = status_map.get(raw_status, raw_status) if raw_status else Status.UNKNOWN.value

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
            # 已知接口无「代替标准」字段（真实响应字段集不含 `replaces` 类字段），留空不臆造
            replaces="",
        )
        if abolish_date:
            result.abolition_date = abolish_date
        # 动态属性：无对应字段，以动态属性承载
        result.standard_name_en = en_name  # type: ignore[attr-defined]
        result.field = field  # type: ignore[attr-defined]
        return result
