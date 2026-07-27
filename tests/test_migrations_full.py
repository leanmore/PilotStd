# tests/test_migrations_full.py
# migrations.py 完整单元测试 — 覆盖所有迁移函数 v2-v40
#
# 设计原则：
# 1. 所有迁移函数接受 db 参数（DI），测试中用 MagicMock
# 2. 不修改被测文件
# 3. 使用 unittest.TestCase 组织
# 4. 使用 assert_any_call 验证 SQL 调用，不匹配完整 SQL 字符串

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.core.db._constants import MIGRATIONS

# ---------------------------------------------------------------------------
# 导入被测试的迁移函数
# ---------------------------------------------------------------------------
from pilotstd.core.db.migrations import (  # type: ignore[import-untyped]
    _migrate_v2_add_file_index,
    _migrate_v3_queue_and_pending,
    _migrate_v4_add_fetch_checkpoint,
    _migrate_v5_announcement_match,
    _migrate_v6_add_rotator_state,
    _migrate_v7_add_last_checked,
    _migrate_v8_drop_expires_at,
    _migrate_v9_add_requery_count,
    _migrate_v10_add_source_and_status_history,
    _migrate_v11_add_daily_limits,
    _migrate_v12_adapter_stats,
    _migrate_v13_adapter_stats_extend,
    _migrate_v14_api_keys,
    _migrate_v15_announcement_record,
    _migrate_v16_standard_validity,
    _migrate_v17_notification_log,
    _migrate_v18_notification_fetch_task,
    _migrate_v19_users,
    _migrate_v20_announce_since_date,
    _migrate_v21_user_layouts,
    _migrate_v22_user_preferences,
    _migrate_v23_cache_system,
    _migrate_v24_task_queue,
    _migrate_v25_announcement_match_cache,
    _migrate_v26_pipeline_runs,
    _migrate_v27_notification_aggregation,
    _migrate_v28_notification_queue,
    _migrate_v29_announce_title_and_count,
    _migrate_v30_failure_tables,
    _migrate_v31_monitor_stats,
    _migrate_v32_cleanup_dead_tables,
    _migrate_v33_adapter_state,
    _migrate_v34_drop_old_adapter_tables,
    _migrate_v35_notification_policy,
    _migrate_v36_announcement_structure,
    _migrate_v37_user_notification_config,
    _migrate_v38_user_settings,
)

# ---------------------------------------------------------------------------
# 辅助方法
# ---------------------------------------------------------------------------


# 用于 PRAGMA table_info 返回的列名 mock
def _make_cols(*names: str):
    """构造 db.fetchall() 返回的列信息列表，每项含 'name' 键。"""
    return [{"name": n} for n in names]


class _AssertMixin:
    """混合断言工具，减少重复代码。"""

    @staticmethod
    def assert_exec_contains(mock_db: MagicMock, sql_fragment: str, msg: str = "") -> None:
        """验证 mock_db.execute 的任意一次调用中包含 sql_fragment。"""
        for call_args in mock_db.execute.call_args_list:
            args = call_args[0]
            if args and sql_fragment in args[0]:
                return
        calls = [c[0][0][:120] if c[0] else "()" for c in mock_db.execute.call_args_list]
        raise AssertionError(f"{msg}未找到包含 '{sql_fragment}' 的 execute 调用。\n实际调用（截取前120字符）: {calls}")

    @staticmethod
    def assert_exec_count(mock_db: MagicMock, expected: int, msg: str = "") -> None:
        """验证 db.execute 的总调用次数。"""
        actual = len(mock_db.execute.call_args_list)
        if actual != expected:
            calls = [c[0][0][:100] if c[0] else "()" for c in mock_db.execute.call_args_list]
            raise AssertionError(f"{msg}期望 execute 调用 {expected} 次，实际 {actual} 次。\n调用列表: {calls}")


# ---------------------------------------------------------------------------
# v2 - v10 迁移测试
# ---------------------------------------------------------------------------


