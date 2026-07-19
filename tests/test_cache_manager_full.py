# tests/test_cache_manager_full.py
"""CacheManager 完整单元测试 —— 覆盖所有公开/内部方法。

使用 MagicMock 模拟 db 依赖，不依赖真实数据库。
"""

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.core.cache_manager import CacheManager, CacheState, DataSource

# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════


def _make_mock_db(tables_exist=True, config_values=None):
    """创建 mock_db，可配置 fetchall/fetchone 返回值。

    Args:
        tables_exist: True=两表都存在, False=都不存在,
                      list=指定返回的表列表
        config_values: dict，键为 config_key，值为 fetchone 返回的 dict 或 None
    """
    mock_db = MagicMock()
    cv = config_values or {}

    if tables_exist is True:
        mock_db.fetchall.return_value = [
            {"name": "cache_config"},
            {"name": "data_source_versions"},
        ]
    elif tables_exist is False:
        mock_db.fetchall.return_value = []
    elif isinstance(tables_exist, list):
        mock_db.fetchall.return_value = tables_exist

    # _load_config_* 在 __init__ 中调用三次 fetchone(key)
    def _fetchone(sql, params=None):
        if params and len(params) > 0:
            key = params[0]
            if key in cv:
                return cv[key]
        return None

    mock_db.fetchone = MagicMock(side_effect=_fetchone)
    return mock_db


# ═══════════════════════════════════════════════════════════
# DataSource 枚举
# ═══════════════════════════════════════════════════════════


class TestDataSourceEnum(unittest.TestCase):
    """DataSource 枚举值验证。"""

    def test_values(self):
        self.assertEqual(DataSource.FILE_INDEX.value, "file_index")
        self.assertEqual(DataSource.ANNOUNCEMENT.value, "announcement")
        self.assertEqual(DataSource.VALIDITY.value, "validity")

    def test_all_members(self):
        members = list(DataSource)
        self.assertEqual(len(members), 3)
        values = {m.value for m in members}
        self.assertEqual(values, {"file_index", "announcement", "validity"})


# ═══════════════════════════════════════════════════════════
# CacheState 枚举
# ═══════════════════════════════════════════════════════════


class TestCacheStateEnum(unittest.TestCase):
    """CacheState 枚举值验证。"""

    def test_values(self):
        self.assertEqual(CacheState.VALID.value, "valid")
        self.assertEqual(CacheState.STALE.value, "stale")
        self.assertEqual(CacheState.REFRESH_PENDING.value, "refresh_pending")

    def test_all_members(self):
        members = list(CacheState)
        self.assertEqual(len(members), 3)
        values = {m.value for m in members}
        self.assertEqual(values, {"valid", "stale", "refresh_pending"})


# ═══════════════════════════════════════════════════════════
# __init__ + _ensure_cache_tables
# ═══════════════════════════════════════════════════════════


