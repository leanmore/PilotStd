"""query/rotator.py 补测。"""
import time
from unittest.mock import MagicMock
import pytest
from pilotstd.query.rotator import SiteState, SiteRotator


class TestSiteState:
    def test_default_active_url_is_base_url(self):
        s = SiteState(name="test", base_url="http://x.com")
        assert s.active_url == "http://x.com"

    def test_explicit_active_url_preserved(self):
        s = SiteState(name="t", base_url="http://a", active_url="http://b")
        assert s.active_url == "http://b"


class TestSiteRotatorStatic:
    def test_today_returns_date(self):
        assert len(SiteRotator._today()) == 10

    def test_check_daily_reset_new_day(self):
        s = SiteState(name="x", base_url="http://x")
        s.daily_count = 100
        s.daily_date = "2020-01-01"
        SiteRotator._check_daily_reset(s)
        assert s.daily_count == 0

    def test_check_daily_reset_same_day(self):
        s = SiteState(name="x", base_url="http://x")
        s.daily_count = 50
        s.daily_date = SiteRotator._today()
        SiteRotator._check_daily_reset(s)
        assert s.daily_count == 50

    def test_enter_cooldown(self):
        s = SiteState(name="x", base_url="http://x", cooldown_seconds=60)
        SiteRotator._enter_cooldown(s)
        assert s.cooldown_until > 0


class TestSiteRotator:
    @pytest.fixture
    def rot(self):
        return SiteRotator()

    @pytest.fixture
    def rot2(self):
        r = SiteRotator()
        r._sites["a"] = SiteState(name="a", base_url="http://a", max_requests=100)
        r._sites["b"] = SiteState(name="b", base_url="http://b", max_requests=200)
        return r

    def test_register(self, rot):
        rot.register(SiteState(name="t", base_url="http://t"))
        assert "t" in rot._sites

    def test_list_sites(self, rot2):
        assert set(rot2.list_sites()) == {"a", "b"}

    def test_get_available_all(self, rot2):
        assert rot2.get_available(["a", "b"]) == ["a", "b"]

    def test_get_available_cooldown(self, rot2):
        rot2._sites["a"].cooldown_until = time.time() + 999
        assert rot2.get_available(["a", "b"]) == ["b"]

    def test_get_available_daily_limit(self, rot2):
        s = rot2._sites["a"]
        s.daily_limit = 10; s.daily_count = 10; s.daily_date = SiteRotator._today()
        assert "a" not in rot2.get_available(["a", "b"])

    def test_record_success(self, rot2):
        rot2.record_success("a")
        assert rot2._sites["a"].request_count == 1

    def test_record_success_cooldown(self, rot2):
        s = rot2._sites["a"]; s.max_requests = 5; s.request_count = 5
        rot2._save = MagicMock()
        rot2.record_success("a")
        assert s.cooldown_until > 0

    def test_all_in_cooldown(self, rot2):
        rot2._sites["a"].cooldown_until = time.time() + 99
        rot2._sites["b"].cooldown_until = time.time() + 99
        assert rot2.all_in_cooldown(["a", "b"]) is True

    def test_not_all_in_cooldown(self, rot2):
        assert rot2.all_in_cooldown(["a", "b"]) is False

    def test_force_cooldown(self, rot2):
        rot2.force_cooldown("a", 30)
        assert rot2._sites["a"].cooldown_until > 0

    def test_reset_all(self, rot2):
        rot2._sites["a"].cooldown_until = time.time() + 999
        rot2._sites["a"].request_count = 50
        rot2.reset_all_cooldowns()
        assert rot2._sites["a"].cooldown_until == 0

    def test_cooldown_remaining(self, rot2):
        rot2._sites["a"].cooldown_until = time.time() + 100
        r = rot2.get_cooldown_remaining("a")
        assert 0 < r <= 100
