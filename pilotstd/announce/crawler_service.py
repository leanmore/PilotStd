# 模块：项目//爬取_服务脚本
"""公告爬取服务 — 编排 AnnounceEngine + checkpoint + 持久化。

check_all: 遍历 gb/hb/db 适配器增量抓取，写 checkpoint。
check_filtered: 按 types 过滤的变体，供 CLI 调用。
"""

from __future__ import annotations

import os
from typing import Any

from pilotstd.announcement.adapters import SamrDbCrawler, SamrGbCrawler, SamrHbCrawler
from pilotstd.announcement.engine import AnnounceEngine
from pilotstd.announcement.matcher import AnnouncementMatcher
from pilotstd.core.config import get_data_dir

_STD_TYPE_DISPLAY: dict[str, str] = {
    "gb": "national",
    "hb": "industry",
    "db": "local",
}


def build_fetch_summary(adapter_results: list[dict[str, Any]]) -> dict[str, Any]:
    """构建各适配器抓取摘要数据（提取自旧 Mixin 类）。"""
    from datetime import datetime, timezone

    return {
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "adapters": adapter_results,
        "total_count": sum(a["count"] for a in adapter_results),
        "has_error": any(a["status"] == "error" for a in adapter_results),
    }


def query_announcement_stats(db: Any, since: str) -> dict[str, int]:
    """查询自 since 起新增公告的分类统计（公告数/标准数，按国标/行标/地标分组）。

    口径：公告数 = COUNT(DISTINCT announce_no)，标准数 = COUNT(*)，
    严禁使用 SUM(standard_count)——同一公告的多条记录共享该值，SUM 会产生 N² 膨胀。
    查询失败（如表不存在）时返回全 0 统计，不阻断抓取流程。
    """
    stats: dict[str, int] = {
        "total_announcements": 0,
        "total_standards": 0,
        "gb_count": 0,
        "hb_count": 0,
        "db_count": 0,
        "gb_standards": 0,
        "hb_standards": 0,
        "db_standards": 0,
    }
    sql = (
        "SELECT source_site,"
        " COUNT(DISTINCT announce_no) AS ann_cnt, COUNT(*) AS std_cnt "
        "FROM announcement_record WHERE fetched_at >= ? GROUP BY source_site"
    )

    def _val(row: Any, key: str, idx: int) -> int:
        """兼容 dict 行与 sqlite3 tuple 行取值。"""
        try:
            return row[key] or 0
        except (KeyError, IndexError, TypeError):
            return row[idx] if len(row) > idx else 0

    try:
        if hasattr(db, "fetchall"):
            rows = db.fetchall(sql, (since,))
        else:
            rows = db.execute(sql, (since,)).fetchall()
        for r in rows or []:
            ann_cnt = _val(r, "ann_cnt", 1)
            std_cnt = _val(r, "std_cnt", 2)
            source = _val(r, "source_site", 0)
            if source == "announcement_gb":
                stats["gb_count"] = ann_cnt
                stats["gb_standards"] = std_cnt
            elif source == "announcement_hb":
                stats["hb_count"] = ann_cnt
                stats["hb_standards"] = std_cnt
            elif source == "announcement_db":
                stats["db_count"] = ann_cnt
                stats["db_standards"] = std_cnt
            stats["total_announcements"] += ann_cnt
            stats["total_standards"] += std_cnt
    except Exception:
        return stats
    return stats


class AnnounceCrawler:
    """公告抓取服务：增量检查 + 类型过滤。"""

    def __init__(self, file_index: Any, persistence: Any, ocr_config: dict | None = None):
        self._file_index = file_index
        self._persistence = persistence
        self._ocr_config = ocr_config
        self._engine: AnnounceEngine | None = None
        self._ocr_provider: Any = None

    @property
    def engine(self) -> AnnounceEngine:
        if self._engine is None:
            adapters = [SamrGbCrawler(), SamrHbCrawler(), SamrDbCrawler()]
            matcher = AnnouncementMatcher(self._file_index._db)
            self._engine = AnnounceEngine(adapters=adapters, matcher=matcher)
        return self._engine

    def _get_ocr_provider(self) -> Any:
        """懒加载 OCR provider，首次调用时从 _ocr_config 创建。"""
        if self._ocr_provider is None and self._ocr_config:
            from pilotstd.announcement.ocr import create_ocr_provider

            self._ocr_provider = create_ocr_provider(self._ocr_config)
        return self._ocr_provider

    # ── 主入口 ──────────────────────────────────────────────

    def check_all(self, adapter_name: str = "") -> dict[str, Any]:
        """对 gb/hb/db 适配器执行全量公告检查，返回摘要数据。"""
        from datetime import datetime

        # 记录抓取开始时刻，用于查询本次窗口新增公告的分类统计
        check_start = datetime.now().isoformat()
        # 确保各类型输出目录存在
        data_dir = get_data_dir()
        for std_type in ("gb", "hb", "db"):
            os.makedirs(os.path.join(data_dir, "announcements", std_type), exist_ok=True)

        engine = self.engine
        ocr = self._get_ocr_provider()
        total_matched = 0
        total_updated = 0
        adapter_results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for adapter in engine.adapters:
            if adapter_name and adapter.standard_type != adapter_name:
                continue
            # 读取实现增量抓取
            since = self._persistence.get_checkpoint(adapter.source_site) or ""

            result = engine.check_one(adapter.standard_type, since_date=since, ocr_provider=ocr)
            if "error" in result:
                self._persistence.record_failure(adapter.source_site, result.get("error", ""))
                adapter_results.append({
                    "name": adapter.site_name,
                    "type": _STD_TYPE_DISPLAY.get(adapter.standard_type, adapter.standard_type),
                    "count": 0,
                    "status": "error",
                    "error_msg": result.get("error", ""),
                })
                errors.append({"source": adapter.source_site, "error": result.get("error", "")})
                continue

            count = result.get("matched", 0) + result.get("updated", 0)
            total_matched += result.get("matched", 0)
            total_updated += result.get("updated", 0)
            # 各适配器成功记录
            adapter_results.append({
                "name": adapter.site_name,
                "type": _STD_TYPE_DISPLAY.get(adapter.standard_type, adapter.standard_type),
                "count": count,
                "status": "success",
                "error_msg": "",
            })
            self._persistence.write_checkpoint(adapter.source_site, result.get("last_notice_date", ""))

        # 本次抓取窗口内新增公告的分类统计（供通知载荷使用）
        stats = query_announcement_stats(self._persistence._db, check_start)
        return {
            "matched": total_matched,
            "updated": total_updated,
            "total_announcements": sum(a["count"] for a in adapter_results),
            "adapters": adapter_results,
            "errors": errors,
            "gb_count": stats["gb_count"],
            "hb_count": stats["hb_count"],
            "db_count": stats["db_count"],
            "gb_standards": stats["gb_standards"],
            "hb_standards": stats["hb_standards"],
            "db_standards": stats["db_standards"],
            "total_standards": stats["total_standards"],
        }

    def check_filtered(self, types: list[str] | None = None, since_date: str = "") -> dict[str, Any]:
        """带类型过滤的公告检查。types 如 ['gb', 'hb']，None 表示全部。"""
        engine = self.engine
        ocr = self._get_ocr_provider()

        adapters = engine.adapters
        if types:
            adapters = [a for a in adapters if a.standard_type in types]

        results: dict[str, Any] = {}
        for adapter in adapters:
            result = engine.check_one(adapter.standard_type, since_date=since_date, ocr_provider=ocr)
            results[adapter.standard_type] = result

        return results
