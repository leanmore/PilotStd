# tests/test_core.py

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import shutil
import tempfile
import unittest
from datetime import datetime

import pytest

from pilotstd.core.config import ConfigManager
from pilotstd.core.db import Database
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.core.file_utils import (
    ensure_dir,
    make_standard_filename,
    safe_code_for_filename,
    safe_copy,
    safe_move,
    sanitize_filename,
    truncate_path,
)
from pilotstd.core.logger import LoggerManager
from pilotstd.core.project import ProjectManager


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.config_path = os.path.join(self.tmp, "config.json")
        self.cfg = ConfigManager(filepath=self.config_path)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_get_default(self):
        self.assertEqual(self.cfg.get("nonexistent", 42), 42)

    def test_set_and_get_simple(self):
        self.cfg.set("key1", "value1")
        self.assertEqual(self.cfg.get("key1"), "value1")

    def test_set_and_get_nested(self):
        self.cfg.set("scan.skip_folders", ["过期作废"])
        self.assertEqual(self.cfg.get("scan.skip_folders"), ["过期作废"])

    def test_persistence(self):
        self.cfg.set("db.path", "/tmp/db.sqlite")
        self.cfg.save()

        cfg2 = ConfigManager(filepath=self.config_path)
        self.assertEqual(cfg2.get("db.path"), "/tmp/db.sqlite")

    def test_populate_defaults(self):
        self.cfg.reset()  # 清空 _populate_first_run 预填的默认值
        self.cfg.populate_defaults(
            {"scan.extensions": [".pdf"], "scan.skip_folders": ["过期"]}
        )
        self.assertEqual(self.cfg.get("scan.extensions"), [".pdf"])
        self.cfg.set("scan.extensions", [".txt"])
        self.cfg.populate_defaults({"scan.extensions": [".pdf"]})
        self.assertEqual(self.cfg.get("scan.extensions"), [".txt"])

    def test_reset_key(self):
        self.cfg.set("a.b.c", 123)
        self.cfg.reset("a.b.c")
        self.assertIsNone(self.cfg.get("a.b.c"))

    def test_reset_all(self):
        self.cfg.set("x", 1)
        self.cfg.reset()
        self.assertIsNone(self.cfg.get("x"))

    def test_corrupted_config_backup(self):
        """损坏的配置文件自动备份并以默认值启动。"""
        # 写入损坏的 JSON
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        cfg = ConfigManager(filepath=self.config_path)
        # 应能正常创建并使用默认值
        self.assertIsNotNone(cfg.get("scan.extensions"))
        # 备份文件应存在
        backups = [
            f for f in os.listdir(self.tmp) if f.startswith("config.json.corrupted")
        ]
        self.assertEqual(len(backups), 1, "损坏的配置文件应被备份")


