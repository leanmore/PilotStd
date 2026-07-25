# tests/test_announcement_matcher_full.py
# AnnouncementMatcher 完整单元测试

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.announcement.matcher import AnnouncementMatcher, clean_announcement_content
from tests.mocks.mock_database import MockDatabase

# ── 测试用数据 ──────────────────────────────────────────────────
# 建表 SQL（模拟 announcement_record 和 announcement_match）
INIT_SQL = """
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_site TEXT,
    pid TEXT,
    announce_no TEXT,
    title TEXT,
    publish_date TEXT,
    source_url TEXT,
    attachment_url TEXT,
    raw_data TEXT,
    created_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    parse_status TEXT DEFAULT 'pending',
    updated_at TEXT
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
);CREATE TABLE IF NOT EXISTS announcement_match (
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
);CREATE TABLE IF NOT EXISTS file_index (
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
    last_checked TEXT,
    raw_number TEXT NOT NULL DEFAULT ''
);"""


class TestAnnouncementMatcherInit(unittest.TestCase):
    """构造函数测试。"""

    def test_init_stores_db(self):
        db = MagicMock()
        matcher = AnnouncementMatcher(db)
        self.assertIs(matcher._db, db)


class TestNormalize(unittest.TestCase):
    """_normalize 测试 —— 按 announce_no 归一化。"""

    def test_single_group_unifies_metadata(self):
        items = [
            {
                "announce_no": "2024-001",
                "publish_date": "2024-01-15",
                "announcement_title": "公告1",
                "std_code": "GB/T 1.1-2020",
            },
            {
                "announce_no": "2024-001",
                "publish_date": "",
                "std_code": "GB/T 2.2-2020",
            },  # 无 announcement_title 键，setdefault 生效
        ]
        result = AnnouncementMatcher._normalize(items)
        for item in result:
            self.assertEqual(item["publish_date"], "2024-01-15")
            self.assertEqual(item["announcement_title"], "公告1")
            self.assertEqual(item["standard_count"], 2)

    def test_multiple_groups_independent(self):
        items = [
            {"announce_no": "2024-001", "publish_date": "2024-01-15", "std_code": "A"},
            {"announce_no": "2024-002", "publish_date": "2024-02-20", "std_code": "B"},
        ]
        result = AnnouncementMatcher._normalize(items)
        self.assertEqual(result[0]["standard_count"], 1)
        self.assertEqual(result[1]["standard_count"], 1)
        self.assertEqual(result[0]["publish_date"], "2024-01-15")
        self.assertEqual(result[1]["publish_date"], "2024-02-20")

    def test_first_non_empty_value_wins(self):
        items = [
            {"announce_no": "X", "publish_date": "", "std_code": "C1"},
            {"announce_no": "X", "publish_date": "2024-05-01", "std_code": "C2"},
            {"announce_no": "X", "publish_date": "2024-06-01", "std_code": "C3"},
        ]
        result = AnnouncementMatcher._normalize(items)
        for item in result:
            self.assertEqual(item["publish_date"], "2024-05-01")

    def test_empty_announce_no_passthrough(self):
        items = [
            {"announce_no": "", "publish_date": "2024-01-15", "std_code": "X"},
        ]
        result = AnnouncementMatcher._normalize(items)
        self.assertEqual(result[0]["publish_date"], "2024-01-15")

    def test_setdefault_announcement_title(self):
        """announcement_title 已有时不覆盖（setdefault 对已存在键不生效，即使值为空字符串）。"""
        items = [
            {"announce_no": "X", "announcement_title": "已有标题", "publish_date": "", "std_code": "C1"},
            {"announce_no": "X", "publish_date": "", "std_code": "C2"},  # 不存在键，会被 setdefault
        ]
        result = AnnouncementMatcher._normalize(items)
        self.assertEqual(result[0]["announcement_title"], "已有标题")
        self.assertEqual(result[1]["announcement_title"], "已有标题")  # setdefault 生效