class TestMigrationsV2V10(unittest.TestCase, _AssertMixin):
    """测试 v2 到 v10 的迁移函数。"""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.db.execute = MagicMock()
        self.db.fetchall = MagicMock()

    # ---- v2 ----------------------------------------------------------------

    def test_v2_creates_file_index_table(self) -> None:
        """v2: 创建 file_index 表 + 2 个索引。"""
        _migrate_v2_add_file_index(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS file_index")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_file_index_hash")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_file_index_code")
        self.assert_exec_count(self.db, 3, "v2")

    # ---- v3 ----------------------------------------------------------------

    def test_v3_creates_queue_and_pending_tables(self) -> None:
        """v3: 创建 download_queue + pending_lookup 表及索引。"""
        self.db.fetchall.return_value = _make_cols("id", "file_path", "status")

        _migrate_v3_queue_and_pending(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS download_queue")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_download_queue_status")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS pending_lookup")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_pending_lookup_status")
        self.db.fetchall.assert_called_once_with("PRAGMA table_info(file_index)")

    def test_v3_adds_status_column_when_missing(self) -> None:
        """v3: file_index 缺少 status 列时执行 ALTER TABLE。"""
        self.db.fetchall.return_value = _make_cols("id", "file_path")

        _migrate_v3_queue_and_pending(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE file_index ADD COLUMN status")

    def test_v3_skips_status_column_when_present(self) -> None:
        """v3: file_index 已有 status 列时跳过 ALTER TABLE。"""
        self.db.fetchall.return_value = _make_cols("id", "file_path", "status")

        _migrate_v3_queue_and_pending(self.db)

        for call_args in self.db.execute.call_args_list:
            args = call_args[0]
            if args:
                self.assertNotIn("ALTER TABLE file_index ADD COLUMN status", args[0])

    # ---- v4 ----------------------------------------------------------------

    def test_v4_creates_fetch_checkpoint(self) -> None:
        """v4: 创建 fetch_checkpoint 表。"""
        _migrate_v4_add_fetch_checkpoint(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS fetch_checkpoint")
        self.assert_exec_count(self.db, 1, "v4")

    # ---- v5 ----------------------------------------------------------------

    def test_v5_creates_announcement_match(self) -> None:
        """v5: 创建 announcement_match 表 + 唯一索引。"""
        _migrate_v5_announcement_match(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS announcement_match")
        self.assert_exec_contains(self.db, "CREATE UNIQUE INDEX IF NOT EXISTS idx_announcement_match_lookup")
        self.assert_exec_count(self.db, 2, "v5")

    # ---- v6 ----------------------------------------------------------------

    def test_v6_creates_rotator_state(self) -> None:
        """v6: 创建 rotator_state 表。"""
        _migrate_v6_add_rotator_state(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS rotator_state")
        self.assert_exec_count(self.db, 1, "v6")

    # ---- v7 ----------------------------------------------------------------

    def test_v7_adds_last_checked_and_index(self) -> None:
        """v7: ALTER TABLE file_index ADD last_checked + 创建索引。"""
        _migrate_v7_add_last_checked(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE file_index ADD COLUMN last_checked")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_file_index_last_checked")
        self.assert_exec_count(self.db, 2, "v7")

    def test_v7_handles_alter_exception_gracefully(self) -> None:
        """v7: ALTER TABLE 抛异常时静默吞掉，继续创建索引。"""
        self.db.execute = MagicMock()
        self.db.execute.side_effect = [
            Exception("列已存在"),  # ALTER TABLE 失败
            None,  # CREATE INDEX 成功
        ]

        _migrate_v7_add_last_checked(self.db)

        self.assertEqual(self.db.execute.call_count, 2)
        # 第二个 execute 调用应该是创建索引
        second_call = self.db.execute.call_args_list[1][0][0]
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_file_index_last_checked", second_call)

    def test_v7_handles_index_exception_gracefully(self) -> None:
        """v7: 索引创建抛异常时静默吞掉。"""
        self.db.execute = MagicMock()
        self.db.execute.side_effect = [
            None,  # ALTER TABLE 成功
            Exception("表不存在"),  # CREATE INDEX 失败
        ]

        _migrate_v7_add_last_checked(self.db)

        self.assertEqual(self.db.execute.call_count, 2)

    def test_v7_handles_both_exceptions_gracefully(self) -> None:
        """v7: ALTER TABLE 和索引创建都抛异常时静默吞掉。"""
        self.db.execute = MagicMock()
        self.db.execute.side_effect = [
            Exception("列已存在"),
            Exception("表不存在"),
        ]

        _migrate_v7_add_last_checked(self.db)

        self.assertEqual(self.db.execute.call_count, 2)

    # ---- v8 ----------------------------------------------------------------

    def test_v8_drops_expires_at_when_exists(self) -> None:
        """v8: standard_info_cache 存在且有 expires_at 列时执行 DROP。"""
        self.db.fetchall.return_value = _make_cols("id", "standard_number", "expires_at")

        _migrate_v8_drop_expires_at(self.db)

        self.db.fetchall.assert_called_once_with("PRAGMA table_info(standard_info_cache)")
        self.assert_exec_contains(self.db, "ALTER TABLE standard_info_cache DROP COLUMN expires_at")

    def test_v8_skips_when_table_missing(self) -> None:
        """v8: standard_info_cache 表不存在时直接返回，不执行 ALTER。"""
        self.db.fetchall.return_value = []  # 空列表表示表不存在

        _migrate_v8_drop_expires_at(self.db)

        self.db.execute.assert_not_called()

    def test_v8_skips_when_column_missing(self) -> None:
        """v8: standard_info_cache 存在但无 expires_at 列时跳过 DROP。"""
        self.db.fetchall.return_value = _make_cols("id", "standard_number")

        _migrate_v8_drop_expires_at(self.db)

        for call_args in self.db.execute.call_args_list:
            args = call_args[0]
            if args:
                self.assertNotIn("DROP COLUMN", args[0])

    # ---- v9 ----------------------------------------------------------------

    def test_v9_adds_requery_count(self) -> None:
        """v9: pending_lookup 缺少 requery_count 列时执行 ALTER TABLE。"""
        self.db.fetchall.return_value = _make_cols("id", "standard_number")

        _migrate_v9_add_requery_count(self.db)

        self.db.fetchall.assert_called_once_with("PRAGMA table_info(pending_lookup)")
        self.assert_exec_contains(self.db, "ALTER TABLE pending_lookup ADD COLUMN requery_count")

    def test_v9_skips_when_table_missing(self) -> None:
        """v9: pending_lookup 表不存在时直接返回。"""
        self.db.fetchall.return_value = []

        _migrate_v9_add_requery_count(self.db)

        self.db.execute.assert_not_called()

    def test_v9_skips_when_column_exists(self) -> None:
        """v9: pending_lookup 已有 requery_count 列时跳过 ALTER。"""
        self.db.fetchall.return_value = _make_cols("id", "requery_count")

        _migrate_v9_add_requery_count(self.db)

        for call_args in self.db.execute.call_args_list:
            args = call_args[0]
            if args:
                self.assertNotIn("ALTER TABLE", args[0])

    # ---- v10 ---------------------------------------------------------------

    def test_v10_adds_source_and_status_history(self) -> None:
        """v10: standard_info_cache 缺少 source/status_history 列时执行 ALTER。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v10_add_source_and_status_history(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE standard_info_cache ADD COLUMN source")
        self.assert_exec_contains(self.db, "ALTER TABLE standard_info_cache ADD COLUMN status_history")
        self.assert_exec_count(self.db, 2, "v10 应添加 2 列")

    def test_v10_skips_when_table_missing(self) -> None:
        """v10: standard_info_cache 表不存在时直接返回。"""
        self.db.fetchall.return_value = []

        _migrate_v10_add_source_and_status_history(self.db)

        self.db.execute.assert_not_called()

    def test_v10_skips_existing_columns(self) -> None:
        """v10: 部分列已存在时只添加缺失的列。"""
        self.db.fetchall.return_value = _make_cols("id", "source")  # status_history 缺失

        _migrate_v10_add_source_and_status_history(self.db)

        # 只应该调用 1 次 ALTER（添加 status_history）
        alter_calls = [c[0][0] for c in self.db.execute.call_args_list if c[0] and "ALTER TABLE" in c[0][0]]
        self.assertEqual(len(alter_calls), 1)
        self.assertIn("status_history", alter_calls[0])


# ---------------------------------------------------------------------------
# v11 - v20 迁移测试
# ---------------------------------------------------------------------------


class TestMigrationsV11V20(unittest.TestCase, _AssertMixin):
    """测试 v11 到 v20 的迁移函数。"""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.db.execute = MagicMock()
        self.db.fetchall = MagicMock()

    # ---- v11 ---------------------------------------------------------------

    def test_v11_adds_daily_limits(self) -> None:
        """v11: rotator_state 缺少 daily_count/daily_date 时执行 ALTER。"""
        self.db.fetchall.return_value = _make_cols("site_name")

        _migrate_v11_add_daily_limits(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE rotator_state ADD COLUMN daily_count")
        self.assert_exec_contains(self.db, "ALTER TABLE rotator_state ADD COLUMN daily_date")
        self.assert_exec_count(self.db, 2, "v11 应添加 2 列")

    def test_v11_skips_when_table_missing(self) -> None:
        """v11: rotator_state 表不存在时直接返回。"""
        self.db.fetchall.return_value = []

        _migrate_v11_add_daily_limits(self.db)

        self.db.execute.assert_not_called()

    # ---- v12 ---------------------------------------------------------------

    def test_v12_creates_adapter_stats(self) -> None:
        """v12: 创建 adapter_stats 表。"""
        _migrate_v12_adapter_stats(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS adapter_stats")
        self.assert_exec_count(self.db, 1, "v12")

    # ---- v13 ---------------------------------------------------------------

    def test_v13_adds_all_missing_columns(self) -> None:
        """v13: adapter_stats 缺少所有扩展列时全部添加（5 列）。"""
        self.db.fetchall.return_value = _make_cols("adapter_name")

        _migrate_v13_adapter_stats_extend(self.db)

        self.assert_exec_count(self.db, 5, "v13 adapter_stats 缺失时应添加 5 列")
        self.assert_exec_contains(self.db, "avg_response_time")
        self.assert_exec_contains(self.db, "total_response_time")
        self.assert_exec_contains(self.db, "cooldown_count")
        self.assert_exec_contains(self.db, "last_cooldown_reason")
        self.assert_exec_contains(self.db, "last_cooldown_at")

    def test_v13_skips_when_table_missing(self) -> None:
        """v13: adapter_stats 表不存在时直接返回。"""
        self.db.fetchall.return_value = []

        _migrate_v13_adapter_stats_extend(self.db)

        self.db.execute.assert_not_called()

    def test_v13_skips_existing_columns(self) -> None:
        """v13: 所有列已存在时跳过全部 ALTER。"""
        self.db.fetchall.return_value = _make_cols(
            "adapter_name",
            "avg_response_time",
            "total_response_time",
            "cooldown_count",
            "last_cooldown_reason",
            "last_cooldown_at",
        )

        _migrate_v13_adapter_stats_extend(self.db)

        for call_args in self.db.execute.call_args_list:
            args = call_args[0]
            if args:
                self.assertNotIn("ALTER TABLE", args[0])

    # ---- v14 ---------------------------------------------------------------

    def test_v14_creates_api_keys(self) -> None:
        """v14: 创建 api_keys 表 + 2 个索引。"""
        _migrate_v14_api_keys(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS api_keys")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_api_keys_is_active")
        self.assert_exec_count(self.db, 3, "v14")

    # ---- v15 ---------------------------------------------------------------

    def test_v15_creates_announcement_record(self) -> None:
        """v15: 创建 announcement_record 表 + 3 个索引。"""
        _migrate_v15_announcement_record(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS announcement_record")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_pid")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_standard")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_matched")
        self.assert_exec_count(self.db, 4, "v15")

    # ---- v16 ---------------------------------------------------------------

    def test_v16_creates_standard_validity(self) -> None:
        """v16: 创建 standard_validity 表 + 2 个索引。"""
        _migrate_v16_standard_validity(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS standard_validity")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_validity_next_check")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_validity_standard")
        self.assert_exec_count(self.db, 3, "v16")

    # ---- v17 ---------------------------------------------------------------

    def test_v17_creates_notification_log(self) -> None:
        """v17: 创建 notification_log 表 + 2 个索引。"""
        _migrate_v17_notification_log(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS notification_log")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_notif_sent_at")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_notif_event_type")
        self.assert_exec_count(self.db, 3, "v17")

    # ---- v18 ---------------------------------------------------------------

    def test_v18_alters_and_creates_tables(self) -> None:
        """v18: ALTER notification_log（2 列） + CREATE fetch_task + CREATE adapter_health。"""
        _migrate_v18_notification_fetch_task(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE notification_log ADD COLUMN is_read")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_notif_is_read")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS fetch_task")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS adapter_health")
        self.assert_exec_count(self.db, 4, "v18")

    def test_v18_handles_alter_exception(self) -> None:
        """v18: ALTER TABLE 抛异常时静默继续。"""
        self.db.execute = MagicMock()
        self.db.execute.side_effect = [
            Exception("列已存在"),  # ALTER TABLE is_read 失败
            None,  # CREATE INDEX idx_notif_is_read 成功
            None,  # CREATE TABLE fetch_task 成功
            None,  # CREATE TABLE adapter_health 成功
        ]

        _migrate_v18_notification_fetch_task(self.db)

        self.assert_exec_count(self.db, 4, "v18 异常路径仍应执行 4 次")

    # ---- v19 ---------------------------------------------------------------

    def test_v19_creates_users(self) -> None:
        """v19: 创建 users 表。"""
        _migrate_v19_users(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS users")
        self.assert_exec_count(self.db, 1, "v19")

    # ---- v20 ---------------------------------------------------------------

    def test_v20_adds_since_date(self) -> None:
        """v20: ALTER TABLE fetch_checkpoint ADD since_date_override。"""
        _migrate_v20_announce_since_date(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE fetch_checkpoint ADD COLUMN since_date_override")

    def test_v20_handles_alter_exception(self) -> None:
        """v20: ALTER TABLE 抛异常时静默吞掉。"""
        self.db.execute.side_effect = Exception("列已存在")

        _migrate_v20_announce_since_date(self.db)

        self.assert_exec_count(self.db, 1, "v20 异常时仍应执行 1 次 ALTER")


# ---------------------------------------------------------------------------
# v21 - v30 迁移测试
# ---------------------------------------------------------------------------


class TestMigrationsV21V30(unittest.TestCase, _AssertMixin):
    """测试 v21 到 v30 的迁移函数。"""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.db.execute = MagicMock()
        self.db.fetchall = MagicMock()

    # ---- v21 ---------------------------------------------------------------

    def test_v21_creates_user_layouts(self) -> None:
        """v21: 创建 user_layouts 表。"""
        _migrate_v21_user_layouts(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS user_layouts")
        self.assert_exec_count(self.db, 1, "v21")

    # ---- v22 ---------------------------------------------------------------

    def test_v22_creates_user_preferences(self) -> None:
        """v22: 创建 user_preferences 表 + 索引。"""
        _migrate_v22_user_preferences(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS user_preferences")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_user_preferences_user_key")
        self.assert_exec_count(self.db, 2, "v22")

    # ---- v23 ---------------------------------------------------------------

    def test_v23_creates_cache_tables_and_alters(self) -> None:
        """v23: 创建 data_source_versions + cache_config 表，并 ALTER 多张表。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v23_cache_system(self.db)

        # 两张新表
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS data_source_versions")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS cache_config")
        # INSERT 操作（data_source_versions 3 行 + cache_config 3 行 = 6 个 INSERT）
        insert_calls = [c for c in self.db.execute.call_args_list if c[0] and "INSERT OR IGNORE" in c[0][0]]
        self.assertEqual(len(insert_calls), 6, "v23 应有 6 个 INSERT OR IGNORE")

    def test_v23_alters_standard_validity(self) -> None:
        """v23: 对 standard_validity 执行 3 个 ALTER TABLE。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v23_cache_system(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE standard_validity ADD COLUMN source_version")
        self.assert_exec_contains(self.db, "ALTER TABLE standard_validity ADD COLUMN data_state")
        self.assert_exec_contains(self.db, "ALTER TABLE standard_validity ADD COLUMN last_accessed_at")

    def test_v23_alters_standard_info_cache(self) -> None:
        """v23: 对 standard_info_cache 执行 3 个 ALTER TABLE。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v23_cache_system(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE standard_info_cache ADD COLUMN source_version")
        self.assert_exec_contains(self.db, "ALTER TABLE standard_info_cache ADD COLUMN data_state")
        self.assert_exec_contains(self.db, "ALTER TABLE standard_info_cache ADD COLUMN last_accessed_at")

    def test_v23_alters_announcement_match(self) -> None:
        """v23: 对 announcement_match 执行 3 个 ALTER TABLE。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v23_cache_system(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE announcement_match ADD COLUMN source_version")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_match ADD COLUMN data_state")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_match ADD COLUMN last_accessed_at")

    def test_v23_alters_announcement_record(self) -> None:
        """v23: 对 announcement_record 执行 3 个 ALTER TABLE。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v23_cache_system(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN source_version")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN data_state")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN last_accessed_at")

    def test_v23_total_execute_count(self) -> None:
        """v23: 总计 execute 调用次数 = 2 CREATE + 6 INSERT + 12 ALTER = 20。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v23_cache_system(self.db)

        # 2 张表 CREATE + 6 个 INSERT + 4 表 × 3 ALTER = 2 + 6 + 12 = 20
        self.assert_exec_count(self.db, 20, "v23")

    # ---- v24 ---------------------------------------------------------------

    def test_v24_creates_task_queue_with_indexes_and_alters(self) -> None:
        """v24: 创建 task_queue 表 + 多个索引 + 7 个 ALTER TABLE ADD COLUMN。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v24_task_queue(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS task_queue")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_task_queue_status")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_task_queue_updated")
        self.assert_exec_contains(self.db, "ALTER TABLE task_queue ADD COLUMN retry_count")
        self.assert_exec_contains(self.db, "ALTER TABLE task_queue ADD COLUMN max_retries")
        self.assert_exec_contains(self.db, "ALTER TABLE task_queue ADD COLUMN timeout_seconds")
        self.assert_exec_contains(self.db, "ALTER TABLE task_queue ADD COLUMN started_at")
        self.assert_exec_contains(self.db, "ALTER TABLE task_queue ADD COLUMN finished_at")
        self.assert_exec_contains(self.db, "ALTER TABLE task_queue ADD COLUMN priority")
        self.assert_exec_contains(self.db, "ALTER TABLE task_queue ADD COLUMN queue_name")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_task_queue_status_created")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_task_queue_status_priority")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_task_queue_queue_name")

    def test_v24_total_execute_count(self) -> None:
        """v24: 总计 execute 调用 = 1 CREATE + 2 初始索引 + 7 ALTER + 3 后续索引 = 13。"""
        self.db.fetchall.return_value = _make_cols("id")

        _migrate_v24_task_queue(self.db)

        self.assert_exec_count(self.db, 13, "v24")

    # ---- v25 ---------------------------------------------------------------

    def test_v25_alters_announcement_match(self) -> None:
        """v25: announcement_match 添加 source + status_history 两列。"""
        _migrate_v25_announcement_match_cache(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE announcement_match ADD COLUMN source")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_match ADD COLUMN status_history")
        self.assert_exec_count(self.db, 2, "v25")

    # ---- v26 ---------------------------------------------------------------

    def test_v26_creates_pipeline_runs(self) -> None:
        """v26: 创建 pipeline_runs 表 + 2 个索引。"""
        _migrate_v26_pipeline_runs(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS pipeline_runs")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status")
        self.assert_exec_count(self.db, 3, "v26")

    # ---- v27 ---------------------------------------------------------------

    def test_v27_alters_notification_log(self) -> None:
        """v27: notification_log 添加 3 列。"""
        _migrate_v27_notification_aggregation(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE notification_log ADD COLUMN aggregated_count")
        self.assert_exec_contains(self.db, "ALTER TABLE notification_log ADD COLUMN link")
        self.assert_exec_contains(self.db, "ALTER TABLE notification_log ADD COLUMN icon")
        self.assert_exec_count(self.db, 3, "v27")

    # ---- v28 ---------------------------------------------------------------

    def test_v28_creates_notification_queue(self) -> None:
        """v28: 创建 notification_queue 表 + 2 个索引。"""
        _migrate_v28_notification_queue(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS notification_queue")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_nq_status")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_nq_scheduled")
        self.assert_exec_count(self.db, 3, "v28")

    # ---- v29 ---------------------------------------------------------------

    def test_v29_alters_announcement_record(self) -> None:
        """v29: announcement_record 添加 announcement_title + standard_count 两列。"""
        _migrate_v29_announce_title_and_count(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN announcement_title")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN standard_count")
        self.assert_exec_count(self.db, 2, "v29")

    # ---- v30 ---------------------------------------------------------------

    def test_v30_creates_failure_tables_and_app_preferences(self) -> None:
        """v30: 创建 fetch_failures + announcement_fetch_failures + fetch_locks + app_preferences 表 + 1 个 INSERT。"""
        _migrate_v30_failure_tables(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS fetch_failures")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS announcement_fetch_failures")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS fetch_locks")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS app_preferences")
        self.assert_exec_contains(self.db, "INSERT OR IGNORE INTO app_preferences")

    def test_v30_total_execute_count(self) -> None:
        """v30: 总计 execute 调用 = 4 CREATE + 1 INSERT = 5。"""
        _migrate_v30_failure_tables(self.db)

        self.assert_exec_count(self.db, 5, "v30")


# ---------------------------------------------------------------------------
# v31 - v37 迁移测试（从 _migrate_v31_plus 导入）
# ---------------------------------------------------------------------------


class TestMigrationsV31V37(unittest.TestCase, _AssertMixin):
    """测试 v31 到 v37 的迁移函数（实现位于 _migrate_v31_plus.py）。"""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.db.execute = MagicMock()
        self.db.fetchall = MagicMock()
        self.db.fetchone = MagicMock()

    # ---- v31 ---------------------------------------------------------------

    def test_v31_creates_monitor_stats(self) -> None:
        """v31: 创建 monitor_stats 表 + 索引 + 从 cache_config 迁移数据。"""
        self.db.fetchone.return_value = None  # cache_config 中无旧数据

        _migrate_v31_monitor_stats(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS monitor_stats")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_monitor_stats_date")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_monitor_stats_key")

    def test_v31_migrates_monitor_data_from_cache_config(self) -> None:
        """v31: cache_config 中有旧监控数据时迁移到 monitor_stats。"""
        self.db.fetchone.side_effect = [
            {"config_value": "42"},  # monitor.processed_today
            {"config_value": "30"},  # monitor.success_today
            {"config_value": "5"},  # monitor.failed_today
        ]

        _migrate_v31_monitor_stats(self.db)

        # 验证从 cache_config 读取了旧数据
        self.assertEqual(self.db.fetchone.call_count, 3)
        # 验证写入 monitor_stats（3 条 INSERT OR REPLACE）
        insert_or_replace_calls = [
            c for c in self.db.execute.call_args_list if c[0] and "INSERT OR REPLACE INTO monitor_stats" in c[0][0]
        ]
        self.assertEqual(len(insert_or_replace_calls), 3)
        # 验证清理旧数据
        self.assert_exec_contains(self.db, "DELETE FROM cache_config")

    # ---- v32 ---------------------------------------------------------------

    def test_v32_drops_announcement_fetch_failures(self) -> None:
        """v32: 删除 announcement_fetch_failures 表。"""
        _migrate_v32_cleanup_dead_tables(self.db)

        self.assert_exec_contains(self.db, "DROP TABLE IF EXISTS announcement_fetch_failures")
        self.assert_exec_count(self.db, 1, "v32")

    # ---- v33 ---------------------------------------------------------------

    def test_v33_creates_adapter_state_and_migrates(self) -> None:
        """v33: 创建 adapter_state 表 + 从三张旧表迁移数据。"""
        self.db.fetchall.return_value = []  # 旧表无数据

        _migrate_v33_adapter_state(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS adapter_state")
        # 验证从三张旧表读取数据
        fetchall_calls = [c[0][0] for c in self.db.fetchall.call_args_list if c[0]]
        self.assertEqual(len(fetchall_calls), 3, "v33 应从 3 张旧表读取数据")

    def test_v33_migrates_rows_from_rotator_state(self) -> None:
        """v33: rotator_state 有数据时逐行迁移到 adapter_state。"""
        self.db.fetchall.side_effect = [
            [  # rotator_state 数据
                {
                    "site_name": "std_gov",
                    "request_count": 100,
                    "daily_count": 10,
                    "daily_date": "2026-01-01",
                    "cooldown_until": 0.0,
                    "consecutive_errors": 0,
                    "active_url": "https://example.com",
                    "updated_at": "2026-01-01",
                },
            ],
            [],  # adapter_stats 无数据
            [],  # adapter_health 无数据
        ]

        _migrate_v33_adapter_state(self.db)

        # 验证 INSERT OR REPLACE INTO adapter_state 被调用
        insert_calls = [
            c for c in self.db.execute.call_args_list if c[0] and "INSERT OR REPLACE INTO adapter_state" in c[0][0]
        ]
        self.assertEqual(len(insert_calls), 1, "v33 应迁移 1 行 rotator_state 数据")

    # ---- v34 ---------------------------------------------------------------

    def test_v34_renames_old_tables(self) -> None:
        """v34: 将三张旧表重命名为备份表。"""
        _migrate_v34_drop_old_adapter_tables(self.db)

        self.assert_exec_contains(self.db, "ALTER TABLE rotator_state RENAME TO rotator_state_backup_v34")
        self.assert_exec_contains(self.db, "ALTER TABLE adapter_stats RENAME TO adapter_stats_backup_v34")
        self.assert_exec_contains(self.db, "ALTER TABLE adapter_health RENAME TO adapter_health_backup_v34")
        self.assert_exec_count(self.db, 3, "v34 应重命名 3 张表")

    def test_v34_handles_rename_exception(self) -> None:
        """v34: 表不存在时 ALTER TABLE RENAME 抛异常被静默吞掉。"""
        self.db.execute = MagicMock()
        self.db.execute.side_effect = [
            Exception("表不存在"),  # rotator_state
            Exception("表不存在"),  # adapter_stats
            Exception("表不存在"),  # adapter_health
        ]

        _migrate_v34_drop_old_adapter_tables(self.db)

        self.assert_exec_count(self.db, 3, "v34 异常路径仍应尝试 3 次")

    # ---- v35 ---------------------------------------------------------------

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    def test_v35_creates_notification_policy(self, mock_cm: MagicMock) -> None:
        """v35: 创建 notification_policy 表 + 索引。"""
        # 模拟配置文件无 notification.rules
        mock_cfg = MagicMock()
        mock_cfg._data = {}
        mock_cm.return_value = mock_cfg

        _migrate_v35_notification_policy(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS notification_policy")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_policy_user")
        # 无旧规则数据时，不应有 INSERT
        insert_calls = [
            c
            for c in self.db.execute.call_args_list
            if c[0] and "INSERT OR REPLACE INTO notification_policy" in c[0][0]
        ]
        self.assertEqual(len(insert_calls), 0, "v35 无旧规则时不插入数据")

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    def test_v35_migrates_existing_rules(self, mock_cm: MagicMock) -> None:
        """v35: 从 config.json 中 notification.rules 迁移到 notification_policy。"""
        mock_cfg = MagicMock()
        mock_cfg._data = {
            "notification.rules.std_update": ["email", "webhook"],
            "notification.rules.announcement": ["email"],
        }
        mock_cm.return_value = mock_cfg

        _migrate_v35_notification_policy(self.db)

        insert_calls = [
            c
            for c in self.db.execute.call_args_list
            if c[0] and "INSERT OR REPLACE INTO notification_policy" in c[0][0]
        ]
        self.assertEqual(len(insert_calls), 2, "v35 应迁移 2 个渠道规则")

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    def test_v35_handles_config_exception(self, mock_cm: MagicMock) -> None:
        """v35: ConfigManager 初始化异常时静默跳过数据迁移。"""
        mock_cm.side_effect = Exception("配置文件不可用")

        _migrate_v35_notification_policy(self.db)

        # 表创建和索引创建应该成功
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS notification_policy")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_policy_user")

    # ---- v36 ---------------------------------------------------------------

    def test_v36_creates_announcements_and_favorites_and_reminders(self) -> None:
        """v36: 创建 announcements + user_favorites + date_reminder_log 三张表。"""
        self.db.fetchall.return_value = []  # 无存量数据

        _migrate_v36_announcement_structure(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS announcements")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS user_favorites")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS date_reminder_log")

    def test_v36_extends_announcement_record(self) -> None:
        """v36: 扩展 announcement_record 表（12 列 + 5 索引）。"""
        self.db.fetchall.return_value = []  # 无存量数据

        _migrate_v36_announcement_structure(self.db)

        # 验证关键新增列
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN announcement_id")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN status")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN implement_date")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN expiry_date")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN superseded_by")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN parser_engine")

        # 验证新增索引
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_announcement_record_announcement_id")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_announcement_record_status")

    def test_v36_migrates_existing_data(self) -> None:
        """v36: 存量数据按 (source_site, pid) 迁移到 announcements。"""
        self.db.fetchall.return_value = [
            ("site_a", "pid_1", "ANO-001", "公告标题1", "2026-01-01"),
        ]

        _migrate_v36_announcement_structure(self.db)

        # 验证 INSERT OR IGNORE INTO announcements
        self.assert_exec_contains(self.db, "INSERT OR IGNORE INTO announcements")

        # 验证 UPDATE announcement_record SET announcement_id
        self.assert_exec_contains(self.db, "UPDATE announcement_record")
        self.assert_exec_contains(self.db, "SET announcement_id")

        # 验证 UPDATE announcement_record SET status = 'draft'
        update_status_calls = [c for c in self.db.execute.call_args_list if c[0] and "SET status = 'draft'" in c[0][0]]
        self.assertGreaterEqual(len(update_status_calls), 1, "v36 应设置默认 status='draft'")

    # ---- v37 ---------------------------------------------------------------

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    @patch("pilotstd.core.config.crypto._get_fernet", autospec=True)
    def test_v37_creates_user_credentials(self, mock_fernet: MagicMock, mock_cm: MagicMock) -> None:
        """v37: 创建 user_credentials 表 + 迁移凭证。"""
        mock_cfg = MagicMock()
        mock_cfg._data = {
            "notification": {
                "channels": {
                    "email": {"smtp_host": "smtp.example.com"},
                }
            }
        }
        mock_cfg._filepath = "/tmp/config.json"
        mock_cm.return_value = mock_cfg

        mock_f = MagicMock()
        mock_f.encrypt.return_value = b"encrypted_data"
        mock_fernet.return_value = mock_f

        _migrate_v37_user_notification_config(self.db)

        # 防御性加列
        self.assert_exec_contains(self.db, "ALTER TABLE notification_policy ADD COLUMN user_id")
        # 创建 user_credentials 表
        self.assert_exec_contains(self.db, 'CREATE TABLE IF NOT EXISTS "user_credentials"')
        # 创建索引
        self.assert_exec_contains(self.db, 'CREATE INDEX IF NOT EXISTS "idx_user_creds_user"')
        # 更新策略表
        self.assert_exec_contains(self.db, 'UPDATE "notification_policy" SET "user_id" = 1')

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    @patch("pilotstd.core.config.crypto._get_fernet", autospec=True)
    def test_v37_migrates_channel_credentials(self, mock_fernet: MagicMock, mock_cm: MagicMock) -> None:
        """v37: 从 config.json 迁移渠道凭证到 user_credentials。"""
        mock_cfg = MagicMock()
        mock_cfg._data = {
            "notification": {
                "channels": {
                    "email": {"smtp_host": "smtp.example.com", "port": 587},
                    "webhook": {"url": "https://hooks.example.com"},
                }
            }
        }
        mock_cfg._filepath = "/tmp/config.json"
        mock_cm.return_value = mock_cfg

        mock_f = MagicMock()
        mock_f.encrypt.return_value = b"encrypted_data"
        mock_fernet.return_value = mock_f

        _migrate_v37_user_notification_config(self.db)

        # 验证两个渠道各写入一次
        insert_calls = [
            c for c in self.db.execute.call_args_list if c[0] and 'INSERT OR REPLACE INTO "user_credentials"' in c[0][0]
        ]
        self.assertEqual(len(insert_calls), 2, "v37 应迁移 2 个渠道凭证")

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    @patch("pilotstd.core.config.crypto._get_fernet", autospec=True)
    def test_v37_handles_config_exception(self, mock_fernet: MagicMock, mock_cm: MagicMock) -> None:
        """v37: ConfigManager 初始化异常时静默跳过数据迁移但完成建表。"""
        mock_cm.side_effect = Exception("配置文件不可用")

        _migrate_v37_user_notification_config(self.db)

        # 建表仍应成功
        self.assert_exec_contains(self.db, 'CREATE TABLE IF NOT EXISTS "user_credentials"')
        # 更新策略表仍应执行
        self.assert_exec_contains(self.db, 'UPDATE "notification_policy" SET "user_id" = 1')

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    @patch("pilotstd.core.config.crypto._get_fernet", autospec=True)
    def test_v37_handles_no_channels(self, mock_fernet: MagicMock, mock_cm: MagicMock) -> None:
        """v37: 配置文件无 channels 配置时不迁移凭证。"""
        mock_cfg = MagicMock()
        mock_cfg._data = {"notification": {}}  # 无 channels
        mock_cfg._filepath = "/tmp/config.json"
        mock_cm.return_value = mock_cfg

        _migrate_v37_user_notification_config(self.db)

        # 不应该插入凭证
        insert_calls = [
            c for c in self.db.execute.call_args_list if c[0] and 'INSERT OR REPLACE INTO "user_credentials"' in c[0][0]
        ]
        self.assertEqual(len(insert_calls), 0, "v37 无渠道时不插入凭证")