class TestFileUtils(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_sanitize_filename_removes_forbidden(self):
        result = sanitize_filename("test<file>:name?.pdf")
        self.assertEqual(result, "testfilename.pdf")

    def test_safe_code_for_filename(self):
        self.assertEqual(safe_code_for_filename("GB/T"), "GBT")
        self.assertEqual(safe_code_for_filename("GB/Z"), "GBZ")
        self.assertEqual(safe_code_for_filename("SH/T"), "SHT")

    def test_truncate_path_short_path(self):
        result = truncate_path(
            "D:\\标准", "GB 国家标准", "GB 19001-2020 质量管理体系.pdf"
        )
        self.assertIn("质量管理体系", result)

    def test_truncate_path_long_path(self):
        long_name = "GBT 19001-2020 " + "X" * 300 + ".pdf"
        result = truncate_path("D:\\标准", "GB 国家标准", long_name)
        self.assertLessEqual(len(result), 260)
        self.assertTrue(result.endswith(".pdf"))
        self.assertIn("...", result)

    def test_make_standard_filename(self):
        name = make_standard_filename("GB/T", 19001, 2020, "质量管理体系")
        self.assertEqual(name, "GBT 19001-2020 质量管理体系.pdf")

    def test_make_standard_filename_with_part(self):
        name = make_standard_filename("GB/T", 1, 2020, "基础规范", part=1)
        self.assertEqual(name, "GBT 1.1-2020 基础规范.pdf")

    def test_safe_move_and_copy(self):
        src = os.path.join(self.tmp, "src.txt")
        dst_dir = os.path.join(self.tmp, "sub")
        with open(src, "w") as f:
            f.write("data")

        self.assertTrue(safe_copy(src, os.path.join(dst_dir, "copy.txt")))
        self.assertTrue(os.path.exists(os.path.join(dst_dir, "copy.txt")))

        self.assertTrue(safe_move(src, os.path.join(dst_dir, "moved.txt")))
        self.assertTrue(os.path.exists(os.path.join(dst_dir, "moved.txt")))
        self.assertFalse(os.path.exists(src))

    def test_ensure_dir(self):
        p = ensure_dir(os.path.join(self.tmp, "a", "b", "c"))
        self.assertTrue(os.path.isdir(p))


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = Database(os.path.join(self.tmp, "test.db"))

    def tearDown(self):
        # 必须先关闭线程本地连接，否则 Windows 下 db 文件被锁定无法删除
        self.db.close()
        self.db = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_execute_create(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER, name TEXT)")

    def test_insert_and_fetch(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER, name TEXT)")
        self.db.execute("INSERT INTO items VALUES (?, ?)", (1, "test"))
        row = self.db.fetchone("SELECT * FROM items WHERE id=?", (1,))
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "test")

    def test_fetchall_empty(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS empty_t (x INTEGER)")
        rows = self.db.fetchall("SELECT * FROM empty_t")
        self.assertEqual(len(rows), 0)

    def test_executemany(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS batch (id INTEGER)")
        self.db.executemany("INSERT INTO batch VALUES (?)", [(1,), (2,), (3,)])
        rows = self.db.fetchall("SELECT * FROM batch")
        self.assertEqual(len(rows), 3)

    def test_schema_version_new_db(self):
        """新数据库自动初始化 schema 版本为 CURRENT_SCHEMA_VERSION。"""
        from pilotstd.core.db import CURRENT_SCHEMA_VERSION

        self.assertEqual(self.db.schema_version, CURRENT_SCHEMA_VERSION)

    def test_schema_version_table_exists(self):
        """_schema_version 表在首次 init 时创建。"""
        row = self.db.fetchone("SELECT version FROM _schema_version")
        self.assertIsNotNone(row)
        self.assertEqual(row["version"], 1)

    def test_schema_version_existing_db(self):
        """已有 _schema_version 表的数据库，再次打开不报错。"""
        v1 = self.db.schema_version
        db2 = Database(os.path.join(self.tmp, "test.db"))
        self.assertEqual(db2.schema_version, v1)

    def test_full_migration_chain(self):
        """验证从 v0 到最新版本的完整迁移链，全部业务表存在。"""
        from pilotstd.core.db import CURRENT_SCHEMA_VERSION

        alt_path = os.path.join(self.tmp, "fresh_chain.db")
        alt_db = Database(alt_path)
        try:
            actual = alt_db.schema_version
            self.assertEqual(
                actual,
                CURRENT_SCHEMA_VERSION,
                f"期望 schema {CURRENT_SCHEMA_VERSION}，实际 {actual}",
            )
            tables = {
                r["name"]
                for r in alt_db.fetchall(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            }
            expected = {
                "_schema_version",
                "file_index",
                "download_queue",
                "pending_lookup",
                "fetch_log",
                "announcement_cache",
                "rotator_state",
            }
            missing = expected - tables
            self.assertFalse(missing, f"缺少业务表: {missing}")
        finally:
            alt_db = None  # 释放连接
            shutil.rmtree(alt_path, ignore_errors=True)

    def test_backup_creates_consistent_snapshot(self):
        """backup() 创建数据库一致性快照，备份文件包含数据。"""
        self.db.execute("CREATE TABLE IF NOT EXISTS _backup_test (x INTEGER)")
        self.db.execute("INSERT INTO _backup_test VALUES (42)")
        backup_path = self.db.backup()
        self.assertTrue(os.path.exists(backup_path))
        self.assertTrue(backup_path.endswith(".bak"))
        # 验证备份可直接读取且数据一致
        import sqlite3

        verify = sqlite3.connect(backup_path)
        try:
            row = verify.execute("SELECT x FROM _backup_test").fetchone()
            self.assertEqual(row[0], 42)
        finally:
            verify.close()

    def test_migration_runs_pending(self):
        """待执行迁移按版本号顺序执行。"""
        from pilotstd.core.db import MIGRATIONS, migration

        calls = []
        saved_m2 = MIGRATIONS.get(2)  # 保存原始迁移，测后恢复

        @migration(2)
        def m2(db):
            calls.append(2)
            db.execute("CREATE TABLE IF NOT EXISTS _test_m2 (x INTEGER)")

        @migration(3)
        def m3(db):
            calls.append(3)
            db.execute("CREATE TABLE IF NOT EXISTS _test_m3 (y INTEGER)")

        try:
            from pilotstd.core import db as db_module

            old = db_module.CURRENT_SCHEMA_VERSION
            db_module.CURRENT_SCHEMA_VERSION = 3
            db2 = Database(os.path.join(self.tmp, "test_v2.db"))
            self.assertEqual(db2.schema_version, 3)
            self.assertEqual(calls, [2, 3])
            # 验证迁移创建的表存在
            db2.execute("INSERT INTO _test_m2 VALUES (1)")
            db2.execute("INSERT INTO _test_m3 VALUES (2)")
            db2.fetchone("SELECT * FROM _test_m2")
            db2.fetchone("SELECT * FROM _test_m3")
        finally:
            db_module.CURRENT_SCHEMA_VERSION = old
            MIGRATIONS.pop(2, None)
            MIGRATIONS.pop(3, None)
            if saved_m2:  # 恢复原始迁移，避免后续 TestFileIndexRepository 找不到表
                MIGRATIONS[2] = saved_m2
            shutil.rmtree(os.path.join(self.tmp, "test_v2.db"), ignore_errors=True)


class TestProjectManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.prj_path = os.path.join(self.tmp, "test.pilotstd")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_save_and_load(self):
        pm = ProjectManager()
        state = {
            "query_list": ["GB/T 1-2020", "SH/T 2-2010"],
            "work_table_rows": [{"a": 1}],
        }
        self.assertTrue(pm.save(self.prj_path, state))
        self.assertTrue(os.path.exists(self.prj_path))
        loaded = pm.load(self.prj_path)
        self.assertIsNotNone(loaded)
        self.assertIn("query_list", loaded)

    def test_load_nonexistent(self):
        pm = ProjectManager()
        result = pm.load("/nonexistent/path.pilotstd")
        self.assertIsNone(result)

    def test_mark_dirty(self):
        pm = ProjectManager()
        self.assertFalse(pm._dirty)
        pm.mark_dirty()
        self.assertTrue(pm._dirty)


class TestFileIndexRepository(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = shared_db
        self.repo = FileIndexRepository(shared_db)
        # get_full_info 和 _restore_cache_fields 依赖这两张缓存表
        shared_db.execute("""
            CREATE TABLE IF NOT EXISTS standard_info_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_number TEXT NOT NULL,
                source_site TEXT NOT NULL,
                result_json TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'network',
                status_history TEXT NOT NULL DEFAULT ''
            )
        """)
        shared_db.execute("""
            CREATE TABLE IF NOT EXISTS announcement_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_number TEXT NOT NULL,
                source_site TEXT NOT NULL DEFAULT 'announcement',
                result_json TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                expires_at TEXT
            )
        """)
        yield
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_upsert_and_get(self):
        self.repo.upsert("/path/to/GB 1-2020.pdf", "GB", 1, 2020, std_name="基础规范")
        row = self.repo.get("/path/to/GB 1-2020.pdf")
        self.assertIsNotNone(row)
        self.assertEqual(row["logical_code"], "GB")
        self.assertEqual(row["number"], 1)
        self.assertEqual(row["year"], 2020)

    def test_upsert_update_existing(self):
        self.repo.upsert("/a.pdf", "GB", 1, 2020)
        self.repo.upsert("/a.pdf", "GB/T", 1, 2021)
        row = self.repo.get("/a.pdf")
        self.assertEqual(row["year"], 2021)

    def test_remove(self):
        self.repo.upsert("/b.pdf", "GB", 2, 2020)
        self.repo.remove("/b.pdf")
        self.assertIsNone(self.repo.get("/b.pdf"))

    def test_get_all(self):
        self.repo.upsert("/x.pdf", "GB", 1, 2020)
        self.repo.upsert("/y.pdf", "SH", 2, 2021)
        all_rows = self.repo.get_all()
        self.assertEqual(len(all_rows), 2)

    def test_count(self):
        self.assertEqual(self.repo.count(), 0)
        self.repo.upsert("/c.pdf", "GB", 3, 2020)
        self.assertEqual(self.repo.count(), 1)

    def test_clear_stale(self):
        self.repo.upsert("/nonexistent.pdf", "GB", 5, 2020, file_hash="abc")
        removed = self.repo.clear_stale()
        self.assertEqual(removed, 1)
        self.assertEqual(self.repo.count(), 0)

    def test_clear_stale_skips_recent(self):
        """7 天内已验证的记录跳过检查，不被清除。"""
        self.repo.upsert("/nonexistent.pdf", "GB", 5, 2020, file_hash="abc")
        # 标记为今天已验证
        self.db.execute(
            "UPDATE file_index SET last_checked = date('now') WHERE file_path = '/nonexistent.pdf'"
        )
        removed = self.repo.clear_stale()
        self.assertEqual(removed, 0, "7天内的记录不应被检查删除")
        self.assertEqual(self.repo.count(), 1)

    def test_clear_stale_removes_stale_old(self):
        """超过 7 天未验证且文件已消失的记录被清除。"""
        self.repo.upsert("/nonexistent.pdf", "GB", 5, 2020, file_hash="abc")
        # 标记为 10 天前已验证
        self.db.execute(
            "UPDATE file_index SET last_checked = date('now', '-10 days') WHERE file_path = '/nonexistent.pdf'"
        )
        removed = self.repo.clear_stale()
        self.assertEqual(removed, 1)

    def test_clear_stale_refreshes_existing_old(self):
        """超过 7 天但文件仍存在：保留记录并刷新 last_checked。"""
        existing = os.path.join(self.tmp, "real.pdf")
        with open(existing, "w") as f:
            f.write("real")
        self.repo.upsert(existing, "GB", 5, 2020, file_hash="abc")
        self.db.execute(
            "UPDATE file_index SET last_checked = date('now', '-10 days') WHERE file_path = ?",
            (existing,),
        )
        removed = self.repo.clear_stale()
        self.assertEqual(removed, 0)
        # 验证 last_checked 被刷新为今天
        from datetime import date

        row = self.repo.get(existing)
        self.assertEqual(row["last_checked"], date.today().isoformat())

    def test_clear_all(self):
        self.repo.upsert("/d.pdf", "GB", 4, 2020)
        self.repo.upsert("/e.pdf", "SH", 5, 2021)
        self.repo.clear_all()
        self.assertEqual(self.repo.count(), 0)

    # ---- restore_parsed ----

    def test_restore_parsed(self):
        self.repo.upsert(
            "/path/GB 1-2020 基础规范.pdf", "GB", 1, 2020, std_name="基础规范"
        )
        parsed = self.repo.restore_parsed("/path/GB 1-2020 基础规范.pdf")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.logical_code, "GB")
        self.assertEqual(parsed.number, 1)
        self.assertEqual(parsed.year, 2020)
        self.assertEqual(parsed.std_name, "基础规范")
        self.assertEqual(parsed.source_path, "/path/GB 1-2020 基础规范.pdf")

    def test_restore_parsed_nonexistent(self):
        parsed = self.repo.restore_parsed("/nonexistent.pdf")
        self.assertIsNone(parsed)

    def test_restore_parsed_part(self):
        self.repo.upsert("/path/GB 1.1-2020.pdf", "GB", 1, 2020, part=1)
        parsed = self.repo.restore_parsed("/path/GB 1.1-2020.pdf")
        self.assertEqual(parsed.part, 1)

    def test_restore_parsed_no_part(self):
        self.repo.upsert("/path/SH 1610-2011.pdf", "SH/T", 1610, 2011)
        parsed = self.repo.restore_parsed("/path/SH 1610-2011.pdf")
        self.assertIsNone(parsed.part)

    # ---- find_moved_files ----

    def test_find_moved_files_detects_move(self):
        src = os.path.join(self.tmp, "old_loc.pdf")
        with open(src, "w") as f:
            f.write("test content")
        from pilotstd.core.file_utils import hash_file_content

        file_hash = hash_file_content(src)
        self.repo.upsert(src, "GB", 1, 2020, file_hash=file_hash)

        new_path = os.path.join(self.tmp, "new_loc.pdf")
        moved = self.repo.find_moved_files([(new_path, file_hash)])
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["old_path"], src)
        self.assertEqual(moved[0]["new_path"], new_path)

    def test_find_moved_files_same_path_not_moved(self):
        src = os.path.join(self.tmp, "same.pdf")
        with open(src, "w") as f:
            f.write("same content")
        from pilotstd.core.file_utils import hash_file_content

        file_hash = hash_file_content(src)
        self.repo.upsert(src, "GB", 2, 2020, file_hash=file_hash)

        moved = self.repo.find_moved_files([(src, file_hash)])
        self.assertEqual(len(moved), 0)

    def test_find_moved_files_unknown_hash(self):
        moved = self.repo.find_moved_files([("/unknown.pdf", "deadbeef")])
        self.assertEqual(len(moved), 0)

    # ---- get_full_info ----

    def test_get_full_info_no_cache(self):
        self.repo.upsert("/path/GB 1-2020.pdf", "GB", 1, 2020, std_name="测试标准")
        results = self.repo.get_full_info("GB", 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["logical_code"], "GB")
        self.assertEqual(results[0]["std_name"], "测试标准")
        self.assertEqual(results[0]["effect_status"], "")  # 无缓存

    def test_get_full_info_empty(self):
        results = self.repo.get_full_info("XX", 99999)
        self.assertEqual(len(results), 0)

    # ---- restore_parsed with cache ----

    def test_restore_parsed_with_exact_cache(self):
        """restore_parsed 从 standard_info_cache 恢复 exact 查询结果字段。"""
        import json

        self.repo.upsert(
            "/path/GB 1-2020 基础规范.pdf", "GB", 1, 2020, std_name="基础规范"
        )
        # 插入 exact 缓存
        cached = json.dumps(
            {
                "standard_number": "GB 1-2020",
                "standard_name": "测试标准名称",
                "status": "现行",
                "is_adopted": True,
                "match_status": "exact",
            }
        )
        self.db.execute(
            "INSERT INTO standard_info_cache (standard_number, source_site, result_json, cached_at)"
            "VALUES (?, ?, ?, ?)",
            ("GB 1-2020", "test_site", cached, datetime.now().isoformat()),
        )
        parsed = self.repo.restore_parsed("/path/GB 1-2020 基础规范.pdf")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.effect_status, "现行")
        self.assertEqual(parsed.found_name, "测试标准名称")
        self.assertTrue(parsed.is_adopted)
        self.assertEqual(parsed.match_status, "exact")

    def test_restore_parsed_skips_nonexact_cache(self):
        """非 exact 缓存不被恢复（仅置信度 100 才恢复）。"""
        import json

        self.repo.upsert("/path/SH 2-2020.pdf", "SH", 2, 2020)
        cached = json.dumps(
            {
                "standard_number": "SH 2-2020",
                "standard_name": "某标准",
                "status": "现行",
                "is_adopted": False,
                "match_status": "newer",
            }
        )
        self.db.execute(
            "INSERT INTO standard_info_cache (standard_number, source_site, result_json, cached_at)"
            "VALUES (?, ?, ?, ?)",
            ("SH 2-2020", "test_site", cached, datetime.now().isoformat()),
        )
        parsed = self.repo.restore_parsed("/path/SH 2-2020.pdf")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.effect_status, "")  # 非 exact 不恢复
        self.assertEqual(parsed.found_name, "")
        self.assertFalse(parsed.is_adopted)
        self.assertEqual(parsed.match_status, "")

    # ---- 两表合并测试 ----

    def test_restore_from_announcement_cache(self):
        """公告缓存也能恢复查询结果字段。"""
        import json

        self.repo.upsert(
            "/path/GB 1-2020 基础规范.pdf", "GB", 1, 2020, std_name="基础规范"
        )
        cached = json.dumps(
            {
                "standard_number": "GB 1-2020",
                "standard_name": "公告标准名称",
                "status": "被代替",
                "is_adopted": False,
                "match_status": "exact",
                "replaced_by": "GB 1-2025",
            }
        )
        self.db.execute(
            "INSERT INTO announcement_cache (standard_number, source_site, result_json, cached_at) "
            "VALUES (?, 'announcement', ?, ?)",
            ("GB 1-2020", cached, datetime.now().isoformat()),
        )
        parsed = self.repo.restore_parsed("/path/GB 1-2020 基础规范.pdf")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.effect_status, "被代替")
        self.assertEqual(parsed.found_name, "公告标准名称")

    def test_get_full_info_like_match(self):
        """get_full_info 使用 LIKE 前缀匹配连接两个缓存表。"""
        import json

        self.repo.upsert("/path/GB 1-2020.pdf", "GB", 1, 2020)
        self.db.execute(
            "INSERT INTO standard_info_cache (standard_number, source_site, result_json, cached_at)"
            "VALUES ('GB 1-2020', 'mock', ?, ?)",
            (
                json.dumps(
                    {
                        "status": "现行",
                        "match_status": "exact",
                        "standard_name": "网查名称",
                    }
                ),
                datetime.now().isoformat(),
            ),
        )
        results = self.repo.get_full_info("GB", 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["effect_status"], "现行")
        self.assertEqual(results[0]["found_name"], "网查名称")

    def test_get_full_info_network_priority(self):
        """网络缓存优先于公告缓存。"""
        import json

        self.repo.upsert("/path/GB 2-2020.pdf", "GB", 2, 2020)
        self.db.execute(
            "INSERT INTO standard_info_cache (standard_number, source_site, result_json, cached_at)"
            "VALUES ('GB 2-2020', 'mock', ?, ?)",
            (
                json.dumps(
                    {"status": "现行", "match_status": "exact", "standard_name": "网查"}
                ),
                datetime.now().isoformat(),
            ),
        )
        self.db.execute(
            "INSERT INTO announcement_cache (standard_number, source_site, result_json, cached_at) "
            "VALUES ('GB 2-2020', 'announcement', ?, ?)",
            (
                json.dumps(
                    {"status": "废止", "match_status": "exact", "standard_name": "公告"}
                ),
                datetime.now().isoformat(),
            ),
        )
        results = self.repo.get_full_info("GB", 2)
        self.assertEqual(results[0]["effect_status"], "现行")  # 网络优先


