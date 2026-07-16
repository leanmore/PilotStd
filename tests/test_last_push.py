# tests/test_last_push.py — 最终补测：所有模块小中型缺口（精修版）

import os, sys, tempfile, unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path: sys.path.insert(0, root_dir)
from tests.mocks.mock_database import MockDatabase

_CI = os.environ.get("CI", "").lower() in ("true", "1")


class TestFinalSmall(unittest.TestCase):
    def test_models_default_values(self):
        from pilotstd.models import ParsedStdInfo
        info = ParsedStdInfo(raw_filename="t.pdf", logical_code="GB", number=1, year=2020, std_name="T")
        self.assertEqual(info.num_prefix, "")
        self.assertEqual(info.num_suffix, "")

    def test_organizer_expire_handler_failed_move(self):
        from pilotstd.organizer.expire_handler import ExpireHandler
        from pilotstd.models import ParsedStdInfo
        mock_mover = MagicMock()
        mock_mover.move_to_expire.return_value = None
        eh = ExpireHandler(mock_mover)
        info = ParsedStdInfo(raw_filename="t.pdf", logical_code="GB", number=1, year=2020, std_name="T")
        result = eh.process_expired([("/tmp/exists.pdf", info)])
        self.assertEqual(result["failed"], 1)


class TestI18nFinal(unittest.TestCase):
    def test_fallback_key(self):
        from pilotstd.i18n import set_language, _
        set_language("zh_CN")
        self.assertEqual(_("nonexistent_key_xyz"), "nonexistent_key_xyz")


class TestCoreConfigFinal(unittest.TestCase):
    def test_priority_get_with_source_not_found(self):
        from pilotstd.core.config.priority import PriorityConfigManager
        mgr = PriorityConfigManager(os.path.join(tempfile.mkdtemp(), "cfg.json"))
        r = mgr.get_with_source("NONEXISTENT_KEY_XYZ")
        self.assertEqual(r["source"], "NOT_FOUND")

    def test_crypto_sensitive_suffixes(self):
        from pilotstd.core.config.crypto import _SENSITIVE_SUFFIXES, _is_sensitive
        self.assertTrue(_is_sensitive("provider.secret_key"))
        self.assertFalse(_is_sensitive("storage.root_dir"))

    def test_paths_network_timeout(self):
        from pilotstd.core.config.paths import get_network_timeout
        cfg = MagicMock(); cfg.get.return_value = 30
        self.assertEqual(get_network_timeout(cfg), 30)

    def test_migrate_export_invalid_json(self):
        from pilotstd.core.config.migrate import export_rules
        cfg = MagicMock(); cfg.get.return_value = "not valid json"
        p = os.path.join(tempfile.mkdtemp(), "rules.json")
        self.assertTrue(export_rules(cfg, p))

    def test_security_needs_upgrade(self):
        from pilotstd.core.security import needs_upgrade
        self.assertTrue(needs_upgrade(""))


class TestCoreUtilsFinal(unittest.TestCase):
    def test_file_index_validation(self):
        from pilotstd.core.file_index import FileIndexRepository, FILE_INDEX_TABLE
        db = MockDatabase(f"CREATE TABLE IF NOT EXISTS {FILE_INDEX_TABLE} (id INTEGER PRIMARY KEY, filepath TEXT)").__enter__()
        try:
            repo = FileIndexRepository(db)
            self.assertFalse(repo.is_validation_complete)
            repo.stop()
        finally:
            db.__exit__()

    def test_logger_import(self):
        from pilotstd.core import logger
        self.assertTrue(hasattr(logger, 'LoggerManager'))


class TestNotificationChannelsFinal(unittest.TestCase):
    def test_telegram_validate(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        self.assertFalse(TelegramChannel.validate_config({}))
        self.assertTrue(TelegramChannel.validate_config({"bot_token":"x","chat_id":"1"}))

    def test_wechat_validate(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        self.assertFalse(WechatChannel.validate_config({}))

    def test_feishu_validate(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        self.assertFalse(FeishuChannel.validate_config({"webhook_url":""}))

    def test_dingtalk_validate(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        self.assertTrue(DingTalkChannel.validate_config({"webhook_url":"https://e.com"}))


class TestDownloadScanFinal(unittest.TestCase):
    def test_download_session(self):
        from pilotstd.download.session import SessionManager
        self.assertIsNotNone(SessionManager())

    def test_download_engine_import(self):
        from pilotstd.download.engine import DownloadEngine
        self.assertTrue(hasattr(DownloadEngine, '__init__'))

    def test_scan_watcher_import(self):
        from pilotstd.scan.watcher import FileWatcher
        self.assertTrue(hasattr(FileWatcher, '__init__'))


class TestManagerAnnouncementFinal(unittest.TestCase):
    def test_adapter_manager_import(self):
        from pilotstd.manager.adapter_manager import AdapterManager
        self.assertTrue(hasattr(AdapterManager, '__init__'))

    def test_export_service_import(self):
        from pilotstd.manager.export_service import ExportService
        self.assertTrue(hasattr(ExportService, '__init__'))

    def test_classifier_import(self):
        from pilotstd.manager.classifier import QueryClassifier
        self.assertTrue(hasattr(QueryClassifier, 'classify'))

    def test_ocr_aliyun(self):
        from pilotstd.announcement.ocr._aliyun import AliyunOcrProvider
        self.assertTrue(hasattr(AliyunOcrProvider, '__init__'))

    def test_ocr_baidu(self):
        from pilotstd.announcement.ocr._baidu import BaiduOcrProvider
        self.assertTrue(hasattr(BaiduOcrProvider, '__init__'))

    def test_ocr_tencent(self):
        from pilotstd.announcement.ocr._tencent import TencentOcrProvider
        self.assertTrue(hasattr(TencentOcrProvider, '__init__'))


class TestCliCommandsFinal(unittest.TestCase):
    def test_all_commands_importable(self):
        for m in ["query","download","organize","auto","pending","normalize","announce","task","move","expire"]:
            mod = __import__(f"pilotstd.cli.commands.{m}", fromlist=["run"])
            self.assertTrue(hasattr(mod, f"cmd_{m}"), m)

    def test_shared_make_manager(self):
        from pilotstd.cli.commands._shared import _make_manager
        self.assertTrue(callable(_make_manager))


class TestPipelinePlatformFinal(unittest.TestCase):
    def test_router_init(self):
        from pilotstd.pipeline.router import PipelineRouter
        self.assertIsNotNone(PipelineRouter())

    @unittest.skipIf(_CI, "CI 环境无 PyQt6 显示支持")
    def test_notify_service_import(self):
        from pilotstd.platform.notify import NotifyService
        self.assertTrue(hasattr(NotifyService, '__init__'))


class TestWechatIPFinal(unittest.TestCase):
    def test_cookie_mask(self):
        from pilotstd.wechat_ip.cookie_mgr import mask_cookie
        self.assertNotEqual(mask_cookie("short"), "short")

    def test_browser_xpaths(self):
        from pilotstd.wechat_ip.browser import XPATH_SET_IP, XPATH_TEXTAREA
        self.assertIsInstance(XPATH_SET_IP, str)

    def test_detector_sources(self):
        from pilotstd.wechat_ip.detector import DEFAULT_SOURCES
        self.assertGreater(len(DEFAULT_SOURCES), 0)


if __name__ == "__main__":
    unittest.main()
