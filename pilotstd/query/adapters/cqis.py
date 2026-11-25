# 模块：项目/查询/适配器/脚本
# 重庆市标准信息平台（db.cqis.cn）查询适配器
# 说明：重庆市智慧市场监管一体化平台 — 地方标准信息公开（重庆 DB50 权威源，含全文 PDF）
# ⚠️ 修改本文件后请在本地运行国内站点端到端测试验证（见 tests/test_e2e_adapters.py，CI 不运行）

import json
import logging
from datetime import datetime
from typing import Any

import requests

from pilotstd.core.status import Status

from ..models import QueryResult
from ..search_strategy import (
    _parse_result_number,
    map_status,
    match_result,
)
from .base import BaseAdapter

DISPLAY_NAME = "重庆标准"  # i18n-allow: 站点中文显示名（前端展示，与其它适配器同口径）

logger = logging.getLogger(__name__)


class CqisAdapter(BaseAdapter):
    """重庆标准信息平台查询适配器（DB50 权威源 + 全文 PDF）。

    入口：`http://db.cqis.cn/`（站点**仅 HTTP**，无可用 HTTPS）。
    检索：`POST /LocalStandard/GetDB50ShareList`，form-urlencoded：
          `queryJson={"FinishCode": <标准号>, ...}` + `page` + `rows`
          按标准号过滤用 `queryJson.FinishCode`（**不是** BZName，后者匹配的是标准名称）。
    详情：`POST /LocalStandard/GetPublicInfo`（本适配器不调用：列表已含全部所需字段）。

    已知限制：
    - 响应 `total` 字段不可靠（实测常为 1/2），故以 `rows` 实际内容为准；
    - 无独立标准状态过滤参数，但每行带 `ReleaseStatus`（现行/废止…）；
    - 覆盖范围为重庆 DB50（该平台同时镜像外省题录，但仅重庆有全文附件）。
    """

    BASE_URL = "http://db.cqis.cn"
    SEARCH_PATH = "/LocalStandard/GetDB50ShareList"

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
                "Origin": self.BASE_URL,
                "Referer": self.BASE_URL + "/",
            }
        )

    @property
    def site_name(self) -> str:
        return "cqis"

    @property
    def site_label(self) -> str:
        return "重庆标准平台"  # i18n-allow: 站点中文标签（与 DISPLAY_NAME 同口径）

    def _build_search_data(self, search_term: str) -> dict[str, Any]:
        """构建 form data：`queryJson.FinishCode` 才是标准号过滤字段。"""
        query = {
            "FinishCode": search_term,
            "BZName": "",
            "SourceName": "",
            "ClassificationIndustry": "",
            "StandardCategory": "",
            "OtherCategory": "",
        }
        return {
            "queryJson": json.dumps(query, ensure_ascii=False),
            "page": "1",
            "rows": "20",
        }

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """POST 检索并解析候选（响应结构是顶层 `rows`，非基类的 `records`）。"""
        from ..network import safe_post

        try:
            resp = safe_post(
                self._session,
                self.get_search_url(),
                self.site_name,
                data=self._build_search_data(search_term),
                timeout=15,
            )
        except Exception:
            # `safe_post` 已对重试耗尽/HTTP>=400 打过 `warning`，此处只兜意外异常
            # i18n-allow: 内部运维日志
            logger.warning("cqis 网络请求意外异常（safe_post 已记录常规失败）", exc_info=True)
            return []
        if resp is None or resp.status_code != 200:
            return []

        try:
            payload = resp.json()
        except ValueError:
            # i18n-allow: 内部运维日志
            # i18n-allow: 内部运维日志
            logger.warning("cqis 响应 JSON 解析失败（站点可能改版），本次返回空结果", exc_info=True)
            return []

        rows = payload.get("rows") or []
        if not rows:
            return []
        return [self._parse_result(rec, search_term) for rec in rows]

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """返回候选列表（与 ttbz/energy 等适配器同一约定；供冒烟脚本与惰性调用）。"""
        return self._search_candidates(standard_number)

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """把列表行映射为 QueryResult（字段全部来自真实响应，见 tests/fixtures/cqis_sample.json）。"""
        code = str(rec.get("Project_FinishCODE") or "")
        name = str(rec.get("BZName") or "")
        raw_status = str(rec.get("ReleaseStatus") or "")
        publish_date = str(rec.get("ReleaseTime") or "")[:10]
        implement_date = str(rec.get("ActiveTime") or "")[:10]
        replaces = str(rec.get("ReplaceStandardNumber") or "")

        mapped = map_status(raw_status)
        # 状态修正：现行但实施日期在未来 → 即将实施（与 `dbba` 同口径）
        if mapped == Status.ACTIVE.value and implement_date:
            try:
                if datetime.strptime(implement_date, "%Y-%m-%d") > datetime.now():
                    mapped = Status.UPCOMING.value
            except ValueError as exc:
                # i18n-allow: 内部运维日志
                logger.info("cqis ActiveTime 解析失败 (%s): %s", implement_date, exc)

        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            name,
            code,
        )

        return QueryResult(
            standard_number=code,
            standard_name=name,
            status=mapped,
            match_status=match_status,
            implementation_date=implement_date,
            publish_date=publish_date,
            responsible_dept=str(rec.get("StandardDepartment") or ""),
            source_site=self.site_name,
            hcno=str(rec.get("BZProjectPublicId") or ""),
            replaces=replaces,
            # `DB` 标准不走 `openstd` 下载链（本平台提供站内 `PDF`，另行处理）
            is_downloadable=False,
        )
