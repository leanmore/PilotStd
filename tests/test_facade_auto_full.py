# tests/test_facade_auto_full.py
"""AutoPipeline 单元测试 — 覆盖 _auto.py 全部公开方法和核心私有方法。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pilotstd.download.models import BatchDownloadStats
from pilotstd.manager.facade._auto import AutoPipeline
from pilotstd.query.models import BatchQueryStats, QueryResult


class TestAutoPipeline(unittest.TestCase):
    """AutoPipeline 全部方法测试。"""

    def setUp(self):
        # 构造 ManagerCore mock
        self.core = MagicMock()
        self.core.cfg = MagicMock()
        self.core.cfg.get.return_value = True
        self.core.download_list = []
        self.core.query_results = []
        self.core.expire_list = []
        self.core.last_skipped_dirs = []

        # 构造 4 个 handler mock
        self.scan_handler = MagicMock()
        self.query_handler = MagicMock()
        self.download_handler = MagicMock()
        self.organize_handler = MagicMock()

        # 构造被测对象
        self.pipeline = AutoPipeline(
            self.core,
            self.scan_handler,
            self.query_handler,
            self.download_handler,
            self.organize_handler,
        )

    def _make_parsed_item(
        self,
        logical_code: str = "GB",
        number: str = "19001",
        year: str = "2016",
        std_name: str = "质量管理体系",
        next_action: str = "download",
    ) -> MagicMock:
        p = MagicMock()
        p.logical_code = logical_code
        p.number = number
        p.year = year
        p.std_name = std_name
        p.next_action = next_action
        return p

    # ── __init__ ──

    def test_init_stores_all_refs(self):
        self.assertIs(self.pipeline._core, self.core)
        self.assertIs(self.pipeline._scan, self.scan_handler)
        self.assertIs(self.pipeline._query, self.query_handler)
        self.assertIs(self.pipeline._download, self.download_handler)
        self.assertIs(self.pipeline._organize, self.organize_handler)

    # ── auto_run ──

    def test_auto_run_full_pipeline(self):
        """验证 auto_run 完整流程：scan→query→download→archive→fallback。"""
        parsed = [self._make_parsed_item()]
        self.scan_handler.scan_directory.return_value = parsed

        stats = BatchQueryStats(found=1)
        fake_result = QueryResult(standard_number="GB/T 19001-2016", standard_name="质量管理体系")
        self.query_handler.query.return_value = (None, stats)

        dl_stats = BatchDownloadStats(success=1)
        self.download_handler.download.return_value = ([], dl_stats)

        self.organize_handler.archive_standards.return_value = {"moved": 1}
        self.organize_handler.organize_skipped_dirs.return_value = {"moved": 0}
        self.organize_handler.organize_fallback.return_value = {"moved": 0}

        # 无跳过目录
        self.core.last_skipped_dirs = []

        report = self.pipeline.auto_run("/fake/root")

        self.assertEqual(report["scan"], 1)
        self.assertEqual(report["query_found"], 1)
        self.assertEqual(report["download_success"], 1)
        self.assertEqual(report["organize_moved"], 1)

        self.scan_handler.scan_directory.assert_called_once_with("/fake/root")
        self.query_handler.query.assert_called_once_with(parsed)
        self.download_handler.download.assert_called_once()
        self.organize_handler.archive_standards.assert_called_once_with(parsed)

    def test_auto_run_mirror_skipped(self):
        """有跳过目录时调用 organize_skipped_dirs。"""
        parsed = [self._make_parsed_item()]
        self.scan_handler.scan_directory.return_value = parsed
        self.query_handler.query.return_value = (None, BatchQueryStats(found=0))
        self.download_handler.download.return_value = ([], BatchDownloadStats())
        self.organize_handler.archive_standards.return_value = {"moved": 0}

        self.core.cfg.get.return_value = True
        self.core.last_skipped_dirs = ["/fake/skipped"]

        self.pipeline.auto_run("/fake/root")
        self.organize_handler.organize_skipped_dirs.assert_called_once_with(["/fake/skipped"], source_root="/fake/root")

    def test_auto_run_mirror_disabled(self):
        """mirror_skipped_dirs=False 时不调用 organize_skipped_dirs。"""
        parsed = [self._make_parsed_item()]
        self.scan_handler.scan_directory.return_value = parsed
        self.query_handler.query.return_value = (None, BatchQueryStats(found=0))
        self.download_handler.download.return_value = ([], BatchDownloadStats())
        self.organize_handler.archive_standards.return_value = {"moved": 0}

        self.core.cfg.get.side_effect = lambda key, default=None: {
            "storage.mirror_skipped_dirs": False,
            "storage.mirror_fallback": False,
        }.get(key, default)

        self.pipeline.auto_run("/fake/root")
        self.organize_handler.organize_skipped_dirs.assert_not_called()

    # ── _auto_stage_query ──

    def test_auto_stage_query_with_progress(self):
        parsed = [self._make_parsed_item()]
        self.query_handler.query.return_value = (None, BatchQueryStats(found=1))
        on_progress = MagicMock()
        on_result = MagicMock()

        report, t_next = self.pipeline._auto_stage_query(parsed, on_progress, on_result, {}, 100.0)
        self.assertEqual(report["query_found"], 1)
        self.assertGreater(t_next, 0)
        # on_progress 至少 1 次（100% 完成回调），query mock 不触发内部 progress_callback
        self.assertGreaterEqual(on_progress.call_count, 1)
        # 最后一次调用应为 (100, 100)
        self.assertEqual(on_progress.call_args_list[-1][0], (100, 100))

    def test_auto_stage_query_no_progress(self):
        parsed = [self._make_parsed_item()]
        self.query_handler.query.return_value = (None, BatchQueryStats(found=0))
        report, t_next = self.pipeline._auto_stage_query(parsed, None, None, {}, 100.0)
        self.assertEqual(report["query_found"], 0)

    # ── _auto_stage_archive_and_fallback ──

    def test_auto_stage_archive_and_fallback(self):
        """验证归档 + 收容完整流程。"""
        parsed = [self._make_parsed_item()]
        self.organize_handler.archive_standards.return_value = {"moved": 1}
        self.organize_handler.organize_skipped_dirs.return_value = {"moved": 2}
        self.organize_handler.organize_fallback.return_value = {"moved": 3}

        self.core.cfg.get.return_value = True
        self.core.last_skipped_dirs = ["/fake/skipped"]

        on_archive_result = MagicMock()
        on_stage_change = MagicMock()

        report = self.pipeline._auto_stage_archive_and_fallback(
            parsed, "/fake/root", on_archive_result, on_stage_change, {}, 100.0
        )

        self.assertEqual(report["organize_moved"], 1)
        self.assertEqual(report["mirror_skipped"], 2)
        self.assertEqual(report["fallback_mirrored"], 3)

        # 应收到 archive / mirror_skipped / fallback / done 四个阶段变更
        stage_names = [call[0][0] for call in on_stage_change.call_args_list]
        self.assertIn("archive", stage_names)
        self.assertIn("mirror_skipped", stage_names)
        self.assertIn("fallback", stage_names)
        self.assertIn("done", stage_names)

    def test_auto_stage_archive_skips_pending(self):
        """next_action='pending' 的条目应被过滤，不参与归档。"""
        parsed = [
            self._make_parsed_item(next_action="download"),
            self._make_parsed_item(number="1", next_action="pending"),
        ]
        self.organize_handler.archive_standards.return_value = {"moved": 1}
        self.core.cfg.get.return_value = False
        self.core.last_skipped_dirs = []

        self.pipeline._auto_stage_archive_and_fallback(parsed, "/fake/root", None, None, {}, 100.0)

        # archive_standards 只收到 1 条（next_action != pending）
        call_args = self.organize_handler.archive_standards.call_args[0][0]
        self.assertEqual(len(call_args), 1)

    def test_auto_stage_archive_no_mirror_when_disabled(self):
        parsed = [self._make_parsed_item()]
        self.organize_handler.archive_standards.return_value = {"moved": 0}
        self.core.cfg.get.return_value = False
        self.core.last_skipped_dirs = ["/exists"]

        self.pipeline._auto_stage_archive_and_fallback(parsed, "/fake/root", None, None, {}, 100.0)
        self.organize_handler.organize_skipped_dirs.assert_not_called()
        self.organize_handler.organize_fallback.assert_not_called()

    # ── auto_run_stream ──

    def test_auto_run_stream_full(self):
        """验证流式管线：scan_stream → query → download_stream → archive。"""
        parsed = [self._make_parsed_item()]
        self.scan_handler.scan_directory_stream.return_value = parsed
        self.query_handler.query.return_value = (None, BatchQueryStats(found=1))

        # download_list 非空 → 触发 download_stream
        self.core.download_list = [parsed[0]]

        dl_stats = BatchDownloadStats(success=1)
        self.download_handler.download_stream.return_value = ([], dl_stats)

        self.organize_handler.archive_standards.return_value = {"moved": 1}
        self.organize_handler.organize_skipped_dirs.return_value = {"moved": 0}
        self.organize_handler.organize_fallback.return_value = {"moved": 0}
        self.core.cfg.get.return_value = True
        self.core.last_skipped_dirs = []

        report = self.pipeline.auto_run_stream("/fake/root")
        self.assertEqual(report["scan"], 1)
        self.assertEqual(report["query_found"], 1)
        self.assertEqual(report["download_success"], 1)

    def test_auto_run_stream_empty_parsed(self):
        """扫描结果为空时立即结束，直接 done。"""
        self.scan_handler.scan_directory_stream.return_value = []

        on_stage_change = MagicMock()

        report = self.pipeline.auto_run_stream("/fake/root", on_stage_change=on_stage_change)
        self.assertEqual(report["scan"], 0)
        # done 回调
        done_calls = [c for c in on_stage_change.call_args_list if c[0][0] == "done"]
        self.assertEqual(len(done_calls), 1)

    def test_auto_run_stream_no_download_when_list_empty(self):
        """download_list 为空时不触发 download_stream。"""
        parsed = [self._make_parsed_item()]
        self.scan_handler.scan_directory_stream.return_value = parsed
        self.query_handler.query.return_value = (None, BatchQueryStats(found=1))

        self.core.download_list = []

        self.organize_handler.archive_standards.return_value = {"moved": 0}
        self.core.cfg.get.return_value = False

        self.pipeline.auto_run_stream("/fake/root")
        self.download_handler.download_stream.assert_not_called()

    def test_auto_run_stream_stage_callbacks(self):
        """验证阶段变更回调顺序。"""
        parsed = [self._make_parsed_item()]
        self.scan_handler.scan_directory_stream.return_value = parsed
        self.query_handler.query.return_value = (None, BatchQueryStats(found=1))
        self.core.download_list = []

        self.organize_handler.archive_standards.return_value = {"moved": 0}
        self.core.cfg.get.return_value = False

        on_stage_change = MagicMock()
        self.pipeline.auto_run_stream("/fake/root", on_stage_change=on_stage_change)

        # 预期的阶段序列：scan → query → (无下载) → archive → done
        stage_seq = [call[0][0] for call in on_stage_change.call_args_list]
        self.assertEqual(stage_seq[0], "scan")
        self.assertEqual(stage_seq[1], "query")
        # download 阶段不应出现
        self.assertNotIn("download", stage_seq)
        self.assertIn("done", stage_seq)


if __name__ == "__main__":
    unittest.main()
