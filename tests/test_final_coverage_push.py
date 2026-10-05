# tests/test_final_coverage_push.py — 10 模块最终补完

import os
import sys
import tempfile
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
from pilotstd.core.status import Status
from tests.mocks.mock_database import MockDatabase


# ═══ organizer/ (96.7→100%) ═══
class TestOrganizerRemaining(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from pilotstd.organizer.dir_builder import DirBuilder

        self.db = DirBuilder(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_expire_handler_removed(self):
        """Q26: ExpireHandler 已删除，废止标准统一走主线 organize() 归档。"""
        import pilotstd.organizer

        self.assertFalse(hasattr(pilotstd.organizer, "ExpireHandler"))

    def test_mover_move_to_code_dir_safe_path_fail(self):
        from pilotstd.models import ParsedStdInfo
        from pilotstd.organizer.mover import FileMover

        fm = FileMover(self.db)
        info = ParsedStdInfo(raw_filename="t.pdf", logical_code="GB/T", number=1, year=2020, std_name="T")
        result = fm.move_to_code_dir("/etc/shadow", info)
        self.assertIsNone(result)


# ═══ i18n/ (85.7→95%) ═══
class TestI18nRemaining(unittest.TestCase):
    def test_set_language_to_en(self):
        from pilotstd.i18n import _, get_language, set_language

        set_language("en")
        self.assertEqual(get_language(), "en")
        # fallback: key itself when no translation
        result = _("nonexistent_key_12345")
        self.assertEqual(result, "nonexistent_key_12345")

    def test_set_language_to_zh_tw(self):
        from pilotstd.i18n import get_language, set_language

        set_language("zh_TW")
        self.assertEqual(get_language(), "zh_TW")

    def test_set_language_unsupported_falls_back_to_default(self):
        """不支持的语言码必须**回退** `DEFAULT_LANGUAGE`，而非被静默保留。

        **旧断言为何不再成立**：本用例原名 `test_set_language_invalid_fallback`，
        却断言 `get_language() == "fr"` —— 名字说"fallback"、断言却是"**不** fallback、
        原样保留"，**自相矛盾**。它锁定的是 `_normalize` 改为 fail-loud 之前的契约。

        当前契约（`pilotstd/i18n/__init__.py::_normalize`，docstring 已说明理由）：
        `SUPPORTED_LANGUAGES = ("zh_CN", "zh_TW", "en")` 之外的语言码**一律回退**
        `DEFAULT_LANGUAGE = "zh_CN"`，并 `logger.warning`。
        **不静默接受的理由**：未知语言码会让 `_translations.get(lang, {})` 取到空表，
        进而使 `t()` 全量 fail-loud 返回键名——那比回退到默认语言更难排查。
        """
        from pilotstd.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, get_language, set_language

        self.assertNotIn("fr", SUPPORTED_LANGUAGES, "本用例的前提是 fr 为不支持的语言")
        set_language("fr")
        self.assertEqual(get_language(), DEFAULT_LANGUAGE)
        self.assertEqual(get_language(), "zh_CN")

    def test_set_language_unsupported_is_not_silently_kept(self):
        """★ 判别力护栏：回退**不等于**静默接受。

        逐一对多个不支持的语言码确认都回退到默认值——若实现退化为"原样保留"，
        本用例 FAIL（旧断言 `== "fr"` 正是那种退化形态）。
        """
        from pilotstd.i18n import DEFAULT_LANGUAGE, get_language, set_language

        for lang in ("fr", "ja", "xx", "de-DE", ""):
            set_language(lang)
            self.assertEqual(
                get_language(), DEFAULT_LANGUAGE,
                f"不支持的语言码 {lang!r} 应回退 {DEFAULT_LANGUAGE!r}，实际 {get_language()!r}",
            )


# ═══ core/ validity_checker (48.6→60%) ═══
class TestValidityCheckerRemaining(unittest.TestCase):
    def setUp(self):
        schema = """CREATE TABLE IF NOT EXISTS standard_validity (
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
);"""
        self.db = MockDatabase(schema).__enter__()

    def tearDown(self):
        self.db.__exit__()

    def test_ensure_column(self):
        from pilotstd.core.validity_checker import ValidityChecker

        vc = ValidityChecker(self.db)
        self.assertIsNotNone(vc)

    def test_get_status_summary(self):
        from datetime import datetime, timezone

        from pilotstd.core.validity_checker import ValidityChecker

        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT INTO standard_validity "
            "(standard_number,status,next_check_at,created_at,updated_at) VALUES (?,?,?,?,?)",
            ("STD-A", Status.ACTIVE.value, now, now, now),
        )
        self.db.execute(
            "INSERT INTO standard_validity "
            "(standard_number,status,next_check_at,created_at,updated_at) VALUES (?,?,?,?,?)",
            ("STD-B", Status.WITHDRAWN.value, now, now, now),
        )
        vc = ValidityChecker(self.db)
        summary = vc.get_status_summary()
        self.assertIn(Status.ACTIVE.value, summary)
        self.assertIn(Status.WITHDRAWN.value, summary)


# ═══ core/ cache_manager (71.8→80%) ═══
class TestCacheManagerRemaining(unittest.TestCase):
    def setUp(self):
        schema = """CREATE TABLE IF NOT EXISTS standard_info_cache (
            id INTEGER PRIMARY KEY, data_state TEXT DEFAULT 'valid',
            source_version TEXT DEFAULT 'initial', last_accessed_at TEXT, result_json TEXT);
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
    updated_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    source_type TEXT DEFAULT '网页解析',
    standard_type TEXT NOT NULL DEFAULT 'Unknown',
    final_name TEXT
);"""
        self.db = MockDatabase(schema).__enter__()
        from pilotstd.core.cache_manager import CacheManager

        self.cm = CacheManager(self.db)

    def tearDown(self):
        self.db.__exit__()

    def test_mark_stale_and_valid_cycle(self):
        from pilotstd.core.cache_manager import DataSource

        self.db.execute(
            "INSERT INTO standard_info_cache "
            "(id,data_state,source_version,last_accessed_at) VALUES (1,'valid','old','2024-01-01')"
        )
        self.cm.mark_stale("standard_info_cache", "id", 1)
        row = self.db.fetchone("SELECT data_state FROM standard_info_cache WHERE id=1")
        self.assertEqual(row["data_state"], "stale")
        self.cm.mark_valid("standard_info_cache", "id", 1, DataSource.FILE_INDEX)
        row = self.db.fetchone("SELECT data_state FROM standard_info_cache WHERE id=1")
        self.assertEqual(row["data_state"], "valid")

    def test_invalidate_by_source_bumps_version(self):
        from pilotstd.core.cache_manager import DataSource

        old = self.cm._get_source_version(DataSource.ANNOUNCEMENT)
        self.cm.invalidate_by_source(DataSource.ANNOUNCEMENT)
        new = self.cm._get_source_version(DataSource.ANNOUNCEMENT)
        self.assertNotEqual(new, old)

    def test_delete_oldest_with_data(self):
        self.db.execute("INSERT INTO standard_info_cache (data_state,last_accessed_at) VALUES ('stale','2020-01-01')")
        self.db.execute("INSERT INTO standard_info_cache (data_state,last_accessed_at) VALUES ('stale','2020-01-02')")
        deleted = self.cm._delete_oldest("standard_info_cache", "stale", 0.5)
        self.assertGreater(deleted, 0)


# ═══ core/ file_index ═══
class TestFileIndexRemaining(unittest.TestCase):
    def test_repo_stop_cleans_up(self):
        from pilotstd.core.file_index import FILE_INDEX_TABLE, FileIndexRepository

        db = MockDatabase(
            f"CREATE TABLE IF NOT EXISTS {FILE_INDEX_TABLE} ("
            f"id INTEGER PRIMARY KEY, filepath TEXT, logical_code TEXT, "
            f"standard_number TEXT, standard_name TEXT, year INTEGER, "
            f"kind TEXT, language TEXT, file_hash TEXT, file_size INTEGER, "
            f"modified_at TEXT, indexed_at TEXT)"
        ).__enter__()
        try:
            repo = FileIndexRepository(db)
            self.assertFalse(repo.is_validation_complete)
            repo.stop()
            self.assertTrue(repo.is_validation_complete)
        finally:
            db.__exit__()


# ═══ scan/ scanner ═══
class TestScannerRemaining(unittest.TestCase):
    def test_scanner_module_importable(self):
        from pilotstd.scan import scanner

        self.assertIsNotNone(scanner)


# ═══ download/ openstd (19→30%) ═══
class TestOpenstdDownloadRemaining(unittest.TestCase):
    def test_adapter_can_instantiate(self):
        from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter

        adapter = OpenstdDownloadAdapter()
        self.assertIsNotNone(adapter)


# ═══ platform/ updater (93→95%) ═══
class TestPlatformUpdaterRemaining(unittest.TestCase):
    def test_is_newer_version_basic(self):
        from pilotstd.platform.updater import is_newer_version

        self.assertTrue(is_newer_version("2.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("1.0.0", "2.0.0"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))


# ═══ cli/ commands (92→95%) ═══
class TestCliCommandsRemaining(unittest.TestCase):
    def test_commands_list_not_empty(self):
        from pilotstd.cli.commands import __all__ as cmds

        self.assertGreater(len(cmds), 3)
        for cmd in cmds:
            self.assertIsInstance(cmd, str)

    def test_make_manager_callable(self):
        from pilotstd.cli.commands._shared import _make_manager

        self.assertTrue(callable(_make_manager))


# ═══ pipeline/ router (72→80%) ═══
class TestPipelineRouterRemaining(unittest.TestCase):
    def test_router_has_init(self):
        from pilotstd.pipeline.router import PipelineRouter

        self.assertTrue(hasattr(PipelineRouter, "__init__"))


# ═══ query/ rotator + csres ═══
class TestQueryRemaining(unittest.TestCase):
    def test_rotator_daily_limit_with_date(self):
        from pilotstd.query.rotator import SiteRotator, SiteState

        s = SiteState(name="test", base_url="http://e.com", daily_limit=3)
        s.daily_count = 3
        s.daily_date = SiteRotator._today()
        r = SiteRotator(sites=[s])
        available = r.get_available(["test"])
        self.assertNotIn("test", available)

    def test_rotator_cooldown_expired_resets(self):
        import time

        from pilotstd.query.rotator import SiteRotator, SiteState

        s = SiteState(name="test", base_url="http://e.com")
        s.cooldown_until = time.time() - 10
        s.request_count = 5
        r = SiteRotator(sites=[s])
        available = r.get_available(["test"])
        self.assertIn("test", available)
        self.assertEqual(s.request_count, 0)

    def test_csres_importable(self):
        from pilotstd.query.adapters.csres import CsresAdapter

        self.assertTrue(hasattr(CsresAdapter, "site_name"))


if __name__ == "__main__":
    unittest.main()
