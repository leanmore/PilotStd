# 模块：项目//_运行器脚本
"""公告抓取异步任务管理 — ThreadPoolExecutor 替代裸线程。"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any


class AnnounceTaskRunner:
    """异步公告抓取任务运行器。"""

    def __init__(self, persistence: Any, crawler: Any, notifier: Any, max_workers: int = 1):
        self._persistence = persistence
        self._crawler = crawler
        self._notifier = notifier
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def trigger(self, adapter_name: str = "") -> dict[str, Any]:
        """创建异步抓取任务并提交到线程池。"""
        task_id = uuid.uuid4().hex
        self._persistence.create_task(task_id)
        self._executor.submit(self._run, task_id, adapter_name)
        return {"task_id": task_id, "status": "pending"}

    def _run(self, task_id: str, adapter_name: str) -> None:
        """后台执行体：更新进度 → 执行抓取 → 写结果。"""
        now = datetime.now().isoformat()
        self._persistence.update_task(task_id, "running", 10)

        try:
            result = self._crawler.check_all(adapter_name)
        except Exception as exc:
            self._persistence.update_task(task_id, "failed", 50, str(exc))
            return

        errors = result.get("errors", [])
        if errors:
            self._persistence.update_task(task_id, "failed", 100, str(errors))
        else:
            self._persistence.update_task(task_id, "success", 100)

        self._notifier.after_fetch(result)
