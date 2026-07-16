# tests/test_rotator.py — SiteRotator 测试

import os
import sys
import time
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.query.rotator import DEFAULT_COOLDOWN_SECONDS, SiteRotator, SiteState


class TestSiteState(unittest.TestCase):
    def test_defaults(self):
        s = SiteState(name="test", base_url="http://example.com")
        self.assertEqual(s.name, "test")
        self.assertEqual(s.base_url, "http://example.com")
        self.assertEqual(s.active_url, "http://example.com")
        self.assertEqual(s.fallback_urls, [])
        self.assertEqual(s.max_requests, 200)
        self.assertEqual(s.daily_limit, 800)
        self.assertEqual(s.cooldown_seconds, 600)
        self.assertEqual(s.request_count, 0)
        self.assertEqual(s.daily_count, 0)
        self.assertEqual(s.cooldown_until, 0.0)
        self.assertEqual(s.consecutive_errors, 0)

    def test_active_url_defaults_to_base(self):
        s = SiteState(name="test", base_url="http://example.com")
        self.assertEqual(s.active_url, "http://example.com")

    def test_explicit_active_url(self):
        s = SiteState(name="test", base_url="http://main.com", active_url="http://fallback.com")
        self.assertEqual(s.active_url, "http://fallback.com")

    def test_fallback_urls(self):
        s = SiteState(name="test", base_url="http://main.com", fallback_urls=["http://fb1.com", "http://fb2.com"])
        self.assertEqual(len(s.fallback_urls), 2)

    def test_max_requests_custom(self):
        s = SiteState(name="test", base_url="http://e.com", max_requests=50)
        self.assertEqual(s.max_requests, 50)


class TestSiteRotatorBasics(unittest.TestCase):
    def test_empty_rotator(self):
        r = SiteRotator()
        self.assertIsInstance(r, SiteRotator)

    def test_register_site(self):
        r = SiteRotator()
        s = SiteState(name="test", base_url="http://example.com")
        r.register(s)
        self.assertIn("test", r._sites)

    def test_today_returns_string(self):
        today = SiteRotator._today()
        self.assertIsInstance(today, str)
        self.assertTrue(today.startswith("20"))
        self.assertEqual(len(today), 10)

    def test_check_daily_reset_same_day(self):
        s = SiteState(name="test", base_url="http://e.com")
        s.daily_count = 100
        s.daily_date = SiteRotator._today()
        SiteRotator._check_daily_reset(s)
        self.assertEqual(s.daily_count, 100)

    def test_check_daily_reset_new_day(self):
        s = SiteState(name="test", base_url="http://e.com")
        s.daily_count = 100
        s.daily_date = "2020-01-01"
        SiteRotator._check_daily_reset(s)
        self.assertEqual(s.daily_count, 0)
        self.assertEqual(s.daily_date, SiteRotator._today())

    def test_constructor_with_sites(self):
        s = SiteState(name="test", base_url="http://e.com")
        r = SiteRotator(sites=[s])
        self.assertIn("test", r._sites)

    def test_default_cooldown(self):
        self.assertEqual(DEFAULT_COOLDOWN_SECONDS, 600)


class TestSiteRotatorCoolDown(unittest.TestCase):
    def setUp(self):
        self.site = SiteState(name="test", base_url="http://e.com", max_requests=5)
        self.rotator = SiteRotator(sites=[self.site])

    def test_enter_cooldown_sets_timestamp(self):
        self.site.request_count = 5
        self.rotator._enter_cooldown(self.site)
        self.assertGreater(self.site.cooldown_until, time.time())
        self.assertEqual(self.site.request_count, 0)

    def test_reset_all_cooldowns(self):
        self.site.cooldown_until = time.time() + 9999
        self.site.request_count = 10
        self.rotator.reset_all_cooldowns()
        self.assertEqual(self.site.cooldown_until, 0.0)
        self.assertEqual(self.site.request_count, 0)


if __name__ == "__main__":
    unittest.main()
