# pilotstd/ui/core/_core_init_query.py
# 查询初始化混入 — 从 _core.py 提取
# 包含查询 UI 适配器创建、信号连接和 QueryUIHandler 初始化

from __future__ import annotations

from ._core_adapters import (
    _DialogOpsAdapter,
    _QueryWorkerFactoryAdapter,
    _TableOpsAdapter,
    _TaskOpsAdapter,
)


class _CoreInitQueryMixin:
    """查询子系统初始化方法集合（混入 MainWindowCore）。"""

    def _init_query(self) -> None:
        """查询初始化入口：依次初始化 UI 适配器、信号连接和状态变量。"""
        self._init_query_ui()
        self._init_query_connections()
        self._init_query_state()

    def _init_query_ui(self) -> None:
        """初始化查询相关 UI 组件适配器。"""
        self._table_ops = _TableOpsAdapter(self)
        self._dialog_ops = _DialogOpsAdapter(self)

    def _init_query_connections(self) -> None:
        """连接查询相关信号：创建 TaskOpsAdapter 和 WorkerFactoryAdapter 依赖。"""
        core = self
        self._deps = type(
            "QueryDeps",
            (),
            {
                "table": self._table_ops,
                "dialog": self._dialog_ops,
                "task": _TaskOpsAdapter(core),
                "worker_factory": _QueryWorkerFactoryAdapter(core),
            },
        )()

    def _init_query_state(self) -> None:
        """初始化查询状态变量并创建 QueryUIHandler。"""
        from .handlers._query import QueryUIHandler

        self.query = QueryUIHandler(
            deps=self._deps,
            config=self._config,
            mgr=self._mgr,
            parsed_results=self._parsed_results,
            run_scan_cb=self._run_scan_cb,
            status_changed=self._status_callback,
            progress_changed=self._progress_callback,
            reset_progress=self._reset_progress,
            force_finish_progress=self._force_finish_progress,
            suppress_dialogs=self._suppress_dialogs,
            project_mark_dirty=self._project_mark_dirty,
        )
