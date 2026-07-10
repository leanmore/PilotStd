# pilotstd/manager/facade/_download.py
# StandardManager 下载混入模块
"""DownloadMixin：下载执行、流式下载、下载等待队列。"""

from __future__ import annotations

import logging
from typing import Any, List

from ...download.models import BatchDownloadStats, DownloadTask

logger = logging.getLogger(__name__)


class DownloadMixin:
    """下载混入类 — 下载执行 + 流式下载 + 按号下载。"""

    _query_results: Any
    _expire_list: Any
    _queried_items: Any
    _parsed_results: Any
    _download_list: Any
    _download_tasks: Any
    _pending_svc: Any
    _scheduled_svc: Any
    download_engine: Any
    notification_mgr: Any
    cache: Any
    handle_expired: Any  # 由 OrganizeMixin 实现

    def download(self, query_results: list[Any] | None = None) -> tuple[list[DownloadTask], BatchDownloadStats]:
        """下载分类结果中的标准文件。"""
        results = query_results or self._query_results

        if self._expire_list:
            self.handle_expired(self._expire_list)

        tasks = []
        queried = self._queried_items if self._queried_items else self._parsed_results
        for p in self._download_list:
            for i, r in enumerate(results):
                if i < len(queried) and queried[i] is p:
                    t = DownloadTask(
                        standard_number=r.standard_number,
                        query_result=r,
                        source_site=getattr(r, "source_site", ""),
                    )
                    tasks.append(t)
                    break

        completed, stats = self.download_engine.download_batch(tasks, notification_mgr=self.notification_mgr)
        self._download_tasks = completed

        for task in completed:
            if task.status.value == "success" and task.saved_path:
                for i, p in enumerate(self._download_list):
                    if i < len(tasks) and tasks[i] is task:
                        p.source_path = task.saved_path
                        old_status = getattr(p, "effect_status", "") or ""
                        old_match = getattr(p, "match_status", "") or ""
                        if old_status in ("废止", "已废止", "作废", "被代替"):
                            new_effect = "现行"
                        elif old_status == "现行" and old_match == "newer":
                            new_effect = "待实施"
                        else:
                            new_effect = ""
                        if new_effect:
                            cached = self.cache.get(task.standard_number, getattr(task, "source_site", ""))
                            if cached:
                                cached.status = new_effect
                                self.cache.put(cached)
                        break

        logger.info(
            "下载完成: 入队 %d, 成功 %d, 跳过(已存在) %d, 失败 %d",
            len(tasks),
            stats.success,
            stats.skipped_exists,
            stats.failed,
        )
        return tasks, stats

    def download_stream(
        self, on_progress: Any = None, on_result: Any = None
    ) -> tuple[list[DownloadTask], BatchDownloadStats]:
        """流式下载（线程安全）。"""
        if self._expire_list:
            self.handle_expired(self._expire_list)
        tasks = []
        queried = self._queried_items if self._queried_items else self._parsed_results
        for p in self._download_list:
            for i, r in enumerate(self._query_results):
                if i < len(queried) and queried[i] is p:
                    t = DownloadTask(
                        standard_number=r.standard_number,
                        query_result=r,
                        source_site=getattr(r, "source_site", ""),
                    )
                    tasks.append((i, t, p))
                    break
        completed = []
        stats = BatchDownloadStats()
        total = len(tasks)
        for idx, (orig_idx, task, parsed) in enumerate(tasks):
            result = self.download_engine.download_single(task, skip_adopted=True)
            completed.append(result)
            status = (
                "已下载"
                if result.status.value == "success"
                else "下载失败"
                if result.status.value == "failed"
                else "采标受限"
                if result.status.value == "skipped"
                else result.status.value
            )
            if result.status.value == "success":
                stats.success += 1
                if result.saved_path:
                    parsed.source_path = result.saved_path
            elif result.status.value == "failed":
                stats.failed += 1
            else:
                stats.skipped_exists += 1
            if on_result:
                on_result(orig_idx, status)
            if on_progress:
                on_progress(idx + 1, total)
        self._download_tasks = completed
        return completed, stats

    def download_by_numbers(self, numbers: List[str]) -> tuple[list[DownloadTask], Any]:
        """按标准号列表下载。"""
        return self._scheduled_svc.download_by_numbers(numbers)  # type: ignore[no-any-return]

    # ── 下载等待队列 ──

    def enqueue_download_wait(self, parsed: Any) -> None:
        """写入下载等待队列。"""
        self._pending_svc.enqueue_download_wait(parsed)

    def get_due_downloads(self) -> list[dict[str, Any]]:
        """获取公开期已到的下载等待项。"""
        return self._pending_svc.get_due_downloads()  # type: ignore[no-any-return]

    def remove_download_queue(self, standard_number: str) -> None:
        """从下载等待队列中移除指定项。"""
        self._pending_svc.remove_download_queue(standard_number)
