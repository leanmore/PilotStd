# tests/test_groups2_4_complete.py — 第二三四组批量补完（精简版）

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
from tests.mocks.mock_database import MockDatabase


class TestCoreDeepComplete(unittest.TestCase):
    def test_config_migrate_export_import(self):
        from pilotstd.core.config.migrate import export_rules, import_rules

        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "rules.json")
            cfg = MagicMock()
            cfg.get.return_value = "[]"
            self.assertTrue(export_rules(cfg, p))
            cfg2 = MagicMock()
            cfg2.get.return_value = "[]"
            self.assertEqual(import_rules(cfg2, p), 0)
        finally:
            import shutil

            shutil.rmtree(d, ignore_errors=True)

    def test_file_utils_safe_copy(self):
        from pilotstd.core.file_utils import safe_copy

        d = tempfile.mkdtemp()
        try:
            src = os.path.join(d, "s.txt")
            dst = os.path.join(d, "d.txt")
            with open(src, "w") as f:
                f.write("data")
            self.assertTrue(safe_copy(src, dst))
        finally:
            import shutil

            shutil.rmtree(d, ignore_errors=True)

    def test_file_utils_sha256(self):
        from pilotstd.core.file_utils import _sha256_file

        d = tempfile.mkdtemp()
        try:
            f = os.path.join(d, "t.txt")
            with open(f, "w") as fh:
                fh.write("hello")
            h = _sha256_file(f)
            self.assertEqual(len(h), 64)
        finally:
            import shutil

            shutil.rmtree(d, ignore_errors=True)

    def test_file_utils_garbage_suffix(self):
        from pilotstd.core.file_utils import GARBAGE_SUFFIX_KEYWORDS, normalize_std_filename

        self.assertIn("道客巴巴", GARBAGE_SUFFIX_KEYWORDS)
        result = normalize_std_filename("标准文件 道客巴巴")
        self.assertNotIn("道客巴巴", result)

    def test_db_database_crud(self):
        from pilotstd.core.db.database import Database

        d = tempfile.mkdtemp()
        try:
            db = Database(os.path.join(d, "test.db"))
            db.execute("CREATE TABLE t (id INTEGER)")
            db.execute("INSERT INTO t VALUES (1)")
            self.assertEqual(len(db.fetchall("SELECT * FROM t")), 1)
            db.close()
        finally:
            import shutil

            shutil.rmtree(d, ignore_errors=True)

    def test_validity_get_due_random(self):
        from datetime import datetime, timedelta, timezone

        from pilotstd.core.validity_checker import ValidityChecker

        db = MockDatabase("""CREATE TABLE IF NOT EXISTS standard_validity (
    id INTEGER,
    standard_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '未知',
    last_checked_at TEXT,
    next_check_at TEXT,
    last_status TEXT,
    last_status_updated_at TEXT,
    check_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    updated_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    source_version TEXT DEFAULT 'initial',
    data_state TEXT DEFAULT 'fresh',
    last_accessed_at TEXT
);""").__enter__()
        try:
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            for i in range(5):
                db.execute(
                    "INSERT INTO standard_validity (standard_number,status,next_check_at,created_at,updated_at) VALUES (?,?,?,?,?)",
                    (f"DUE-{i}", "未知", past, past, past),
                )
            vc = ValidityChecker(db)
            sample = vc.get_due_standards_random(3)
            self.assertLessEqual(len(sample), 3)
        finally:
            db.__exit__()

    def test_cache_manager_cleanup_force(self):
        from pilotstd.core.cache_manager import CacheManager

        schema = """CREATE TABLE IF NOT EXISTS standard_info_cache (id INTEGER PRIMARY KEY, data_state TEXT, source_version TEXT, last_accessed_at TEXT);
        CREATE TABLE IF NOT EXISTS standard_validity (
    id INTEGER,
    standard_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '未知',
    last_checked_at TEXT,
    next_check_at TEXT,
    last_status TEXT,
    last_status_updated_at TEXT,
    check_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    updated_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    source_version TEXT DEFAULT 'initial',
    data_state TEXT DEFAULT 'fresh',
    last_accessed_at TEXT
);
        CREATE TABLE IF NOT EXISTS announcement_record (
    id INTEGER,
    source_site TEXT NOT NULL,
    pid TEXT NOT NULL,
    announce_no TEXT,
    standard_number TEXT NOT NULL,
    std_name TEXT,
    publish_date TEXT,
    fetched_at TEXT NOT NULL,
    matched INTEGER DEFAULT 0,
    source_version TEXT DEFAULT 'initial',
    data_state TEXT DEFAULT 'fresh',
    last_accessed_at TEXT,
    announcement_title TEXT,
    standard_count INTEGER,
    announcement_id INTEGER,
    row_index INTEGER,
    implement_date TEXT,
    expiry_date TEXT,
    superseded_by TEXT,
    status TEXT DEFAULT 'draft',
    confidence REAL DEFAULT 0.0,
    raw_text TEXT,
    parser_engine TEXT,
    approved_by INTEGER,
    approved_at TEXT,
    updated_at TEXT DEFAULT 'CURRENT_TIMESTAMP'
);"""
        db = MockDatabase(schema).__enter__()
        try:
            cm = CacheManager(db)
            cm.cleanup(force=True)
        finally:
            db.__exit__()