class TestInitEnsureTables(unittest.TestCase):
    """测试 __init__ 和 _ensure_cache_tables。"""

    def test_both_tables_exist_no_create(self):
        """两表都已存在 → 不执行 CREATE TABLE。"""
        mock_db = _make_mock_db(tables_exist=True)
        CacheManager(mock_db)

        execute_sqls = [str(c[0][0]) for c in mock_db.execute.call_args_list if c[0]]
        create_calls = [s for s in execute_sqls if "CREATE TABLE" in s.upper() and "IF NOT EXISTS" in s.upper()]
        self.assertEqual(len(create_calls), 0, "两表已存在时不应有 CREATE TABLE 调用")

    def test_both_tables_missing_creates_both(self):
        """两表都不存在 → 创建两表并插入默认数据。"""
        mock_db = _make_mock_db(tables_exist=False)
        CacheManager(mock_db)

        execute_sqls = [str(c[0][0]) for c in mock_db.execute.call_args_list if c[0]]
        self.assertTrue(any("cache_config" in s for s in execute_sqls), "应创建 cache_config 表")
        self.assertTrue(any("data_source_versions" in s for s in execute_sqls), "应创建 data_source_versions 表")

        insert_count = sum(1 for s in execute_sqls if "INSERT" in s.upper())
        # 3 条 cache_config 默认值 + 3 条 data_source_versions 默认值 = 6
        self.assertGreaterEqual(insert_count, 6, "应插入 6 条默认数据")

    def test_only_cache_config_exists(self):
        """仅 cache_config 存在 → 只创建 data_source_versions。"""
        mock_db = _make_mock_db(tables_exist=[{"name": "cache_config"}])
        CacheManager(mock_db)

        execute_sqls = [str(c[0][0]) for c in mock_db.execute.call_args_list if c[0]]
        self.assertTrue(any("data_source_versions" in s for s in execute_sqls), "应创建 data_source_versions 表")
        create_cc = [s for s in execute_sqls if "CREATE TABLE" in s.upper() and "cache_config" in s]
        self.assertEqual(len(create_cc), 0, "cache_config 已存在不应重复创建")

    def test_only_data_source_versions_exists(self):
        """仅 data_source_versions 存在 → 只创建 cache_config。"""
        mock_db = _make_mock_db(tables_exist=[{"name": "data_source_versions"}])
        CacheManager(mock_db)

        execute_sqls = [str(c[0][0]) for c in mock_db.execute.call_args_list if c[0]]
        self.assertTrue(any("cache_config" in s for s in execute_sqls), "应创建 cache_config 表")
        create_dsv = [s for s in execute_sqls if "CREATE TABLE" in s.upper() and "data_source_versions" in s]
        self.assertEqual(len(create_dsv), 0, "data_source_versions 已存在不应重复创建")

    def test_default_config_values(self):
        """配置表中无记录 → 使用默认值。"""
        mock_db = _make_mock_db(
            tables_exist=True,
            config_values={
                "max_size_mb": None,
                "auto_cleanup": None,
                "cleanup_ratio": None,
            },
        )
        cm = CacheManager(mock_db)
        self.assertEqual(cm._max_mb, 50)
        self.assertEqual(cm._auto_cleanup, True)
        self.assertAlmostEqual(cm._cleanup_ratio, 0.1)

    def test_config_from_db(self):
        """配置表中有记录 → 使用 DB 中的值。"""
        mock_db = _make_mock_db(
            tables_exist=True,
            config_values={
                "max_size_mb": {"config_value": "100"},
                "auto_cleanup": {"config_value": "false"},
                "cleanup_ratio": {"config_value": "0.25"},
            },
        )
        cm = CacheManager(mock_db)
        self.assertEqual(cm._max_mb, 100)
        self.assertEqual(cm._auto_cleanup, False)
        self.assertAlmostEqual(cm._cleanup_ratio, 0.25)

    def test_fetchall_returns_none(self):
        """fetchall 返回 None（而非空列表）→ 视为无表。"""
        mock_db = MagicMock()
        # fetchall 返回 None
        mock_db.fetchall.return_value = None
        # fetchone 默认返回 None
        mock_db.fetchone = MagicMock(return_value=None)

        CacheManager(mock_db)

        # 应创建两表
        execute_sqls = [str(c[0][0]) for c in mock_db.execute.call_args_list if c[0]]
        self.assertTrue(any("cache_config" in s for s in execute_sqls))
        self.assertTrue(any("data_source_versions" in s for s in execute_sqls))


# ═══════════════════════════════════════════════════════════
# get()
# ═══════════════════════════════════════════════════════════


class TestGet(unittest.TestCase):
    """测试 get() 所有场景。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_cache_miss_no_row(self):
        """查询行不存在 → 返回 None。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                {"version": "v1"},  # _get_source_version
                None,  # SELECT * 无数据
            ]
        )
        result = self.cm.get("standard_info_cache", "standard_id", "GB/T 1.1", DataSource.FILE_INDEX)
        self.assertIsNone(result)

    def test_cache_hit(self):
        """版本匹配 → 返回完整 dict。"""
        row = {"id": 1, "standard_id": "K1", "result_json": '{"t":"x"}', "source_version": "v1", "data_state": "valid"}
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                {"version": "v1"},  # _get_source_version
                row,  # SELECT *
            ]
        )
        result = self.cm.get("standard_info_cache", "standard_id", "K1", DataSource.FILE_INDEX)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["standard_id"], "K1")

    def test_version_expired_returns_none(self):
        """版本不匹配 → 标记 stale 并返回 None。"""
        row = {"id": 1, "standard_id": "K1", "result_json": "{}", "source_version": "v1", "data_state": "valid"}
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                {"version": "v2"},  # 新版本
                row,  # 行中版本 v1
            ]
        )
        result = self.cm.get("standard_info_cache", "standard_id", "K1", DataSource.FILE_INDEX)
        self.assertIsNone(result)

        # 验证标记 stale 的 execute 调用
        stale_calls = [c for c in self.mock_db.execute.call_args_list if "data_state='stale'" in str(c[0][0])]
        self.assertGreaterEqual(len(stale_calls), 1, "版本过期必须标记 stale")

    def test_updates_last_accessed_at(self):
        """每次命中都会更新 last_accessed_at。"""
        row = {"id": 1, "standard_id": "K1", "result_json": "{}", "source_version": "v1", "data_state": "valid"}
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                {"version": "v1"},
                row,
            ]
        )
        self.cm.get("standard_info_cache", "standard_id", "K1", DataSource.FILE_INDEX)

        access_calls = [c for c in self.mock_db.execute.call_args_list if "last_accessed_at" in str(c[0][0])]
        self.assertGreaterEqual(len(access_calls), 1, "必须更新 last_accessed_at")

    def test_get_with_announcement_source(self):
        """ANNOUNCEMENT 数据源也能正常读取。"""
        row = {"id": 1, "announce_id": "A1", "result_json": "{}", "source_version": "v1", "data_state": "valid"}
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                {"version": "v1"},
                row,
            ]
        )
        result = self.cm.get("announcement_record", "announce_id", "A1", DataSource.ANNOUNCEMENT)
        self.assertIsNotNone(result)

    def test_get_with_validity_source(self):
        """VALIDITY 数据源也能正常读取。"""
        row = {"id": 1, "standard_id": "K1", "result_json": "{}", "source_version": "v1", "data_state": "valid"}
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                {"version": "v1"},
                row,
            ]
        )
        result = self.cm.get("standard_validity", "standard_id", "K1", DataSource.VALIDITY)
        self.assertIsNotNone(result)


