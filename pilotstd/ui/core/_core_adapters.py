# 模块：项目//核心/_核心_适配器脚本
# 用户界面协议适配器—从_核心脚本提取
# 每个适配器将回调解耦为协议接口，供用户界面等消费。
# 分隔
# 适配器期望的宿主接口契约（通过核心参数注入）：
# _.___()→向工作区表格添加行
# _.____()→按序号查找行号
# _.__()→清空表格
# _.____()→获取选中路径
# _.__→引用
# _.__(,)→弹出确认对话框
# _.___(...)→弹出前置条件对话框
# _.___(...)→弹出阶段结果对话框
# _._→父级
# _.__(*,**)→注册新任务
# _._→实例
# _.__→线程.暂停控制

from __future__ import annotations

from typing import Any


class _TableOpsAdapter:
    """表格操作适配器：将 MainWindowCore 的回调包装进 ITableOps 协议接口。"""

    def __init__(self, core: Any) -> None:
        self._c = core

    def add_table_row(self, data: dict) -> int:
        """将 dict 转换为 RowUpdate 后委托给核心回调，返回行号（当前固定为0）。"""
        from ...workers import RowUpdate

        update = RowUpdate(
            seq=data.get("seq", 0),
            parsed=data.get("parsed"),
            work_status=data.get("work_status", ""),
            total=data.get("total", 0),
        )
        self._c._add_table_row(update)
        return 0

    def find_row_by_seq(self, seq: int) -> int:
        return self._c._find_row_by_seq(seq)

    def clear_table(self) -> None:
        self._c._clear_table()

    def get_table_as_list(self) -> list:
        return []

    def remove_selected_rows(self) -> None:
        pass

    def get_selected_path(self) -> str:
        return self._c._get_selected_path_cb() if self._c._get_selected_path_cb else ""

    def get_selected_seq(self) -> str | None:
        return None

    def get_work_table(self) -> Any:
        return self._c._work_table


class _DialogOpsAdapter:
    """对话框操作适配器：将 MainWindowCore 的回调包装进 IDialogOps 协议接口。"""

    def __init__(self, core: Any) -> None:
        self._c = core

    def question_dlg(self, title: str, msg: str) -> bool:
        """弹出是/否确认对话框，返回用户选择（True=是）。"""
        from PyQt6.QtWidgets import QMessageBox

        result = self._c._question_dlg(title, msg)
        return result == QMessageBox.StandardButton.Yes

    def stage_prereq_dialog(self, title: str, msg: str, task_name: str) -> str | None:
        return self._c._stage_prereq_dialog(title, msg, task_name)

    def show_stage_dialog(self, title: str, content: str, next_action: Any = None) -> None:
        self._c._show_stage_dialog(title, content, next_action)

    def info_dlg(self, title: str, msg: str) -> None:
        """弹出信息提示对话框。"""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.information(self._c._parent, title, msg)

    def warning_dlg(self, title: str, msg: str) -> None:
        """弹出警告提示对话框。"""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(self._c._parent, title, msg)


class _TaskOpsAdapter:
    """任务操作适配器：将 register_task 等操作包装进 ITaskOps 协议。"""

    def __init__(self, core: Any) -> None:
        self._c = core

    def register_task(self, *args: Any, **kwargs: Any) -> str:
        """注册新任务，委托给核心回调，返回空字符串（UI 层不追踪返回值）。"""
        self._c._register_task(*args, **kwargs)
        return ""

    def update_task_status(self, task_id: str, progress: int, msg: str = "") -> None:
        pass

    def task_completed(self, task_id: str) -> None:
        pass

    def get_task_status(self, task_id: str) -> dict | None:
        return None


class _QueryWorkerFactoryAdapter:
    """Worker 工厂适配器：包装 QueryWorkerFactory 和 PendingQueryDialog 创建逻辑。"""

    def __init__(self, core: Any) -> None:
        from .handlers.query_worker_factory import QueryWorkerFactory

        self._c = core
        self._factory = QueryWorkerFactory(core._mgr, core._pause_event, core._parent)

    def create_query_worker(self, parsed_list: list, callbacks: Any) -> Any:
        return self._factory.create_query_worker(parsed_list, callbacks)

    def create_pending_query_dialog(self, data: list, parent: Any) -> Any:
        """创建待确认查询对话框实例。"""
        from ...ui.pending_query_dialog import PendingQueryDialog

        return PendingQueryDialog(self._c._mgr, data, parent)
