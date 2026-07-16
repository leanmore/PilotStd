# tests/test_announcement_base.py — BaseAnnounceCrawler 测试

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.announcement.base import AdapterFrozenError, BaseAnnounceCrawler


class ConcreteCrawler(BaseAnnounceCrawler):
    """用于测试的具体子类——只需实现四个抽象属性。"""

    @property
    def site_name(self) -> str:
        return "test_site"

    @property
    def standard_type(self) -> str:
        return "gb"

    @property
    def _list_url(self) -> str:
        return "https://example.com/api/list"

    @property
    def _detail_url(self) -> str:
        return "https://example.com/detail"


class TestConcreteCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = ConcreteCrawler()

    def test_site_name(self):
        self.assertEqual(self.crawler.site_name, "test_site")

    def test_standard_type(self):
        self.assertEqual(self.crawler.standard_type, "gb")

    def test_source_site(self):
        self.assertEqual(self.crawler.source_site, "announcement_gb")

    def test_initial_state(self):
        self.assertEqual(self.crawler._cb_freeze_count, 0)
        self.assertIsNone(self.crawler._cb_first_freeze_time)
        self.assertIsNone(self.crawler._cb_frozen_until)
        self.assertEqual(self.crawler._cb_fail_streak, 0)
        self.assertFalse(self.crawler._cb_loaded)

    @patch.object(ConcreteCrawler, "_cb_save_health")
    def test_record_success_resets_fail_streak(self, mock_save):
        self.crawler._cb_fail_streak = 5
        self.crawler._cb_record_success()
        self.assertEqual(self.crawler._cb_fail_streak, 0)

    @patch.object(ConcreteCrawler, "_cb_save_health")
    @patch.object(ConcreteCrawler, "_cb_load_health")
    def test_check_frozen_not_frozen(self, mock_load, mock_save):
        self.crawler._cb_check_frozen()


class TestAdapterFrozenError(unittest.TestCase):
    def test_message(self):
        err = AdapterFrozenError("test_adapter", 300)
        self.assertIn("test_adapter", str(err))
        self.assertIn("300", str(err))
        self.assertEqual(err.adapter_name, "test_adapter")
        self.assertEqual(err.remaining_seconds, 300)


class TestFinalizeItems(unittest.TestCase):
    def test_adds_default_fields(self):
        items = [{"std_code": "GB/T 1.1"}]
        result = BaseAnnounceCrawler._finalize_items(items, "https://example.com/doc.pdf")
        self.assertEqual(result[0]["attachment_url"], "https://example.com/doc.pdf")
        self.assertEqual(result[0]["attachment_path"], "")

    def test_does_not_overwrite_existing(self):
        items = [{"std_code": "GB/T 1.1", "attachment_url": "old_url", "attachment_path": "/tmp/old"}]
        result = BaseAnnounceCrawler._finalize_items(items, "new_url")
        self.assertEqual(result[0]["attachment_url"], "old_url")
        self.assertEqual(result[0]["attachment_path"], "/tmp/old")

    def test_empty_items(self):
        result = BaseAnnounceCrawler._finalize_items([], "")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
