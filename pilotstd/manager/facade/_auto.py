# pilotstd/manager/facade/_auto.py
"""AutoPipeline：一键自动运行管线（扫描→查询→下载→归档→收容），替代原 AutoMixin。"""

from __future__ import annotations

import logging
import time as _time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._core import ManagerCore
    from ._download import DownloadHandler
    from ._organize import OrganizeHandler
    from ._query import QueryHandler
    from ._scan import ScanHandler

logger = logging.getLogger(__name__)


class AutoPipeline:
    """自动管线 — 编排扫描→查询→下载→归档流程，替代原 AutoMixin。"""

    def __init__(
        self,
        core: "ManagerCore",
        scan_handler: "ScanHandler",
        query_handler: "QueryHandler",
        download_handler: "DownloadHandler",
        organize_handler: "OrganizeHandler",
    ):
        self._core = core
        self._scan = scan_handler
        self._query = query_handler
        self._download = download_handler
        self._organize = organize_handler

    def auto_run(self, root_path: str, _adapter: Any = None) -> dict[str, int]:
        """一键自动运行：扫描 → 查询 → 下载 → 归类。
        _adapter: DI 注入，可传入 mock 适配器链覆盖默认适配器。
        """
        report: dict[str, int] = {
            "scan": 0,
            "query_found": 0,
            "download_success": 0,
            "organize_moved": 0,
        }
        t_stage = _time.monotonic()

        parsed = self._scan.scan_directory(root_path)
        report["scan"] = len(parsed)
        logger.info("阶段耗时 scan: %.1fs (%d 条)", _time.monotonic() - t_stage, len(parsed))
        t_stage = _time.monotonic()

        _, q_stats = self._query.query(parsed)
        report["query_found"] = q_stats.found
        logger.info("阶段耗时 query: %.1fs (%d 条)", _time.monotonic() - t_stage, q_stats.found)
        t_stage = _time.monotonic()

        dl_tasks, dl_stats = self._download.download()
        report["download_success"] = dl_stats.success
        logger.info("阶段耗时 download: %.1fs (%d 成功)", _time.monotonic() - t_stage, report["download_success"])
        t_stage = _time.monotonic()

        org_result = self._organize.archive_standards(parsed)
        report["organize_moved"] = org_result["moved"]
        report["mirror_skipped"] = 0
        report["fallback_mirrored"] = 0
        logger.info("阶段耗时 archive: %.1fs (%d 已移动)", _time.monotonic() - t_stage, report["organize_moved"])
        t_stage = _time.monotonic()

        if self._core.cfg.get("storage.mirror_skipped_dirs", True):
            skipped = getattr(self._core, "last_skipped_dirs", [])
            if skipped:
                mirror_result = self._organize.organize_skipped_dirs(skipped, source_root=root_path)
                report["mirror_skipped"] = mirror_result.get("moved", 0)

        if self._core.cfg.get("storage.mirror_fallback", True):
            fallback_result = self._organize.organize_fallback(root_path)
            report["fallback_mirrored"] = fallback_result.get("moved", 0)

        logger.info(
            "阶段耗时 收容: %.1fs (镜像跳过%d 兜底%d)",
            _time.monotonic() - t_stage,
            report["mirror_skipped"],
            report["fallback_mirrored"],
        )
        logger.info("自动运行完成: %s", report)
        return report

    def _auto_stage_query(
        self,
        parsed: list[Any],
        on_query_progress: Any,
        on_query_result: Any,
        report: dict[str, int],
        t_stage: float,
    ) -> tuple[dict[str, int], float]:
        """查询阶段：包装进度回调 → 调用 query → 更新 report。"""
        _progress_cb = None
        if on_query_progress:

            def _wrapped(cur: int, total: int) -> None:
                scaled = 90 + int(cur / total * 9) if total > 0 else 90
                on_query_progress(scaled, 100)

            _progress_cb = _wrapped

        _, q_stats = self._query.query(parsed, progress_callback=_progress_cb, result_callback=on_query_result)
        if on_query_progress:
            on_query_progress(100, 100)

        report["query_found"] = q_stats.found
        logger.info("阶段耗时 query: %.1fs (%d 条)", _time.monotonic() - t_stage, q_stats.found)
        return report, _time.monotonic()

    def _auto_stage_archive_and_fallback(
        self,
        parsed: list[Any],
        root_path: str,
        on_archive_result: Any,
        on_stage_change: Any,
        report: dict[str, int],
        t_stage: float,
    ) -> dict[str, int]:
        """归档 + 镜像跳过目录 + 兜底残留文件 + done 信号。"""
        if on_stage_change:
            on_stage_change("archive", 0, len(parsed))

        to_archive = [p for p in parsed if getattr(p, "next_action", "") != "pending"]
        org_result = self._organize.archive_standards(to_archive, on_result=on_archive_result)
        report["organize_moved"] = org_result.get("moved", 0)
        logger.info("阶段耗时 archive: %.1fs (%d 已移动)", _time.monotonic() - t_stage, report["organize_moved"])
        report["mirror_skipped"] = 0
        report["fallback_mirrored"] = 0
        t_stage = _time.monotonic()

        if self._core.cfg.get("storage.mirror_skipped_dirs", True):
            skipped = getattr(self._core, "last_skipped_dirs", [])
            if skipped:
                if on_stage_change:
                    on_stage_change("mirror_skipped", 0, len(skipped))
                mirror_result = self._organize.organize_skipped_dirs(skipped, source_root=root_path)
                report["mirror_skipped"] = mirror_result.get("moved", 0)

        if self._core.cfg.get("storage.mirror_fallback", True):
            if on_stage_change:
                on_stage_change("fallback", 0, 0)
            fallback_result = self._organize.organize_fallback(root_path)
            report["fallback_mirrored"] = fallback_result.get("moved", 0)

        if on_stage_change:
            on_stage_change("done", 0, 0)

        logger.info(
            "阶段耗时 收容: %.1fs (镜像跳过%d 兜底%d)",
            _time.monotonic() - t_stage,
            report["mirror_skipped"],
            report["fallback_mirrored"],
        )
        logger.info("自动运行完成: %s", report)
        return report

    def auto_run_stream(
        self,
        root_path: str,
        on_scan_batch: Any = None,
        on_scan_progress: Any = None,
        on_query_progress: Any = None,
        on_query_result: Any = None,
        on_download_progress: Any = None,
        on_download_result: Any = None,
        on_archive_result: Any = None,
        on_stage_change: Any = None,
        _adapter: Any = None,
    ) -> dict[str, int]:
        """流式自动管线（线程安全）。
        _adapter: DI 注入，可传入 mock 适配器链覆盖默认适配器。
        """
        report: dict[str, int] = {
            "scan": 0,
            "query_found": 0,
            "download_success": 0,
            "organize_moved": 0,
        }
        t_stage = _time.monotonic()

        if on_stage_change:
            on_stage_change("scan", 0, 0)

        parsed = self._scan.scan_directory_stream(root_path, on_progress=on_scan_progress, on_batch=on_scan_batch)
        report["scan"] = len(parsed)
        logger.info("阶段耗时 scan: %.1fs (%d 条)", _time.monotonic() - t_stage, len(parsed))
        t_stage = _time.monotonic()

        if not parsed:
            if on_stage_change:
                on_stage_change("done", 0, 0)
            return report

        if on_stage_change:
            on_stage_change("query", 0, len(parsed))

        report, t_stage = self._auto_stage_query(parsed, on_query_progress, on_query_result, report, t_stage)

        dl_list = self._core.download_list
        if dl_list:
            if on_stage_change:
                on_stage_change("download", 0, len(dl_list))
            _, dl_stats = self._download.download_stream(on_progress=on_download_progress, on_result=on_download_result)
            report["download_success"] = dl_stats.success

        logger.info("阶段耗时 download: %.1fs (%d 成功)", _time.monotonic() - t_stage, report["download_success"])
        t_stage = _time.monotonic()

        return self._auto_stage_archive_and_fallback(
            parsed, root_path, on_archive_result, on_stage_change, report, t_stage
        )
