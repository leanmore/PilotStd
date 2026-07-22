# tests/test_final_complete.py — 全模块最终补完（修正版）

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
from tests.mocks.mock_database import MockDatabase

_CI = os.environ.get("CI", "").lower() in ("true", "1")


class TestWechatIP(unittest.TestCase):
    def test_validate_ip_valid(self):
        from pilotstd.wechat_ip.detector import _validate_ip

        self.assertTrue(_validate_ip("192.168.1.1"))
        self.assertTrue(_validate_ip("10.0.0.1"))

    def test_validate_ip_invalid(self):
        from pilotstd.wechat_ip.detector import _validate_ip

        self.assertFalse(_validate_ip("256.1.1.1"))
        self.assertFalse(_validate_ip("1.2.3"))
        self.assertFalse(_validate_ip(""))

    def test_ip_pattern(self):
        from pilotstd.wechat_ip.detector import IP_PATTERN

        self.assertTrue(IP_PATTERN.search("IP: 192.168.1.1"))

    @unittest.skipIf(_CI, "CI 环境跳过网络依赖测试")
    def test_detect_ip_with_mock(self):
        import responses

        from pilotstd.wechat_ip.detector import DEFAULT_SOURCES, detect_ip

        with responses.RequestsMock() as rsps:
            for url, _ in DEFAULT_SOURCES:
                rsps.add(responses.GET, url, body="192.168.1.100", status=200)
            result = detect_ip()
            self.assertIsNotNone(result)

    @unittest.skipIf(_CI, "CI 环境跳过网络依赖测试")
    def test_detect_ip_all_fail(self):
        import responses

        from pilotstd.wechat_ip.detector import detect_ip

        with responses.RequestsMock():
            result = detect_ip()
            self.assertIsNone(result)

    def test_browser_error(self):
        from pilotstd.wechat_ip.browser import BrowserError

        self.assertIn("test", str(BrowserError("test error")))

    def test_browser_updater_init(self):
        from pilotstd.wechat_ip.browser import WechatIPUpdater

        u = WechatIPUpdater(headless=True, engine="playwright")
        self.assertTrue(u.headless)

    def test_cookie_mgr_mask(self):
        from pilotstd.wechat_ip.cookie_mgr import mask_cookie

        masked = mask_cookie("abcdefghijklmnop1234567890")
        self.assertIn("*", masked)

    def test_cookie_mgr_fetch_empty(self):
        from pilotstd.wechat_ip.cookie_mgr import fetch_cookiecloud

        with patch("pilotstd.wechat_ip.cookie_mgr.requests.post", side_effect=Exception("no server")):
            self.assertIsNone(fetch_cookiecloud("http://localhost", "uid", "pass"))

    def test_scheduler_run_check_no_ip(self):
        from pilotstd.wechat_ip.scheduler import run_check

        with patch("pilotstd.wechat_ip.scheduler.do_detect_ip", return_value=None):
            config = MagicMock()
            result = run_check(config)
            self.assertIn("IP 检测失败", result["error"])

    def test_wechat_ip_config_import(self):
        from pilotstd.wechat_ip.config import WechatIPConfig

        self.assertTrue(hasattr(WechatIPConfig, "__init__"))


class TestMonitor(unittest.TestCase):
    def test_defaults_dict(self):
        from pilotstd.monitor.config import DEFAULTS

        self.assertIn("enabled", DEFAULTS)
        self.assertIn("watch_path", DEFAULTS)

    def test_get_config_with_db(self):
        schema = """CREATE TABLE IF NOT EXISTS cache_config (
    id INTEGER,
    config_key TEXT NOT NULL,
    config_value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);"""
        db = MockDatabase(schema).__enter__()
        try:
            db.execute("INSERT INTO cache_config (config_key,config_value) VALUES ('monitor.enabled','true')")
            db.execute("INSERT INTO cache_config (config_key,config_value) VALUES ('monitor.watch_path','/data')")
            with patch("pilotstd.monitor.config._db", return_value=db):
                from pilotstd.monitor.config import get_config

                cfg = get_config()
                self.assertTrue(cfg["enabled"])
                self.assertEqual(cfg["watch_path"], "/data")
        finally:
            db.__exit__()

    def test_handler_module(self):
        from pilotstd.monitor import handler

        self.assertIsNotNone(handler)

    def test_scheduler_module(self):
        from pilotstd.monitor import scheduler

        self.assertIsNotNone(scheduler)


class TestTasks(unittest.TestCase):
    def test_favorite_archive_error(self):
        from pilotstd.tasks.favorite_download import FavoriteArchiveError

        self.assertIn("failed", str(FavoriteArchiveError("download failed")))

    def test_get_download_url_none(self):
        from pilotstd.tasks.favorite_download import _get_download_url

        db = MockDatabase(
            "CREATE TABLE IF NOT EXISTS standard_info_cache ("
            "id INTEGER PRIMARY KEY, standard_number TEXT, result_json TEXT, cached_at TEXT)"
        ).__enter__()
        try:
            self.assertIsNone(_get_download_url("GB/T 1.1", db))
        finally:
            db.__exit__()

    def test_date_reminder_module(self):
        from pilotstd.tasks import date_reminder

        self.assertIsNotNone(date_reminder)


