# -*- coding: utf-8 -*-
"""FileIndexRepository 完整单元测试。

覆盖 FileIndexRepository 的所有公开方法和内部方法，
使用 MagicMock 模拟 Database 依赖，mock 文件系统操作和后台线程。
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from pilotstd.core.file_index import (
    FILE_INDEX_TABLE,
    FileIndexRepository,
)
from pilotstd.models import ParsedStdInfo

# ================================================================
# 常量：测试中反复使用的假数据
# ================================================================
MOCK_NOW = "2024-01-15T10:30:00"
SAMPLE_PATH = "/data/std/GB 12345-2020.pdf"
SAMPLE_HASH = "abc123def456"
SAMPLE_ROW = {
    "id": 1,
    "file_path": SAMPLE_PATH,
    "logical_code": "GB",
    "number": 12345,
    "year": 2020,
    "part": -1,
    "std_name": "测试标准名称",
    "file_hash": SAMPLE_HASH,
    "status": "现行",
    "scanned_at": MOCK_NOW,
    "last_checked": None,
}


class TestFileIndexRepository(unittest.TestCase):
    """FileIndexRepository 完整单元测试"""

    # ================================================================
    # 夹具
    # ================================================================

    def setUp(self) -> None:
        """每个测试方法前创建全新的 mock_db，默认返回空。"""
        self.mock_db = MagicMock()
        self.mock_db.fetchone.return_value = None
        self.mock_db.fetchall.return_value = []

    def _make_repo(self) -> FileIndexRepository:
        """创建 FileIndexRepository 并禁止后台校验线程启动。"""
        with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
            repo = FileIndexRepository(self.mock_db)
        repo._validation_complete.set()
        return repo

    # ================================================================
    # __init__ / _start_delayed_validation
    # ================================================================

    def test_init_stores_db_and_creates_events(self) -> None:
        """__init__ 应保存 db 引用，创建 stop_event 和 validation_complete Event"""
        repo = self._make_repo()
        self.assertIs(repo._db, self.mock_db)
        self.assertIsNotNone(repo._stop_event)
        self.assertIsNotNone(repo._validation_complete)

    @patch("threading.Thread")
    @patch("time.sleep", return_value=None)
    def test_run_early_stop_skips_db_and_validates(self, _mock_sleep: MagicMock, mock_thread_class: MagicMock) -> None:
        """后台 _run：stop_event 已设置时应立即标记完成，不查 DB、不校验路径"""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
            repo = FileIndexRepository(self.mock_db)
        repo._stop_event.set()
        repo._validation_complete.clear()

        # 手动调用真实 _start_delayed_validation，捕获 target
        FileIndexRepository._start_delayed_validation(repo)
        target = mock_thread_class.call_args[1]["target"]
        target()  # 同步执行

        self.assertTrue(repo._validation_complete.is_set(), "应标记校验完成")
        self.mock_db.fetchone.assert_not_called()

    @patch("time.sleep", return_value=None)
    @patch("threading.Thread")
    def test_run_normal_flow_calls_validate_paths(self, mock_thread_class: MagicMock, _mock_sleep: MagicMock) -> None:
        """后台 _run 正常流程：查计数、等待、调用 validate_paths，最后标记完成"""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread
        self.mock_db.fetchone.return_value = {"cnt": 2500}  # delay = min(30, max(5, 5)) = 5

        with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
            repo = FileIndexRepository(self.mock_db)
        repo._stop_event.clear()
        repo._validation_complete.clear()

        with patch.object(repo, "validate_paths", return_value=7) as mock_validate:
            FileIndexRepository._start_delayed_validation(repo)
            target = mock_thread_class.call_args[1]["target"]
            target()

        self.assertTrue(repo._validation_complete.is_set())
        mock_validate.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch("threading.Thread")
    def test_run_db_error_uses_default_delay(self, mock_thread_class: MagicMock, _mock_sleep: MagicMock) -> None:
        """后台 _run：DB 查询 COUNT 失败时，使用默认延迟 10s，继续校验"""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread
        self.mock_db.fetchone.side_effect = Exception("DB down")

        with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
            repo = FileIndexRepository(self.mock_db)
        repo._stop_event.clear()
        repo._validation_complete.clear()

        with patch.object(repo, "validate_paths", return_value=0) as mock_validate:
            FileIndexRepository._start_delayed_validation(repo)
            target = mock_thread_class.call_args[1]["target"]
            target()

        mock_validate.assert_called_once()
        self.assertTrue(repo._validation_complete.is_set())

    @patch("time.sleep", return_value=None)
    @patch("threading.Thread")
    def test_run_validate_paths_raises_is_caught(self, mock_thread_class: MagicMock, _mock_sleep: MagicMock) -> None:
        """后台 _run：validate_paths 抛异常时吞掉异常，仍标记完成"""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread
        self.mock_db.fetchone.return_value = {"cnt": 0}

        with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
            repo = FileIndexRepository(self.mock_db)
        repo._stop_event.clear()
        repo._validation_complete.clear()

        with patch.object(repo, "validate_paths", side_effect=RuntimeError("boom")):
            FileIndexRepository._start_delayed_validation(repo)
            target = mock_thread_class.call_args[1]["target"]
            target()  # 不应抛异常

        self.assertTrue(repo._validation_complete.is_set())

    @patch("threading.Thread")
    def test_run_db_row_is_none_handled(self, mock_thread_class: MagicMock) -> None:
        """后台 _run：fetchone 返回 None 时，row_count 回退为 0，delay 为 5"""
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread
        self.mock_db.fetchone.return_value = None  # row 为 None

        with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
            repo = FileIndexRepository(self.mock_db)
        repo._stop_event.clear()
        repo._validation_complete.clear()

        # time.sleep 不 mock 返回 None，我们需要让它立即完成；改为 mock 掉 sleep
        with patch("time.sleep", return_value=None):
            with patch.object(repo, "validate_paths", return_value=0) as mock_validate:
                FileIndexRepository._start_delayed_validation(repo)
                target = mock_thread_class.call_args[1]["target"]
                target()

        mock_validate.assert_called_once()
        self.assertTrue(repo._validation_complete.is_set())

    def test_start_delayed_validation_sets_thread_reference(self) -> None:
        """_start_delayed_validation 应将创建的线程引用保存到 _validation_thread"""
        with patch("threading.Thread") as mock_thread_class:
            mock_thread = MagicMock()
            mock_thread_class.return_value = mock_thread

            with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
                repo = FileIndexRepository(self.mock_db)

            FileIndexRepository._start_delayed_validation(repo)
            self.assertIs(repo._validation_thread, mock_thread)

    # ================================================================
    # is_validation_complete
    # ================================================================

    def test_is_validation_complete_initially_false(self) -> None:
        """新创建的 repo 在校验线程未完成前 is_validation_complete 为 False"""
        with patch.object(FileIndexRepository, "_start_delayed_validation", return_value=None):
            repo = FileIndexRepository(self.mock_db)
        # _validation_complete 尚未 set
        repo._validation_complete.clear()
        self.assertFalse(repo.is_validation_complete)

    def test_is_validation_complete_after_set(self) -> None:
        """标记完成后 is_validation_complete 为 True"""
        repo = self._make_repo()
        self.assertTrue(repo.is_validation_complete)

    # ================================================================
    # validate_paths
    # ================================================================

    def test_validate_paths_stop_event_set_returns_zero(self) -> None:
        """stop_event 已设置时直接返回 0"""
        repo = self._make_repo()
        repo._stop_event.set()
        result = repo.validate_paths()
        self.assertEqual(result, 0)

    def test_validate_paths_empty_table_returns_zero(self) -> None:
        """空表时返回 0，不执行任何 DELETE"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = []

        result = repo.validate_paths()

        self.assertEqual(result, 0)
        self.mock_db.execute.assert_not_called()

    @patch("os.path.exists")
    def test_validate_paths_all_exist_returns_zero(self, mock_exists: MagicMock) -> None:
        """所有路径都存在时返回 0，不执行 DELETE"""
        repo = self._make_repo()
        mock_exists.return_value = True
        self.mock_db.fetchall.return_value = [
            {"id": 1, "file_path": "/a.pdf"},
            {"id": 2, "file_path": "/b.pdf"},
        ]

        result = repo.validate_paths()

        self.assertEqual(result, 0)
        self.mock_db.execute.assert_not_called()

    @patch("os.path.exists")
    def test_validate_paths_some_missing_deletes_them(self, mock_exists: MagicMock) -> None:
        """部分路径不存在时，删除对应记录并返回删除数量"""
        repo = self._make_repo()
        mock_exists.side_effect = lambda p: p == "/a.pdf"  # 只有 /a.pdf 存在
        self.mock_db.fetchall.return_value = [
            {"id": 1, "file_path": "/a.pdf"},
            {"id": 2, "file_path": "/b.pdf"},
            {"id": 3, "file_path": "/c.pdf"},
        ]

        result = repo.validate_paths()

        self.assertEqual(result, 2)  # b, c 被删除
        self.assertEqual(self.mock_db.execute.call_count, 2)

    @patch("os.path.exists")
    def test_validate_paths_delete_error_continues(self, mock_exists: MagicMock) -> None:
        """单条 DELETE 失败时应继续处理后续记录"""
        repo = self._make_repo()
        mock_exists.return_value = False
        self.mock_db.fetchall.return_value = [
            {"id": 1, "file_path": "/a.pdf"},
            {"id": 2, "file_path": "/b.pdf"},
        ]
        # 第一条 DELETE 抛异常，第二条正常
        self.mock_db.execute.side_effect = [Exception("lock"), None]

        result = repo.validate_paths()

        self.assertEqual(result, 1)  # 只有第二条成功删除
        self.assertEqual(self.mock_db.execute.call_count, 2)

    def test_validate_paths_db_error_returns_zero(self) -> None:
        """fetchall 抛异常时返回 0 并标记完成"""
        repo = self._make_repo()
        repo._validation_complete.clear()
        self.mock_db.fetchall.side_effect = Exception("table missing")

        result = repo.validate_paths()

        self.assertEqual(result, 0)
        self.assertTrue(repo._validation_complete.is_set())

    @patch("os.path.exists")
    def test_validate_paths_sets_validation_complete(self, mock_exists: MagicMock) -> None:
        """正常执行后应标记 validation_complete"""
        repo = self._make_repo()
        repo._validation_complete.clear()
        mock_exists.return_value = True
        self.mock_db.fetchall.return_value = [{"id": 1, "file_path": "/a.pdf"}]

        repo.validate_paths()

        self.assertTrue(repo._validation_complete.is_set())

    # ================================================================
    # upsert
    # ================================================================

    @patch("pilotstd.core.file_index.datetime")
    @patch("pilotstd.core.file_index.hash_file_content")
    @patch("os.path.exists")
    def test_upsert_new_file_with_hash_calculation(
        self, mock_exists: MagicMock, mock_hash: MagicMock, mock_dt: MagicMock
    ) -> None:
        """新文件（路径不存在于索引）+ 文件存在 + 无预设 hash → INSERT 并自动计算 hash"""
        repo = self._make_repo()
        mock_exists.return_value = True
        mock_hash.return_value = SAMPLE_HASH
        mock_dt.now.return_value.isoformat.return_value = MOCK_NOW
        self.mock_db.fetchone.return_value = None  # 路径不存在

        repo.upsert(
            file_path=SAMPLE_PATH,
            logical_code="GB",
            number=12345,
            year=2020,
            part=None,
            std_name="测试标准",
        )

        # 校验：先查路径是否存在
        self.mock_db.fetchone.assert_called_once_with(
            f"SELECT id FROM {FILE_INDEX_TABLE} WHERE file_path=?", (SAMPLE_PATH,)
        )
        # 应执行 INSERT
        self.mock_db.execute.assert_called_once()
        sql: str = self.mock_db.execute.call_args[0][0]
        params: tuple = self.mock_db.execute.call_args[0][1]
        self.assertIn("INSERT", sql)
        self.assertEqual(params[0], SAMPLE_PATH)
        self.assertEqual(params[1], "GB")
        self.assertEqual(params[2], 12345)
        self.assertEqual(params[3], 2020)
        self.assertEqual(params[4], -1)  # part=None → -1
        self.assertEqual(params[6], SAMPLE_HASH)

    @patch("pilotstd.core.file_index.datetime")
    @patch("os.path.exists")
    def test_upsert_new_file_not_on_disk_no_hash(self, mock_exists: MagicMock, mock_dt: MagicMock) -> None:
        """新文件但文件不存在 → hash 保持空字符串"""
        repo = self._make_repo()
        mock_exists.return_value = False
        mock_dt.now.return_value.isoformat.return_value = MOCK_NOW
        self.mock_db.fetchone.return_value = None

        repo.upsert(
            file_path="/missing/file.pdf",
            logical_code="GB",
            number=1,
            year=2023,
            file_hash="",
        )

        params = self.mock_db.execute.call_args[0][1]
        self.assertEqual(params[6], "")  # file_hash 为空

    @patch("pilotstd.core.file_index.datetime")
    @patch("os.path.exists")
    def test_upsert_hash_provided_no_recalculation(self, mock_exists: MagicMock, mock_dt: MagicMock) -> None:
        """已提供 hash 时，即使文件存在也不重新计算"""
        repo = self._make_repo()
        mock_exists.return_value = True
        mock_dt.now.return_value.isoformat.return_value = MOCK_NOW
        self.mock_db.fetchone.return_value = None
        provided_hash = "precomputed_hash_123"

        repo.upsert(
            file_path=SAMPLE_PATH,
            logical_code="GB",
            number=1,
            year=2023,
            file_hash=provided_hash,
        )

        params = self.mock_db.execute.call_args[0][1]
        self.assertEqual(params[6], provided_hash)

    @patch("pilotstd.core.file_index.datetime")
    @patch("os.path.exists")
    def test_upsert_existing_file_updates(self, mock_exists: MagicMock, mock_dt: MagicMock) -> None:
        """路径已存在于索引 → UPDATE 而非 INSERT"""
        repo = self._make_repo()
        mock_exists.return_value = True
        mock_dt.now.return_value.isoformat.return_value = MOCK_NOW
        self.mock_db.fetchone.return_value = {"id": 42}  # 已存在

        repo.upsert(
            file_path=SAMPLE_PATH,
            logical_code="GB",
            number=12345,
            year=2020,
            part=1,
            std_name="更新名称",
            status="废止",
        )

        sql: str = self.mock_db.execute.call_args[0][0]
        params: tuple = self.mock_db.execute.call_args[0][1]
        self.assertIn("UPDATE", sql)
        self.assertEqual(params[-1], 42)  # WHERE id=42
        self.assertEqual(params[3], 1)  # part 保持原值

    @patch("pilotstd.core.file_index.datetime")
    @patch("os.path.exists")
    def test_upsert_part_zero_preserved(self, mock_exists: MagicMock, mock_dt: MagicMock) -> None:
        """part=0 应保持为 0（与 None 区分，None 才转为 -1）"""
        repo = self._make_repo()
        mock_exists.return_value = True
        mock_dt.now.return_value.isoformat.return_value = MOCK_NOW
        self.mock_db.fetchone.return_value = None

        repo.upsert(file_path=SAMPLE_PATH, logical_code="GB", number=1, year=2023, part=0)

        params = self.mock_db.execute.call_args[0][1]
        self.assertEqual(params[4], 0)

    # ================================================================
    # remove
    # ================================================================

    def test_remove_deletes_by_file_path(self) -> None:
        """remove 应按 file_path 执行 DELETE"""
        repo = self._make_repo()

        repo.remove(SAMPLE_PATH)

        self.mock_db.execute.assert_called_once_with(
            f"DELETE FROM {FILE_INDEX_TABLE} WHERE file_path=?",
            (SAMPLE_PATH,),
        )

    # ================================================================
    # get
    # ================================================================

    def test_get_found_returns_row(self) -> None:
        """路径存在时返回完整行"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = SAMPLE_ROW.copy()

        result = repo.get(SAMPLE_PATH)

        self.assertEqual(result, SAMPLE_ROW)
        self.mock_db.fetchone.assert_called_once_with(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE file_path=?",
            (SAMPLE_PATH,),
        )

    def test_get_not_found_returns_none(self) -> None:
        """路径不存在时返回 None"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = None

        result = repo.get("/nonexistent.pdf")

        self.assertIsNone(result)

    # ================================================================
    # get_all
    # ================================================================

    def test_get_all_returns_all_rows_ordered(self) -> None:
        """get_all 返回按 logical_code, number, part 排序的全部记录"""
        repo = self._make_repo()
        expected = [SAMPLE_ROW.copy(), {**SAMPLE_ROW, "id": 2}]
        self.mock_db.fetchall.return_value = expected

        result = repo.get_all()

        self.assertEqual(result, expected)
        self.mock_db.fetchall.assert_called_once_with(
            f"SELECT * FROM {FILE_INDEX_TABLE} ORDER BY logical_code, number, part"
        )

    def test_get_all_empty_returns_empty_list(self) -> None:
        """表为空时返回空列表"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = []

        result = repo.get_all()

        self.assertEqual(result, [])

    # ================================================================
    # find_by_standard
    # ================================================================

    def test_find_by_standard_matches_all_fields(self) -> None:
        """按 logical_code + number + year + part 精确匹配"""
        repo = self._make_repo()
        expected = [SAMPLE_ROW.copy()]
        self.mock_db.fetchall.return_value = expected

        result = repo.find_by_standard("GB", 12345, 2020, 1)

        self.assertEqual(result, expected)
        self.mock_db.fetchall.assert_called_once_with(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE logical_code=? AND number=? AND year=? AND part=?",
            ("GB", 12345, 2020, 1),
        )

    def test_find_by_standard_part_none_uses_minus_one(self) -> None:
        """part=None 时使用 -1 查询"""
        repo = self._make_repo()

        repo.find_by_standard("GB", 12345, 2020, None)

        self.mock_db.fetchall.assert_called_once_with(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE logical_code=? AND number=? AND year=? AND part=?",
            ("GB", 12345, 2020, -1),
        )

    # ================================================================
    # find_by_hash
    # ================================================================

    def test_find_by_hash_found(self) -> None:
        """哈希匹配时返回行"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = SAMPLE_ROW.copy()

        result = repo.find_by_hash(SAMPLE_HASH)

        self.assertEqual(result, SAMPLE_ROW)
        self.mock_db.fetchone.assert_called_once_with(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE file_hash=?",
            (SAMPLE_HASH,),
        )

    def test_find_by_hash_not_found(self) -> None:
        """哈希无匹配时返回 None"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = None

        result = repo.find_by_hash("nonexistent_hash")

        self.assertIsNone(result)

    # ================================================================
    # clear_stale
    # ================================================================

    def test_clear_stale_empty_returns_zero(self) -> None:
        """无过期记录时返回 0"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = []

        result = repo.clear_stale()

        self.assertEqual(result, 0)

    @patch("os.path.exists")
    def test_clear_stale_file_exists_updates_last_checked(self, mock_exists: MagicMock) -> None:
        """文件存在时更新 last_checked，不删除"""
        repo = self._make_repo()
        mock_exists.return_value = True
        self.mock_db.fetchall.return_value = [
            {"id": 1, "file_path": "/a.pdf"},
            {"id": 2, "file_path": "/b.pdf"},
        ]

        result = repo.clear_stale()

        self.assertEqual(result, 0)
        self.assertEqual(self.mock_db.execute.call_count, 2)
        # 两次都应执行 UPDATE
        for call_args in self.mock_db.execute.call_args_list:
            self.assertIn("UPDATE", call_args[0][0])

    @patch("os.path.exists")
    def test_clear_stale_file_missing_deletes(self, mock_exists: MagicMock) -> None:
        """文件不存在时删除记录，返回删除数量"""
        repo = self._make_repo()
        mock_exists.return_value = False
        self.mock_db.fetchall.return_value = [
            {"id": 1, "file_path": "/missing.pdf"},
        ]

        result = repo.clear_stale()

        self.assertEqual(result, 1)
        self.mock_db.execute.assert_called_once()
        self.assertIn("DELETE", self.mock_db.execute.call_args[0][0])

    @patch("os.path.exists")
    def test_clear_stale_mixed_exist_and_missing(self, mock_exists: MagicMock) -> None:
        """混合场景：部分存在更新、部分不存在删除"""
        repo = self._make_repo()
        mock_exists.side_effect = lambda p: p == "/exists.pdf"
        self.mock_db.fetchall.return_value = [
            {"id": 1, "file_path": "/exists.pdf"},
            {"id": 2, "file_path": "/missing.pdf"},
            {"id": 3, "file_path": "/also_missing.pdf"},
        ]

        result = repo.clear_stale()

        self.assertEqual(result, 2)  # 两个被删除
        self.assertEqual(self.mock_db.execute.call_count, 3)

    # ================================================================
    # count
    # ================================================================

    def test_count_returns_row_cnt(self) -> None:
        """count 返回 COUNT(*) 结果"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = {"cnt": 42}

        result = repo.count()

        self.assertEqual(result, 42)

    def test_count_empty_table_returns_zero(self) -> None:
        """fetchone 返回 None（空表）时返回 0"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = None

        result = repo.count()

        self.assertEqual(result, 0)

    # ================================================================
    # get_status_stats
    # ================================================================

    def test_get_status_stats_normal(self) -> None:
        """正常返回按状态分组的统计"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = [
            {"status": "现行", "cnt": 10},
            {"status": "废止", "cnt": 3},
            {"status": "被代替", "cnt": 2},
            {"status": "待确认", "cnt": 1},
            {"status": "即将实施", "cnt": 4},
        ]

        stats = repo.get_status_stats()

        self.assertEqual(stats["current"], 10)
        self.assertEqual(stats["expired"], 5)  # 废止 3 + 被代替 2
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["upcoming"], 4)

    def test_get_status_stats_db_error_returns_defaults(self) -> None:
        """DB 异常时返回全 0 默认字典"""
        repo = self._make_repo()
        self.mock_db.fetchall.side_effect = Exception("table missing")

        stats = repo.get_status_stats()

        self.assertEqual(stats, {"current": 0, "expired": 0, "pending": 0, "upcoming": 0})

    def test_get_status_stats_missing_statuses_default_to_zero(self) -> None:
        """某些状态缺席时对应计数为 0"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = [
            {"status": "现行", "cnt": 5},
        ]

        stats = repo.get_status_stats()

        self.assertEqual(stats["current"], 5)
        self.assertEqual(stats["expired"], 0)
        self.assertEqual(stats["pending"], 0)
        self.assertEqual(stats["upcoming"], 0)

    # ================================================================
    # clear_all
    # ================================================================

    def test_clear_all_deletes_all_records(self) -> None:
        """clear_all 执行 DELETE FROM file_index"""
        repo = self._make_repo()

        repo.clear_all()

        self.mock_db.execute.assert_called_once_with(f"DELETE FROM {FILE_INDEX_TABLE}")

    # ================================================================
    # restore_parsed
    # ================================================================

    def test_restore_parsed_not_found_returns_none(self) -> None:
        """索引中无对应路径时返回 None"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = None

        result = repo.restore_parsed("/nonexistent.pdf")

        self.assertIsNone(result)

    def test_restore_parsed_found_returns_parsed_info(self) -> None:
        """命中索引记录时返回 ParsedStdInfo，part=-1 转 None"""
        repo = self._make_repo()
        row = SAMPLE_ROW.copy()
        # restore_parsed: get() 一次 + _restore_cache_fields 两次（网络缓存+公告缓存）
        self.mock_db.fetchone.side_effect = [
            row,  # get() 命中索引
            None,  # _restore_cache_fields: 网络缓存未命中
            None,  # _restore_cache_fields: 公告缓存未命中
        ]

        import os as _os

        result = repo.restore_parsed(SAMPLE_PATH)

        self.assertIsInstance(result, ParsedStdInfo)
        self.assertEqual(result.logical_code, "GB")  # type: ignore[union-attr]
        self.assertEqual(result.number, 12345)  # type: ignore[union-attr]
        self.assertEqual(result.year, 2020)  # type: ignore[union-attr]
        self.assertIsNone(result.part)  # type: ignore[union-attr]  # -1 → None
        self.assertEqual(result.std_name, "测试标准名称")  # type: ignore[union-attr]
        self.assertEqual(result.source_path, SAMPLE_PATH)  # type: ignore[union-attr]
        self.assertEqual(result.raw_filename, _os.path.basename(SAMPLE_PATH))  # type: ignore[union-attr]

    def test_restore_parsed_part_positive_preserved(self) -> None:
        """part > 0 时保留原值"""
        repo = self._make_repo()
        row = {**SAMPLE_ROW, "part": 3}
        self.mock_db.fetchone.side_effect = [row, None, None]

        result = repo.restore_parsed(SAMPLE_PATH)

        self.assertEqual(result.part, 3)  # type: ignore[union-attr]

    def test_restore_parsed_calls_cache_restore(self) -> None:
        """restore_parsed 应调用 _restore_cache_fields 填充查询结果"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = SAMPLE_ROW.copy()

        with patch.object(repo, "_restore_cache_fields") as mock_restore:
            repo.restore_parsed(SAMPLE_PATH)
            mock_restore.assert_called_once()
            # 传入的 info 应为 ParsedStdInfo 类型
            self.assertIsInstance(mock_restore.call_args[0][0], ParsedStdInfo)

    # ================================================================
    # _restore_cache_fields
    # ================================================================

    def test_restore_cache_fields_network_hit(self) -> None:
        """网络缓存命中时，使用网络缓存结果，不查公告缓存"""
        repo = self._make_repo()
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )
        info.get_full_number()
        net_cache_json = json.dumps(
            {"match_status": "exact", "status": "现行", "standard_name": "国标名称", "is_adopted": True}
        )

        # fetchone 第一次调用（网络缓存）返回结果
        self.mock_db.fetchone.side_effect = [
            {"result_json": net_cache_json},  # 网络缓存命中
        ]

        repo._restore_cache_fields(info)

        self.assertEqual(info.effect_status, "现行")
        self.assertEqual(info.found_name, "国标名称")
        self.assertTrue(info.is_adopted)
        self.assertEqual(info.match_status, "exact")
        # 只应查网络缓存一次，不应再查公告缓存
        self.assertEqual(self.mock_db.fetchone.call_count, 1)

    def test_restore_cache_fields_network_miss_announcement_hit(self) -> None:
        """网络缓存未命中，回退到公告缓存"""
        repo = self._make_repo()
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )
        info.get_full_number()
        ann_cache_json = json.dumps(
            {"match_status": "exact", "status": "废止", "standard_name": "旧标准名", "is_adopted": False}
        )

        self.mock_db.fetchone.side_effect = [
            None,  # 网络缓存未命中
            {"result_json": ann_cache_json},  # 公告缓存命中
        ]

        repo._restore_cache_fields(info)

        self.assertEqual(info.effect_status, "废止")
        self.assertEqual(info.found_name, "旧标准名")
        self.assertFalse(info.is_adopted)
        self.assertEqual(self.mock_db.fetchone.call_count, 2)

    def test_restore_cache_fields_network_result_json_empty_falls_back(self) -> None:
        """网络缓存行存在但 result_json 为空时，回退到公告缓存"""
        repo = self._make_repo()
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )
        ann_cache_json = json.dumps({"match_status": "exact", "status": "即将实施"})

        self.mock_db.fetchone.side_effect = [
            {"result_json": ""},  # 网络缓存 result_json 为空
            {"result_json": ann_cache_json},  # 公告缓存
        ]

        repo._restore_cache_fields(info)

        self.assertEqual(info.effect_status, "即将实施")
        self.assertEqual(self.mock_db.fetchone.call_count, 2)

    def test_restore_cache_fields_both_miss(self) -> None:
        """网络和公告缓存均未命中时，不修改 info 字段"""
        repo = self._make_repo()
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )

        self.mock_db.fetchone.side_effect = [None, None]

        repo._restore_cache_fields(info)

        # 所有字段应保持默认值
        self.assertEqual(info.effect_status, "")
        self.assertEqual(info.found_name, "")
        self.assertFalse(info.is_adopted)
        self.assertEqual(info.match_status, "")
        self.assertEqual(self.mock_db.fetchone.call_count, 2)

    # ================================================================
    # _apply_cache_result
    # ================================================================

    def test_apply_cache_result_exact_match_fills_fields(self) -> None:
        """match_status=exact 时填充所有字段"""
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )
        result_json = json.dumps(
            {
                "match_status": "exact",
                "status": "现行",
                "standard_name": "测试标准全名",
                "is_adopted": True,
            }
        )

        FileIndexRepository._apply_cache_result(result_json, info)

        self.assertEqual(info.effect_status, "现行")
        self.assertEqual(info.found_name, "测试标准全名")
        self.assertTrue(info.is_adopted)
        self.assertEqual(info.match_status, "exact")

    def test_apply_cache_result_non_exact_does_not_fill(self) -> None:
        """match_status 不是 exact 时不填充字段"""
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )
        result_json = json.dumps(
            {
                "match_status": "code_only",
                "status": "现行",
                "standard_name": "名称",
            }
        )

        FileIndexRepository._apply_cache_result(result_json, info)

        self.assertEqual(info.effect_status, "")  # 未修改
        self.assertEqual(info.found_name, "")  # 未修改
        self.assertFalse(info.is_adopted)
        self.assertEqual(info.match_status, "")

    def test_apply_cache_result_invalid_json_passes(self) -> None:
        """无效 JSON 时静默跳过，不修改 info"""
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )

        FileIndexRepository._apply_cache_result("not valid json {{{", info)

        self.assertEqual(info.effect_status, "")

    def test_apply_cache_result_missing_fields_use_defaults(self) -> None:
        """JSON 缺少某些字段时使用默认值（空字符串/False）"""
        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=12345,
            year=2020,
            source_path="/tmp/test.pdf",
        )
        # 只有 match_status=exact，缺少 status/standard_name/is_adopted
        result_json = json.dumps({"match_status": "exact"})

        FileIndexRepository._apply_cache_result(result_json, info)

        self.assertEqual(info.match_status, "exact")
        self.assertEqual(info.effect_status, "")
        self.assertEqual(info.found_name, "")
        self.assertFalse(info.is_adopted)

    # ================================================================
    # find_moved_files
    # ================================================================

    def test_find_moved_files_hash_match_different_path(self) -> None:
        """哈希命中 + 路径不同 → 加入结果"""
        repo = self._make_repo()
        old_row = {
            "file_path": "/old/path/doc.pdf",
            "logical_code": "GB",
            "number": 1,
            "year": 2023,
            "part": -1,
            "std_name": "某标准",
        }
        self.mock_db.fetchone.return_value = old_row

        candidates = [("/new/path/doc.pdf", SAMPLE_HASH)]
        result = repo.find_moved_files(candidates)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["old_path"], "/old/path/doc.pdf")
        self.assertEqual(result[0]["new_path"], "/new/path/doc.pdf")
        self.assertEqual(result[0]["logical_code"], "GB")

    def test_find_moved_files_hash_match_same_path_skipped(self) -> None:
        """哈希命中但路径相同 → 跳过"""
        repo = self._make_repo()
        same_path = "/same/path/doc.pdf"
        self.mock_db.fetchone.return_value = {"file_path": same_path}

        candidates = [(same_path, SAMPLE_HASH)]
        result = repo.find_moved_files(candidates)

        self.assertEqual(len(result), 0)

    def test_find_moved_files_no_hash_skipped(self) -> None:
        """candidate 的 hash 为空 → 跳过"""
        repo = self._make_repo()

        candidates = [("/some/path.pdf", "")]
        result = repo.find_moved_files(candidates)

        self.assertEqual(len(result), 0)
        self.mock_db.fetchone.assert_not_called()

    def test_find_moved_files_hash_not_found_skipped(self) -> None:
        """find_by_hash 返回 None → 跳过"""
        repo = self._make_repo()
        self.mock_db.fetchone.return_value = None

        candidates = [("/new/path.pdf", SAMPLE_HASH)]
        result = repo.find_moved_files(candidates)

        self.assertEqual(len(result), 0)

    def test_find_moved_files_multiple_candidates(self) -> None:
        """多个 candidate 混合场景"""
        repo = self._make_repo()
        old_row = {
            "file_path": "/old/a.pdf",
            "logical_code": "GB",
            "number": 1,
            "year": 2023,
            "part": -1,
            "std_name": "A",
        }

        # side_effect 对应 find_by_hash 的调用顺序
        self.mock_db.fetchone.side_effect = [
            old_row,  # 第一个：命中且路径不同
            None,  # 第二个：未命中
            {"file_path": "/same/path.pdf"},  # 第三个：命中但路径相同
        ]

        candidates = [
            ("/new/a.pdf", "hash_a"),
            ("/new/b.pdf", "hash_b"),
            ("/same/path.pdf", "hash_c"),
        ]
        result = repo.find_moved_files(candidates)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["old_path"], "/old/a.pdf")

    # ================================================================
    # get_full_info
    # ================================================================

    def test_get_full_info_empty_result(self) -> None:
        """无匹配行时返回空列表"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = []

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(result, [])

    def test_get_full_info_network_cache_priority(self) -> None:
        """网络缓存有值时优先使用，忽略公告缓存"""
        repo = self._make_repo()
        nc_json = json.dumps(
            {"match_status": "exact", "status": "现行", "standard_name": "网络版名称", "is_adopted": True}
        )
        ac_json = json.dumps({"match_status": "exact", "status": "废止", "standard_name": "公告版名称"})
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": -1,
                "std_name": "本地名称",
                "nc_result_json": nc_json,
                "nc_cached_at": "2024-01-01",
                "ac_result_json": ac_json,
                "ac_cached_at": "2024-01-02",
            }
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["effect_status"], "现行")  # 取网络缓存
        self.assertEqual(result[0]["found_name"], "网络版名称")
        self.assertEqual(result[0]["cached_at"], "2024-01-01")
        self.assertTrue(result[0]["is_adopted"])

    def test_get_full_info_announcement_cache_fallback(self) -> None:
        """网络缓存无值时回退到公告缓存"""
        repo = self._make_repo()
        ac_json = json.dumps(
            {"match_status": "exact", "status": "废止", "standard_name": "公告版名称", "is_adopted": False}
        )
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": -1,
                "std_name": "本地名称",
                "nc_result_json": None,
                "nc_cached_at": None,
                "ac_result_json": ac_json,
                "ac_cached_at": "2024-02-01",
            }
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["effect_status"], "废止")
        self.assertEqual(result[0]["found_name"], "公告版名称")
        self.assertEqual(result[0]["cached_at"], "2024-02-01")

    def test_get_full_info_no_cache_at_all(self) -> None:
        """两个缓存都无值时返回默认值"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": -1,
                "std_name": "本地名称",
                "nc_result_json": None,
                "nc_cached_at": None,
                "ac_result_json": None,
                "ac_cached_at": None,
            }
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["effect_status"], "")
        self.assertEqual(result[0]["found_name"], "")
        self.assertFalse(result[0]["is_adopted"])
        self.assertEqual(result[0]["match_status"], "")
        self.assertEqual(result[0]["cached_at"], "")

    def test_get_full_info_json_decode_error_handled(self) -> None:
        """缓存 JSON 解析失败时静默跳过，不影响其他字段"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": -1,
                "std_name": "本地名称",
                "nc_result_json": "not valid json @@@",
                "nc_cached_at": "2024-01-01",
                "ac_result_json": None,
                "ac_cached_at": None,
            }
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(len(result), 1)
        # JSON 解析失败，保持默认值
        self.assertEqual(result[0]["effect_status"], "")

    def test_get_full_info_part_normalization(self) -> None:
        """part=-1 应转为 None"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": -1,
                "std_name": "名称",
                "nc_result_json": None,
                "nc_cached_at": None,
                "ac_result_json": None,
                "ac_cached_at": None,
            }
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertIsNone(result[0]["part"])

    def test_get_full_info_part_positive_preserved(self) -> None:
        """part > 0 保留原值"""
        repo = self._make_repo()
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": 2,
                "std_name": "名称",
                "nc_result_json": None,
                "nc_cached_at": None,
                "ac_result_json": None,
                "ac_cached_at": None,
            }
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(result[0]["part"], 2)

    def test_get_full_info_cached_at_none_uses_empty_string(self) -> None:
        """cached_at 为 None 时使用空字符串"""
        repo = self._make_repo()
        nc_json = json.dumps({"match_status": "exact"})
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": -1,
                "std_name": "名称",
                "nc_result_json": nc_json,
                "nc_cached_at": None,
                "ac_result_json": None,
                "ac_cached_at": None,
            }
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(result[0]["cached_at"], "")

    def test_get_full_info_multiple_rows(self) -> None:
        """多行结果各自独立处理"""
        repo = self._make_repo()
        nc_json = json.dumps({"match_status": "exact", "status": "现行"})
        self.mock_db.fetchall.return_value = [
            {
                "file_path": "/a.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2020,
                "part": -1,
                "std_name": "A",
                "nc_result_json": nc_json,
                "nc_cached_at": "2024-01-01",
                "ac_result_json": None,
                "ac_cached_at": None,
            },
            {
                "file_path": "/b.pdf",
                "logical_code": "GB",
                "number": 12345,
                "year": 2021,
                "part": -1,
                "std_name": "B",
                "nc_result_json": None,
                "nc_cached_at": None,
                "ac_result_json": None,
                "ac_cached_at": None,
            },
        ]

        result = repo.get_full_info("GB", 12345)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["effect_status"], "现行")
        self.assertEqual(result[1]["effect_status"], "")

    def test_get_full_info_sql_uses_like_prefix_for_cache_join(self) -> None:
        """JOIN 应使用 LIKE 前缀匹配（兼容新旧连接号格式）"""
        repo = self._make_repo()

        repo.get_full_info("GB", 12345)

        call_sql: str = self.mock_db.fetchall.call_args[0][0]
        self.assertIn("LIKE", call_sql)
        self.assertIn("|| ' ' ||", call_sql)  # SQLite 字符串拼接

    # ================================================================
    # stop
    # ================================================================

    def test_stop_sets_both_events(self) -> None:
        """stop 应设置 stop_event 和 validation_complete"""
        repo = self._make_repo()
        repo._stop_event.clear()
        repo._validation_complete.clear()

        repo.stop()

        self.assertTrue(repo._stop_event.is_set())
        self.assertTrue(repo._validation_complete.is_set())

    def test_stop_calls_db_close_all(self) -> None:
        """stop 应调用 db.close_all()"""
        repo = self._make_repo()

        repo.stop()

        self.mock_db.close_all.assert_called_once()

    def test_stop_db_is_none_no_close(self) -> None:
        """_db 为 None 时跳过 close_all()"""
        repo = self._make_repo()
        repo._db = None  # type: ignore[assignment]

        repo.stop()  # 不应抛异常

        self.mock_db.close_all.assert_not_called()

    def test_stop_db_close_all_raises_is_caught(self) -> None:
        """db.close_all() 抛异常时应吞掉"""
        repo = self._make_repo()
        self.mock_db.close_all.side_effect = Exception("connection lost")

        repo.stop()  # 不应抛异常

        self.assertTrue(repo._stop_event.is_set())

    def test_stop_thread_already_dead_does_not_block(self) -> None:
        """线程已结束时 join 立即返回"""
        repo = self._make_repo()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        repo._validation_thread = mock_thread

        repo.stop()

        mock_thread.join.assert_not_called()

    def test_stop_thread_alive_joins_with_timeout(self) -> None:
        """线程仍在运行时 join(timeout=5)"""
        repo = self._make_repo()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        repo._validation_thread = mock_thread

        repo.stop()

        mock_thread.join.assert_called_once_with(timeout=5)

    def test_stop_thread_is_none_no_join(self) -> None:
        """_validation_thread 为 None 时不做 join"""
        repo = self._make_repo()
        repo._validation_thread = None

        repo.stop()  # 不应抛异常

        # join 不应该被调用（因为 None 没有 join 方法）
        # 这里是验证不抛异常即可
        self.assertTrue(repo._stop_event.is_set())

    def test_stop_no_db_attribute_handled(self) -> None:
        """没有 _db 属性时也能安全退出（defensive check）"""
        repo = self._make_repo()
        # 删除 _db 属性模拟极端情况
        delattr(repo, "_db")  # type: ignore[arg-type]

        repo.stop()  # 不应抛异常

        self.assertTrue(repo._stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
