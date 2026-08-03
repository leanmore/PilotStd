# pilotstd/announce/notifier.py
"""公告抓取完成后的通知与缓存失效。"""

from __future__ import annotations

from typing import Any


class AnnounceNotifier:
    """纯通知与缓存失效：抓取完成后的副作用处理。"""

    def __init__(self, notification_mgr: Any = None, mgr_db: Any = None):
        self.notification_mgr = notification_mgr
        self.mgr_db = mgr_db

    def after_fetch(self, result: dict[str, Any], source: str = "") -> None:
        """Fetch post-processing: notify + cache invalidation.

        Cache is only invalidated when updated > 0 (actual new data).
        """
        updated = result.get("updated", 0)
        if self.notification_mgr:
            self._send_notifications(result, source)
        if self.mgr_db and updated > 0:
            self._invalidate_cache()

    def _send_notifications(self, result: dict[str, Any], source: str) -> None:
        """Dispatch announcement_check_complete notification event."""
        matched = result.get("matched", 0)
        updated = result.get("updated", 0)
        adapters = result.get("adapters", [])
        has_error = any(a.get("status") == "error" for a in adapters)

        try:
            self.notification_mgr.send_event(
                "announcement_check_complete",
                {
                    "source": source or "手动",
                    "total_announcements": result.get("total_announcements", 0),
                    "total_standards": result.get("total_standards", 0),
                    "matched": matched,
                    "updated": updated,
                    "failures": 1 if has_error else 0,
                },
            )
        except Exception:
            pass

    def _invalidate_cache(self) -> None:
        """Invalidate announcement cache via CacheManager."""
        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self.mgr_db).invalidate_by_source(DataSource.ANNOUNCEMENT)
        except Exception:
            pass
