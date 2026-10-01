"""_download.py (DownloadHandler) 覆盖率补齐 — 目标: 20% → 85%+"""

from unittest.mock import MagicMock

import pytest

from pilotstd.core.status import Status
from pilotstd.download.models import BatchDownloadStats, DownloadStatus, DownloadTask
from pilotstd.manager.facade._download import DownloadHandler


@pytest.fixture
def handler(mock_core):
    return DownloadHandler(mock_core)


def _make_task(success=True, saved_path="/out/test.pdf"):
    task = DownloadTask(standard_number="GB/T 1234-2020", source_site="ahbz")
    if success:
        task.status = DownloadStatus.SUCCESS
        task.saved_path = saved_path
    else:
        task.status = DownloadStatus.FAILED
    return task


# ════════════════════════════════════════════════════════════
# _post_process_download
# ════════════════════════════════════════════════════════════

class TestPostProcessDownload:
    def test_handles_empty_completed(self, handler, mock_core):
        """空 completed 列表 → 不执行任何操作。"""
        handler._post_process_download([], [])
        # 不抛异常即为通过

    def test_success_task_updates_source_path(self, handler, mock_core):
        """下载成功的 task → parsed item 的 source_path 被更新。"""
        parsed = MagicMock()
        parsed.source_path = ""
        parsed.effect_status = Status.ACTIVE.value
        parsed.match_status = "exact"
        mock_core.download_list = [parsed]

        task = _make_task()
        tasks = [task]

        handler._post_process_download([task], tasks)
        assert parsed.source_path == "/out/test.pdf"

    def test_expired_status_updates_to_current(self, handler, mock_core):
        """废止标准下载成功 → effect_status 更新为 '现行'（L38-39）。"""
        parsed = MagicMock()
        parsed.source_path = ""
        parsed.effect_status = Status.WITHDRAWN.value
        parsed.match_status = ""
        mock_core.download_list = [parsed]

        task = _make_task()
        tasks = [task]

        mock_core.cache.get.return_value = MagicMock()
        handler._post_process_download([task], tasks)
        mock_core.cache.put.assert_called_once()

    def test_current_newer_updates_to_pending_impl(self, handler, mock_core):
        """现行 + newer → effect_status 更新为 '待实施'（L40-41）。"""
        parsed = MagicMock()
        parsed.source_path = ""
        parsed.effect_status = Status.ACTIVE.value
        parsed.match_status = "newer"
        mock_core.download_list = [parsed]

        task = _make_task()
        tasks = [task]

        mock_core.cache.get.return_value = MagicMock()
        handler._post_process_download([task], tasks)
        mock_core.cache.put.assert_called_once()

    def test_failed_task_skipped(self, handler, mock_core):
        """下载失败的 task → 不更新 parsed。"""
        parsed = MagicMock()
        parsed.source_path = "original"
        mock_core.download_list = [parsed]

        task = _make_task(success=False)
        tasks = [task]

        handler._post_process_download([task], tasks)
        assert parsed.source_path == "original"


# ════════════════════════════════════════════════════════════
# download() / download_stream()
# ════════════════════════════════════════════════════════════

class TestDownload:
    def test_download_happy_path(self, handler, mock_core):
        """完整下载流程 — 构建 tasks → download_batch → post_process。"""
        parsed = MagicMock()
        mock_core.download_list = [parsed]
        mock_core.queried_items = [parsed]
        result_mock = MagicMock()
        result_mock.standard_number = "GB/T 1234-2020"
        result_mock.source_site = "ahbz"
        mock_core.query_results = [result_mock]

        completed = [_make_task()]
        stats = BatchDownloadStats(success=1)
        mock_core.download_engine.download_batch.return_value = (completed, stats)

        tasks, result_stats = handler.download()
        assert result_stats.success == 1
        mock_core.download_engine.download_batch.assert_called_once()

    def test_download_uses_query_results_param(self, handler, mock_core):
        """传入 query_results 参数 → 覆盖 self._core.query_results。"""
        mock_core.download_list = []
        mock_core.download_engine.download_batch.return_value = (
            [], BatchDownloadStats()
        )
        custom_results = []
        tasks, stats = handler.download(query_results=custom_results)
        assert tasks == []

    def test_download_by_numbers(self, handler, mock_core):
        handler.download_by_numbers(["GB 1-2020"])
        mock_core.scheduled_svc.download_by_numbers.assert_called_once_with(["GB 1-2020"])


# ════════════════════════════════════════════════════════════
# download_stream()
# ════════════════════════════════════════════════════════════