# ═══════════════════════════════════════════════════════════
# set()
# ═══════════════════════════════════════════════════════════


class TestSet(unittest.TestCase):
    """测试 set()。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_set_writes_insert_or_replace(self):
        """set 执行 INSERT OR REPLACE，包含版本和数据状态。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "v1"})

        self.cm.set("standard_info_cache", "standard_id", "K1", {"title": "test"}, DataSource.FILE_INDEX)

        insert_calls = [c for c in self.mock_db.execute.call_args_list if "INSERT OR REPLACE" in str(c[0][0]).upper()]
        self.assertGreaterEqual(len(insert_calls), 1, "应有 INSERT OR REPLACE")
        sql_str = str(insert_calls[0][0][0])
        # SQL 使用 VALUES (?, ?, ?, 'valid', ?) 格式，data_state 在列名中，
        # 'valid' 在 VALUES 中但不以 "data_state='valid'" 形式出现
        self.assertIn("data_state", sql_str)
        self.assertIn("'valid'", sql_str)
        self.assertIn("source_version", sql_str)

    def test_set_triggers_cleanup_when_enabled(self):
        """auto_cleanup=True → set 触发清理。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "v1"})
        self.cm.set_config("auto_cleanup", True)

        with patch.object(self.cm, "cleanup") as mock_cleanup:
            self.cm.set("standard_info_cache", "standard_id", "K1", {"t": 1}, DataSource.FILE_INDEX)
            mock_cleanup.assert_called_once()

    def test_set_no_cleanup_when_disabled(self):
        """auto_cleanup=False → set 不触发清理。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "v1"})
        self.cm.set_config("auto_cleanup", False)

        with patch.object(self.cm, "_check_and_cleanup") as mock_cc:
            self.cm.set("standard_info_cache", "standard_id", "K1", {"t": 1}, DataSource.FILE_INDEX)
            mock_cc.assert_not_called()

    def test_set_check_and_cleanup_handles_exception(self):
        """_check_and_cleanup 内部异常不向外传播。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "v1"})
        self.cm.set_config("auto_cleanup", True)

        with patch.object(self.cm, "cleanup", side_effect=RuntimeError("boom")):
            # 不应抛出异常
            self.cm.set("standard_info_cache", "standard_id", "K1", {"t": 1}, DataSource.FILE_INDEX)


# ═══════════════════════════════════════════════════════════
# invalidate_by_source
# ═══════════════════════════════════════════════════════════


class TestInvalidateBySource(unittest.TestCase):
    """测试 invalidate_by_source。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_invalidate_file_index(self):
        """FILE_INDEX 失效 → 标记 standard_info_cache 中版本不匹配的行为 stale。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "old"})

        self.cm.invalidate_by_source(DataSource.FILE_INDEX)

        stale_calls = [
            c
            for c in self.mock_db.execute.call_args_list
            if "data_state='stale'" in str(c[0][0]) and "standard_info_cache" in str(c[0][0])
        ]
        self.assertGreaterEqual(len(stale_calls), 1, "应标记 standard_info_cache 为 stale")

    def test_invalidate_announcement(self):
        """ANNOUNCEMENT 失效 → 标记 announcement_record。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "old"})

        self.cm.invalidate_by_source(DataSource.ANNOUNCEMENT)

        stale_calls = [
            c
            for c in self.mock_db.execute.call_args_list
            if "data_state='stale'" in str(c[0][0]) and "announcement_record" in str(c[0][0])
        ]
        self.assertGreaterEqual(len(stale_calls), 1)

    def test_invalidate_validity(self):
        """VALIDITY 失效 → 标记 standard_validity。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "old"})

        self.cm.invalidate_by_source(DataSource.VALIDITY)

        stale_calls = [
            c
            for c in self.mock_db.execute.call_args_list
            if "data_state='stale'" in str(c[0][0]) and "standard_validity" in str(c[0][0])
        ]
        self.assertGreaterEqual(len(stale_calls), 1)

    def test_invalidate_bumps_version(self):
        """失效操作会 bump 版本号。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "old"})

        self.cm.invalidate_by_source(DataSource.FILE_INDEX)

        bump_calls = [c for c in self.mock_db.execute.call_args_list if "UPDATE data_source_versions" in str(c[0][0])]
        self.assertGreaterEqual(len(bump_calls), 1, "应更新 data_source_versions")


