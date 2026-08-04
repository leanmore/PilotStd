# 模块：pilotstd/manager/facade/_download.py
"""DownloadHandler：下载执行、流式下载、下载等待队列，替代原 DownloadMixin。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ...download.models import BatchDownloadStats, DownloadTask

if TYPE_CHECKING:
    from ._core import ManagerCore

logger = logging.getLogger(__name__)
# DownloadHandler — 下载处理器，封装所有下载方法，替代原 DownloadMixin


class DownloadHandler:
    """下载处理器 — 封装所有下载方法，替代原 DownloadMixin。"""

    def __init__(self, core: "ManagerCore"):
        """初始化下载处理器，持有 ManagerCore 引用。"""
        self._core = core

    def _handle_expired_if_needed(self) -> None:
        """（已废弃）废止标准统一走主线 organize() 归档，不再独立处理。保留方法签名供测试兼容。"""

    def _post_process_download(self, completed: list[DownloadTask], tasks: list[DownloadTask]) -> None:
        """下载后处理：更新 source_path 和缓存状态。"""
        for task in completed:
            if task.status.value == "success" and task.saved_path:
                for i, p in enumerate(self._core.download_list):
                    if i < len(tasks) and tasks[i] is task:
                        p.source_path = task.saved_path
                        old_status = getattr(p, "effect_status", "") or ""
                        old_match = getattr(p, "match_status", "") or ""
                        new_effect = ""
                        if old_status in ("废止", "已废止", "作废", "被代替"):
                            new_effect = "现行"
                        elif old_status == "现行" and old_match == "newer":
                            new_effect = "待实施"
                        if new_effect:
                            cached = self._core.cache.get(task.standard_number, getattr(task, "source_site", ""))
                            if cached:
                                cached.status = new_effect
                                self._core.cache.put(cached)
                        break

    # download — 批量下载分类结果中的标准文件
    def download(
        self, query_results: list[Any] | None = None, _adapter: Any = None
    ) -> tuple[list[DownloadTask], BatchDownloadStats]:
        """下载分类结果中的标准文件。
        _adapter: DI 注入，可传入 mock 下载适配器覆盖默认适配器。
        """
        results = query_results or self._core.query_results

        tasks: list[DownloadTask] = []
        queried = self._core.queried_items if self._core.queried_items else self._core.parsed_results

        for p in self._core.download_list:
            for i, r in enumerate(results):
                if i < len(queried) and queried[i] is p:
                    tasks.append(
                        DownloadTask(
                            standard_number=r.standard_number,
                            query_result=r,
                            source_site=getattr(r, "source_site", ""),
                        )
                    )
                    break

        completed, stats = self._core.download_engine.download_batch(
            tasks, notification_mgr=self._core.notification_mgr
        )
        self._core.download_tasks = completed
        self._post_process_download(completed, tasks)

        logger.info(
            "下载完成: 入队 %d, 成功 %d, 跳过(已存在) %d, 失败 %d",
            len(tasks),
            stats.success,
            stats.skipped_exists,
            stats.failed,
        )
        return tasks, stats

    # download_stream — 流式下载（线程安全），逐条下载并回调进度和结果
    def download_stream(
        self, on_progress: Any = None, on_result: Any = None, _adapter: Any = None
    ) -> tuple[list[DownloadTask], BatchDownloadStats]:
        """流式下载（线程安全）。
        _adapter: DI 注入，可传入 mock 下载适配器覆盖默认适配器。
        """

        tasks: list[tuple[int, DownloadTask, Any]] = []
        queried = self._core.queried_items if self._core.queried_items else self._core.parsed_results

        for p in self._core.download_list:
            for i, r in enumerate(self._core.query_results):
                if i < len(queried) and queried[i] is p:
                    tasks.append(
                        (
                            i,
                            DownloadTask(
                                standard_number=r.standard_number,
                                query_result=r,
                                source_site=getattr(r, "source_site", ""),
                            ),
                            p,
                        )
                    )
                    break

        completed: list[DownloadTask] = []
        stats = BatchDownloadStats()
        total = len(tasks)

        for idx, (orig_idx, task, parsed) in enumerate(tasks):
            result = self._core.download_engine.download_single(task, skip_adopted=True)
            completed.append(result)

            if result.status.value == "success":
                stats.success += 1
                if result.saved_path:
                    parsed.source_path = result.saved_path
            elif result.status.value == "failed":
                stats.failed += 1
            else:
                stats.skipped_exists += 1

            status = (
                "已下载"
                if result.status.value == "success"
                else "下载失败"
                if result.status.value == "failed"
                else "采标受限"
                if result.status.value == "skipped"
                else result.status.value
            )
            if on_result:
                on_result(orig_idx, status)
            if on_progress:
                on_progress(idx + 1, total)

        self._core.download_tasks = completed
        return completed, stats

    def download_by_numbers(self, numbers: list[str]) -> tuple[list[DownloadTask], Any]:
        """按标准号列表下载。"""
        return self._core.scheduled_svc.download_by_numbers(numbers)  # type: ignore[no-any-return]

    # ── 下载等待队列 ──

    def enqueue_download_wait(self, parsed: Any) -> None:
        """将解析结果加入下载等待队列。"""
        self._core.pending_svc.enqueue_download_wait(parsed)

    def get_due_downloads(self) -> list[dict[str, Any]]:
        """获取到期的下载等待队列项。"""
        return self._core.pending_svc.get_due_downloads()  # type: ignore[no-any-return]

    def remove_download_queue(self, standard_number: str) -> None:
        """从下载等待队列中移除指定标准号。"""
        self._core.pending_svc.remove_download_queue(standard_number)
