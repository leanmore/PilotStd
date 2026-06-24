# pilotstd/download/engine.py
# 下载引擎：适配器编排、后处理命名、并发控制、统计收集

from __future__ import annotations

import logging
import os
import sys
import time
from typing import List, Optional

import requests

from ..core.file_utils import (
    ensure_dir,
    make_standard_filename,
)
from ..core.frozen import is_frozen
from ..core.path_guard import validate_path_in_root
from .adapters.base import BaseDownloadAdapter
from .models import BatchDownloadStats, DownloadStatus, DownloadTask
from .session import SessionManager

logger = logging.getLogger(__name__)


class DownloadEngine:
    """文件下载引擎，负责适配器选择、文件后处理和统计。"""

    def __init__(
        self,
        adapters: List[BaseDownloadAdapter],
        session_manager: SessionManager,
        save_root: Optional[str] = None,
        min_delay: float = 1.0,
        max_delay: float = 2.0,
        batch_size: int = 10,
        long_rest: float = 15.0,
        max_workers: int = 2,
        max_retries: int = 2,
    ):
        self._adapters = adapters
        self._session_mgr = session_manager
        if is_frozen():
            self._save_root = os.path.join(os.path.dirname(sys.executable), "downloads")
        elif save_root:
            self._save_root = save_root
        else:
            self._save_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "downloads"))
        self._min_delay = min_delay  # 请求间最小间隔秒数，防反爬
        self._max_delay = max_delay  # 请求间最大间隔秒数（实际随机取区间中值）
        self._batch_size = batch_size  # 每批下载数量，批次间长休息
        self._long_rest = long_rest  # 批次间休息秒数，避免触发站点限流
        self._max_workers = max_workers  # 并发下载线程数，2 线程平衡速度与反爬
        self._max_retries = max_retries  # 网络失败最大重试次数

        ensure_dir(self._save_root)

    # ---- 公共 API ----

    def download_single(self, task: DownloadTask, skip_adopted: bool = True) -> DownloadTask:
        """下载单个任务，返回更新后的任务对象（含状态和本地路径）。"""
        if skip_adopted and task.query_result and getattr(task.query_result, "is_adopted", False):
            task.status = DownloadStatus.SKIPPED
            task.error_message = "采标标准，版权受限，自动跳过"
            logger.info(f"跳过采标: {task.standard_number}")
            return task

        # 下载前去重：目标文件已存在则跳过 HTTP 请求
        logger.debug("下载: %s | 适配器=%s", task.standard_number, task.source_site or "auto")
        existing_path = self._get_existing_file(task)
        if existing_path:
            task.status = DownloadStatus.SKIPPED
            task.saved_path = existing_path
            task.error_message = "文件已存在，跳过下载"
            logger.info(f"跳过已存在: {os.path.basename(existing_path)}")
            return task

        adapter = self._find_adapter(task)
        if adapter is None:
            task.status = DownloadStatus.FAILED
            task.error_message = "没有匹配的下载适配器"
            return task

        self._session_mgr.delay()
        task.status = DownloadStatus.RUNNING

        try:
            content = adapter.download(task)
        except (requests.Timeout, requests.ConnectionError) as e:
            if task.retry_count < self._max_retries:
                task.retry_count += 1
                task.status = DownloadStatus.RETRYING
                task.error_message = f"网络异常，将重试 ({task.retry_count}/{self._max_retries}): {e}"
                logger.warning(task.error_message)
                return task
            task.status = DownloadStatus.FAILED
            task.error_message = str(e)
            return task
        except Exception as e:
            task.status = DownloadStatus.FAILED
            task.error_message = str(e)
            return task

        if not content:  # None 或空 bytes 均视为失败
            task.status = DownloadStatus.FAILED
            logger.warning(
                "下载失败(content为空): %s | %s",
                task.standard_number,
                task.error_message or "无错误信息",
            )
            return task

        saved = self._save_file(task, content, adapter)
        if saved:
            task.status = DownloadStatus.SUCCESS
        else:
            task.status = DownloadStatus.FAILED
            task.error_message = "文件保存失败"
        return task

    def download_batch(
        self, tasks: List[DownloadTask], skip_adopted: bool = True
    ) -> tuple[List[DownloadTask], BatchDownloadStats]:
        """批量下载，支持网络失败自动重试。"""
        import concurrent.futures
        import time as _time

        _dl_t0 = _time.monotonic()
        _last_progress = _dl_t0
        _total = len(tasks)
        stats = BatchDownloadStats(total=_total)
        results: List[Optional[DownloadTask]] = [None] * len(tasks)
        # 预建任务到索引的映射，避免 retry 循环中 O(n²) 的 tasks.index() 调用
        task_index = {id(t): i for i, t in enumerate(tasks)}

        for batch_start in range(0, len(tasks), self._batch_size):
            batch_end = min(batch_start + self._batch_size, len(tasks))
            batch = tasks[batch_start:batch_end]

            # 重试循环：最多 self._max_retries 轮，每轮只提交 RETRYING/PENDING 的任务
            for retry_round in range(self._max_retries + 1):
                pending = [t for t in batch if t.status in (DownloadStatus.PENDING, DownloadStatus.RETRYING)]
                if not pending:
                    break
                if retry_round > 0:
                    wait = 2**retry_round  # 指数退避: 2s/4s/...
                    logger.info(
                        "重试第 %d 轮，%d 个任务，等待 %ds",
                        retry_round,
                        len(pending),
                        wait,
                    )
                    time.sleep(wait)

                with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                    futures = {}
                    for i, task in enumerate(pending):
                        idx = task_index[id(task)]
                        future = executor.submit(self.download_single, task, skip_adopted)
                        futures[future] = idx

                    for future in concurrent.futures.as_completed(futures):
                        idx = futures[future]
                        try:
                            results[idx] = future.result()
                        except Exception as e:
                            logger.error(f"下载线程异常: {e}")
                            task = tasks[idx]
                            task.status = DownloadStatus.FAILED
                            task.error_message = str(e)
                            results[idx] = task

            if batch_end < len(tasks):
                _elapsed = _time.monotonic() - _dl_t0
                _pct = int(batch_end / _total * 100) if _total > 0 else 0
                logger.info(
                    "下载进度: %d/%d (%d%%) 已耗时 %.0fs，休息 %ds",
                    batch_end,
                    _total,
                    _pct,
                    _elapsed,
                    self._long_rest,
                )
                time.sleep(self._long_rest)

        completed = [r for r in results if r is not None]
        for task in completed:
            if task.status == DownloadStatus.SUCCESS:
                stats.success += 1
            elif task.status == DownloadStatus.SKIPPED:
                stats.skipped_adopted += 1
            elif task.status == DownloadStatus.FAILED:
                stats.failed += 1
            else:
                stats.errors += 1

        return completed, stats

    # ---- 内部 ----

    def _resolve_target_path(self, task: DownloadTask) -> str:
        """解析任务的标准号并生成目标文件路径，校验路径范围。"""
        from ..query.search_strategy import _parse_result_number

        query = task.query_result
        std_name = getattr(query, "standard_name", "") if query else ""
        parsed = _parse_result_number(task.standard_number)
        if parsed:
            logical_code = f"{parsed['code']}"
        else:
            logical_code = task.standard_number.split()[0] if " " in task.standard_number else task.standard_number
        number = parsed.get("number", 0) if parsed else 0
        year = parsed.get("year", 0) if parsed else 0
        part = parsed.get("part", None) if parsed else None

        filename = make_standard_filename(logical_code, number or 0, year or 0, std_name, part, ext=".pdf")
        # 仅保留文件名，剥离可能混入的路径分隔符
        filename = os.path.basename(filename)
        final_path = os.path.join(self._save_root, filename)
        validate_path_in_root(final_path, self._save_root)  # 路径遍历防护
        return final_path

    def _get_existing_file(self, task: DownloadTask) -> Optional[str]:
        """计算目标文件路径，如果已存在则返回路径，否则返回 None。"""
        target_path = self._resolve_target_path(task)
        return target_path if os.path.exists(target_path) else None

    # 查询站点名 → 下载适配器名 映射（查询和下载的 site_name 命名体系不同）
    _QUERY_TO_DOWNLOAD_SITE = {
        "std_gov": "openstd_download",
    }

    def _find_adapter(self, task: DownloadTask) -> Optional[BaseDownloadAdapter]:
        """根据 task.source_site 查找匹配的下载适配器。
        优先精确匹配，再通过映射表（std_gov→openstd_download），
        最后回退到 can_handle 兜底。"""
        if task.source_site:
            # 精确匹配
            for a in self._adapters:
                if a.site_name == task.source_site:
                    return a
            # 通过映射表查找
            mapped = self._QUERY_TO_DOWNLOAD_SITE.get(task.source_site)
            if mapped:
                for a in self._adapters:
                    if a.site_name == mapped:
                        return a
        # 回退到 can_handle
        for a in self._adapters:
            if a.can_handle(task):
                return a
        return None

    def _save_file(self, task: DownloadTask, content: bytes, adapter: BaseDownloadAdapter) -> bool:
        """保存下载内容到规范命名的文件。"""
        try:
            final_path = self._resolve_target_path(task)
            try:
                validate_path_in_root(final_path, self._save_root)
            except ValueError:
                logger.error("路径校验失败: %s", final_path)
                task.error_message = "路径校验失败"
                return False

            with open(final_path, "wb") as f:
                f.write(content)

            # 校验下载内容类型与扩展名一致
            ext = os.path.splitext(final_path)[1].lower()
            if ext == ".pdf" and not content[:5] == b"%PDF-":
                logger.warning("文件类型异常，非PDF: %s", final_path)
            elif ext in (".doc", ".docx") and len(content) < 512:
                logger.warning("文件过小，可能非有效文档: %s (%d bytes)", final_path, len(content))

            task.saved_path = final_path
            logger.info(f"保存成功: {final_path}")
            return True
        except OSError as e:
            logger.error(f"保存失败: {task.standard_number} - {e}")
            task.error_message = str(e)
            return False
