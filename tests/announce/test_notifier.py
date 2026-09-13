"""AnnounceNotifier tests -- notification dispatch and cache invalidation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pilotstd.announce.notifier import AnnounceNotifier


@pytest.fixture
def notifier():
    mgr = MagicMock()
    db = MagicMock()
    return AnnounceNotifier(notification_mgr=mgr, mgr_db=db)


class TestAfterFetch:
    def test_sends_notification_when_matched_positive(self, notifier):
        result = {"matched": 5, "updated": 2, "total_announcements": 10,
                  "total_standards": 20, "adapters": []}
        notifier.after_fetch(result, source="手动")

        # C-1（批次2）：检查汇总 + 拉取完成各发一条（announcement_fetch_complete 无条件发送）
        calls = notifier.notification_mgr.send_event.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == "announcement_check_complete"
        assert calls[0][0][1]["matched"] == 5
        assert calls[0][0][1]["source"] == "手动"
        assert calls[1][0][0] == "announcement_fetch_complete"

    def test_invalidates_cache_when_updated_positive(self, notifier):
        result = {"matched": 0, "updated": 3, "total_announcements": 5,
                  "total_standards": 10, "adapters": []}
        with patch("pilotstd.core.cache_manager.CacheManager") as mock_cm:
            notifier.after_fetch(result)

        mock_cm.assert_called_once_with(notifier.mgr_db)
        mock_cm.return_value.invalidate_by_source.assert_called_once()

    def test_skips_cache_invalidation_when_updated_zero(self, notifier):
        result = {"matched": 1, "updated": 0, "total_announcements": 0,
                  "total_standards": 0, "adapters": []}
        with patch("pilotstd.core.cache_manager.CacheManager") as mock_cm:
            notifier.after_fetch(result)

        mock_cm.assert_not_called()

    def test_no_notification_mgr_is_safe(self, notifier):
        notifier.notification_mgr = None
        result = {"matched": 1, "updated": 1, "total_announcements": 0,
                  "total_standards": 0, "adapters": []}

        notifier.after_fetch(result)  # should not raise

    def test_no_mgr_db_is_safe(self, notifier):
        notifier.mgr_db = None
        result = {"matched": 0, "updated": 1, "total_announcements": 0,
                  "total_standards": 0, "adapters": []}

        notifier.after_fetch(result)  # should not raise


class TestDeadEventsRestored:
    """阶段三：恢复 announcement_fetch_failed / announce_fetch_summary 触发逻辑。"""

    def _events(self, notifier):
        return [c.args[0] for c in notifier.notification_mgr.send_event.call_args_list]

    def test_failed_event_when_all_sites_fail(self, notifier):
        result = {
            "matched": 0, "updated": 0, "total_announcements": 0, "total_standards": 0,
            "adapters": [{"status": "error", "error_msg": "timeout", "count": 0}],
        }
        notifier.after_fetch(result, source="定时")

        events = self._events(notifier)
        assert "announcement_check_complete" in events
        assert "announcement_fetch_failed" in events
        payload = next(
            c.args[1] for c in notifier.notification_mgr.send_event.call_args_list
            if c.args[0] == "announcement_fetch_failed"
        )
        assert payload["error"] == "timeout"
        assert payload["source"] == "定时"

    def test_no_failed_event_when_partial_success(self, notifier):
        result = {
            "matched": 2, "updated": 0, "total_announcements": 2, "total_standards": 2,
            "adapters": [{"status": "success"}, {"status": "error", "error_msg": "boom"}],
        }
        notifier.after_fetch(result)

        assert "announcement_fetch_failed" not in self._events(notifier)

    def test_summary_event_when_adapters_present(self, notifier):
        result = {
            "matched": 3, "updated": 1, "total_announcements": 4, "total_standards": 5,
            "adapters": [
                {"name": "GB", "type": "national", "count": 4, "status": "success", "error_msg": ""},
            ],
        }
        notifier.after_fetch(result, source="手动")

        events = self._events(notifier)
        assert "announce_fetch_summary" in events
        payload = next(
            c.args[1] for c in notifier.notification_mgr.send_event.call_args_list
            if c.args[0] == "announce_fetch_summary"
        )
        assert payload["total_count"] == 4
        assert payload["has_error"] is False

    def test_no_summary_when_adapters_empty(self, notifier):
        result = {"matched": 0, "updated": 0, "total_announcements": 0,
                  "total_standards": 0, "adapters": []}
        notifier.after_fetch(result)

        assert "announce_fetch_summary" not in self._events(notifier)

    def test_failure_count_in_check_complete(self, notifier):
        result = {
            "matched": 0, "updated": 0, "total_announcements": 0, "total_standards": 0,
            "adapters": [
                {"status": "error", "error_msg": "a"}, {"status": "error", "error_msg": "b"},
            ],
        }
        notifier.after_fetch(result)
        payload = next(
            c.args[1] for c in notifier.notification_mgr.send_event.call_args_list
            if c.args[0] == "announcement_check_complete"
        )
        assert payload["failures"] == 2


class TestAnnouncementTitleWindow:
    """修复回归：明细只列本次抓取窗口内新增的公告。

    历史缺陷：查询是全表最近 fetched 的 10 条，与本次是否新增无关，
    导致"新增公告：0"却仍列出历史公告，且每次运行原样复现。
    """

    def _payload(self, notifier):
        return next(
            c.args[1] for c in notifier.notification_mgr.send_event.call_args_list
            if c.args[0] == "announcement_fetch_complete"
        )

    def test_no_titles_when_no_new_announcements(self, notifier):
        result = {"matched": 0, "updated": 0, "total_announcements": 0,
                  "total_standards": 0, "adapters": []}
        notifier.after_fetch(result, source="定时", since="2026-09-13T01:00:00")

        assert self._payload(notifier)["announcements"] == []
        notifier.mgr_db.fetchall.assert_not_called()

    def test_titles_scoped_by_run_window(self, notifier):
        notifier.mgr_db.fetchall.return_value = [
            {"announce_no": "2026年第31号", "announcement_title": "关于批准发布…的公告"}
        ]
        result = {"matched": 0, "updated": 0, "total_announcements": 1,
                  "total_standards": 1, "adapters": []}
        notifier.after_fetch(result, source="定时", since="2026-09-13T01:00:00")

        assert self._payload(notifier)["announcements"][0]["title"] == "关于批准发布…的公告"
        # 只挑明细查询那一次调用（updated>0 时缓存失效也会走 fetchall）
        title_calls = [
            c for c in notifier.mgr_db.fetchall.call_args_list if "fetched_at >= ?" in c.args[0]
        ]
        assert len(title_calls) == 1, "必须按本次抓取窗口过滤"
        assert title_calls[0].args[1][0] == "2026-09-13T01:00:00"

    def test_no_since_means_no_titles(self, notifier):
        """窗口未知时宁缺勿错：不展示任何明细。"""
        result = {"matched": 0, "updated": 0, "total_announcements": 1,
                  "total_standards": 1, "adapters": []}
        notifier.after_fetch(result)

        assert self._payload(notifier)["announcements"] == []
        notifier.mgr_db.fetchall.assert_not_called()
