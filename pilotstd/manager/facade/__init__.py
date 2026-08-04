# 模块：pilotstd/manager/facade/__init__.py
"""StandardManager — 业务逻辑门面，统一 API 封装扫描→查询→下载→归类完整流程。

组合模式重构：所有 Mixin 已拆分为独立 Handler，通过 BaseFacade 组合。
"""

import json
from typing import Any, Optional

from ._base import BaseFacade


class StandardManager(BaseFacade):
    """标准管理统一 API — 业务逻辑门面。"""

    @property
    def pipeline_store(self):
        """代理底层核心组件的管道运行存储。"""
        return self._core.pipeline_store

    # ===== 兼容旧代码：静态方法 =====

    @staticmethod
    def _resolve_industry_in_path(rel_path: str) -> str:
        """解析相对路径第一段中的行业代号为完整目录名（委托 OrganizeHandler）。"""
        from ._organize import OrganizeHandler

        return OrganizeHandler._resolve_industry_in_path(rel_path)

    # ===== 公告检查 delegation（→ AnnounceService） =====

    def check_announcements(self) -> dict[str, Any]:
        """检查各公告源的新公告，匹配本地标准。"""
        return self._announce_svc.check_announcements()

    def check_announcements_filtered(
        self,
        std_type: Optional[str] = None,
        since_date: str = "",
        progress_callback: Any = None,
        types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """带类型过滤和日期筛选的公告检查。供 CLI / API 调用。"""
        return self._announce_svc.check_announcements_filtered(
            std_type=std_type,
            since_date=since_date,
            progress_callback=progress_callback,
            types=types,
        )

    def get_announcement_match(self, limit: int = 500) -> list[dict[str, Any]]:
        """从 announcement_match 表读取最近公告结果。"""
        rows = self.db.fetchall(
            "SELECT standard_number, source_site, result_json, cached_at "
            "FROM announcement_match ORDER BY cached_at DESC LIMIT ?",
            (limit,),
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            item: dict[str, Any] = {
                "std_code": row.get("standard_number", ""),
                "source_site": row.get("source_site", "gb"),
            }
            rj = row.get("result_json", "")
            if rj:
                try:
                    extra = json.loads(rj) if isinstance(rj, str) else rj
                    if isinstance(extra, dict):
                        item["std_name"] = extra.get("standard_name", "")
                        item["replaces_code"] = extra.get("replaces", "")
                        item["publish_date"] = extra.get("publish_date", "")
                except (json.JSONDecodeError, TypeError):
                    pass
            items.append(item)
        return items

    def announce_stream(
        self,
        since_date: str = "",
        on_progress: Any = None,
        on_adapter_done: Any = None,
    ) -> dict[str, Any]:
        """流式公告检查（线程安全）。逐适配器检查并通过回调通知进度。"""
        engine = self._announce_svc._get_or_create_engine()
        ocr = self._announce_svc._get_ocr_provider()
        total = len(engine.adapters)
        results: dict[str, Any] = {}
        matched_total = 0

        for idx, adapter in enumerate(engine.adapters):
            if not since_date:
                log_row = self.db.fetchone(
                    "SELECT * FROM fetch_checkpoint WHERE source_site=?",
                    (adapter.source_site,),
                )
                since = log_row["last_notice_date"] if log_row else ""
            else:
                since = since_date

            result = engine.check_one(adapter.standard_type, since_date=since, ocr_provider=ocr)
            results[adapter.standard_type] = result
            matched_total += result.get("matched", 0)

            if on_adapter_done:
                on_adapter_done(adapter.standard_type, result)
            if on_progress:
                on_progress(idx + 1, total, matched_total)

        return {"matched": matched_total, "results": results}


__all__ = ["StandardManager"]
