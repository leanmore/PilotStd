"""manager/adapter_manager.py 补测。"""
from unittest.mock import MagicMock
import pytest
from pilotstd.manager.adapter_manager import AdapterManager


@pytest.fixture
def rotator():
    r = MagicMock()
    r._sites = {"ahbz": MagicMock(), "std_gov": MagicMock()}
    r._sites["ahbz"].cooldown_until = 0
    r._sites["ahbz"].request_interval = 1.5
    r._sites["std_gov"].cooldown_until = 0
    r._sites["std_gov"].request_interval = 2.0
    return r


@pytest.fixture
def quota():
    q = MagicMock()
    q._limits = {"ahbz": 500}
    q.get_used.return_value = 100
    return q


@pytest.fixture
def mgr(rotator, quota):
    db = MagicMock()
    db.fetchone.return_value = {"frozen_until": None, "freeze_count": 0, "fail_streak": 0}
    return AdapterManager(db=db, rotator=rotator, quota_tracker=quota)


class TestAdapterManager:
    def test_list_adapters(self, mgr):
        assert len(mgr.list_adapters()) == 2
        assert "ahbz" in mgr.list_adapters()

    def test_get_adapter_status(self, mgr):
        s = mgr.get_adapter_status("ahbz")
        assert s["name"] == "ahbz"
        assert s["daily_used"] == 100
        assert s["daily_limit"] == 500

    def test_get_all_status(self, mgr):
        all_s = mgr.get_all_status()
        assert "ahbz" in all_s
        assert "std_gov" in all_s

    def test_get_all_health(self, mgr):
        mgr._db.fetchall.return_value = [{"adapter_name": "ahbz", "frozen_until": None}]
        h = mgr.get_all_health()
        assert len(h) == 1

    def test_get_all_health_no_db(self):
        mgr = AdapterManager(db=None, rotator=MagicMock(), quota_tracker=MagicMock())
        assert mgr.get_all_health() == []

    def test_get_request_interval(self, mgr):
        assert mgr.get_request_interval("ahbz") == 1.5
        assert mgr.get_request_interval("unknown") == 0.0

    def test_test_adapter_exists(self, mgr):
        r = mgr.test_adapter("ahbz")
        assert r["ok"] is True

    def test_test_adapter_not_exists(self, mgr):
        r = mgr.test_adapter("nonexistent")
        assert r["ok"] is False
        assert "不存在" in r["message"]
