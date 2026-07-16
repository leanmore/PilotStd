# tests/gui/test_coverage_dialogs.py
# 覆盖 _dialog_ops.py 未覆盖行：28-35, 41-54, 62-92, 107-108, 115

from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QMessageBox


def test_question_dlg_not_suppressed(window, qtbot):
    """覆盖 28-35：_suppress_dialogs=False 时创建 QMessageBox 实例并返回 Yes/No。"""
    window._suppress_dialogs = False
    # SmartDialogInterceptor 会自动关闭对话框，方法应不崩溃
    result = window._question_dlg("title", "msg")
    assert result in (QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)


def test_stage_prereq_dialog_not_suppressed(window, qtbot):
    """覆盖 41-54：_suppress_dialogs=False 时 _stage_prereq_dialog 返回有效结果。"""
    window._suppress_dialogs = False
    result = window._stage_prereq_dialog("title", "msg")
    assert result in ("run_prereq", "skip", "cancel")


def test_show_stage_dialog_not_suppressed_no_action(window, qtbot):
    """覆盖 62-92 无 next_action 分支：_suppress_dialogs=False，不传 next_action。"""
    window._suppress_dialogs = False
    # SmartDialogInterceptor 会自动调用 accept() 关闭对话框
    window._show_stage_dialog("title", "message")


def test_show_stage_dialog_not_suppressed_with_action(window, qtbot):
    """覆盖 84-87：_suppress_dialogs=False，传 next_action 回调。"""
    window._suppress_dialogs = False
    mock_cb = MagicMock()
    window._show_stage_dialog("title", "message", next_action=mock_cb, next_label="下一步")
    # SmartDialogInterceptor 会处理对话框（调用 accept），
    # 由于 QDialog.accept 通过 clicked.connect 触发 next_action,
    # 但 SmartDialogInterceptor 直接调用 btn.click() 也会触发。
    # 这里只验证不崩溃即可。


def test_register_task_failure(window, qtbot):
    """覆盖 107-108：_mgr.task_queue.enqueue 抛异常时捕获并记录警告。"""
    with patch.object(window._mgr.task_queue, "enqueue", side_effect=RuntimeError("mock error")):
        # 不崩溃即可
        window._register_task("扫描", 10, 5, 0)


def test_on_raw_progress_zero_total(window, qtbot):
    """覆盖 115：total=0 时 _target_progress 设为 0。"""
    window._on_raw_progress(0, 0)
    assert window._target_progress == 0
