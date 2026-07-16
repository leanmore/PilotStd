# tests/test_regression_architecture.py
"""架构重构回归测试 — 针对本轮修复的 10 个 BUG 的防回归用例。

覆盖:
- P0-1: _suppress_dialogs 取消后重置
- P0-2: NormalizeWorker.error 信号连接
- P1-1: 待确认查询后按钮状态刷新
- P1-2: 汇总弹窗保存CSV不修改共享列表
- P2-1: QueryWorker.result_ready 信号连接
- A: handlers 目录所有模块可导入
- D: StandardManager.task_queue 可访问
- B/C: 图标路径 / _hash_file 函数存在性
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSuppressDialogsReset(unittest.TestCase):
    """P0-1: 取消一键处理后 _suppress_dialogs 应重置为 False"""

    def test_on_cancel_resets_suppress_dialogs(self):
        """模拟取消操作后 _suppress_dialogs 为 False"""
        from pilotstd.ui.main_window.parts._actions_ops import _on_cancel

        # 创建一个模拟的 MainWindow 实例
        mock_self = MagicMock()
        mock_self._suppress_dialogs = True
        mock_self._paused = True
        mock_self._mgr_ready = True
        mock_self.btn_pause = MagicMock()
        mock_self.btn_query = MagicMock()
        mock_self.btn_download = MagicMock()
        mock_self.btn_cancel = MagicMock()
        mock_self.progress_bar = MagicMock()
        mock_self.style.return_value = MagicMock()
        mock_self._pause_event = MagicMock()
        mock_self.status_changed = MagicMock()

        _on_cancel(mock_self)

        self.assertFalse(mock_self._suppress_dialogs, "_on_cancel 应将 _suppress_dialogs 重置为 False")


class TestNormalizeWorkerErrorSignal(unittest.TestCase):
    """P0-2: NormalizeWorker 的 error 信号应被连接"""

    def test_normalize_worker_error_signal_connected(self):
        """验证 ArchiveUIHandler.on_normalize 中 error 信号已连接"""
        import inspect

        from pilotstd.ui.core.handlers._archive import ArchiveUIHandler

        source = inspect.getsource(ArchiveUIHandler.on_normalize)
        # P9: ArchiveCallbacks 对象传递回调，不再直接 .connect
        self.assertIn("callbacks = ArchiveCallbacks(", source)
        self.assertIn("on_error=lambda msg", source)


class TestPendingQueryButtonState(unittest.TestCase):
    """P1-1: 待确认查询完成后应刷新按钮状态"""

    def test_do_pending_query_calls_update_button_states(self):
        """验证 _do_pending_query 方法体包含 _update_button_states 调用"""
        import inspect

        from pilotstd.ui.main_window.parts._query_ops import _do_pending_query

        source = inspect.getsource(_do_pending_query)
        self.assertIn("_update_button_states", source, "_do_pending_query 应在返回前调用 _update_button_states()")


class TestSummaryDialogNoSharedListMutation(unittest.TestCase):
    """P1-2: 汇总弹窗保存 CSV 不应修改共享 _parsed_results"""

    def test_on_save_section_csv_no_slice_assign(self):
        """验证 on_save_section_csv 不再使用 [:] = 修改共享列表"""
        import inspect

        from pilotstd.ui.core.handlers._query_summary import QuerySummaryHandler

        source = inspect.getsource(QuerySummaryHandler.on_save_section_csv)
        self.assertNotIn("_parsed_results[:]", source, "on_save_section_csv 不应使用 [:] = 修改共享列表")


class TestQueryWorkerResultReadySignal(unittest.TestCase):
    """P2-1: QueryWorker.result_ready 应在 Handler 流程中被连接"""

    def test_result_ready_connected_in_on_query(self):
        """验证 QueryUIHandler.on_query 中 result_ready 信号已连接"""
        import inspect

        from pilotstd.ui.core.handlers._query import QueryUIHandler

        source = inspect.getsource(QueryUIHandler.on_query)
        # P9: QueryCallbacks 对象传递回调，不再直接 .connect
        self.assertIn("callbacks = QueryCallbacks(", source)
        self.assertIn("on_result_ready=self.on_query_result_ready", source)


class TestHandlerImports(unittest.TestCase):
    """A: handlers 目录下所有模块均可正常导入"""

    HANDLER_MODULES = [
        "pilotstd.ui.core.handlers._actions",
        "pilotstd.ui.core.handlers._announce",
        "pilotstd.ui.core.handlers._archive",
        "pilotstd.ui.core.handlers._auto",
        "pilotstd.ui.core.handlers._cleanup",
        "pilotstd.ui.core.handlers._dialog",
        "pilotstd.ui.core.handlers._download",
        "pilotstd.ui.core.handlers._export",
        "pilotstd.ui.core.handlers._file_dialog",
        "pilotstd.ui.core.handlers._file_tree",
        "pilotstd.ui.core.handlers._persistence",
        "pilotstd.ui.core.handlers._project",
        "pilotstd.ui.core.handlers._query",
        "pilotstd.ui.core.handlers._query_summary",
        "pilotstd.ui.core.handlers._scan",
        "pilotstd.ui.core.handlers._settings",
        "pilotstd.ui.core.handlers._settings_io",
        "pilotstd.ui.core.handlers._table",
        "pilotstd.ui.core.handlers._table_helper",
        "pilotstd.ui.core.handlers._theme",
        "pilotstd.ui.core.handlers._ui_setup",
    ]

    def test_all_handler_modules_importable(self):
        """逐模块导入，任一失败即报错"""
        failed = []
        for mod_name in self.HANDLER_MODULES:
            try:
                __import__(mod_name)
            except ImportError as e:
                failed.append(f"{mod_name}: {e}")
        self.assertEqual(len(failed), 0, "以下模块导入失败:\n" + "\n".join(failed))


class TestTaskQueueProxy(unittest.TestCase):
    """D: StandardManager.task_queue 应可通过属性访问"""

    def test_task_queue_accessible_on_standard_manager(self):
        """验证 task_queue 可以作为属性访问（不抛 AttributeError）"""
        from pilotstd.manager.facade._base import BaseFacade

        # 通过 inspect 确认 task_queue property 存在
        self.assertTrue(
            hasattr(BaseFacade, "task_queue") and isinstance(getattr(BaseFacade, "task_queue"), property),
            "BaseFacade 应有 task_queue 的 @property 代理",
        )


class TestIconPath(unittest.TestCase):
    """B/C: 图标路径计算和 hash_file_content 函数存在性"""

    def test_hash_file_content_exists(self):
        """验证 hash_file_content 函数存在于 file_utils"""
        from pilotstd.core.file_utils import hash_file_content

        self.assertTrue(callable(hash_file_content))

    def test_icon_path_calculation(self):
        """验证图标路径计算逻辑：从 parts/ 向上 4 层到达项目根"""
        import inspect

        from pilotstd.ui.main_window.parts._theme_ops import _apply_icon

        source = inspect.getsource(_apply_icon)
        # 源码模式下应为 4 层 ".."
        self.assertIn('"..", "..", "..", "..", "desktop"', source, "图标路径应向上 4 层到达项目根 desktop/")


if __name__ == "__main__":
    unittest.main()
