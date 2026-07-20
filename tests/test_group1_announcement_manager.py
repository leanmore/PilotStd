# tests/test_group1_announcement_manager.py — 第一组：announcement + manager 攻坚

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tests.mocks.mock_database import MockDatabase

# ═══════════════════════════════════════════════════════
# announcement/matcher.py
# ═══════════════════════════════════════════════════════

_MATCHER_SCHEMA = """CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_site TEXT NOT NULL,
    pid TEXT NOT NULL,
    announce_no TEXT,
    title TEXT NOT NULL,
    publish_date TEXT,
    source_url TEXT,
    attachment_url TEXT,
    raw_data TEXT,
    created_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    parse_status TEXT DEFAULT 'pending',
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS announcement_match (
    id INTEGER,
    standard_number TEXT NOT NULL,
    source_site TEXT NOT NULL DEFAULT 'announcement',
    result_json TEXT NOT NULL,
    cached_at TEXT NOT NULL,
    expires_at TEXT,
    source_version TEXT DEFAULT 'initial',
    data_state TEXT DEFAULT 'fresh',
    last_accessed_at TEXT,
    source TEXT NOT NULL DEFAULT 'announcement',
    status_history TEXT NOT NULL DEFAULT ''
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
CREATE TABLE IF NOT EXISTS file_index (
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
);
CREATE TABLE IF NOT EXISTS announcement_log (id INTEGER PRIMARY KEY);"""


class TestAnnouncementMatcher(unittest.TestCase):
    def setUp(self):
        self.db = MockDatabase(_MATCHER_SCHEMA).__enter__()

    def tearDown(self):
        self.db.__exit__()

    def test_init(self):
        from pilotstd.announcement.matcher import AnnouncementMatcher

        m = AnnouncementMatcher(self.db)
        self.assertIsNotNone(m)

    def test_match_empty_items(self):
        from pilotstd.announcement.matcher import AnnouncementMatcher

        m = AnnouncementMatcher(self.db)
        result = m.match_and_update([])
        self.assertEqual(result["matched"], 0)

    def test_normalize_items(self):
        from pilotstd.announcement.matcher import AnnouncementMatcher

        items = [
            {"announce_no": "2024-001", "publish_date": "2024-01-15", "announcement_title": "公告1"},
            {"announce_no": "2024-001", "publish_date": "", "announcement_title": ""},
        ]
        normalized = AnnouncementMatcher._normalize(items)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["publish_date"], "2024-01-15")

    def test_match_and_update_with_items(self):
        from pilotstd.announcement.matcher import AnnouncementMatcher

        m = AnnouncementMatcher(self.db)
        items = [
            {
                "announce_no": "2024-001",
                "publish_date": "2024-01-15",
                "announcement_title": "测试公告",
                "standard_number": "GB/T 1.1-2020",
                "standard_name": "标准化导则",
                "source_site": "samr_gb",
            }
        ]
        result = m.match_and_update(items)
        self.assertIsInstance(result, dict)
        self.assertIn("matched", result)


# ═══════════════════════════════════════════════════════
# announcement/base.py — 更深覆盖
# ═══════════════════════════════════════════════════════


class TestAnnouncementBaseDeep(unittest.TestCase):
    def setUp(self):
        from pilotstd.announcement.base import BaseAnnounceCrawler

        class TestCrawler(BaseAnnounceCrawler):
            @property
            def site_name(self):
                return "test_crawler"

            @property
            def standard_type(self):
                return "gb"

            @property
            def _list_url(self):
                return "https://e.com/api"

            @property
            def _detail_url(self):
                return "https://e.com/detail"

        self.crawler = TestCrawler()

    def test_source_site(self):
        self.assertEqual(self.crawler.source_site, "announcement_gb")

    def test_cb_threshold_default(self):
        from pilotstd.announcement._circuit_breaker import _DEFAULT_FAILURE_THRESHOLD

        with patch("pilotstd.core.config.ConfigManager") as mock_cm:
            mock_cm.return_value.get.return_value = None
            self.assertEqual(self.crawler._cb._threshold, _DEFAULT_FAILURE_THRESHOLD)

    def test_cb_durations_default(self):
        from pilotstd.announcement._circuit_breaker import _DEFAULT_FREEZE_DURATIONS

        with patch("pilotstd.core.config.ConfigManager") as mock_cm:
            mock_cm.return_value.get.return_value = None
            self.assertEqual(self.crawler._cb._durations, list(_DEFAULT_FREEZE_DURATIONS))

    def test_record_success_resets_streak(self):
        self.crawler._cb.fail_streak = 10
        with patch.object(self.crawler, "_cb_save_health"):
            self.crawler._cb_record_success()
        self.assertEqual(self.crawler._cb.fail_streak, 0)

    def test_record_failure_increments(self):
        self.crawler._cb.fail_streak = 0
        with patch.object(self.crawler, "_cb_save_health"):
            result = self.crawler._cb_record_failure()
        self.assertEqual(self.crawler._cb.fail_streak, 1)
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════
# announcement/parser.py — 更深度覆盖
# ═══════════════════════════════════════════════════════