class TestParseStdCode(unittest.TestCase):
    """_parse_std_code 测试 —— 委托 parse_std_number。"""

    def setUp(self):
        self.db = MagicMock()
        self.matcher = AnnouncementMatcher(self.db)

    def test_valid_gb_code(self):
        result = self.matcher._parse_std_code("GB/T 1.1-2020")
        self.assertIsNotNone(result)
        self.assertEqual(result["logical_code"], "GBT")  # parse_std_number 去除 /
        self.assertEqual(result["number"], 1)  # type: ignore[index]

    def test_valid_db_code(self):
        result = self.matcher._parse_std_code("DB35/T 1234-2020")
        self.assertIsNotNone(result)
        self.assertEqual(result["logical_code"], "DB35T")  # parse_std_number 去除 /
        self.assertEqual(result["number"], 1234)  # type: ignore[index]

    def test_invalid_code_returns_none(self):
        self.assertIsNone(self.matcher._parse_std_code("不是标准号"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(self.matcher._parse_std_code(""))


class TestFindInFileIndex(unittest.TestCase):
    """_find_in_file_index 测试。"""

    def test_queries_with_code_and_number(self):
        db = MagicMock()
        db.fetchall.return_value = [{"id": 1, "logical_code": "GB/T", "number": 1}]
        matcher = AnnouncementMatcher(db)

        result = matcher._find_in_file_index("GB/T", 1)

        self.assertEqual(len(result), 1)
        db.fetchall.assert_called_once()


class TestBuildCacheRow(unittest.TestCase):
    """_build_cache_row 测试。"""

    def setUp(self):
        self.db = MagicMock()
        self.matcher = AnnouncementMatcher(self.db)

    def test_new_match_with_implementation_date(self):
        fi_row = {"logical_code": "GBT", "number": 1, "year": 2020, "std_name": "测试标准"}
        item = {
            "std_code": "GB/T 1.1-2020",
            "implementation_date": "2027-06-01",  # 未来日期 → "即将实施"
            "publish_date": "2020-03-31",
            "replaces_code": "",
            "announcement_title": "公告1",
            "attachment_url": "",
            "attachment_path": "",
        }
        cache_rows = []

        updated = self.matcher._build_cache_row(fi_row, item, "new", "test_site", "2024-01-01T00:00:00", cache_rows)

        self.assertTrue(updated)
        self.assertEqual(len(cache_rows), 1)
        std_number, source, result_json, cached_at, expires_at = cache_rows[0]
        self.assertIn("GBT 1-2020", std_number)
        self.assertIn("即将实施", result_json)

    def test_replaced_match_status(self):
        fi_row = {"logical_code": "GB/T", "number": 1, "year": 2009, "std_name": "旧标准"}
        item = {
            "std_code": "GB/T 1.1-2020",
            "implementation_date": "",
            "publish_date": "",
            "replaces_code": "",
        }
        cache_rows = []

        self.matcher._build_cache_row(fi_row, item, "replaced", "test_site", "now", cache_rows)

        self.assertIn("被代替", cache_rows[0][2])

    def test_current_status_when_no_implementation_date(self):
        fi_row = {"logical_code": "GB/T", "number": 1, "year": 2020, "std_name": "现行标准"}
        item = {
            "std_code": "GB/T 1.1-2020",
            "implementation_date": "",
            "publish_date": "",
            "replaces_code": "",
        }
        cache_rows = []

        self.matcher._build_cache_row(fi_row, item, "new", "test_site", "now", cache_rows)

        self.assertIn("现行", cache_rows[0][2])

    def test_cache_row_structure(self):
        fi_row = {"logical_code": "GB/T", "number": 1, "year": 2020, "std_name": "测试"}
        item = {
            "std_code": "GB/T 1.1-2020",
            "implementation_date": "2020-10-01",
            "publish_date": "2020-03-31",
            "replaces_code": "",
            "announcement_title": "标题",
            "attachment_url": "http://example.com/doc.pdf",
            "attachment_path": "/tmp/doc.pdf",
        }
        cache_rows = []

        self.matcher._build_cache_row(fi_row, item, "new", "announcement_gb", "2024-01-01", cache_rows)

        std_number, source, result_json, cached_at, expires_at = cache_rows[0]
        self.assertIn("standard_name", result_json)
        self.assertIn("match_status", result_json)
        self.assertIn('"is_adopted": false', result_json)
        self.assertIn("announcement_gb", result_json)


class TestProcessItem(unittest.TestCase):
    """_process_item 测试。"""

    def setUp(self):
        self.db = MagicMock()
        self.matcher = AnnouncementMatcher(self.db)

    def test_no_std_code_skips(self):
        log_rows = []
        cache_rows = []
        result = {"matched": 0, "updated": 0, "details": []}
        item = {"std_code": "", "announce_no": "X"}

        self.matcher._process_item(item, "test_site", "now", log_rows, cache_rows, result)

        self.assertEqual(log_rows, [])

    def test_unmatched_adds_log_only(self):
        """未匹配到 file_index：只写日志，不写缓存。"""
        self.db.fetchall.return_value = []
        log_rows = []
        cache_rows = []
        result = {"matched": 0, "updated": 0, "details": []}
        item = {
            "std_code": "GB/T 99999-2020",
            "announce_no": "2024-001",
            "publish_date": "2024-01-15",
            "_pid": "p001",
            "std_name": "未知标准",
        }

        self.matcher._process_item(item, "test_site", "now", log_rows, cache_rows, result)

        self.assertEqual(len(log_rows), 1)
        self.assertEqual(len(cache_rows), 0)
        self.assertEqual(result["matched"], 0)

    def test_matched_adds_log_and_cache(self):
        """匹配到 file_index：写日志和缓存。"""
        self.db.fetchall.return_value = [{"logical_code": "GB/T", "number": 1, "year": 2020, "std_name": "标准化导则"}]
        log_rows = []
        cache_rows = []
        result = {"matched": 0, "updated": 0, "details": []}
        item = {
            "std_code": "GB/T 1.1-2020",
            "announce_no": "2024-001",
            "publish_date": "2024-01-15",
            "implementation_date": "2020-10-01",
            "_pid": "p001",
            "std_name": "标准化导则",
            "replaces_code": "",
            "announcement_title": "公告1",
            "standard_count": 1,
        }

        self.matcher._process_item(item, "test_site", "now", log_rows, cache_rows, result)

        self.assertEqual(len(log_rows), 1)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["updated"], 1)

    def test_replaces_code_fallback(self):
        """std_code 未匹配时，用 replaces_code 重试。"""
        self.db.fetchall.side_effect = [
            [],  # 第一次：std_code 无匹配
            [{"logical_code": "GB/T", "number": 1, "year": 2009, "std_name": "旧版"}],  # replaces_code 匹配
        ]
        log_rows = []
        cache_rows = []
        result = {"matched": 0, "updated": 0, "details": []}
        item = {
            "std_code": "GB/T 1.1-2020",
            "replaces_code": "GB/T 1.1-2009",
            "announce_no": "2024-001",
            "_pid": "p001",
            "std_name": "新版",
            "publish_date": "",
        }

        self.matcher._process_item(item, "test_site", "now", log_rows, cache_rows, result)

        self.assertEqual(result["matched"], 1)

    def test_log_row_contains_all_fields(self):
        self.db.fetchall.return_value = []
        log_rows = []
        cache_rows = []
        result = {"matched": 0, "updated": 0, "details": []}
        item = {
            "std_code": "GB/T 99999-2020",
            "announce_no": "2024-001",
            "publish_date": "2024-01-15",
            "_pid": "p001",
            "std_name": "测试",
            "announcement_title": "公告标题",
            "standard_count": 3,
        }

        self.matcher._process_item(item, "announcement_gb", "2024-01-01T00:00:00", log_rows, cache_rows, result)

        row = log_rows[0]
        self.assertEqual(len(row), 16)
        self.assertEqual(row[0], "announcement_gb")  # source_site
        self.assertEqual(row[1], "p001")  # pid
        self.assertEqual(row[2], "2024-001")  # announce_no
        self.assertEqual(row[3], "GB/T 99999-2020")  # standard_number


class TestGetCompletePids(unittest.TestCase):
    """_get_complete_pids 测试。"""

    def test_returns_pids_with_all_names(self):
        db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("pid001",), ("pid002",)]
        db.execute.return_value = mock_cursor
        matcher = AnnouncementMatcher(db)

        result = matcher._get_complete_pids("announcement_gb")

        self.assertEqual(result, {"pid001", "pid002"})

    def test_returns_empty_set(self):
        db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        db.execute.return_value = mock_cursor
        matcher = AnnouncementMatcher(db)

        result = matcher._get_complete_pids("announcement_gb")

        self.assertEqual(result, set())