# ═══════════════════════════════════════════════════════════
# mark_stale / mark_valid
# ═══════════════════════════════════════════════════════════


class TestMarkStaleValid(unittest.TestCase):
    """测试 mark_stale 和 mark_valid。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_mark_stale(self):
        """设置 data_state='stale'。"""
        self.cm.mark_stale("standard_info_cache", "standard_id", "K1")

        stale_calls = [c for c in self.mock_db.execute.call_args_list if "data_state='stale'" in str(c[0][0])]
        self.assertGreaterEqual(len(stale_calls), 1)

    def test_mark_valid(self):
        """设置 data_state='valid' 并更新 source_version。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "v99"})

        self.cm.mark_valid("standard_info_cache", "standard_id", "K1", DataSource.FILE_INDEX)

        valid_calls = [c for c in self.mock_db.execute.call_args_list if "data_state='valid'" in str(c[0][0])]
        self.assertGreaterEqual(len(valid_calls), 1)

    def test_mark_stale_multiple_tables(self):
        """不同表的 mark_stale 互不干扰。"""
        self.cm.mark_stale("standard_info_cache", "standard_id", "A")
        self.cm.mark_stale("announcement_record", "announce_id", "B")
        self.cm.mark_stale("standard_validity", "standard_id", "C")

        stale_calls = [c for c in self.mock_db.execute.call_args_list if "data_state='stale'" in str(c[0][0])]
        self.assertGreaterEqual(len(stale_calls), 3, "三次调用都应执行")

    def test_mark_valid_updates_version(self):
        """mark_valid 将 source_version 更新为当前数据源版本。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "v2026"})

        self.cm.mark_valid("standard_info_cache", "standard_id", "K1", DataSource.FILE_INDEX)

        # 检查 execute 参数中包含版本号
        all_sql = [str(c[0][0]) for c in self.mock_db.execute.call_args_list if c[0]]
        valid_sql = [s for s in all_sql if "data_state='valid'" in s]
        self.assertTrue(any("source_version=?" in s for s in valid_sql))


# ═══════════════════════════════════════════════════════════
# cleanup
# ═══════════════════════════════════════════════════════════


class TestCleanup(unittest.TestCase):
    """测试 cleanup 方法。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_cleanup_skip_below_threshold(self):
        """总大小低于 90% 阈值 → 跳过清理。"""
        self.cm._max_mb = 50  # 阈值 45MB
        with patch.object(self.cm, "get_total_size_mb", return_value=10.0):
            self.cm.cleanup(force=False)
        # 不应有任何 DELETE 调用
        delete_calls = [c for c in self.mock_db.execute.call_args_list if "DELETE FROM" in str(c[0][0]).upper()]
        self.assertEqual(len(delete_calls), 0, "低于阈值不应删除")

    def test_cleanup_force_always_runs(self):
        """force=True 无视阈值。"""
        self.cm._max_mb = 50
        self.mock_db.fetchone = MagicMock(return_value={"cnt": 0})

        with patch.object(self.cm, "get_total_size_mb", return_value=1.0):
            self.cm.cleanup(force=True)

        self.assertTrue(self.mock_db.fetchone.called, "force=True 必须执行清理")

    def test_cleanup_above_threshold(self):
        """超阈值时，依次清理 stale 再清理 valid。"""
        self.cm._max_mb = 50
        self.cm._cleanup_ratio = 0.5
        self.mock_db.fetchone = MagicMock(return_value={"cnt": 10})

        with patch.object(self.cm, "get_total_size_mb", side_effect=[50.0, 30.0]):
            self.cm.cleanup(force=False)

        # 3 个受管理表 x 2 种状态 = 6 次 DELETE
        delete_calls = [c for c in self.mock_db.execute.call_args_list if "DELETE FROM" in str(c[0][0]).upper()]
        self.assertEqual(len(delete_calls), 6, "3 tables x 2 states = 6 DELETE calls")


# ═══════════════════════════════════════════════════════════
# _delete_oldest
# ═══════════════════════════════════════════════════════════