class TestAnnouncementParserDeep(unittest.TestCase):
    def test_parse_html_table_multiple_rows(self):
        from pilotstd.announcement.parser import parse_html_table

        html = """<table>
        <tr><th>序号</th><th>std_code</th><th>std_name</th><th>publish_date</th></tr>
        <tr><td>1</td><td>GB/T 1.1-2020</td><td>标准化工作导则</td><td>2020-03-31</td></tr>
        <tr><td>2</td><td>GB/T 19000-2016</td><td>质量管理体系</td><td>2016-12-30</td></tr>
        </table>"""
        results = parse_html_table(html)
        self.assertIsInstance(results, list)

    def test_parse_announcement_meta(self):
        from pilotstd.announcement.parser import parse_announcement_meta

        html = "<div>公告标题：2024年国家标准公告</div><div>发布部门：标准委</div>"
        meta = parse_announcement_meta(html)
        self.assertIsInstance(meta, dict)

    def test_parse_text_table(self):
        from pilotstd.announcement.parser import parse_text_table

        text = "GB/T 1.1-2020 标准化工作导则 2020-03-31"
        result = parse_text_table(text)
        self.assertIsInstance(result, list)

    def test_replaces_pattern(self):
        from pilotstd.announcement.parser import REPLACES_PATTERN

        m = REPLACES_PATTERN.search("被GB/T 1.1-2020代替")
        self.assertIsNotNone(m)

    def test_code_key(self):
        from pilotstd.announcement.parser import _code_key

        key = _code_key({"std_code": "GB/T", "std_name": "Standard"})
        self.assertIn("GB/T", key)

    def test_parse_wps_text_realistic(self):
        from pilotstd.announcement.parser import parse_wps_text

        raw = "GB/T 1.1-2020\x00标准化工作导则\x00".encode("utf-16-le")
        result = parse_wps_text(raw)
        self.assertIsInstance(result, str)


# ═══════════════════════════════════════════════════════
# manager/announce_service.py
# ═══════════════════════════════════════════════════════

_SERVICE_SCHEMA = """CREATE TABLE IF NOT EXISTS fetch_checkpoint (
    id INTEGER,
    source_site TEXT NOT NULL,
    last_fetched_at TEXT NOT NULL DEFAULT '',
    last_notice_date TEXT NOT NULL DEFAULT '',
    since_date_override TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS fetch_failures (
    id INTEGER,
    task_type TEXT NOT NULL,
    source_site TEXT NOT NULL,
    since_date TEXT NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TEXT,
    resolved BOOLEAN DEFAULT 'FALSE',
    created_at TEXT DEFAULT 'CURRENT_TIMESTAMP'
);CREATE TABLE IF NOT EXISTS fetch_locks (
    lock_key TEXT,
    locked_at TEXT,
    locked_by TEXT
);"""


class TestAnnounceService(unittest.TestCase):
    def setUp(self):
        self.db = MockDatabase(_SERVICE_SCHEMA).__enter__()
        self.mock_file_index = MagicMock()
        self.mock_file_index._db = self.db

    def tearDown(self):
        self.db.__exit__()

    def test_init(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index)
        self.assertIsNotNone(svc)

    def test_init_with_ocr_config(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index, ocr_config={"baidu": {}})
        self.assertIsNotNone(svc)

    def test_get_or_create_engine(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index)
        engine = svc._get_or_create_engine()
        self.assertIsNotNone(engine)

    def test_write_checkpoint_new(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index)
        svc._write_checkpoint("test_site", "2024-06-01")
        row = self.db.fetchone("SELECT * FROM fetch_checkpoint WHERE source_site=?", ("test_site",))
        self.assertIsNotNone(row)

    def test_write_checkpoint_empty_date(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index)
        svc._write_checkpoint("test_site", "")
        row = self.db.fetchone("SELECT * FROM fetch_checkpoint WHERE source_site=?", ("test_site",))
        self.assertIsNone(row)

    def test_record_fetch_failure(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index)
        svc._record_fetch_failure("fetch", "site_a", "2024-01-01", "timeout")
        rows = self.db.fetchall("SELECT * FROM fetch_failures")
        self.assertEqual(len(rows), 1)

    def test_acquire_manual_lock(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index)
        result = svc._acquire_manual_lock()
        self.assertTrue(result)

    def test_ocr_provider_lazy_init(self):
        from pilotstd.manager.announce_service import AnnounceService

        svc = AnnounceService(self.mock_file_index, ocr_config={"test": True})
        self.assertIsNone(svc._ocr_provider)


