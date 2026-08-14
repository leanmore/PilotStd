"""archive_retry_service + user_service 补测。"""
from unittest.mock import MagicMock, patch

from pilotstd.manager.archive_retry_service import ArchiveRetryService


class TestArchiveRetryService:
    def test_init_stores_manager(self):
        mgr = object()
        svc = ArchiveRetryService(mgr)
        assert svc._mgr is mgr

    def test_retry_pending_empty_db(self):
        mgr = MagicMock()
        svc = ArchiveRetryService(mgr)
        mock_db = MagicMock()
        mock_db.fetchall.return_value = []
        with patch("pilotstd.manager.archive_retry_service.Database", return_value=mock_db):
            with patch("pilotstd.manager.archive_retry_service.get_db_path", return_value=":memory:"):
                r = svc.retry_pending()
                assert r["total"] == 0
                assert r["success"] == 0

    def test_notify_abandoned_with_notification_mgr(self):
        mgr = MagicMock()
        mgr.notification_mgr.send_event = MagicMock()
        svc = ArchiveRetryService(mgr)
        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"standard_number": "GB/T 1", "std_name": "测试"}
        with patch("pilotstd.manager.archive_retry_service.Database", return_value=mock_db):
            with patch("pilotstd.manager.archive_retry_service.get_db_path", return_value=":memory:"):
                svc._notify_abandoned(1, 42, "download failed")
                mgr.notification_mgr.send_event.assert_called_once()

    def test_notify_abandoned_no_notification_mgr(self):
        mgr = MagicMock(spec=[])
        svc = ArchiveRetryService(mgr)
        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"standard_number": "GB/T 1", "std_name": "测试"}
        with patch("pilotstd.manager.archive_retry_service.Database", return_value=mock_db):
            with patch("pilotstd.manager.archive_retry_service.get_db_path", return_value=":memory:"):
                svc._notify_abandoned(1, 42, "err")  # 不抛异常
