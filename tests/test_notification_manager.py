"""notification/manager.py 补测 v3。"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from tests.fixtures.engine_mock_tree import ConfigStub


@pytest.fixture
def mgr():
    from pilotstd.core.notification.manager import NotificationManager
    cfg = ConfigStub({"notification.enabled": False, "notification.aggregate_enabled": False})
    db = MagicMock()
    db.fetchone.return_value = None
    db.fetchall.return_value = []
    return NotificationManager(cfg, db, 1, None)


class TestInit:
    def test_constructor_disabled(self, mgr):
        assert mgr._enabled is False
        assert mgr._user_id == 1
        assert mgr._channels == {}
        assert mgr.aggregator is None


class TestQuietHours:
    def test_disabled(self, mgr):
        assert mgr._is_quiet_hours() is False

    def test_cross_midnight(self, mgr):
        mgr._cfg.set("notification.quiet_hours_enabled", True)
        dt = datetime(2026, 1, 15, 23, 30, 0)
        with patch("pilotstd.core.notification.manager.datetime") as mdt:
            mdt.now.return_value = dt
            mdt.strptime = datetime.strptime
            assert mgr._is_quiet_hours() is True

    def test_daytime(self, mgr):
        mgr._cfg.set("notification.quiet_hours_enabled", True)
        dt = datetime(2026, 1, 15, 12, 0, 0)
        with patch("pilotstd.core.notification.manager.datetime") as mdt:
            mdt.now.return_value = dt
            mdt.strptime = datetime.strptime
            assert mgr._is_quiet_hours() is False


class TestLogMethods:
    def test_unread(self, mgr):
        mgr._db.fetchone.return_value = {"cnt": 5}
        assert mgr.get_unread_count() == 5

    def test_mark_all(self, mgr):
        assert mgr.mark_logs_read(None) == 0

    def test_mark_ids(self, mgr):
        mgr._db.execute.return_value.rowcount = 3
        assert mgr.mark_logs_read([1, 2, 3]) == 3

    def test_cleanup(self, mgr):
        mgr._db.execute.return_value.rowcount = 10
        assert mgr.cleanup_logs(30) == 10

    def test_get_logs(self, mgr):
        mgr._db.fetchone.return_value = {"cnt": 2}
        mgr._db.fetchall.return_value = [{"id": 1, "event_type": "t"}]
        r = mgr.get_logs()
        assert r["total"] == 2


class TestWSBroadcast:
    def test_no_ws(self, mgr):
        mgr._broadcast_to_ws("x", MagicMock())

    def test_with_ws(self, mgr):
        mgr._ws_broadcast = MagicMock()
        msg = MagicMock()
        msg.event_type = "x"
        mgr._broadcast_to_ws("x", msg)
        mgr._ws_broadcast.assert_called_once()


class TestTestSend:
    def test_ok(self, mgr):
        with patch("pilotstd.core.notification.manager.do_test_send") as m:
            m.return_value = {"ok": True}
            assert mgr.test_send("tg", MagicMock())["ok"] is True


class TestSendEvent:
    def test_disabled(self, mgr):
        mgr._enabled = False
        mgr.send_event("test", {"k": "v"})