class TestDeleteOldest(unittest.TestCase):
    """测试 _delete_oldest。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_with_data(self):
        """表中有数据 → 按 ratio 删除最旧记录。"""
        self.mock_db.fetchone = MagicMock(return_value={"cnt": 20})
        self.mock_db.execute = MagicMock()

        deleted = self.cm._delete_oldest("standard_info_cache", "stale", 0.3)
        self.assertEqual(deleted, 6)  # max(1, int(20*0.3)) = 6

        delete_sql = str(self.mock_db.execute.call_args[0][0])
        self.assertIn("DELETE FROM standard_info_cache", delete_sql)
        self.assertIn("LIMIT 6", delete_sql)

    def test_empty_table(self):
        """空表 → 返回 0，不执行 DELETE。"""
        self.mock_db.fetchone = MagicMock(return_value={"cnt": 0})
        self.mock_db.execute = MagicMock()

        deleted = self.cm._delete_oldest("standard_info_cache", "stale", 0.1)
        self.assertEqual(deleted, 0)
        self.mock_db.execute.assert_not_called()

    def test_count_none(self):
        """fetchone 返回 None → 返回 0。"""
        self.mock_db.fetchone = MagicMock(return_value=None)
        deleted = self.cm._delete_oldest("standard_info_cache", "stale", 0.1)
        self.assertEqual(deleted, 0)

    def test_exception_returns_zero(self):
        """fetchone 异常 → 返回 0，不崩溃。"""
        self.mock_db.fetchone = MagicMock(side_effect=Exception("DB error"))
        deleted = self.cm._delete_oldest("standard_info_cache", "stale", 0.1)
        self.assertEqual(deleted, 0)

    def test_min_limit_is_one(self):
        """ratio 极小 → limit 至少为 1。"""
        self.mock_db.fetchone = MagicMock(return_value={"cnt": 100})

        deleted = self.cm._delete_oldest("standard_info_cache", "stale", 0.001)
        # int(100 * 0.001) = 0, max(1, 0) = 1
        self.assertEqual(deleted, 1)

    def test_execute_exception_returns_zero(self):
        """execute 异常 → 返回 0，不崩溃。"""
        self.mock_db.fetchone = MagicMock(return_value={"cnt": 10})
        self.mock_db.execute = MagicMock(side_effect=Exception("delete failed"))

        deleted = self.cm._delete_oldest("standard_info_cache", "stale", 0.5)
        self.assertEqual(deleted, 0)


# ═══════════════════════════════════════════════════════════
# get_stats
# ═══════════════════════════════════════════════════════════


class TestGetStats(unittest.TestCase):
    """测试 get_stats。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_structure(self):
        """返回结构完整，包含所有必要字段。"""
        self.mock_db.fetchall = MagicMock(
            return_value=[
                {"data_state": "valid", "cnt": 10},
                {"data_state": "stale", "cnt": 3},
            ]
        )

        with patch.object(self.cm, "get_total_size_mb", return_value=2.5):
            stats = self.cm.get_stats()

        self.assertIn("total_size_mb", stats)
        self.assertIn("max_size_mb", stats)
        self.assertIn("auto_cleanup", stats)
        self.assertIn("cleanup_ratio", stats)
        self.assertIn("tables", stats)
        self.assertEqual(stats["total_size_mb"], 2.5)
        self.assertEqual(stats["max_size_mb"], 50)
        self.assertIs(stats["auto_cleanup"], True)
        self.assertAlmostEqual(stats["cleanup_ratio"], 0.1)

    def test_all_managed_tables_included(self):
        """三个受管理表都有统计条目。"""
        self.mock_db.fetchall = MagicMock(return_value=[])

        with patch.object(self.cm, "get_total_size_mb", return_value=0.0):
            stats = self.cm.get_stats()

        for t in ("standard_info_cache", "standard_validity", "announcement_record"):
            self.assertIn(t, stats["tables"], f"{t} 应在 tables 中")

    def test_empty_tables_stats(self):
        """空表时 tables 中的条目为空 dict。"""
        self.mock_db.fetchall = MagicMock(return_value=[])

        with patch.object(self.cm, "get_total_size_mb", return_value=0.0):
            stats = self.cm.get_stats()

        for t in ("standard_info_cache", "standard_validity", "announcement_record"):
            self.assertEqual(stats["tables"][t], {})


# ═══════════════════════════════════════════════════════════
# get_total_size_mb（三条降级路径）
# ═══════════════════════════════════════════════════════════


