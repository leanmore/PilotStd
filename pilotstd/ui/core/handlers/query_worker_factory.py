# 模块：pilotstd/ui/core/handlers/query_worker_factory.py
"""QueryWorkerFactory — 封装 QueryWorker 创建和信号连接。

将 on_query 中的 6 行信号连接逻辑从 Handler 迁移至工厂，
Handler 仅需定义 callbacks 并调用 create_query_worker()。
"""

from __future__ import annotations

from typing import Any

from ...workers import QueryWorker
from .protocols import QueryCallbacks


class QueryWorkerFactory:
    """创建 QueryWorker 并自动连接所有信号到回调。"""

    def __init__(self, mgr: Any, pause_event: Any, parent: Any = None) -> None:
        self._mgr = mgr
        self._pause_event = pause_event
        self._parent = parent

    def create_query_worker(self, parsed_list: list[Any], callbacks: QueryCallbacks) -> QueryWorker:
        """创建 QueryWorker，连接全部 5 个信号，返回已就绪（未启动）的 Worker。

        callbacks 结构：
          - on_result_ready(idx, result)  — 单条结果就绪
          - on_batch_ready(batch)         — 批量结果就绪
          - on_progress(current)          — 进度更新
          - on_finished(results)          — 查询完成
          - on_error(msg)                 — 异常/错误
        """
        worker = QueryWorker(
            self._mgr,
            parsed_list,
            pause_event=self._pause_event,
            parent=self._parent,
        )
        worker.result_ready.connect(callbacks.on_result_ready)
        worker.batch_ready.connect(callbacks.on_batch_ready)
        worker.progress.connect(callbacks.on_progress)
        worker.finished_signal.connect(callbacks.on_finished)
        worker.error.connect(callbacks.on_error)
        return worker
