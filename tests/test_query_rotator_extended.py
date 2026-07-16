# tests/test_query_rotator_extended.py — rotator 补充测试

import os
import sys
import time
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.query.rotator import SiteRotator, SiteState


class TestSiteRotatorAdvanced(unittest.TestCase):
    def setUp(self):
        self.s1 = SiteState(name="site_a", base_url="http://a.com", max_requests=3)
        self.s2 = SiteState(name="site_b", base_url="http://b.com", max_requests=5)
        self.rotator = SiteRotator(sites=[self.s1, self.s2])

    def test_get_available_all_free(self):
        available = self.rotator.get_available(["site_a", "site_b"])
        self.assertIn("site_a", available)
        self.assertIn("site_b", available)

    def test_get_available_unknown_passthrough(self):
        available = self.rotator.get_available(["site_a", "unknown", "site_b"])
        self.assertIn("unknown", available)

    def test_record_success(self):
        self.rotator.record_success("site_a")
        self.assertEqual(self.s1.request_count, 1)
        self.assertEqual(self.s1.consecutive_errors, 0)

    def test_record_error(self):
        self.rotator.record_error("site_a")
        self.assertEqual(self.s1.consecutive_errors, 1)

    def test_cooldown_expired_recovery(self):
        self.s1.cooldown_until = time.time() - 10
        self.s1.request_count = 3
        available = self.rotator.get_available(["site_a"])
        self.assertIn("site_a", available)
        self.assertEqual(self.s1.cooldown_until, 0.0)

    def test_daily_limit_exceeded_skips(self):
        self.s1.daily_limit = 5
        self.s1.daily_count = 5
        self.s1.daily_date = SiteRotator._today()
        available = self.rotator.get_available(["site_a", "site_b"])
        self.assertNotIn("site_a", available)

    def test_reset_all_cooldowns(self):
        self.s1.cooldown_until = time.time() + 9999
        self.rotator.reset_all_cooldowns()
        self.assertEqual(self.s1.cooldown_until, 0.0)

    def test_record_daily_count(self):
        self.rotator.record_success("site_a")
        self.rotator.record_success("site_a")
        self.assertEqual(self.s1.daily_count, 2)


class TestCsresAdapter(unittest.TestCase):
    def test_import_and_attrs(self):
        from pilotstd.query.adapters.csres import CsresAdapter
        self.assertTrue(hasattr(CsresAdapter, 'site_name'))


if __name__ == "__main__":
    unittest.main()
