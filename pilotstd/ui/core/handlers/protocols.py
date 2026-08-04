# 模块：项目//核心/处理器/脚本
"""Query Handler 依赖接口协议。

将 QueryUIHandler 的 30+ 构造参数收敛为 4 个子接口 + 1 个聚合接口，
便于单元测试 mock 和依赖关系显式化。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol


@dataclass
class QueryCallbacks:
    """查询 Worker 回调集合 — 由 Handler 定义，工厂负责连接。"""

    on_result_ready: Callable[[int, Any], None]
    on_batch_ready: Callable[[list], None]
    on_progress: Callable[[int], None]
    on_finished: Callable[[list], None]
    on_error: Callable[[str], None]


class ITableOps(Protocol):
    """表格操作接口：行增删、查找、导出。"""

    def add_table_row(self, data: Dict[str, Any]) -> int: ...
    def find_row_by_seq(self, seq: int) -> int: ...
    def clear_table(self) -> None: ...
    def get_table_as_list(self) -> List[Dict[str, Any]]: ...
    def remove_selected_rows(self) -> None: ...
    def get_selected_path(self) -> str: ...
    def get_selected_seq(self) -> Optional[str]: ...
    def get_work_table(self) -> Any: ...  # QTableWidget


class IDialogOps(Protocol):
    """对话框操作接口：确认、前置检查、阶段展示。"""

    def question_dlg(self, title: str, msg: str) -> bool: ...
    def stage_prereq_dialog(self, title: str, msg: str, task_name: str) -> Optional[str]: ...
    def show_stage_dialog(self, title: str, content: str, next_action: Optional[Callable[[], None]] = None) -> None: ...
    def info_dlg(self, title: str, msg: str) -> None: ...
    def warning_dlg(self, title: str, msg: str) -> None: ...


class ITaskOps(Protocol):
    """任务管理接口：注册、进度更新、完成标记。"""

    def register_task(self, name: str, total: int = 100) -> str: ...
    def update_task_status(self, task_id: str, progress: int, msg: str = "") -> None: ...
    def task_completed(self, task_id: str) -> None: ...
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]: ...


class IQueryWorkerFactory(Protocol):
    """Worker 工厂接口：创建查询 Worker 和待确认对话框。"""

    def create_query_worker(self, parsed_list: List[Any], callbacks: QueryCallbacks) -> Any: ...
    def create_pending_query_dialog(self, data: List[Dict[str, Any]], parent: Any) -> Any: ...


class IQueryDependencies(Protocol):
    """Query Handler 的聚合依赖接口。"""

    table: ITableOps
    dialog: IDialogOps
    task: ITaskOps
    worker_factory: IQueryWorkerFactory
