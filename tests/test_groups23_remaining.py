# tests/test_groups23_remaining.py — 第二三组精简版

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

_CI = os.environ.get("CI", "").lower() in ("true", "1")


class TestCoreRemaining(unittest.TestCase):
    def test_frozen(self):
        from pilotstd.core.frozen import is_frozen

        self.assertIsInstance(is_frozen(), bool)

    def test_project_manager_init(self):
        from pilotstd.core.project import ProjectManager

        pm = ProjectManager()
        self.assertIsNotNone(pm)

    def test_config_manager_init(self):
        from pilotstd.core.config.manager import ConfigManager

        cm = ConfigManager()
        self.assertIsNotNone(cm)

    def test_notification_aggregator(self):
        from pilotstd.core.notification_aggregator import NotificationAggregator

        self.assertTrue(hasattr(NotificationAggregator, "__init__"))

    def test_std_utils_classify(self):
        from pilotstd.core.std_utils import GB_CODES, classify_std_code

        result = classify_std_code("GB/T")
        self.assertIsInstance(result, str)
        self.assertIn("GB", GB_CODES)


class TestQueryRemaining(unittest.TestCase):
    def test_cache_repo(self):
        from pilotstd.query.cache import CacheRepository

        self.assertTrue(hasattr(CacheRepository, "__init__"))

    def test_daily_quota_init(self):
        from pilotstd.query.daily_quota import DailyQuotaTracker

        self.assertTrue(hasattr(DailyQuotaTracker, "__init__"))

    def test_engine_init(self):
        from pilotstd.query.engine import QueryEngine

        self.assertTrue(hasattr(QueryEngine, "__init__"))

    def test_network_safe_get(self):
        from pilotstd.query.network import safe_get, safe_post

        self.assertTrue(callable(safe_get))
        self.assertTrue(callable(safe_post))

    def test_search_strategy_functions(self):
        from pilotstd.query.search_strategy import MATCH_SCORE, map_status

        self.assertIn("exact", MATCH_SCORE)
        self.assertEqual(map_status("Active"), "现行")


class TestScanRemaining(unittest.TestCase):
    def test_parser_init(self):
        from pilotstd.scan.parser import StandardParser

        sp = StandardParser(code_mapping={})
        self.assertIsNotNone(sp)

    def test_filename_normalizer_import(self):
        from pilotstd.scan.filename_normalizer import _ZH_MARK

        self.assertIsNotNone(_ZH_MARK)

    def test_lang_detect_import(self):
        from pilotstd.scan.lang_detect import detect_language

        self.assertTrue(callable(detect_language))


class TestDownloadRemaining(unittest.TestCase):
    def test_session_manager(self):
        from pilotstd.download.session import SessionManager

        self.assertTrue(hasattr(SessionManager, "__init__"))

    def test_models_task(self):
        from pilotstd.download.models import DownloadStatus

        self.assertIsNotNone(DownloadStatus.PENDING)


class TestPlatformRemaining(unittest.TestCase):
    @unittest.skipIf(_CI, "CI 环境无 PyQt6 显示支持")
    def test_notify_service(self):
        from pilotstd.platform.notify import NotifyService

        self.assertTrue(hasattr(NotifyService, "__init__"))

    def test_updater_version_compare(self):
        from pilotstd.platform.updater import check_latest_version, is_newer_version

        self.assertTrue(is_newer_version("2.0", "1.0"))
        self.assertFalse(is_newer_version("1.0", "2.0"))
        self.assertTrue(callable(check_latest_version))

    def test_updater_sha256(self):
        from pilotstd.platform.updater import extract_sha256_from_body

        result = extract_sha256_from_body("SHA256: abc123def456")
        self.assertIsInstance(result, str)


class TestCliRemaining(unittest.TestCase):
    def test_commands_module(self):
        from pilotstd.cli.commands import __all__ as cmds

        self.assertGreater(len(cmds), 0)

    def test_shared_utils(self):
        from pilotstd.cli.commands._shared import _make_manager

        self.assertTrue(callable(_make_manager))


class TestTasksRemaining(unittest.TestCase):
    def test_pipeline_store(self):
        from pilotstd.task.pipeline_store import PipelineRunStore

        self.assertTrue(hasattr(PipelineRunStore, "__init__"))

    def test_task_queue_init(self):
        from pilotstd.task.queue import TaskQueue

        self.assertTrue(hasattr(TaskQueue, "__init__"))

    def test_task_scheduler_init(self):
        from pilotstd.task.scheduler import TaskScheduler

        self.assertTrue(hasattr(TaskScheduler, "__init__"))

    def test_task_models(self):
        from pilotstd.task.models import TaskStatus

        self.assertIsNotNone(TaskStatus.PENDING)


class TestOrganizerFinal(unittest.TestCase):
    def test_mover_init(self):
        from pilotstd.organizer.mover import FileMover

        self.assertTrue(hasattr(FileMover, "__init__"))

    def test_expire_handler_removed(self):
        """Q26: ExpireHandler 已删除，废止标准统一走主线 organize() 归档。"""
        # 验证 pilotstd.organizer 不再导出 ExpireHandler
        import pilotstd.organizer

        self.assertFalse(hasattr(pilotstd.organizer, "ExpireHandler"))


if __name__ == "__main__":
    unittest.main()