class TestGetTotalSizeMb(unittest.TestCase):
    """测试 get_total_size_mb 三条降级路径。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    # ── 路径 1: dbstat ──

    def test_dbstat_path(self):
        """dbstat 可用 → 直接使用 pgsize 总和。"""
        self.mock_db.fetchone = MagicMock(return_value={"total_bytes": 2097152})  # 2 MB
        result = self.cm.get_total_size_mb()
        self.assertAlmostEqual(result, 2.0, places=1)

    def test_dbstat_none_total_bytes_falls_back(self):
        """dbstat 返回 total_bytes=None → 降级到估算。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                {"total_bytes": None},  # dbstat
                Exception("pragma failed"),  # pragma
                {"cnt": 50},  # standard_info_cache
                {"cnt": 30},  # standard_validity
                {"cnt": 20},  # announcement_record
            ]
        )
        result = self.cm.get_total_size_mb()
        expected = 100 * 500 / (1024 * 1024)  # ≈ 0.0477
        self.assertAlmostEqual(result, expected, places=3)

    # ── 路径 2: pragma ──

    def test_pragma_path(self):
        """dbstat 异常 → 降级到 pragma 估算。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                Exception("dbstat not available"),  # dbstat 异常
                {"db_bytes": 5242880},  # pragma: 5 MB
                {"cnt": 100},  # table 1
                {"cnt": 0},  # table 2
                {"cnt": 0},  # table 3
            ]
        )
        self.mock_db.fetchall = MagicMock(return_value=[{"cnt": 500}])

        result = self.cm.get_total_size_mb()
        # ratio = 100 / 500 = 0.2; 5242880 * 0.2 / (1024*1024) = 1.0
        self.assertAlmostEqual(result, 1.0, places=1)

    def test_pragma_zero_rows(self):
        """pragma 路径，缓存表行数为 0 → 按 30% 估算。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                Exception("dbstat not available"),
                {"db_bytes": 10485760},  # 10 MB
                {"cnt": 0},
                {"cnt": 0},
                {"cnt": 0},
            ]
        )
        result = self.cm.get_total_size_mb()
        # 0 rows → 10 * 0.3 = 3.0
        self.assertAlmostEqual(result, 3.0, places=1)

    def test_pragma_none_db_bytes_falls_back(self):
        """pragma 返回 db_bytes=None → 降级到行数估算。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                Exception("dbstat not available"),
                {"db_bytes": None},  # pragma: None
                {"cnt": 10},
                {"cnt": 20},
                {"cnt": 30},
            ]
        )
        result = self.cm.get_total_size_mb()
        expected = 60 * 500 / (1024 * 1024)
        self.assertAlmostEqual(result, expected, places=3)

    def test_pragma_exception_during_row_counts(self):
        """pragma 路径中，fetchall for sqlite_master 异常 → 降级。
        异常导致所有 fetchone side_effect 耗尽后方案3也返回 0。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                Exception("dbstat not available"),
                {"db_bytes": 10485760},
                {"cnt": 50},
                {"cnt": 0},
                {"cnt": 0},
            ]
        )
        self.mock_db.fetchall = MagicMock(side_effect=Exception("master fail"))

        result = self.cm.get_total_size_mb()
        # fetchone side_effect 在方案2中耗尽，方案3所有调用都抛 StopIteration → 返回 0.0
        self.assertEqual(result, 0.0)

    # ── 路径 3: 行数估算 ──

    def test_fallback_path(self):
        """dbstat 和 pragma 都失败 → 行数 * 500 字节估算。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                Exception("dbstat failed"),
                Exception("pragma failed"),
                {"cnt": 100},
                {"cnt": 50},
                {"cnt": 50},
            ]
        )
        result = self.cm.get_total_size_mb()
        expected = 200 * 500 / (1024 * 1024)
        self.assertAlmostEqual(result, expected, places=3)

    def test_fallback_individual_table_exception(self):
        """fallback 中单个表 COUNT 异常不影响其他表。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                Exception("dbstat failed"),
                Exception("pragma failed"),
                {"cnt": 100},  # ok
                Exception("table missing"),  # 异常，跳过
                {"cnt": 50},  # ok
            ]
        )
        result = self.cm.get_total_size_mb()
        expected = 150 * 500 / (1024 * 1024)
        self.assertAlmostEqual(result, expected, places=3)

    def test_fallback_all_tables_exception(self):
        """fallback 中所有表都异常 → 返回 0。"""
        self.mock_db.fetchone = MagicMock(
            side_effect=[
                Exception("dbstat failed"),
                Exception("pragma failed"),
                Exception("table1 missing"),
                Exception("table2 missing"),
                Exception("table3 missing"),
            ]
        )
        result = self.cm.get_total_size_mb()
        self.assertEqual(result, 0.0)


# ═══════════════════════════════════════════════════════════
# get_config / set_config
# ═══════════════════════════════════════════════════════════