class TestDownloadStream:
    def test_stream_with_progress_and_result(self, handler, mock_core):
        """流式下载 — on_progress + on_result 回调。"""
        parsed = MagicMock()
        mock_core.download_list = [parsed]
        mock_core.queried_items = [parsed]
        result_mock = MagicMock()
        result_mock.standard_number = "GB/T 1234"
        result_mock.source_site = "ahbz"
        mock_core.query_results = [result_mock]

        dl_task = DownloadTask(
            standard_number="GB/T 1234",
            query_result=result_mock,
            source_site="ahbz",
        )
        dl_task.status = DownloadStatus.SUCCESS
        dl_task.saved_path = "/out/test.pdf"
        mock_core.download_engine.download_single.return_value = dl_task

        on_progress = MagicMock()
        on_result = MagicMock()

        handler.download_stream(on_progress=on_progress, on_result=on_result)
        on_progress.assert_called_once_with(1, 1)
        on_result.assert_called_once()

    def test_stream_failed_task(self, handler, mock_core):
        """流式下载 — 失败 task → stats.failed++。"""
        parsed = MagicMock()
        mock_core.download_list = [parsed]
        mock_core.queried_items = [parsed]
        result_mock = MagicMock()
        result_mock.standard_number = "GB/T 1234"
        result_mock.source_site = "ahbz"
        mock_core.query_results = [result_mock]

        dl_task = DownloadTask(
            standard_number="GB/T 1234",
            query_result=result_mock,
            source_site="ahbz",
        )
        dl_task.status = DownloadStatus.FAILED
        mock_core.download_engine.download_single.return_value = dl_task

        completed, stats = handler.download_stream()
        assert stats.failed == 1

    def test_stream_sends_notification(self, handler, mock_core):
        """流式下载结束必须发 batch_download_complete（主下载链路通知接线）。

        回归背景：download_stream 手工累加 stats，从不传 notification_mgr，
        导致 Web（/api/download）与桌面（DownloadWorker）批量下载结束零通知，
        而 favorites 链（经 run_paced_batches）自己发通知——两条路径行为不一致。
        """
        parsed = MagicMock()
        mock_core.download_list = [parsed]
        mock_core.queried_items = [parsed]
        result_mock = MagicMock()
        result_mock.standard_number = "GB/T 1234"
        result_mock.source_site = "ahbz"
        mock_core.query_results = [result_mock]

        dl_task = DownloadTask(
            standard_number="GB/T 1234",
            query_result=result_mock,
            source_site="ahbz",
        )
        dl_task.status = DownloadStatus.SUCCESS
        dl_task.saved_path = "/out/test.pdf"
        mock_core.download_engine.download_single.return_value = dl_task

        handler.download_stream()

        mock_core.notification_mgr.send_event.assert_called_once_with(
            "batch_download_complete",
            {"total": 1, "success": 1, "failed": 0, "skipped": 0},
        )

    def test_stream_notification_counts_failure(self, handler, mock_core):
        """失败条目必须计入通知的 failed，且 total 覆盖全部分类。"""
        parsed = MagicMock()
        mock_core.download_list = [parsed]
        mock_core.queried_items = [parsed]
        result_mock = MagicMock()
        result_mock.standard_number = "GB/T 1234"
        result_mock.source_site = "ahbz"
        mock_core.query_results = [result_mock]

        dl_task = DownloadTask(
            standard_number="GB/T 1234",
            query_result=result_mock,
            source_site="ahbz",
        )
        dl_task.status = DownloadStatus.FAILED
        mock_core.download_engine.download_single.return_value = dl_task

        handler.download_stream()

        mock_core.notification_mgr.send_event.assert_called_once_with(
            "batch_download_complete",
            {"total": 1, "success": 0, "failed": 1, "skipped": 0},
        )

    def test_stream_notification_skipped_maps_to_skipped(self, handler, mock_core):
        """跳过（文件已存在）必须计入通知的 skipped，而非丢失。

        download_stream 记的是 stats.skipped_exists，而 _notify_download_complete
        读的是 stats.skipped_adopted；不归一化会导致 skipped 恒为 0。
        """
        parsed = MagicMock()
        mock_core.download_list = [parsed]
        mock_core.queried_items = [parsed]
        result_mock = MagicMock()
        result_mock.standard_number = "GB/T 1234"
        result_mock.source_site = "ahbz"
        mock_core.query_results = [result_mock]

        dl_task = DownloadTask(
            standard_number="GB/T 1234",
            query_result=result_mock,
            source_site="ahbz",
        )
        dl_task.status = DownloadStatus.SKIPPED
        mock_core.download_engine.download_single.return_value = dl_task

        handler.download_stream()

        mock_core.notification_mgr.send_event.assert_called_once_with(
            "batch_download_complete",
            {"total": 1, "success": 0, "failed": 0, "skipped": 1},
        )

    def test_stream_no_tasks_sends_zero_summary(self, handler, mock_core):
        """无任务时仍走同一通知流程（与 download_batch 无条件通知口径一致）。"""
        mock_core.download_list = []
        mock_core.query_results = []

        handler.download_stream()

        mock_core.notification_mgr.send_event.assert_called_once_with(
            "batch_download_complete",
            {"total": 0, "success": 0, "failed": 0, "skipped": 0},
        )


# ════════════════════════════════════════════════════════════
# download 等待队列
# ════════════════════════════════════════════════════════════

class TestDownloadQueue:
    def test_enqueue_download_wait(self, handler, mock_core):
        parsed = MagicMock()
        handler.enqueue_download_wait(parsed)
        mock_core.pending_svc.enqueue_download_wait.assert_called_once_with(parsed)

    def test_get_due_downloads(self, handler, mock_core):
        mock_core.pending_svc.get_due_downloads.return_value = [{"id": 1}]
        assert handler.get_due_downloads() == [{"id": 1}]

    def test_remove_download_queue(self, handler, mock_core):
        handler.remove_download_queue("GB 1")
        mock_core.pending_svc.remove_download_queue.assert_called_once_with("GB 1")