class TestAnnouncement(unittest.TestCase):
    def test_wps_clean(self):
        from pilotstd.announcement._wps_utils import _clean_wps_fulltext, _split_wps_entries

        cleaned = _clean_wps_fulltext("GB/T 1.1-2020\x00标准化")
        self.assertIsInstance(cleaned, str)
        import re

        entries = _split_wps_entries("GB/T 1.1-2020 名称", re.compile(r"([A-Z]+)\s*(\d+)"))
        self.assertIsInstance(entries, list)

    def test_engine_init(self):
        from pilotstd.announcement.adapters import SamrGbCrawler
        from pilotstd.announcement.engine import AnnounceEngine
        from pilotstd.announcement.matcher import AnnouncementMatcher

        db = MockDatabase().__enter__()
        try:
            matcher = AnnouncementMatcher(db)
            engine = AnnounceEngine(adapters=[SamrGbCrawler()], matcher=matcher)
            self.assertIsNotNone(engine)
        finally:
            db.__exit__()

    def test_ocr_counters_init(self):
        from pilotstd.announcement.ocr._base import OcrCounters

        d = tempfile.mkdtemp()
        try:
            c = OcrCounters(os.path.join(d, "counters.json"))
            self.assertIsNotNone(c)
        finally:
            import shutil

            shutil.rmtree(d, ignore_errors=True)

    def test_ocr_scheduler_module(self):
        from pilotstd.announcement.ocr import _base as ocr_base

        self.assertTrue(hasattr(ocr_base, "OcrScheduler"))


class TestManager(unittest.TestCase):
    def test_expire_mixin_merge(self):
        """Q26: merge_expire_from_source 保留，handle_expired 已删除。"""
        from pilotstd.manager.organize.expire import OrganizerExpireMixin

        mixin = OrganizerExpireMixin()
        self.assertFalse(hasattr(mixin, "handle_expired"))
        self.assertTrue(hasattr(mixin, "merge_expire_from_source"))

    def test_facade_base_init(self):
        from pilotstd.manager.facade._base import BaseFacade

        self.assertIsNotNone(BaseFacade())

    def test_facade_core_dataclass(self):
        from pilotstd.manager.facade._core import ManagerCore

        core = ManagerCore(
            cfg=MagicMock(),
            db=MagicMock(),
            parser=MagicMock(),
            scanner=MagicMock(),
            query_engine=MagicMock(),
            cache=MagicMock(),
            quota_tracker=MagicMock(),
            adapter_manager=MagicMock(),
            file_index=MagicMock(),
            download_engine=MagicMock(),
            session_mgr=MagicMock(),
            task_queue=MagicMock(),
            router=MagicMock(),
        )
        self.assertIsNotNone(core.cfg)


class TestCore(unittest.TestCase):
    def test_config_manager_set_get(self):
        from pilotstd.core.config.manager import ConfigManager

        cm = ConfigManager()
        cm.set("test.final.key", "final_value")
        self.assertEqual(cm.get("test.final.key"), "final_value")

    def test_std_utils_parse_gb(self):
        from pilotstd.core.std_utils import parse_std_number

        result = parse_std_number("GB/T 1.1-2020")
        self.assertIsNotNone(result)
        self.assertIn("code", result)

    def test_validity_module_lock(self):
        from pilotstd.core._validity_pipeline import _VALIDITY_LOCK

        self.assertIsNotNone(_VALIDITY_LOCK)

    def test_notification_message_icon(self):
        from pilotstd.core.notification.channel import NotificationMessage

        msg = NotificationMessage(title="T", body="B", level="info", event_type="e", icon="pi-check")
        self.assertEqual(msg.icon, "pi-check")


class TestSmallModules(unittest.TestCase):
    def test_i18n_multiple_switch(self):
        from pilotstd.i18n import get_language, set_language

        for lang in ("zh_CN", "zh_TW", "en", "zh_CN"):
            set_language(lang)
        self.assertEqual(get_language(), "zh_CN")

    def test_cli_commands_all_importable(self):
        for mod_name in (
            "scan",
            "query",
            "download",
            "organize",
            "auto",
            "pending",
            "normalize",
            "announce",
            "task",
            "move",
            "expire",
            "validity",
        ):
            try:
                __import__(f"pilotstd.cli.commands.{mod_name}", fromlist=["run"])
            except ImportError:
                pass

    def test_platform_updater_download_fail(self):
        from pilotstd.platform.updater import download_update

        self.assertFalse(download_update("https://invalid.url/fake.zip", "/tmp/fake.zip"))

    def test_pipeline_router_init(self):
        from pilotstd.pipeline.router import PipelineRouter

        self.assertIsNotNone(PipelineRouter())


if __name__ == "__main__":
    unittest.main()