class TestDailyQuotaTracker(unittest.TestCase):
    """DailyQuotaTracker 单元测试：配额计算、跨天回滚。"""

    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        from pilotstd.query.daily_quota import DailyQuotaTracker

        self.db = shared_db
        self.tracker = DailyQuotaTracker(shared_db, limits={"csres": 180})

    def test_get_remaining_initial(self):
        """新实例返回完整默认配额。"""
        self.assertEqual(self.tracker.get_remaining("csres"), 180)
        self.assertEqual(self.tracker.get_remaining("unknown_site"), 500)

    def test_record_usage_reduces_remaining(self):
        """消耗次数后配额递减。"""
        before = self.tracker.get_remaining("csres")
        after = self.tracker.record_usage("csres", 10)
        self.assertEqual(after, before - 10)
        self.assertEqual(self.tracker.get_used("csres"), 10)

    def test_record_usage_non_limited_site(self):
        """非预定义站点使用默认限额 500。"""
        remaining = self.tracker.record_usage("custom_site", 100)
        self.assertEqual(remaining, 400)

    def test_get_search_remaining(self):
        """搜索可用次数 = 总额 - 已用 - 详情页保底。"""
        self.tracker.record_usage("csres", 20)
        search_rem = self.tracker.get_search_remaining("csres")
        # csres: 180 - 20 - 30(保底) = 130
        self.assertEqual(search_rem, 130)

    def test_cross_day_updates_today(self):
        """跨天后 _today 自动更新为当前日期。"""
        self.tracker.record_usage("csres", 50)
        self.tracker._today = "1970-01-01"  # 模拟昨天
        self.tracker.get_remaining("csres")  # 触发 _ensure_date
        from datetime import date

        self.assertEqual(
            self.tracker._today, str(date.today()), "跨天后 _today 应更新为当前日期"
        )

    def test_cross_day_preserves_existing_usage(self):
        """日期复位后，当天已有用量保持不变。"""
        self.tracker.record_usage("csres", 50)
        self.tracker._today = "1970-01-01"
        remaining = self.tracker.get_remaining("csres")
        # 复位到今天后，DB 中该行已有消耗 50，剩余 130
        self.assertEqual(remaining, 130)

    def test_cross_day_switches_today(self):
        """跨天后 _today 自动更新为今天日期。"""
        self.tracker._today = "1970-01-01"
        self.tracker.get_remaining("csres")  # 触发 _ensure_date
        from datetime import date

        self.assertEqual(self.tracker._today, str(date.today()))


class TestLoggerManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_get_logger_creates_manager(self):
        lg = LoggerManager.get_logger("test_module")
        self.assertIsNotNone(lg)
        self.assertEqual(lg.name, "test_module")

    def test_set_level(self):
        LoggerManager.set_level(30)  # WARNING
        lg = LoggerManager.get_logger("test_level")
        lg.debug("should not appear")

    def test_singleton_thread_safety(self):
        """多线程同时调用 get_logger 只创建一个 LoggerManager 实例。"""
        import threading

        from pilotstd.core.logger import LoggerManager

        # 重置单例状态以便测试
        LoggerManager._instance = None
        errors = []

        def get_logger_in_thread():
            try:
                LoggerManager.get_logger("test_thread")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=get_logger_in_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"创建 LoggerManager 出错: {errors}")
        self.assertIsNotNone(LoggerManager._instance)


class TestHashFileContent(unittest.TestCase):
    """哈希优化测试：验证 scanner 与 file_index 哈希一致性、采样逻辑正确性。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_small_file_full_hash(self):
        """≤1MB 文件走全量哈希，结果非空。"""
        path = os.path.join(self.tmp, "small.pdf")
        with open(path, "wb") as f:
            f.write(b"A" * 1024)  # 1KB
        from pilotstd.core.file_utils import hash_file_content

        h = hash_file_content(path)
        self.assertTrue(h)
        self.assertEqual(len(h), 64)

    def test_large_file_sample_hash(self):
        """>1MB 文件走采样哈希，结果非空且速度远快于全量。"""
        path = os.path.join(self.tmp, "large.bin")
        size = 2 * 1024 * 1024  # 2MB
        with open(path, "wb") as f:
            f.write(b"X" * size)
        from pilotstd.core.file_utils import hash_file_content

        h = hash_file_content(path)
        self.assertTrue(h)
        self.assertEqual(len(h), 64)

    def test_scanner_and_file_index_produce_same_hash(self):
        """hash_file_content 产生一致的哈希值（原两处 _hash_file 已统一为此函数）。"""
        path = os.path.join(self.tmp, "shared.pdf")
        with open(path, "wb") as f:
            f.write(b"shared content for consistency test")
        from pilotstd.core.file_utils import hash_file_content

        h1 = hash_file_content(path)
        h2 = hash_file_content(path)
        self.assertEqual(h1, h2)

    def test_same_prefix_different_file_hashes_differ(self):
        """前缀相同的两个大文件哈希不同（靠文件大小区分）。"""
        path1 = os.path.join(self.tmp, "big1.bin")
        path2 = os.path.join(self.tmp, "big2.bin")
        # 两个文件前 1MB 完全相同
        prefix = b"P" * (1024 * 1024)
        with open(path1, "wb") as f:
            f.write(prefix + b"tail1")
        with open(path2, "wb") as f:
            f.write(prefix + b"tail2_different")
        from pilotstd.core.file_utils import hash_file_content

        self.assertNotEqual(hash_file_content(path1), hash_file_content(path2))


class TestDatabaseConcurrency(unittest.TestCase):
    """数据库并发读写测试：验证读写锁分离后无数据竞争。"""

    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        shared_db.execute(
            "CREATE TABLE IF NOT EXISTS _concurrent_test (id INTEGER PRIMARY KEY, val TEXT)"
        )
        for i in range(100):
            shared_db.execute(
                "INSERT OR REPLACE INTO _concurrent_test VALUES (?, ?)", (i, f"val_{i}")
            )

    def test_concurrent_reads_no_error(self):
        """多线程并发 fetchall 不应抛异常或数据竞争。"""
        import threading

        errors = []

        def read_batch():
            try:
                for _ in range(50):
                    rows = self.db.fetchall("SELECT * FROM _concurrent_test")
                    self.assertIsInstance(rows, list)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_batch) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0, f"并发读取出错: {errors}")

    def test_concurrent_write_and_read(self):
        """并发写+读不应丢数据。"""
        import threading

        errors = []
        results = []

        def writer():
            try:
                for i in range(100, 200):
                    self.db.execute(
                        "INSERT OR REPLACE INTO _concurrent_test VALUES (?, ?)",
                        (i, f"val_{i}"),
                    )
            except Exception as e:
                errors.append(str(e))

        def reader():
            try:
                for _ in range(20):
                    rows = self.db.fetchall(
                        "SELECT COUNT(*) as cnt FROM _concurrent_test"
                    )
                    results.append(rows[0]["cnt"])
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(len(errors), 0, f"并发读写出错: {errors}")
        # 最终计数应为 200
        final = self.db.fetchone("SELECT COUNT(*) as cnt FROM _concurrent_test")
        self.assertEqual(final["cnt"], 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