class TestBulkInsertRecords(unittest.TestCase):
    """_bulk_insert_records 测试 —— 批量写入 announcement_record。"""

    def setUp(self):
        self.db = MagicMock()
        self.matcher = AnnouncementMatcher(self.db)

    def test_empty_rows_noop(self):
        self.matcher._bulk_insert_records([])
        self.db.execute.assert_not_called()

    def test_single_row_insert(self):
        rows = [
            (
                "site",
                "p1",
                "ann1",
                "GB/T 1.1-2020",
                "name",
                "2024-01-15",
                "",
                "",
                "",
                0.0,
                1,
                "draft",
                "now",
                1,
                "title",
                5,
            )
        ]
        self.matcher._bulk_insert_records(rows)
        self.db.execute.assert_called_once()
        sql = self.db.execute.call_args[0][0]
        self.assertIn("INSERT OR IGNORE", sql)
        self.assertIn("announcement_record", sql)

    def test_batch_splitting(self):
        """超过 BATCH_SIZE 时自动分批。"""
        rows = [
            ("site", f"p{i}", "ann", "GB/T X", "n", "d", "", "", "", 0.0, 1, "draft", "t", 1, "t", 5) for i in range(60)
        ]
        self.matcher._bulk_insert_records(rows)
        # 60 行 -> 50 + 10 = 2 批
        self.assertEqual(self.db.execute.call_count, 2)


