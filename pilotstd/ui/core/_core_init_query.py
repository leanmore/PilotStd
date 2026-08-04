# 模块：pilotstd/ui/core/_core_init_query.py
# 查询子系统初始化 — 原 _CoreInitQueryMixin，现为工厂函数

from __future__ import annotations

from ._core_adapters import (
    _DialogOpsAdapter,
    _QueryWorkerFactoryAdapter,
    _TableOpsAdapter,
    _TaskOpsAdapter,
)


def init_query_subsystem(core) -> None:
    """查询子系统初始化：创建适配器 + 信号连接 + QueryUIHandler。

    原 _CoreInitQueryMixin 的 4 个方法合并为一个工厂函数。
    core 即 MainWindowCore 实例。
    """
    # 原 _init_query_ui
    core._table_ops = _TableOpsAdapter(core)
    core._dialog_ops = _DialogOpsAdapter(core)

    # 原 _init_query_connections
    deps = type(
        "QueryDeps",
        (),
        {
            "table": core._table_ops,
            "dialog": core._dialog_ops,
            "task": _TaskOpsAdapter(core),
            "worker_factory": _QueryWorkerFactoryAdapter(core),
        },
    )()
    core._deps = deps

    # 原 _init_query_state
    from .handlers._query import QueryUIHandler

    core.query = QueryUIHandler(
        deps=deps,
        config=core._config,
        mgr=core._mgr,
        parsed_results=core._parsed_results,
        run_scan_cb=core._run_scan_cb,
        status_changed=core._status_callback,
        progress_changed=core._progress_callback,
        reset_progress=core._reset_progress,
        force_finish_progress=core._force_finish_progress,
        suppress_dialogs=core._suppress_dialogs,
        project_mark_dirty=core._project_mark_dirty,
    )
