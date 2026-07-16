# tests/test_announce_detail.py — 公告详情页 API 测试

import os
import sqlite3
import sys
import tempfile
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


class TestAnnounceDetailAPI(unittest.TestCase):
    """验证 /api/announcements/{announce_no} 从 announcement_record 表查询。

    根因：详情页 API 原查 announcements 表（仅 v36 迁移时写入），
    新公告在 announcements 中不存在 → 404。修复后查 announcement_record。
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS announcement_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_site TEXT, pid TEXT,
                announce_no TEXT, standard_number TEXT,
                std_name TEXT, publish_date TEXT,
                fetched_at TEXT, matched INTEGER DEFAULT 0,
                announcement_title TEXT, standard_count INTEGER,
                row_index INTEGER DEFAULT 0,
                implement_date TEXT, expiry_date TEXT,
                superseded_by TEXT, status TEXT DEFAULT 'draft',
                confidence REAL DEFAULT 0.0,
                created_at TEXT, updated_at TEXT
            )"""
        )
        self.conn.execute(
            "INSERT INTO announcement_record"
            " (source_site, pid, announce_no, standard_number, std_name,"
            "  publish_date, fetched_at, announcement_title)"
            " VALUES ('ahbz', 'pid-001', 'ANNOUNCE-2026-001', 'GB/T 19001-2016',"
            "  '质量管理体系', '2026-06-01', '2026-06-15', '2026年第1号公告')"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_mgr(self):
        """构造 mock manager，db.fetchone/fetchall 返回测试数据。"""
        from unittest.mock import MagicMock

        row = self.conn.execute(
            "SELECT announce_no, announcement_title AS title, publish_date"
            " FROM announcement_record WHERE announce_no = ?",
            ("ANNOUNCE-2026-001",),
        ).fetchone()

        records = self.conn.execute(
            "SELECT * FROM announcement_record WHERE announce_no = ? ORDER BY id",
            ("ANNOUNCE-2026-001",),
        ).fetchall()

        mgr = MagicMock()
        mgr.db.fetchone.return_value = row
        mgr.db.fetchall.return_value = records
        return mgr

    def test_detail_returns_header_from_record(self):
        """详情页应从 announcement_record 返回公告头信息。"""
        from docker.api.announce_detail import get_announcement_detail

        mgr = self._make_mgr()
        result = get_announcement_detail("ANNOUNCE-2026-001", mgr=mgr)
        self.assertIsNotNone(result)
        self.assertIn("announcement", result)
        self.assertEqual(result["announcement"]["announce_no"], "ANNOUNCE-2026-001")

    def test_detail_unknown_raises_404(self):
        """不存在的公告号应返回 404。"""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        from docker.api.announce_detail import get_announcement_detail

        mgr = MagicMock()
        mgr.db.fetchone.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            get_announcement_detail("NONEXISTENT", mgr=mgr)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_detail_returns_records_array(self):
        """详情页应返回关联的标准记录列表。"""
        from docker.api.announce_detail import get_announcement_detail

        mgr = self._make_mgr()
        result = get_announcement_detail("ANNOUNCE-2026-001", mgr=mgr)
        self.assertIn("records", result)
        self.assertIsInstance(result["records"], list)
        self.assertIn("parse_status", result)


if __name__ == "__main__":
    unittest.main()
