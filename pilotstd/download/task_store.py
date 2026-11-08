"""下载任务持久化：落 task_queue，服务重启后重建待重试任务。"""

# 设计：复用通用 task_queue，不新增下载专属表；task_type=download 区分。
# 任务状态与错误留在同一行，UI/运维可直接查；重试次数放在 result_json。

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, List

from ..core.time_utils import iso_now
from .models import DownloadTask

logger = logging.getLogger(__name__)


class DownloadTaskStore:
    """把 DownloadTask 状态映射到通用 task_queue 表（task_type=download）。"""

    def __init__(self, db: Any) -> None:
        self._db = db

    def persist(self, task: DownloadTask) -> None:
        """写入/更新一行下载任务；失败只告警，不影响主下载链路。"""
        if self._db is None:
            return
        try:
            now = iso_now()
            # task_id 按站点 + 标准号稳定生成，同一任务多次更新不膨胀
            task_id = "download:" + hashlib.sha1(
                f"{getattr(task, 'source_site', '')}|{task.standard_number}".encode(),
                usedforsecurity=False,
            ).hexdigest()[:16]
            status = task.status.value
            completed = 1 if status in ("success", "skipped") else 0
            failed = 1 if status == "failed" else 0
            payload = json.dumps(
                {
                    "standard_number": task.standard_number,
                    "standard_name": getattr(getattr(task, "query_result", None), "std_name", "") or "",
                    "source_site": getattr(task, "source_site", "") or "",
                    "download_url": getattr(task, "download_url", "") or "",
                    "retry_count": int(getattr(task, "retry_count", 0)),
                    "max_retries": int(getattr(task, "max_retries", 3)),
                    "saved_path": getattr(task, "saved_path", "") or "",
                    "error_message": getattr(task, "error_message", "") or "",
                },
                ensure_ascii=False,
            )
            self._db.execute(
                "INSERT INTO task_queue (task_id, task_type, status, total_items, completed_items, "
                "failed_items, created_at, updated_at, result_json, error_log) "
                "VALUES (?, 'download', ?, 1, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(task_id) DO UPDATE SET status=excluded.status, "
                "completed_items=excluded.completed_items, failed_items=excluded.failed_items, "
                "updated_at=excluded.updated_at, result_json=excluded.result_json, "
                "error_log=excluded.error_log",
                (task_id, status, completed, failed, now, now, payload, getattr(task, "error_message", "") or ""),
            )
        except Exception as exc:
            logger.warning("下载任务持久化失败: %s (%s)", task.standard_number, exc)  # i18n-allow: 内部运维日志

    def load_retryable(self, limit: int, default_max_retries: int) -> List[DownloadTask]:
        """重建未完成任务；retry_count 已到上限的任务不再返回。"""
        if self._db is None:
            return []
        try:
            rows = self._db.fetchall(
                "SELECT task_id, status, result_json, error_log FROM task_queue "
                "WHERE task_type='download' AND status IN ('pending','running','failed','retrying') "
                "ORDER BY updated_at LIMIT ?",
                (limit,),
            )
        except Exception as exc:
            logger.warning("读取待重试下载任务失败: %s", exc)  # i18n-allow: 内部运维日志
            return []
        recovered: List[DownloadTask] = []
        for row in rows:
            try:
                data = json.loads(row.get("result_json") or "{}")
            except (TypeError, ValueError):
                continue
            retry_count = int(data.get("retry_count", 0) or 0)
            max_retries = int(data.get("max_retries", default_max_retries) or default_max_retries)
            # 达到上限保持 failed，避免重启后无限重试
            if retry_count >= max_retries:
                continue
            recovered.append(
                DownloadTask(
                    standard_number=str(data.get("standard_number", "") or ""),
                    source_site=str(data.get("source_site", "") or ""),
                    download_url=str(data.get("download_url", "") or ""),
                    retry_count=retry_count + 1,
                    max_retries=max_retries,
                    error_message=str(data.get("error_message", "") or ""),
                )
            )
        return recovered
