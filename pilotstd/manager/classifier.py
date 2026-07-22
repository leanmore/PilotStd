# pilotstd/manager/classifier.py
# QueryClassifier — 查询后分类，将查询结果按状态/替代关系分堆

import logging
import re
from typing import Any

from ..core.std_utils import GB_CODES, is_gb_code

logger = logging.getLogger(__name__)


class QueryClassifier:
    """查询后分类器：回写状态 → 跨站补查替代关系 → 委托路由调度器分堆。

    分类规则统一由 PipelineRouter.classify_after_query() 定义。
    此服务负责：
      1. 将查询结果回写到 ParsedStdInfo（effect_status / match_status / found_replaces）
      2. 对废止但无替代信息的 GB 标准跨站补查（resolve_replaces）
      3. 委托 router.apply_actions() 统一分堆

    分类结果存入传入的 download_list / expire_list / pending_list 三个可变列表。
    """

    _GB_CODES = GB_CODES  # 向后兼容，定义见 pilotstd.core.std_utils
    _EXPIRE_STATUSES = frozenset({"废止", "已废止", "作废", "被代替"})

    def __init__(self, router: Any, query_adapters: Any, quota_tracker: Any, query_engine: Any) -> None:
        """注入依赖。

        Args:
            router: PipelineRouter 实例，提供 apply_actions() 分堆逻辑
            query_adapters: 查询适配器列表，供跨站补查替代关系
            quota_tracker: DailyQuotaTracker 实例，检查站点配额
            query_engine: QueryEngine 实例，供补查结果写缓存
        """
        self._router = router
        self._query_adapters = query_adapters
        self._quota_tracker = quota_tracker
        self._query_engine = query_engine

    # ════════════════════════════════════════════════════════════════
    # 公共 API
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def parse_std_number(standard_number: str) -> tuple[str | None, int | None]:
        """从标准号字符串中提取代号和序号。如 'GB/T 713.1-2023' → ('GB/T', 713)。"""
        m = re.match(r"([A-Z]+(?:\s*/\s*[A-Z]+)?)\s*(\d+(?:\.\d+)?)", str(standard_number))
        if m:
            code = m.group(1).replace(" ", "")
            number = int(float(m.group(2)))
            return code, number
        return None, None

    def classify(
        self,
        query_results: Any,
        parsed_list: Any,
        download_list: Any,
        expire_list: Any,
        pending_list: Any,
        notification_mgr: Any = None,
    ) -> None:
        """查询后分类：回写状态 → 跨站补查替代关系 → 委托路由调度器分堆。

        分类规则统一由 PipelineRouter.classify_after_query() 定义。
        此方法负责：
          1. 将查询结果回写到 ParsedStdInfo（effect_status / match_status / found_replaces）
          2. 对废止但无替代信息的 GB 标准跨站补查（resolve_replaces）
          3. 委托 router.apply_actions() 统一分堆

        Args:
            query_results: QueryResult 列表（与 parsed_list 一一对应）
            parsed_list: ParsedStdInfo 列表
            download_list: 输出列表，将被清空并填入需下载的条目
            expire_list: 输出列表，将被清空并填入需过期处理的条目
            pending_list: 输出列表，将被清空并填入需人工确认的条目
            notification_mgr: 可选，通知管理器，用于发送 replacement_not_found 事件
        """
        items = parsed_list
        results = query_results

        self._write_back_results(items, results)
        self._resolve_cross_site_replaces(items, results, notification_mgr)
        self._dispatch_by_router(items, download_list, expire_list, pending_list)

    def _write_back_results(self, items: list, results: list) -> None:
        """将 QueryResult 字段写回 ParsedStdInfo（原地修改）。"""
        for p, r in zip(items, results):
            p.effect_status = r.status
            p.match_status = getattr(r, "match_status", "") or ""
            p.found_replaces = getattr(r, "replaces", "") or ""
            p.is_adopted = getattr(r, "is_adopted", False)
            p.found_name = getattr(r, "standard_name", "") or ""
            p.split_parts = getattr(r, "split_into", "") or ""
            p.found_publish_date = getattr(r, "publish_date", "") or ""
            p.found_impl_date = getattr(r, "implementation_date", "") or ""
            p.found_responsible_dept = getattr(r, "responsible_dept", "") or ""
            p.found_abolition_date = getattr(r, "abolition_date", "") or ""
            p.found_source_site = getattr(r, "source_site", "") or ""

    def _resolve_cross_site_replaces(self, items: list, results: list, notification_mgr: Any = None) -> None:
        """跨站补查替代关系：废止/被代替/作废 + 无 replaces + GB 代码。"""
        for p, r in zip(items, results):
            if (
                r.status in self._EXPIRE_STATUSES
                and not r.replaces
                and is_gb_code(p.logical_code)
                and r.match_status != "newer"
            ):
                replaced_by = self.resolve_replaces(p.get_full_number(), notification_mgr)
                if not replaced_by:
                    continue
                r.replaces = replaced_by
                repl_code, _ = self.parse_std_number(replaced_by)
                if repl_code and is_gb_code(repl_code):
                    in_results = any(qr.standard_number and repl_code in qr.standard_number for qr in results)
                    if not in_results:
                        p._replacement_number = replaced_by
                        p.found_replaces = replaced_by

    def _dispatch_by_router(self, items: list, download_list: list, expire_list: list, pending_list: list) -> None:
        """路由器分堆 + stage_status 回写。"""
        buckets = self._router.apply_actions(items)
        download_list.clear()
        download_list.extend(buckets.get("download", []))
        expire_list.clear()
        expire_list.extend(buckets.get("expire", []))
        pending_list.clear()
        pending_list.extend(buckets.get("pending", []))

        for p in buckets.get("download", []):
            p.stage_status = "download"
        for p in buckets.get("expire", []):
            p.stage_status = "expired"
        for p in buckets.get("pending", []):
            if not getattr(p, "stage_status", ""):
                p.stage_status = "pending"
        for p in buckets.get("organize", []) + buckets.get("normalize", []):
            p.stage_status = "archive_ready"

    def resolve_replaces(self, standard_number: str, notification_mgr: Any = None) -> str:
        """跨站点补查替代关系。遍历所有适配器，由适配器声明能力而非硬编码站点名。"""

        searched_sources: list[str] = []
        for adapter in self._query_adapters:
            site = adapter.site_name
            if self._quota_tracker and not self._quota_tracker.can_use_for_detail(site):
                continue
            if not getattr(adapter, "supports_replaces_detail", False):
                continue
            searched_sources.append(site)
            try:
                from ..core.std_utils import parse_std_number

                parsed = parse_std_number(standard_number)
                if not parsed:
                    continue
                result = adapter.query_with_strategy(
                    parsed["code"],
                    parsed["number"],
                    parsed.get("year", 0),
                    num_prefix=parsed.get("num_prefix", ""),
                )
                if result is None or not result.is_found():
                    continue
                if self._query_engine._use_cache:
                    self._query_engine._cache.put(result)
                replaces = adapter.fetch_replaces_detail(result)
                if replaces:
                    return str(replaces)
            except Exception:
                logger.warning(f"替代关系补查失败 ({site}): {standard_number}", exc_info=True)
                continue

        if searched_sources and notification_mgr:
            try:
                notification_mgr.send_event(
                    "replacement_not_found",
                    {"standard_number": standard_number, "searched_sources": searched_sources},
                )
            except Exception:
                pass

        return ""