class TestBulkUpsertCache(unittest.TestCase):
    """_bulk_upsert_cache 测试 —— 批量写入 announcement_match。"""

    def setUp(self):
        self.db = MagicMock()
        self.matcher = AnnouncementMatcher(self.db)

    def test_empty_rows_noop(self):
        self.matcher._bulk_upsert_cache([])
        self.db.execute.assert_not_called()

    def test_single_row_upsert(self):
        rows = [("GBT 1-2020", "announcement_gb", '{"status":"现行"}', "2024-01-01", None)]
        self.matcher._bulk_upsert_cache(rows)
        self.db.execute.assert_called_once()
        sql = self.db.execute.call_args[0][0]
        self.assertIn("INSERT OR REPLACE", sql)
        self.assertIn("announcement_match", sql)

    def test_batch_splitting(self):
        rows = [("X", "s", "{}", "t", None) for _ in range(60)]
        self.matcher._bulk_upsert_cache(rows)
        self.assertEqual(self.db.execute.call_count, 2)


class TestMatchAndUpdate(unittest.TestCase):
    """match_and_update 集成测试 —— 使用内存 SQLite。"""

    def test_empty_items_returns_zero(self):
        """空列表返回 matched=0, updated=0。"""
        with MockDatabase(INIT_SQL) as db:
            matcher = AnnouncementMatcher(db)
            result = matcher.match_and_update([], "announcement_gb")
            self.assertEqual(result["matched"], 0)
            self.assertEqual(result["updated"], 0)

    def test_no_match_writes_log_only(self):
        """无匹配项：只写 announcement_record，不写缓存。"""
        with MockDatabase(INIT_SQL) as db:
            matcher = AnnouncementMatcher(db)
            items = [
                {
                    "std_code": "GB/T 99999-2020",
                    "announce_no": "2024-001",
                    "publish_date": "2024-01-15",
                    "std_name": "未知标准",
                    "_pid": "p001",
                    "replaces_code": "",
                    "announcement_title": "公告1",
                }
            ]
            result = matcher.match_and_update(items, "announcement_gb")
            self.assertEqual(result["matched"], 0)
            self.assertEqual(result["updated"], 0)
            # 验证 announcement_record 有数据
            count = db.fetchone("SELECT COUNT(*) AS cnt FROM announcement_record")
            self.assertEqual(count["cnt"], 1)

    def test_with_matching_file_index(self):
        """有匹配项：写 announcement_record 和 announcement_match。"""
        with MockDatabase(INIT_SQL) as db:
            # 预先插入 file_index 记录
            fi_sql = "INSERT INTO file_index (logical_code, number, year, part, std_name, file_path)"
            fi_sql += " VALUES (?, ?, ?, ?, ?, ?)"
            db.execute(
                fi_sql,
                ("GBT", 1, 2020, "", "标准化工作导则", "/path/to/file.pdf"),  # parse_std_number 返回 code="GBT"
            )
            matcher = AnnouncementMatcher(db)
            items = [
                {
                    "std_code": "GB/T 1.1-2020",
                    "announce_no": "2024-001",
                    "publish_date": "2024-01-15",
                    "implementation_date": "2027-06-01",  # 未来日期
                    "std_name": "标准化导则",
                    "_pid": "p001",
                    "replaces_code": "",
                    "announcement_title": "公告1",
                    "standard_count": 1,
                }
            ]
            result = matcher.match_and_update(items, "announcement_gb")
            self.assertEqual(result["matched"], 1)
            self.assertEqual(result["updated"], 1)
            # 验证缓存表
            cache = db.fetchone("SELECT * FROM announcement_match WHERE standard_number=?", ("GBT 1-2020",))
            self.assertIsNotNone(cache)
            # 用 json 检查缓存内容
            import json

            cache_data = json.loads(cache["result_json"])
            self.assertIn("即将实施", cache_data["status"])

    def test_multiple_items_mixed_results(self):
        """混合：部分匹配、部分不匹配。"""
        with MockDatabase(INIT_SQL) as db:
            fi_sql = "INSERT INTO file_index (logical_code, number, year, part, std_name, file_path)"
            fi_sql += " VALUES (?, ?, ?, ?, ?, ?)"
            db.execute(
                fi_sql,
                ("GBT", 1, 2020, "", "标准化导则", "/path/to/file.pdf"),
            )
            matcher = AnnouncementMatcher(db)
            items = [
                {
                    "std_code": "GB/T 1.1-2020",
                    "announce_no": "2024-A",
                    "publish_date": "2024-01-15",
                    "implementation_date": "2027-06-01",  # 未来日期
                    "std_name": "标准化导则",
                    "_pid": "p001",
                    "replaces_code": "",
                    "announcement_title": "公告A",
                    "standard_count": 2,
                },
                {
                    "std_code": "GB/T 99999-2020",
                    "announce_no": "2024-A",
                    "publish_date": "2024-01-15",
                    "std_name": "不存在",
                    "_pid": "p001",
                    "replaces_code": "",
                    "announcement_title": "公告A",
                    "standard_count": 2,
                },
            ]
            result = matcher.match_and_update(items, "announcement_gb")
            self.assertEqual(result["matched"], 1)
            # 两条都需要标准化（归一化后 standard_count=2）
            count = db.fetchone("SELECT COUNT(*) AS cnt FROM announcement_record")
            self.assertEqual(count["cnt"], 2)

    def test_normalize_called_in_match_and_update(self):
        """match_and_update 内部调用 _normalize。"""
        with MockDatabase(INIT_SQL) as db:
            matcher = AnnouncementMatcher(db)
            items = [
                {
                    "std_code": "GB/T 99999-2020",
                    "announce_no": "2024-B",
                    "publish_date": "",
                    "std_name": "X",
                    "_pid": "p002",
                    "replaces_code": "",
                    # 无 announcement_title 键，setdefault 会从同组第一条获取
                },
                {
                    "std_code": "GB/T 88888-2020",
                    "announce_no": "2024-B",
                    "publish_date": "2024-06-01",
                    "std_name": "Y",
                    "_pid": "p002",
                    "replaces_code": "",
                    "announcement_title": "公告B标题",
                },
            ]
            matcher.match_and_update(items, "announcement_gb")
            # 归一化后第二条的空字段被第一条的非空值填充
            rows = db.fetchall("SELECT * FROM announcement_record WHERE announce_no=?", ("2024-B",))
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row["publish_date"], "2024-06-01")
                self.assertEqual(row["announcement_title"], "公告B标题")


