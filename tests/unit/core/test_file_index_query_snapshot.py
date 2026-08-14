"""FileIndexQuery Phase 0/1 行为快照测试。

使用 sqlite3 :memory: + 薄包装器，覆盖全部 11 个方法。
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from pilotstd.core._file_index_query import (
    ANNOUNCEMENT_CACHE_TABLE,
    FILE_INDEX_TABLE,
    NETWORK_CACHE_TABLE,
    FileIndexQuery,
)
from pilotstd.models import ParsedStdInfo


class _FakeDB:
    """模拟 Database 接口（fetchone/fetchall/execute），底层 sqlite3 :memory:。"""

    def __init__(self):
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

    def fetchone(self, sql: str, params=()):
        cur = self._conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params=()):
        cur = self._conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def execute(self, sql: str, params=()):
        self._conn.execute(sql, params)
        self._conn.commit()


@pytest.fixture
def db():
    d = _FakeDB()
    d.execute(f"""
        CREATE TABLE {FILE_INDEX_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            logical_code TEXT,
            number INTEGER,
            year INTEGER,
            part INTEGER DEFAULT -1,
            std_name TEXT DEFAULT '',
            file_hash TEXT DEFAULT '',
            status TEXT DEFAULT '现行',
            raw_number TEXT DEFAULT ''
        )
    """)
    d.execute(f"""
        CREATE TABLE {NETWORK_CACHE_TABLE} (
            standard_number TEXT PRIMARY KEY,
            result_json TEXT,
            cached_at TEXT
        )
    """)
    d.execute(f"""
        CREATE TABLE {ANNOUNCEMENT_CACHE_TABLE} (
            standard_number TEXT PRIMARY KEY,
            result_json TEXT,
            cached_at TEXT
        )
    """)
    return d


@pytest.fixture
def q(db):
    return FileIndexQuery(db)


def _seed(db, file_path, logical_code, number, year, **kw):
    db.execute(
        f"INSERT INTO {FILE_INDEX_TABLE} (file_path, logical_code, number, year, part, "
        "std_name, file_hash, status, raw_number) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (file_path, logical_code, number, year, kw.get("part", -1),
         kw.get("std_name", ""), kw.get("file_hash", ""),
         kw.get("status", "现行"), kw.get("raw_number", str(number))),
    )


class TestBasicQueries:

    def test_get_hit(self, db, q):
        _seed(db, "/a/b.pdf", "GB", 1234, 2020, std_name="测试标准")
        row = q.get("/a/b.pdf")
        assert row["logical_code"] == "GB"
        assert row["number"] == 1234

    def test_get_miss(self, q):
        assert q.get("/nonexistent.pdf") is None

    def test_get_all_order(self, db, q):
        _seed(db, "/b.pdf", "GB", 200, 2020)
        _seed(db, "/a.pdf", "GB", 100, 2019)
        rows = q.get_all()
        assert len(rows) == 2
        assert rows[0]["number"] <= rows[1]["number"]

    def test_get_all_empty(self, q):
        assert q.get_all() == []

    def test_find_by_standard_hit(self, db, q):
        _seed(db, "/x.pdf", "SH", 56, 2021, part=1)
        rows = q.find_by_standard("SH", 56, 2021, part=1)
        assert len(rows) == 1
        assert rows[0]["logical_code"] == "SH"

    def test_find_by_standard_miss(self, q):
        assert q.find_by_standard("XX", 999, 2099) == []

    def test_find_by_hash_hit(self, db, q):
        _seed(db, "/h.pdf", "GB", 1, 2020, file_hash="abc123")
        row = q.find_by_hash("abc123")
        assert row["file_path"] == "/h.pdf"

    def test_find_by_hash_miss(self, q):
        assert q.find_by_hash("no_such_hash") is None


class TestStats:

    def test_count(self, db, q):
        _seed(db, "/1.pdf", "GB", 1, 2020)
        _seed(db, "/2.pdf", "SH", 2, 2021)
        assert q.count() == 2

    def test_count_empty(self, q):
        assert q.count() == 0

    def test_get_status_stats(self, db, q):
        _seed(db, "/a.pdf", "GB", 1, 2020, status="现行")
        _seed(db, "/b.pdf", "GB", 2, 2019, status="废止")
        _seed(db, "/c.pdf", "GB", 3, 2021, status="即将实施")
        stats = q.get_status_stats()
        assert stats["current"] == 1
        assert stats["expired"] == 1
        assert stats["upcoming"] == 1

    def test_get_status_stats_empty_db(self, q):
        stats = q.get_status_stats()
        assert stats == {"current": 0, "expired": 0, "pending": 0, "upcoming": 0}


class TestRestoreParsed:

    def test_restore_hit(self, db, q):
        _seed(db, "/r.pdf", "GB", 1234, 2020, std_name="恢复测试")
        info = q.restore_parsed("/r.pdf")
        assert info is not None
        assert info.logical_code == "GB"
        assert info.number == 1234

    def test_restore_miss(self, q):
        assert q.restore_parsed("/no.pdf") is None

    def test_restore_with_network_cache(self, db, q):
        _seed(db, "/cached.pdf", "GB", 555, 2021)
        db.execute(
            f"INSERT INTO {NETWORK_CACHE_TABLE} (standard_number, result_json) VALUES (?, ?)",
            (
                "GB 555-2021",
                json.dumps({"status": "现行", "standard_name": "网络名", "is_adopted": True, "match_status": "exact"}),
            ),
        )
        info = q.restore_parsed("/cached.pdf")
        assert info.effect_status == "现行"
        assert info.is_adopted is True

    def test_restore_with_announcement_cache_fallback(self, db, q):
        _seed(db, "/ann.pdf", "GB", 666, 2022)
        db.execute(
            f"INSERT INTO {ANNOUNCEMENT_CACHE_TABLE} (standard_number, result_json) VALUES (?, ?)",
            ("GB 666-2022", json.dumps({"status": "废止", "standard_name": "公告名", "match_status": "exact"})),
        )
        info = q.restore_parsed("/ann.pdf")
        assert info.effect_status == "废止"


class TestFindMovedFiles:

    def test_moved_detected(self, db, q):
        _seed(db, "/old/path.pdf", "GB", 1, 2020, file_hash="hash_move")
        results = q.find_moved_files([("/new/path.pdf", "hash_move")])
        assert len(results) == 1
        assert results[0]["old_path"] == "/old/path.pdf"

    def test_no_move_same_path(self, db, q):
        _seed(db, "/same.pdf", "GB", 1, 2020, file_hash="hash_same")
        results = q.find_moved_files([("/same.pdf", "hash_same")])
        assert len(results) == 0

    def test_empty_hash_skipped(self, db, q):
        results = q.find_moved_files([("/new.pdf", "")])
        assert len(results) == 0


class TestGetFullInfo:

    def test_full_info_basic(self, db, q):
        _seed(db, "/f1.pdf", "GB", 100, 2020, std_name="基础标准", part=1)
        results = q.get_full_info("GB", 100)
        assert len(results) == 1
        assert results[0]["logical_code"] == "GB"
        assert results[0]["std_name"] == "基础标准"

    def test_full_info_with_cache(self, db, q):
        _seed(db, "/f2.pdf", "SH", 200, 2021)
        db.execute(
            f"INSERT INTO {NETWORK_CACHE_TABLE} (standard_number, result_json, cached_at) VALUES (?, ?, ?)",
            (
                "SH 200",
                json.dumps({"status": "现行", "standard_name": "行标名", "match_status": "exact"}),
                "2024-01-01",
            ),
        )
        results = q.get_full_info("SH", 200)
        assert results[0]["effect_status"] == "现行"

    def test_full_info_miss(self, q):
        assert q.get_full_info("ZZ", 999) == []


class TestApplyCacheResult:

    def test_exact_match_applied(self):
        info = ParsedStdInfo(raw_filename="t.pdf", logical_code="GB", number=1, year=2020)
        FileIndexQuery._apply_cache_result(
            json.dumps({"status": "现行", "standard_name": "测试", "is_adopted": False, "match_status": "exact"}),
            info,
        )
        assert info.effect_status == "现行"

    def test_non_exact_skipped(self):
        info = ParsedStdInfo(raw_filename="t.pdf", logical_code="GB", number=1, year=2020)
        info.effect_status = "原始"
        FileIndexQuery._apply_cache_result(
            json.dumps({"match_status": "partial"}),
            info,
        )
        assert info.effect_status == "原始"

    def test_invalid_json_silent(self):
        info = ParsedStdInfo(raw_filename="t.pdf", logical_code="GB", number=1, year=2020)
        FileIndexQuery._apply_cache_result("not json{", info)
        assert info.effect_status == ""