# ═══════════════════════════════════════════════════════
# manager/facade/_query.py — 更深度覆盖
# ═══════════════════════════════════════════════════════


class TestQueryHandlerDeep(unittest.TestCase):
    def setUp(self):
        self.core = MagicMock()
        self.core.cfg = MagicMock()
        self.core.cfg.get.return_value = None
        self.core.query_engine = MagicMock()

    def test_pending_reasons(self):
        from pilotstd.manager.facade._query import QueryHandler

        h = QueryHandler(self.core)
        self.assertIn("older", h._PENDING_REASONS)
        self.assertIn("mismatch", h._PENDING_REASONS)

    def test_expire_statuses(self):
        from pilotstd.manager.facade._query import QueryHandler

        h = QueryHandler(self.core)
        self.assertIn("废止", h._EXPIRE_STATUSES)

    def test_query_announcement_timeout(self):
        import requests

        from pilotstd.manager.facade._query import QueryHandler

        self.core.cfg.get.side_effect = lambda k, d=None: {
            "query.announcement_url": "http://localhost:9028",
            "query.announcement_api_key": "test_key",
            "network.timeout": 5,
        }.get(k, d)
        h = QueryHandler(self.core)
        with patch("pilotstd.manager.facade._query_exec.requests.get", side_effect=requests.exceptions.Timeout()):
            result = h._query_announcement_match("GB/T 1.1")
            self.assertIsNone(result)

    def test_query_announcement_connection_error(self):
        import requests

        from pilotstd.manager.facade._query import QueryHandler

        self.core.cfg.get.side_effect = lambda k, d=None: {
            "query.announcement_url": "http://localhost:9028",
            "query.announcement_api_key": "test_key",
            "network.timeout": 5,
        }.get(k, d)
        h = QueryHandler(self.core)
        with patch(
            "pilotstd.manager.facade._query_exec.requests.get", side_effect=requests.exceptions.ConnectionError()
        ):
            result = h._query_announcement_match("GB/T 1.1")
            self.assertIsNone(result)

    def test_query_announcement_found(self):
        from pilotstd.manager.facade._query import QueryHandler

        self.core.cfg.get.side_effect = lambda k, d=None: {
            "query.announcement_url": "http://localhost:9028",
            "query.announcement_api_key": "test_key",
            "network.timeout": 5,
        }.get(k, d)
        h = QueryHandler(self.core)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"found": True, "data": {"standard_name": "Test"}, "cached_at": "2024-01-01"}
        with patch("pilotstd.manager.facade._query_exec.requests.get", return_value=mock_resp):
            result = h._query_announcement_match("GB/T 1.1")
            self.assertIsNotNone(result)
            self.assertEqual(result["data"]["standard_name"], "Test")


# ═══════════════════════════════════════════════════════
# manager/organize/mirror.py
# ═══════════════════════════════════════════════════════


class TestOrganizerMirror(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmpdir = tempfile.mkdtemp()
        self.mixin = MagicMock()
        self.mixin._cfg = MagicMock()
        self.mixin._cfg.get.return_value = "过期作废"
        self.mixin._FALLBACK_SKIP_FILES = frozenset()
        self.mixin._FALLBACK_SKIP_PREFIX = ()
        self.mixin._skipped_source_files = frozenset()
        from pilotstd.manager.organize.mirror import OrganizerMirrorMixin

        # Bind methods
        self.mixin.organize_skipped_dirs = OrganizerMirrorMixin.organize_skipped_dirs.__get__(self.mixin)
        self.mixin._resolve_skipped_relative = OrganizerMirrorMixin._resolve_skipped_relative.__get__(self.mixin)
        self.mixin._check_path_traversal = OrganizerMirrorMixin._check_path_traversal.__get__(self.mixin)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_path_traversal_safe(self):
        root = self.tmpdir
        dst = os.path.join(root, "subdir", "file.txt")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w") as f:
            f.write("test")
        result = self.mixin._check_path_traversal(dst, root, self.tmpdir)
        self.assertTrue(result)

    def test_organize_skipped_dirs_empty(self):
        result = self.mixin.organize_skipped_dirs([])
        self.assertEqual(result["moved"], 0)

    def test_resolve_skipped_relative_nonexistent(self):
        result = self.mixin._resolve_skipped_relative("/nonexistent/path", self.tmpdir, "/src")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
