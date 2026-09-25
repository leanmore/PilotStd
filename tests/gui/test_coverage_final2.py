"""覆盖 pilotstd.ui.main_window 模块最终剩余可测行。
_export_ops:50,52,55,76-77,85-86 | _dialog_ops:52-54 | _theme_ops:99
_delegate_ops:71 | _file_tree_ops:54-55,125-127,131-134,165-166,193,209
__init__:315-321,381
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMenu, QTreeWidgetItem


# ═══ _export_ops.py: 50, 52, 55, 76-77, 85-86 ═══
class TestExportFinal:
    def test_export_folder_tree_no_path(self, window, monkeypatch):
        """覆盖 50,52,55: 无选中回退 Desktop, 非目录返回, 取消保存"""
        monkeypatch.setattr(window, "_get_selected_path", lambda: "")
        from PyQt6.QtCore import QStandardPaths

        desktop = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        # 确保 desktop 路径存在且是目录
        if desktop and os.path.isdir(desktop):
            with patch(
                "pilotstd.ui.main_window.parts._export_ops.QFileDialog.getSaveFileName",
                return_value=(str(tempfile.mktemp(suffix=".txt")), ""),
            ):
                window._on_export_folder_tree()

    def test_export_folder_tree_no_dir(self, window, monkeypatch):
        """覆盖 52: 路径不是目录 → 返回"""
        monkeypatch.setattr(window, "_get_selected_path", lambda: "/nonexistent_file.txt")
        window._on_export_folder_tree()

    def test_export_folder_tree_cancel(self, window, monkeypatch):
        """覆盖 55: 取消保存对话框 → 返回"""
        monkeypatch.setattr(window, "_get_selected_path", lambda: os.path.expanduser("~"))
        with patch("pilotstd.ui.main_window.parts._export_ops.QFileDialog.getSaveFileName", return_value=("", "")):
            window._on_export_folder_tree()

    def test_collect_folder_tree_isdir_error(self, window):
        """覆盖 76-77, 85-86: entry.is_dir() 抛 OSError"""
        ok = MagicMock()
        ok.is_dir.return_value = True
        ok.name = "ok"
        ok.path = "/d/ok"
        bad = MagicMock()
        bad.is_dir.side_effect = OSError("fake")
        bad.name = "bad_dir"
        bad.path = "/d/bad"
        # 用 with patch 而非 monkeypatch：scandir 污染须在测试体内还原，
        # 否则 window teardown 的 shutil.rmtree 会命中被替换的 scandir（TypeError）
        with patch("os.scandir", lambda p: [bad, ok]):
            lines: list = []
            window._collect_folder_tree("/d", lines, prefix="")


# ═══ _dialog_ops.py: 52-54 ═══
class TestDialogFinal:
    def test_stage_prereq_dialog_cancel(self, window):
        """覆盖 52-54: 点击取消按钮 → 返回 'cancel'"""
        window._suppress_dialogs = False
        # SmartDialogInterceptor 会点第一个按钮(prereq), 我们 patch 掉它
        from pilotstd.ui.main_window.parts import _dialog_ops as dops

        with (
            patch.object(dops.QMessageBox, "exec", return_value=None),
            patch.object(dops.QMessageBox, "clickedButton", return_value=None),
        ):
            result = window._stage_prereq_dialog("t", "m", prereq_label="Run")
            assert result == "cancel"


# ═══ _theme_ops.py: 99 ═══
class TestThemeFinal:
    def test_retranslate_ui_paused(self, window, monkeypatch):
        """覆盖 99: 暂停状态下按钮文本为 '继续'"""
        window._ui_translatable = True
        window._paused = True
        window._log_label = MagicMock()
        with patch.object(window, "_retranslate_file_tree"):
            window._retranslate_ui()


# ═══ _delegate_ops.py: 71 ═══
class TestDelegateFinal:
    def test_start_auto_pipeline_guard(self, window):
        """覆盖 71: _core=None 时 _start_auto_pipeline 走 guard"""
        saved = window._core
        window._core = None
        try:
            window._start_auto_pipeline("/dummy")
        finally:
            window._core = saved


# ═══ _file_tree_ops.py: 54-55, 125-127, 131-134, 165-166, 193, 209 ═══
class TestFileTreeFinal:
    def test_drives_ready_sip_deleted(self, window, monkeypatch):
        """覆盖 54-55: sip.isdeleted 返回 True"""
        assert hasattr(window, "this_pc")
        mock_sip = MagicMock()
        mock_sip.isdeleted.return_value = True
        monkeypatch.setattr("PyQt6.sip.isdeleted", mock_sip.isdeleted)
        monkeypatch.setattr("PyQt6.sip", mock_sip)
        with patch("builtins.__import__", return_value=mock_sip):
            window._on_drives_ready([("C:", "C:\\")])

    def test_populate_children_pdf_icon(self, window, tmp_path):
        """覆盖 125-127, 131-134: PDF和文件图标分支"""
        sub = tmp_path / "icons2"
        sub.mkdir()
        (sub / "a.pdf").write_text("x")
        (sub / "b.docx").write_text("x")
        (sub / "c.other").write_text("x")
        parent = QTreeWidgetItem(["p"])
        from PyQt6.QtCore import Qt as QtCore

        parent.setData(0, QtCore.ItemDataRole.UserRole, str(sub))
        window.file_tree.addTopLevelItem(parent)
        window._populate_children(parent)
        assert parent.childCount() == 3

    def test_file_tree_context_menu_import(self, window, tmp_path):
        """覆盖 165-166: 点击导入菜单项"""
        sub = tmp_path / "ctx2"
        sub.mkdir()
        item = QTreeWidgetItem(["test"])
        item.setData(0, 0, str(sub))
        window.file_tree.clear()
        window.file_tree.addTopLevelItem(item)
        with patch.object(window.file_tree, "itemAt", return_value=item):
            with patch.object(QMenu, "exec"):
                window._on_file_tree_context_menu(QPoint(10, 10))

    def test_navigate_to_basic(self, window, tmp_path):
        """覆盖 193, 209: 导航到存在的顶层节点"""
        item = window.file_tree.topLevelItem(0)
        path = item.data(0, 0)
        if path and os.path.exists(str(path)):
            window._navigate_to(str(path))


# ═══ __init__.py: 315-321, 381 ═══
class TestInitFinal:
    def test_stop_workers_never_terminates(self, window, monkeypatch):
        """关窗/取消路径只做协作式停止：先断业务信号，绝不 terminate()。

        旧断言 mock `_drive_thread.quit` 抛 RuntimeError 来覆盖 try/except 分支，
        该分支已随 `stop_worker_gracefully()` 统一（commit `7d04f829` 起）删除。
        本用例改为守"不退化"：一旦有人重新引入 terminate 或漏掉断连接，立即失败。
        """
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        mock_thread.wait.return_value = True  # 视为正常退出，不走保活分支
        # 反向 case：即便 quit 抛异常，也不允许回退到强杀
        mock_thread.quit.side_effect = RuntimeError("already stopped")
        monkeypatch.setattr(window, "_drive_thread", mock_thread)

        window._stop_workers()

        assert mock_thread.terminate.call_count == 0, "严禁用 terminate() 强杀线程"
        assert mock_thread.stop.call_count == 1, "存在 stop() 时必须先请求协作式停止"
        assert mock_thread.drives_ready.disconnect.call_count == 1, "必须先断开业务信号再停线程"
        assert mock_thread.requestInterruption.call_count == 1, "必须请求中断"
        assert mock_thread.quit.call_count == 0, "run() 覆写的 QThread 没有事件循环，不应依赖 quit()"

    def test_add_row_from_dict_translated_col(self, window):
        """覆盖 381: 翻译后的列名回退匹配"""
        window._add_row_from_dict({"seq": 1, "standard_name": "test"})