class TestMatchAndUpdateWithMockDb(unittest.TestCase):
    """match_and_update 测试 —— 使用 MagicMock（验证方法调用）。"""

    def setUp(self):
        self.db = MagicMock()
        self.matcher = AnnouncementMatcher(self.db)

    @patch.object(AnnouncementMatcher, "_process_item")
    def test_process_item_called_for_each(self, mock_process):
        items = [
            {"std_code": "A", "announce_no": "1"},
            {"std_code": "B", "announce_no": "2"},
        ]
        self.matcher.match_and_update(items, "site")
        self.assertEqual(mock_process.call_count, 2)

    @patch.object(AnnouncementMatcher, "_process_item")
    @patch.object(AnnouncementMatcher, "_bulk_insert_records")
    @patch.object(AnnouncementMatcher, "_bulk_upsert_cache")
    def test_bulk_methods_not_called_when_empty(self, mock_upsert, mock_insert, mock_process):
        self.matcher.match_and_update([], "site")
        mock_insert.assert_not_called()
        mock_upsert.assert_not_called()


# ── clean_announcement_content 测试样例 ──────────────────────

# 国标公告正文样例（含标准号表格 + 引言 + 落款）
GB_CONTENT_SAMPLE = """国家市场监督管理总局（国家标准化管理委员会）批准发布以下国家标准，现予以公告。

序号\t标准编号\t标准名称\t代替标准\t实施日期
1\tGB/T 1.1-2020\t标准化工作导则 第1部分\tGB/T 1.1-2009\t2020-10-01
2\tGB/T 19000-2016\t质量管理体系 基础和术语\t\t2017-07-01
3\tGB/T 20000.1-2014\t标准化工作指南 第1部分\tGB/T 20000.1-2014\t2015-06-01

一、上述标准中，GB/T 1.1-2020《标准化工作导则 第1部分：标准化文件的结构和起草规则》代替 GB/T 1.1-2009。

国家市场监督管理总局 国家标准化管理委员会 2026-07-02"""

