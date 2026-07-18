# tests/test_facade_download_full.py
"""DownloadHandler 单元测试 — 覆盖 _download.py 全部公开方法和核心私有方法。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.download.models import BatchDownloadStats, DownloadStatus, DownloadTask
from pilotstd.manager.facade._download import DownloadHandler
from pilotstd.query.models import QueryResult


def _make_parsed_item(
    logical_code: str = "GB",
    number: str = "19001",
    year: str = "2016",
    std_name: str = "质量管理体系",
    source_path: str = "/fake/path.pdf",
) -> MagicMock:
    p = MagicMock()
    p.logical_code = logical_code
    p.number = number
    p.year = year
    p.std_name = std_name
    p.source_path = source_path
    p.effect_status = ""
    p.match_status = ""
    return p


class TestDownloadHandler(unittest.TestCase):
    """DownloadHandler 全部方法测试。"""

    def setUp(self):
        self.core = MagicMock()
        self.core.download_engine = MagicMock()
        self.core.download_list = []
        self.core.expire_list = []
        self.core.query_results = []
        self.core.queried_items = []
        self.core.parsed_results = []
        self.core.download_tasks = []
        self.core.cache = MagicMock()
        self.core.scheduled_svc = MagicMock()
        self.core.pending_svc = MagicMock()
        self.core.notification_mgr = MagicMock()

        self.handler = DownloadHandler(self.core)

    # ── __init__ ──

    def test_init_stores_core_and_organize_none(self):
        self.assertIs(self.handler._core, self.core)
        self.assertIsNone(self.handler._organize_handler)

    # ── _set_organize_handler ──

    def test_set_organize_handler(self):
        mock_org = MagicMock()
        self.handler._set_organize_handler(mock_org)
        self.assertIs(self.handler._organize_handler, mock_org)

    # ── _handle_expired_if_needed ──

    def test_handle_expired_when_list_and_handler_present(self):
        item = _make_parsed_item()
        self.core.expire_list = [item]
        mock_org = MagicMock()
        self.handler._set_organize_handler(mock_org)

        self.handler._handle_expired_if_needed()
        mock_org.handle_expired.assert_called_once_with([item])

    def test_handle_expired_when_list_empty(self):
        self.core.expire_list = []
        mock_org = MagicMock()
        self.handler._set_organize_handler(mock_org)

        self.handler._handle_expired_if_needed()
        mock_org.handle_expired.assert_not_called()

    def test_handle_expired_when_handler_none(self):
        self.core.expire_list = [_make_parsed_item()]
        self.handler._organize_handler = None

        # 不应抛异常
        self.handler._handle_expired_if_needed()

    # ── _post_process_download ──

    def test_post_process_download_success_updates_source_path(self):
        """下载成功后更新 parsed item 的 source_path。"""
        parsed = _make_parsed_item()
        self.core.download_list = [parsed]

        task = DownloadTask(standard_number="GB/T 19001-2016", source_site="std_gov")
        task.status = DownloadStatus.SUCCESS
        task.saved_path = "/saved/19001.pdf"

        tasks = [task]

        self.handler._post_process_download([task], tasks)
        self.assertEqual(parsed.source_path, "/saved/19001.pdf")

    def test_post_process_download_cached_status_update(self):
        """下载成功后根据状态映射规则更新缓存。"""
        parsed = _make_parsed_item()
        parsed.effect_status = "废止"
        self.core.download_list = [parsed]

        task = DownloadTask(standard_number="GB/T 19001-2016", source_site="std_gov")
        task.status = DownloadStatus.SUCCESS
        task.saved_path = "/saved/19001.pdf"

        cached_entry = MagicMock()
        cached_entry.status = "废止"
        self.core.cache.get.return_value = cached_entry

        tasks = [task]
        self.handler._post_process_download([task], tasks)

        self.core.cache.get.assert_called_once_with("GB/T 19001-2016", "std_gov")
        self.assertEqual(cached_entry.status, "现行")
        self.core.cache.put.assert_called_once_with(cached_entry)

    def test_post_process_download_newer_status_update(self):
        """现行 + match_status=newer → 更新为待实施。"""
        parsed = _make_parsed_item()
        parsed.effect_status = "现行"
        parsed.match_status = "newer"
        self.core.download_list = [parsed]

        task = DownloadTask(standard_number="GB/T 1-2020", source_site="std_gov")
        task.status = DownloadStatus.SUCCESS
        task.saved_path = "/saved/1.pdf"

        cached_entry = MagicMock()
        cached_entry.status = "现行"
        self.core.cache.get.return_value = cached_entry

        tasks = [task]
        self.handler._post_process_download([task], tasks)

        self.assertEqual(cached_entry.status, "待实施")
        self.core.cache.put.assert_called_once_with(cached_entry)

    def test_post_process_download_no_status_change(self):
        """无需变更的状态不更新缓存。"""
        parsed = _make_parsed_item()
        parsed.effect_status = "现行"
        parsed.match_status = "exact"
        self.core.download_list = [parsed]

        task = DownloadTask(standard_number="GB/T 1-2020", source_site="std_gov")
        task.status = DownloadStatus.SUCCESS
        task.saved_path = "/saved/1.pdf"

        tasks = [task]
        self.handler._post_process_download([task], tasks)

        # new_effect 为空时跳过 cache.get/cache.put
        self.core.cache.get.assert_not_called()
        self.core.cache.put.assert_not_called()

    def test_post_process_download_failed_does_not_update(self):
        """下载失败不更新 source_path。"""
        parsed = _make_parsed_item()
        parsed.source_path = "/original.pdf"
        self.core.download_list = [parsed]

        task = DownloadTask(standard_number="GB/T 19001-2016", source_site="std_gov")
        task.status = DownloadStatus.FAILED
        task.saved_path = ""

        tasks = [task]
        self.handler._post_process_download([task], tasks)
        # source_path 应不变
        self.assertEqual(parsed.source_path, "/original.pdf")

    def test_post_process_download_skipped_does_not_update(self):
        parsed = _make_parsed_item()
        parsed.source_path = "/original.pdf"
        self.core.download_list = [parsed]

        task = DownloadTask(standard_number="GB/T 19001-2016", source_site="std_gov")
        task.status = DownloadStatus.SKIPPED
        task.saved_path = ""

        tasks = [task]
        self.handler._post_process_download([task], tasks)
        self.assertEqual(parsed.source_path, "/original.pdf")

    # ── download ──

    def test_download_constructs_tasks_and_calls_engine(self):
        """验证 download() 从 download_list 构建 DownloadTask 并调用引擎。"""
        parsed = _make_parsed_item()
        self.core.download_list = [parsed]
        self.core.queried_items = [parsed]  # 与 download_list 同一对象 ⇒ 匹配
        qr = QueryResult(standard_number="GB/T 19001-2016", standard_name="质量管理体系", source_site="std_gov")
        self.core.query_results = [qr]

        completed_task = MagicMock(spec=DownloadTask)
        completed_task.status = DownloadStatus.SUCCESS
        stats = BatchDownloadStats(total=1, success=1)
        self.core.download_engine.download_batch.return_value = ([completed_task], stats)

        with patch.object(self.handler, "_handle_expired_if_needed"):
            with patch.object(self.handler, "_post_process_download"):
                tasks, ret_stats = self.handler.download()

        self.core.download_engine.download_batch.assert_called_once()
        call_args = self.core.download_engine.download_batch.call_args[0][0]
        self.assertEqual(len(call_args), 1)
        self.assertIsInstance(call_args[0], DownloadTask)
        self.assertEqual(call_args[0].standard_number, "GB/T 19001-2016")
        self.assertEqual(call_args[0].source_site, "std_gov")
        self.assertEqual(ret_stats, stats)

    def test_download_with_explicit_query_results(self):
        """传入 query_results 参数时使用传入值而非 core.query_results。"""
        parsed = _make_parsed_item()
        self.core.download_list = [parsed]
        self.core.queried_items = [parsed]
        external_results = [QueryResult(standard_number="GB/T 1-2020", standard_name="ext")]

        stats = BatchDownloadStats()
        self.core.download_engine.download_batch.return_value = ([], stats)

        with patch.object(self.handler, "_handle_expired_if_needed"):
            with patch.object(self.handler, "_post_process_download"):
                tasks, _ = self.handler.download(query_results=external_results)

        # 构建的 task 应使用 external_results 的数据
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].standard_number, "GB/T 1-2020")

    def test_download_no_match_skipped(self):
        """当 download_list 与 queried_items 无对象匹配时，tasks 为空。"""
        parsed = _make_parsed_item()
        self.core.download_list = [parsed]
        # queried_items 使用不同对象 ⇒ is 匹配失败
        parsed2 = _make_parsed_item()
        self.core.queried_items = [parsed2]
        self.core.query_results = [QueryResult(standard_number="GB/T 19001-2016")]

        stats = BatchDownloadStats()
        self.core.download_engine.download_batch.return_value = ([], stats)

        with patch.object(self.handler, "_handle_expired_if_needed"):
            with patch.object(self.handler, "_post_process_download"):
                tasks, _ = self.handler.download()

        self.assertEqual(len(tasks), 0)

    # ── download_stream ──

    def test_download_stream(self):
        """流式下载：逐条调用 download_single。"""
        parsed = _make_parsed_item()
        self.core.download_list = [parsed]
        self.core.queried_items = [parsed]
        qr = QueryResult(standard_number="GB/T 19001-2016", standard_name="质量管理体系", source_site="std_gov")
        self.core.query_results = [qr]

        single_result = MagicMock(spec=DownloadTask)
        single_result.status = DownloadStatus.SUCCESS
        single_result.saved_path = "/saved/19001.pdf"
        self.core.download_engine.download_single.return_value = single_result

        with patch.object(self.handler, "_handle_expired_if_needed"):
            completed, stats = self.handler.download_stream()

        self.core.download_engine.download_single.assert_called_once()
        self.assertEqual(len(completed), 1)
        self.assertEqual(stats.success, 1)
        self.assertEqual(parsed.source_path, "/saved/19001.pdf")

    def test_download_stream_failed(self):
        parsed = _make_parsed_item()
        parsed.source_path = "/orig.pdf"
        self.core.download_list = [parsed]
        self.core.queried_items = [parsed]
        qr = QueryResult(standard_number="GB/T 1-2020")
        self.core.query_results = [qr]

        single_result = MagicMock(spec=DownloadTask)
        single_result.status = DownloadStatus.FAILED
        single_result.saved_path = ""
        self.core.download_engine.download_single.return_value = single_result

        with patch.object(self.handler, "_handle_expired_if_needed"):
            completed, stats = self.handler.download_stream()

        self.assertEqual(stats.failed, 1)
        self.assertEqual(parsed.source_path, "/orig.pdf")

    def test_download_stream_skipped(self):
        parsed = _make_parsed_item()
        self.core.download_list = [parsed]
        self.core.queried_items = [parsed]
        qr = QueryResult(standard_number="GB/T 1-2020")
        self.core.query_results = [qr]

        single_result = MagicMock(spec=DownloadTask)
        single_result.status = DownloadStatus.SKIPPED
        self.core.download_engine.download_single.return_value = single_result

        with patch.object(self.handler, "_handle_expired_if_needed"):
            completed, stats = self.handler.download_stream()

        self.assertEqual(stats.skipped_exists, 1)

    def test_download_stream_with_callbacks(self):
        parsed = _make_parsed_item()
        self.core.download_list = [parsed]
        self.core.queried_items = [parsed]
        qr = QueryResult(standard_number="GB/T 19001-2016", source_site="std_gov")
        self.core.query_results = [qr]

        single_result = MagicMock(spec=DownloadTask)
        single_result.status = DownloadStatus.SUCCESS
        single_result.saved_path = ""
        self.core.download_engine.download_single.return_value = single_result

        on_progress = MagicMock()
        on_result = MagicMock()

        with patch.object(self.handler, "_handle_expired_if_needed"):
            self.handler.download_stream(on_progress=on_progress, on_result=on_result)

        on_progress.assert_called_once_with(1, 1)
        on_result.assert_called_once_with(0, "已下载")

    # ── download_by_numbers ──

    def test_download_by_numbers(self):
        self.core.scheduled_svc.download_by_numbers.return_value = ([], BatchDownloadStats())
        nums = ["GB/T 19001-2016"]
        tasks, stats = self.handler.download_by_numbers(nums)
        self.core.scheduled_svc.download_by_numbers.assert_called_once_with(nums)

    # ── enqueue_download_wait ──

    def test_enqueue_download_wait(self):
        parsed = _make_parsed_item()
        self.handler.enqueue_download_wait(parsed)
        self.core.pending_svc.enqueue_download_wait.assert_called_once_with(parsed)

    # ── get_due_downloads ──

    def test_get_due_downloads(self):
        self.core.pending_svc.get_due_downloads.return_value = [{"standard_number": "GB/T 1"}]
        result = self.handler.get_due_downloads()
        self.assertEqual(result, [{"standard_number": "GB/T 1"}])

    # ── remove_download_queue ──

    def test_remove_download_queue(self):
        self.handler.remove_download_queue("GB/T 1")
        self.core.pending_svc.remove_download_queue.assert_called_once_with("GB/T 1")


if __name__ == "__main__":
    unittest.main()