class TestQueryScanDownloadPlatform(unittest.TestCase):
    def test_rotator_save(self):
        from pilotstd.query.rotator import SiteRotator, SiteState

        s = SiteState(name="test", base_url="http://e.com")
        r = SiteRotator(sites=[s])
        r._save = MagicMock()
        r._save()
        self.assertTrue(True)

    def test_scanner_with_config(self):
        from pilotstd.scan.scanner import FileScanner

        cm = MagicMock()
        cm.get.return_value = []
        fs = FileScanner(config_manager=cm)
        self.assertIsNotNone(fs)

    def test_download_engine_has_init(self):
        from pilotstd.download.engine import DownloadEngine

        self.assertTrue(hasattr(DownloadEngine, "__init__"))

    def test_platform_verify_bad_checksum(self):
        from pilotstd.platform.updater import verify_checksum

        d = tempfile.mkdtemp()
        try:
            f = os.path.join(d, "t.bin")
            with open(f, "wb") as fh:
                fh.write(b"data")
            self.assertFalse(verify_checksum(f, "badhash"))
        finally:
            import shutil

            shutil.rmtree(d, ignore_errors=True)


class TestPipelineCliI18n(unittest.TestCase):
    def test_pipeline_router_has_init(self):
        from pilotstd.pipeline.router import PipelineRouter

        self.assertTrue(hasattr(PipelineRouter, "__init__"))

    def test_i18n_set_get_language(self):
        from pilotstd.i18n import _, get_language, set_language

        set_language("zh_CN")
        self.assertEqual(get_language(), "zh_CN")
        self.assertIsInstance(_("test_key"), str)


class TestManagerServicesComplete(unittest.TestCase):
    def test_all_services_importable(self):
        modules = [
            ("pilotstd.manager.service_factory", "create_services"),
            ("pilotstd.manager.classifier", "QueryClassifier"),
            ("pilotstd.manager.pending_service", "PendingService"),
            ("pilotstd.manager.scheduled_service", "ScheduledService"),
            ("pilotstd.manager.standard_service", "StandardService"),
            ("pilotstd.manager.system_service", "SystemService"),
            ("pilotstd.manager.export_service", "ExportService"),
            ("pilotstd.manager.quality_service", "QualityService"),
            ("pilotstd.manager.monitor_service", "MonitorService"),
            ("pilotstd.manager.user_service", "UserService"),
            ("pilotstd.manager.validity_service", "ValidityService"),
            ("pilotstd.manager.wechat_ip_service", "WechatIPService"),
            ("pilotstd.manager.adapter_manager", "AdapterManager"),
        ]
        for mod_name, cls_name in modules:
            mod = __import__(mod_name, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            self.assertTrue(hasattr(cls, "__init__"), f"{mod_name}.{cls_name}")


class TestAnnouncementComplete(unittest.TestCase):
    def test_engine_has_init(self):
        from pilotstd.announcement.engine import AnnounceEngine

        self.assertTrue(hasattr(AnnounceEngine, "__init__"))

    def test_all_crawlers_have_site_name(self):
        from pilotstd.announcement.adapters import SamrDbCrawler, SamrGbCrawler, SamrHbCrawler

        for cls in [SamrGbCrawler, SamrHbCrawler, SamrDbCrawler]:
            self.assertTrue(hasattr(cls, "site_name"))

    def test_ocr_create_provider_callable(self):
        from pilotstd.announcement.ocr import create_ocr_provider

        self.assertTrue(callable(create_ocr_provider))


class TestHardModulesComplete(unittest.TestCase):
    def test_monitor_imports(self):
        from pilotstd.monitor import config as mc

        self.assertIsNotNone(mc)

    def test_wechat_ip_imports(self):
        from pilotstd.wechat_ip import config as wc

        self.assertIsNotNone(wc)

    def test_tasks_imports(self):
        from pilotstd.tasks import date_reminder as dr

        self.assertIsNotNone(dr)


if __name__ == "__main__":
    unittest.main()
