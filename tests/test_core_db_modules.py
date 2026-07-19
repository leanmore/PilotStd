# tests/test_core_db_modules.py — 用 MockDatabase 补测 DB 密集型 core/ 模块

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tests.mocks.mock_database import MockDatabase

_VALIDITY_SCHEMA = """CREATE TABLE IF NOT EXISTS standard_validity (
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

_CACHE_SCHEMA = """CREATE TABLE IF NOT EXISTS standard_info_cache (id INTEGER PRIMARY KEY, standard_number TEXT, data_state TEXT DEFAULT 'valid');
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
    source_type TEXT DEFAULT '网页解析'
);
CREATE TABLE IF NOT EXISTS cache_metadata (source TEXT PRIMARY KEY, version TEXT, state TEXT, updated_at TEXT);"""

_FILE_INDEX_SCHEMA = """CREATE TABLE IF NOT EXISTS file_index (
    id INTEGER,
    file_path TEXT NOT NULL,
    logical_code TEXT NOT NULL DEFAULT '',
    number INTEGER NOT NULL DEFAULT 0,
    year INTEGER NOT NULL DEFAULT 0,
    part INTEGER NOT NULL DEFAULT '-1',
    std_name TEXT NOT NULL DEFAULT '',
    file_hash TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '现行',
    scanned_at TEXT NOT NULL DEFAULT '',
    last_checked TEXT
);"""


class TestValidityChecker(unittest.TestCase):
    def setUp(self):
        self.db = MockDatabase(_VALIDITY_SCHEMA).__enter__()

    def tearDown(self):
        self.db.__exit__()

    def test_register_new_standard(self):
        from pilotstd.core.validity_checker import ValidityChecker

        vc = ValidityChecker(self.db)
        vc.register_new_standard("GB/T 1.1-2020")
        row = self.db.fetchone("SELECT * FROM standard_validity WHERE standard_number=?", ("GB/T 1.1-2020",))
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "未知")

    def test_register_duplicate_skips(self):
        from pilotstd.core.validity_checker import ValidityChecker

        vc = ValidityChecker(self.db)
        vc.register_new_standard("GB/T 1.1-2020")
        vc.register_new_standard("GB/T 1.1-2020")
        rows = self.db.fetchall(
            "SELECT COUNT(*) as cnt FROM standard_validity WHERE standard_number=?", ("GB/T 1.1-2020",)
        )
        self.assertEqual(rows[0]["cnt"], 1)

    def test_get_due_standards(self):
        from datetime import datetime, timedelta, timezone

        from pilotstd.core.validity_checker import ValidityChecker

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.db.execute(
            "INSERT INTO standard_validity (standard_number,status,next_check_at,created_at,updated_at) VALUES (?,'未知',?,?,?)",
            ("GB/T 1.1-2020", past, past, past),
        )
        vc = ValidityChecker(self.db)
        due = vc.get_due_standards()
        self.assertIn("GB/T 1.1-2020", due)

    def test_count_due_standards(self):
        from datetime import datetime, timedelta, timezone

        from pilotstd.core.validity_checker import ValidityChecker

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.db.execute(
            "INSERT INTO standard_validity (standard_number,status,next_check_at,created_at,updated_at) VALUES (?,'未知',?,?,?)",
            ("TEST-1", past, past, past),
        )
        vc = ValidityChecker(self.db)
        cnt = vc.count_due_standards()
        self.assertGreaterEqual(cnt, 1)

    def test_random_slice(self):
        from pilotstd.core.validity_checker import ValidityChecker

        candidates = [f"STD-{i}" for i in range(100)]
        result = ValidityChecker.random_slice(candidates, 27, batch_size=25)
        self.assertLessEqual(len(result), 25)
        self.assertGreater(len(result), 0)


class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.db = MockDatabase(_CACHE_SCHEMA).__enter__()

    def tearDown(self):
        self.db.__exit__()

    def test_init(self):
        from pilotstd.core.cache_manager import CacheManager

        cm = CacheManager(self.db)
        self.assertIsNotNone(cm)

    def test_data_source_enum(self):
        from pilotstd.core.cache_manager import DataSource

        self.assertEqual(DataSource.FILE_INDEX.value, "file_index")
        self.assertEqual(DataSource.ANNOUNCEMENT.value, "announcement")

    def test_cache_state_enum(self):
        from pilotstd.core.cache_manager import CacheState

        self.assertEqual(CacheState.VALID.value, "valid")
        self.assertEqual(CacheState.STALE.value, "stale")

    def test_get_stats(self):
        from pilotstd.core.cache_manager import CacheManager

        cm = CacheManager(self.db)
        stats = cm.get_stats()
        self.assertIsInstance(stats, dict)

    def test_get_total_size_mb(self):
        from pilotstd.core.cache_manager import CacheManager

        cm = CacheManager(self.db)
        size = cm.get_total_size_mb()
        self.assertGreaterEqual(size, 0)

    def test_get_config(self):
        from pilotstd.core.cache_manager import CacheManager

        cm = CacheManager(self.db)
        cfg = cm.get_config()
        self.assertIsInstance(cfg, dict)


class TestFileIndexRepository(unittest.TestCase):
    def setUp(self):
        self.db = MockDatabase(_FILE_INDEX_SCHEMA).__enter__()

    def tearDown(self):
        self.db.__exit__()
        import time

        time.sleep(0.1)

    def test_init(self):
        from pilotstd.core.file_index import FileIndexRepository

        repo = FileIndexRepository(self.db)
        self.assertIsNotNone(repo)
        repo.stop()

    def test_initial_validation_not_complete(self):
        from pilotstd.core.file_index import FileIndexRepository

        repo = FileIndexRepository(self.db)
        self.assertFalse(repo.is_validation_complete)
        repo.stop()

    def test_stop_cleanly(self):
        from pilotstd.core.file_index import FileIndexRepository

        repo = FileIndexRepository(self.db)
        repo.stop()
        self.assertTrue(repo.is_validation_complete)

    def test_table_constants(self):
        from pilotstd.core.file_index import FILE_INDEX_TABLE

        self.assertEqual(FILE_INDEX_TABLE, "file_index")


if __name__ == "__main__":
    unittest.main()