class TestGetSetConfig(unittest.TestCase):
    """测试 get_config 和 set_config。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_get_config_defaults(self):
        """get_config 返回默认值。"""
        c = self.cm.get_config()
        self.assertEqual(c["max_size_mb"], 50)
        self.assertIs(c["auto_cleanup"], True)
        self.assertAlmostEqual(c["cleanup_ratio"], 0.1)

    def test_set_config_max_size_mb(self):
        """set_config("max_size_mb", ...) 更新实例变量并写入 DB。"""
        self.cm.set_config("max_size_mb", 200)
        self.assertEqual(self.cm._max_mb, 200)
        self.mock_db.execute.assert_called()
        call_sql = str(self.mock_db.execute.call_args[0][0])
        self.assertIn("cache_config", call_sql)

    def test_set_config_auto_cleanup_bool(self):
        """set_config("auto_cleanup", bool)。"""
        self.cm.set_config("auto_cleanup", False)
        self.assertIs(self.cm._auto_cleanup, False)
        self.cm.set_config("auto_cleanup", True)
        self.assertIs(self.cm._auto_cleanup, True)

    def test_set_config_auto_cleanup_string(self):
        """set_config("auto_cleanup", "true") → True。"""
        self.cm.set_config("auto_cleanup", "true")
        self.assertIs(self.cm._auto_cleanup, True)
        self.cm.set_config("auto_cleanup", "false")
        self.assertIs(self.cm._auto_cleanup, False)

    def test_set_config_cleanup_ratio(self):
        """set_config("cleanup_ratio", float/int)。"""
        self.cm.set_config("cleanup_ratio", 0.5)
        self.assertAlmostEqual(self.cm._cleanup_ratio, 0.5)
        self.cm.set_config("cleanup_ratio", 1)
        self.assertAlmostEqual(self.cm._cleanup_ratio, 1.0)

    def test_set_config_unknown_key(self):
        """未知 key 只写 DB，不影响实例变量，不崩溃。"""
        old_max = self.cm._max_mb
        self.cm.set_config("unknown_key", "value")
        self.assertEqual(self.cm._max_mb, old_max)
        self.mock_db.execute.assert_called()

    def test_get_config_after_set(self):
        """set_config 后 get_config 反映新值。"""
        self.cm.set_config("max_size_mb", 150)
        self.cm.set_config("auto_cleanup", False)
        self.cm.set_config("cleanup_ratio", 0.25)

        c = self.cm.get_config()
        self.assertEqual(c["max_size_mb"], 150)
        self.assertIs(c["auto_cleanup"], False)
        self.assertAlmostEqual(c["cleanup_ratio"], 0.25)

    def test_set_config_stores_bool_as_lowercase_string(self):
        """set_config bool 值存入 DB 应为 'true'/'false' 小写。"""
        self.cm.set_config("auto_cleanup", True)
        # 检查 execute 的 params
        call_params = self.mock_db.execute.call_args[0][1]
        self.assertIn("true", call_params)


# ═══════════════════════════════════════════════════════════
# _get_source_version / _bump_version
# ═══════════════════════════════════════════════════════════


class TestSourceVersion(unittest.TestCase):
    """测试版本管理内部方法。"""

    def setUp(self):
        self.mock_db = _make_mock_db(tables_exist=True)
        self.cm = CacheManager(self.mock_db)

    def test_get_source_version_exists(self):
        """行存在 → 返回版本字符串。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "2026-07-14T00:00:00"})
        v = self.cm._get_source_version(DataSource.FILE_INDEX)
        self.assertEqual(v, "2026-07-14T00:00:00")

    def test_get_source_version_not_exists(self):
        """行不存在 → 返回 "initial"。"""
        self.mock_db.fetchone = MagicMock(return_value=None)
        v = self.cm._get_source_version(DataSource.FILE_INDEX)
        self.assertEqual(v, "initial")

    def test_bump_version_returns_iso_format(self):
        """_bump_version 返回 ISO 格式时间戳。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "old"})

        result = self.cm._bump_version(DataSource.FILE_INDEX)
        self.assertIsInstance(result, str)
        self.assertIn("T", result, "应为 ISO 8601 格式")

    def test_bump_version_updates_db(self):
        """_bump_version 更新 data_source_versions 表。"""
        self.mock_db.fetchone = MagicMock(return_value={"version": "old"})

        self.cm._bump_version(DataSource.ANNOUNCEMENT)

        update_calls = [c for c in self.mock_db.execute.call_args_list if "UPDATE data_source_versions" in str(c[0][0])]
        self.assertGreaterEqual(len(update_calls), 1)

    def test_bump_version_all_sources(self):
        """三种数据源都可以 bump 版本。"""
        for src in (DataSource.FILE_INDEX, DataSource.ANNOUNCEMENT, DataSource.VALIDITY):
            mock_db = _make_mock_db(tables_exist=True)
            cm = CacheManager(mock_db)
            mock_db.fetchone = MagicMock(return_value={"version": "old"})

            result = cm._bump_version(src)
            self.assertIsInstance(result, str)
            self.assertIn("T", result)


# ═══════════════════════════════════════════════════════════
# _load_config_int / _load_config_bool / _load_config_float
# ═══════════════════════════════════════════════════════════


class TestLoadConfig(unittest.TestCase):
    """测试 _load_config_* 三个内部方法。"""

    def _make_fresh_cm(self):
        """创建干净的 CacheManager 用于独立测试 _load_* 方法。"""
        mock_db = _make_mock_db(tables_exist=True)
        cm = CacheManager(mock_db)
        return cm, mock_db

    # ── _load_config_int ──

    def test_load_int_from_db(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "80"})
        self.assertEqual(cm._load_config_int("max_size_mb", 50), 80)

    def test_load_int_default_when_none(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value=None)
        self.assertEqual(cm._load_config_int("max_size_mb", 50), 50)

    def test_load_int_default_on_exception(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(side_effect=ValueError("bad"))
        self.assertEqual(cm._load_config_int("max_size_mb", 50), 50)

    def test_load_int_invalid_string(self):
        """config_value 不是合法整数 → 异常 → 返回默认值。"""
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "not_a_number"})
        self.assertEqual(cm._load_config_int("max_size_mb", 50), 50)

    # ── _load_config_bool ──

    def test_load_bool_true(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "true"})
        self.assertIs(cm._load_config_bool("auto_cleanup", False), True)

    def test_load_bool_false(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "false"})
        self.assertIs(cm._load_config_bool("auto_cleanup", True), False)

    def test_load_bool_non_true_value(self):
        """ "true" 以外的值都视为 False。"""
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "yes"})
        self.assertIs(cm._load_config_bool("auto_cleanup", True), False)

    def test_load_bool_default_when_none(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value=None)
        self.assertIs(cm._load_config_bool("auto_cleanup", True), True)

    def test_load_bool_default_on_exception(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(side_effect=RuntimeError("fail"))
        self.assertIs(cm._load_config_bool("auto_cleanup", False), False)

    # ── _load_config_float ──

    def test_load_float_from_db(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "0.35"})
        self.assertAlmostEqual(cm._load_config_float("cleanup_ratio", 0.1), 0.35)

    def test_load_float_default_when_none(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value=None)
        self.assertAlmostEqual(cm._load_config_float("cleanup_ratio", 0.1), 0.1)

    def test_load_float_default_on_exception(self):
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(side_effect=Exception("fail"))
        self.assertAlmostEqual(cm._load_config_float("cleanup_ratio", 0.1), 0.1)

    def test_load_float_invalid_string(self):
        """config_value 不是合法浮点数 → 异常 → 返回默认值。"""
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "abc"})
        self.assertAlmostEqual(cm._load_config_float("cleanup_ratio", 0.1), 0.1)

    def test_load_float_int_value(self):
        """config_value 是整数也能正确解析为 float。"""
        cm, mock_db = self._make_fresh_cm()
        mock_db.fetchone = MagicMock(return_value={"config_value": "1"})
        self.assertAlmostEqual(cm._load_config_float("cleanup_ratio", 0.1), 1.0)


# ═══════════════════════════════════════════════════════════
# 集成场景
# ═══════════════════════════════════════════════════════════


class TestIntegrationScenarios(unittest.TestCase):
    """端到端生命周期：set → get → invalidate → get → mark_valid。"""

    def test_cleanup_full_cycle(self):
        """cleanup 完整流程：从跳过到强制清理。"""
        mock_db = _make_mock_db(tables_exist=True)
        cm = CacheManager(mock_db)
        cm._max_mb = 50
        cm._cleanup_ratio = 0.5

        # 低于阈值 → 跳过
        mock_db.fetchone = MagicMock(return_value={"cnt": 10})
        with patch.object(cm, "get_total_size_mb", return_value=10.0):
            cm.cleanup(force=False)
        # 确认没有 DELETE
        delete_calls = [c for c in mock_db.execute.call_args_list if "DELETE FROM" in str(c[0][0]).upper()]
        self.assertEqual(len(delete_calls), 0)

        # 强制清理
        mock_db.execute.reset_mock()
        with patch.object(cm, "get_total_size_mb", return_value=1.0):
            cm.cleanup(force=True)
        delete_calls = [c for c in mock_db.execute.call_args_list if "DELETE FROM" in str(c[0][0]).upper()]
        self.assertGreater(len(delete_calls), 0)


if __name__ == "__main__":
    unittest.main()