# 行业月报正文样例（含统计汇总表 + 废止段落）
HB_MONTHLY_SAMPLE = """工业和信息化部发布行业标准备案月报。

序号\t标准发布部门\t省市区\t行业领域\t备案数量
1\t工业和信息化部\t北京市\t化工\t15
2\t国家能源局\t山东省\t能源\t8
合计\t\t\t\t23

2026年5月工业和信息化部、国家能源局等3个部门8个省市共发布278项行业标准，共废止21项行业标准。

工业和信息化部 2026-07-02"""

# 地方月报正文样例（含统计汇总表 + 废止段落）
DB_MONTHLY_SAMPLE = """国家标准化管理委员会发布地方标准备案月报。

序号\t省市区\t标准发布部门\t行业领域\t备案数量
1\t浙江省\t浙江省市场监督管理局\t农业\t12
2\t广东省\t广东省市场监督管理局\t服务业\t8
合计\t\t\t\t20

2026年5月浙江省、广东省等2个省市区共发布20项地方标准，共废止5项地方标准。

国家标准化管理委员会 2026-07-02"""


class TestCleanAnnouncementContent(unittest.TestCase):
    """clean_announcement_content 状态机清洗测试。"""

    def test_empty_content(self):
        self.assertEqual(clean_announcement_content(""), "")

    def test_gb_strips_standard_table(self):
        """国标公告：表格行剥离，引言和总结段落保留。"""
        result = clean_announcement_content(GB_CONTENT_SAMPLE)
        # 表头关键词不应出现
        self.assertNotIn("代替标准", result)
        self.assertNotIn("实施日期", result)
        # 表格行首的数字序号+标准号组合不应出现
        self.assertNotIn("\tGB/T", result)
        # 正文引言应保留
        self.assertIn("批准发布以下国家标准", result)
        self.assertIn("现予以公告", result)
        # 总结段落应保留（含标准号引用是正文正常内容）
        self.assertIn("上述标准中", result)
        self.assertIn("代替", result)
        # 落款应保留
        self.assertIn("国家市场监督管理总局", result)
        self.assertIn("国家标准化管理委员会", result)
        self.assertIn("2026-07-02", result)
        self.assertIn("<p>", result)

    def test_gb_date_split(self):
        """国标公告：落款日期拆分为独立右对齐行。"""
        result = clean_announcement_content(GB_CONTENT_SAMPLE)
        self.assertIn('style="text-align:right"', result)
        self.assertIn("2026-07-02", result)

    def test_hb_monthly_preserves_abolition(self):
        """行业月报：废止段落和末尾日期保留，统计表剥离。"""
        result = clean_announcement_content(HB_MONTHLY_SAMPLE)
        # 不应含统计表数据
        self.assertNotIn("工业和信息化部\t北京市", result)
        self.assertNotIn("备案数量", result)
        # 应保留废止段落
        self.assertIn("共废止21项", result)
        self.assertIn("共发布278项", result)
        # 应保留落款
        self.assertIn("工业和信息化部", result)
        self.assertIn("2026-07-02", result)

    def test_db_monthly_preserves_abolition(self):
        """地方月报：废止段落和末尾日期保留，统计表剥离。"""
        result = clean_announcement_content(DB_MONTHLY_SAMPLE)
        # 不应含统计表数据
        self.assertNotIn("浙江省市场监督管理局", result)
        self.assertNotIn("备案数量", result)
        # 应保留废止段落
        self.assertIn("共废止5项", result)
        self.assertIn("共发布20项", result)
        # 应保留落款
        self.assertIn("国家标准化管理委员会", result)
        self.assertIn("2026-07-02", result)

    def test_pure_text_passthrough(self):
        """纯文本无表格时原样保留。"""
        text = "这是一段普通的公告正文，没有任何表格数据。"
        result = clean_announcement_content(text)
        self.assertIn("没有任何表格数据", result)
        self.assertIn("<p>", result)

    def test_paragraph_wrapping(self):
        """多段落文本正确包裹 p 标签。"""
        text = "第一段内容。\n\n第二段内容。"
        result = clean_announcement_content(text)
        self.assertIn("第一段内容", result)
        self.assertIn("第二段内容", result)


if __name__ == "__main__":
    unittest.main()
