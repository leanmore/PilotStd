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

        notifier.notification_mgr.send_event.assert_called_once()
        args = notifier.notification_mgr.send_event.call_args[0]
        assert args[0] == "announcement_check_complete"
        assert args[1]["matched"] == 5
        assert args[1]["source"] == "手动"

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