# ---------------------------------------------------------------------------
# v38 迁移测试
# ---------------------------------------------------------------------------


class TestMigrationV38(unittest.TestCase, _AssertMixin):
    """测试 v38 迁移函数（user_settings 表）。"""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.db.execute = MagicMock()
        self.db.fetchone = MagicMock()

    def test_v38_creates_user_settings_when_not_exists(self) -> None:
        """v38: user_settings 表不存在时创建表 + 索引。"""
        self.db.fetchone.return_value = None  # 表不存在

        _migrate_v38_user_settings(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE user_settings")
        self.assert_exec_contains(self.db, "CREATE INDEX idx_user_settings_user_id")
        self.assert_exec_count(self.db, 2, "v38 应创建表 + 索引共 2 次 execute")

    def test_v38_skips_when_table_exists(self) -> None:
        """v38: user_settings 表已存在时跳过创建。"""
        self.db.fetchone.return_value = {"name": "user_settings"}  # 表已存在

        _migrate_v38_user_settings(self.db)

        self.db.execute.assert_not_called()

    def test_v38_checks_sqlite_master(self) -> None:
        """v38: 查询 sqlite_master 确认表是否存在。"""
        _migrate_v38_user_settings(self.db)

        self.db.fetchone.assert_called_once()
        fetchone_sql = self.db.fetchone.call_args[0][0]
        self.assertIn("sqlite_master", fetchone_sql)
        self.assertIn("user_settings", fetchone_sql)


# ---------------------------------------------------------------------------
# 迁移注册与模块 Mock 测试
# ---------------------------------------------------------------------------


class TestMigrationRegistration(unittest.TestCase):
    """测试迁移函数注册和 _migrate_v31_plus 模块 Mock。"""

    def test_all_versions_registered(self) -> None:
        """验证 v2-v38 全部迁移函数已在 MIGRATIONS 中注册。"""
        for version in range(2, 41):
            self.assertIn(version, MIGRATIONS, f"v{version} 应在 MIGRATIONS 中注册")

    def test_migrations_dict_has_no_gaps(self) -> None:
        """验证 MIGRATIONS 字典各版本号无缺口。"""
        versions = sorted(MIGRATIONS.keys())
        self.assertEqual(versions[0], 2, "第一个迁移版本应为 v2")
        # v2.1: 末尾版本从硬编码 42 改为 max(MIGRATIONS.keys())，适配 v43/v44
        max_v = max(MIGRATIONS.keys())
        self.assertEqual(versions[-1], max_v, f"最后一个迁移版本应为 v{max_v}")
        for i, v in enumerate(versions):
            expected = i + 2
            self.assertEqual(v, expected, f"MIGRATIONS 版本号不连续: 期望 {expected}, 实际 {v}")

    def test_v31_v37_are_registered(self) -> None:
        """验证 v31-v37 已正确注册到 MIGRATIONS 字典中。"""
        for v in range(31, 38):
            self.assertIn(v, MIGRATIONS, f"v{v} 应在 MIGRATIONS 中注册")

    def test_v31_v37_are_callable(self) -> None:
        """验证 v31-v37 已注册的函数是可调用的。"""
        for v in range(31, 38):
            fn = MIGRATIONS.get(v)
            self.assertIsNotNone(fn, f"v{v} 迁移函数不应为 None")
            self.assertTrue(callable(fn), f"v{v} 迁移函数应是可调用的")

    def test_v38_is_registered_and_callable(self) -> None:
        """验证 v38 迁移函数已注册且可调用。"""
        self.assertIn(38, MIGRATIONS)
        self.assertTrue(callable(MIGRATIONS[38]))
        self.assertEqual(MIGRATIONS[38].__name__, "_migrate_v38_user_settings")


# ---------------------------------------------------------------------------
# v31-v37 函数完整性测试（直接调用真实函数 + mock db）
# ---------------------------------------------------------------------------


class TestV31V37DirectCall(unittest.TestCase, _AssertMixin):
    """对 v31-v37 真实函数做直接调用 + mock db 测试（非 mock 模块路径）。"""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.db.execute = MagicMock()
        self.db.fetchall = MagicMock(return_value=[])
        self.db.fetchone = MagicMock(return_value=None)

    def test_v31_direct_call(self) -> None:
        """v31 直接调用：创建 monitor_stats 表 + 3 索引 + 数据迁移 + 清理。"""
        _migrate_v31_monitor_stats(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS monitor_stats")
        self.assert_exec_contains(self.db, "DELETE FROM cache_config")

    def test_v32_direct_call(self) -> None:
        """v32 直接调用：DROP announcement_fetch_failures。"""
        _migrate_v32_cleanup_dead_tables(self.db)

        self.assert_exec_contains(self.db, "DROP TABLE IF EXISTS announcement_fetch_failures")

    def test_v33_direct_call(self) -> None:
        """v33 直接调用：创建 adapter_state + 迁移旧数据。"""
        self.db.fetchall.return_value = []

        _migrate_v33_adapter_state(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS adapter_state")

    def test_v34_direct_call(self) -> None:
        """v34 直接调用：重命名三张旧表。"""
        _migrate_v34_drop_old_adapter_tables(self.db)

        self.assert_exec_contains(self.db, "rotator_state RENAME TO rotator_state_backup_v34")
        self.assert_exec_contains(self.db, "adapter_stats RENAME TO adapter_stats_backup_v34")
        self.assert_exec_contains(self.db, "adapter_health RENAME TO adapter_health_backup_v34")

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    def test_v35_direct_call(self, mock_cm: MagicMock) -> None:
        """v35 直接调用：创建 notification_policy 表 + 索引。"""
        mock_cfg = MagicMock()
        mock_cfg._data = {}
        mock_cm.return_value = mock_cfg

        _migrate_v35_notification_policy(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS notification_policy")
        self.assert_exec_contains(self.db, "CREATE INDEX IF NOT EXISTS idx_policy_user")

    def test_v36_direct_call(self) -> None:
        """v36 直接调用：创建三张新表 + 扩展 announcement_record + 迁移数据。"""
        self.db.fetchall.return_value = []

        _migrate_v36_announcement_structure(self.db)

        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS announcements")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS user_favorites")
        self.assert_exec_contains(self.db, "CREATE TABLE IF NOT EXISTS date_reminder_log")
        self.assert_exec_contains(self.db, "ALTER TABLE announcement_record ADD COLUMN announcement_id")

    @patch("pilotstd.core.config.ConfigManager", autospec=True)
    @patch("pilotstd.core.config.crypto._get_fernet", autospec=True)
    def test_v37_direct_call(self, mock_fernet: MagicMock, mock_cm: MagicMock) -> None:
        """v37 直接调用：创建 user_credentials 表 + 迁移凭证 + 更新策略。"""
        mock_cfg = MagicMock()
        mock_cfg._data = {}
        mock_cfg._filepath = "/tmp/config.json"
        mock_cm.return_value = mock_cfg

        _migrate_v37_user_notification_config(self.db)

        self.assert_exec_contains(self.db, 'CREATE TABLE IF NOT EXISTS "user_credentials"')
        self.assert_exec_contains(self.db, 'UPDATE "notification_policy" SET "user_id" = 1')


# ---------------------------------------------------------------------------
# 边缘条件 / 综合测试
# ---------------------------------------------------------------------------


class TestEdgeCases(unittest.TestCase, _AssertMixin):
    """边界条件与综合测试。"""

    def test_v3_fetchall_empty_list(self) -> None:
        """v3: fetchall 返回空列表时 ALTER TABLE（列信息缺失，安全添加）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchall = MagicMock(return_value=[])  # 空列表，status 不在其中

        _migrate_v3_queue_and_pending(db)

        # 空列表时 "status" 不在 cols 中，应执行 ALTER TABLE
        self.assert_exec_contains(db, "ALTER TABLE file_index ADD COLUMN status")

    def test_v8_fetchall_empty_skips_drop(self) -> None:
        """v8: fetchall 返回空列表时跳过 DROP（表不存在）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchall = MagicMock(return_value=[])

        _migrate_v8_drop_expires_at(db)

        db.execute.assert_not_called()

    def test_v9_fetchall_empty_skips_alter(self) -> None:
        """v9: fetchall 返回空列表时跳过 ALTER（表不存在）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchall = MagicMock(return_value=[])

        _migrate_v9_add_requery_count(db)

        db.execute.assert_not_called()

    def test_v10_fetchall_empty_skips_alter(self) -> None:
        """v10: fetchall 返回空列表时跳过 ALTER（表不存在）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchall = MagicMock(return_value=[])

        _migrate_v10_add_source_and_status_history(db)

        db.execute.assert_not_called()

    def test_v11_fetchall_empty_skips_alter(self) -> None:
        """v11: fetchall 返回空列表时跳过 ALTER（表不存在）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchall = MagicMock(return_value=[])

        _migrate_v11_add_daily_limits(db)

        db.execute.assert_not_called()

    def test_v13_fetchall_empty_skips_alter(self) -> None:
        """v13: fetchall 返回空列表时跳过 ALTER（表不存在）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchall = MagicMock(return_value=[])

        _migrate_v13_adapter_stats_extend(db)

        db.execute.assert_not_called()

    def test_v38_fetchone_none_creates_table(self) -> None:
        """v38: fetchone 返回 None 时创建表（表不存在）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchone = MagicMock(return_value=None)

        _migrate_v38_user_settings(db)

        self.assert_exec_count(db, 2, "v38 表不存在时应创建表 + 索引共 2 次 execute")

    def test_v38_fetchone_dict_skips_create(self) -> None:
        """v38: fetchone 返回非空 dict 时跳过创建（表已存在）。"""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetchone = MagicMock(return_value={"name": "user_settings"})

        _migrate_v38_user_settings(db)

        db.execute.assert_not_called()

    def test_migration_decorator_sets_function_name(self) -> None:
        """验证 @migration 装饰器保留原始函数名。"""
        self.assertEqual(_migrate_v2_add_file_index.__name__, "_migrate_v2_add_file_index")
        self.assertEqual(_migrate_v19_users.__name__, "_migrate_v19_users")
        self.assertEqual(_migrate_v38_user_settings.__name__, "_migrate_v38_user_settings")
