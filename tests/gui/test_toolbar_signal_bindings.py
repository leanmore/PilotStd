"""验证工具栏按钮的 clicked 信号已正确连接"""

from PyQt6.QtWidgets import QPushButton


def _assert_bound(btn: QPushButton) -> None:
    """验证按钮的 clicked 信号已连接至少一个接收者。"""
    assert btn.receivers(btn.clicked) > 0, f"{btn.text()} clicked 信号未连接"


class TestToolbarSignalBindings:
    """通过 receivers() 检查每个工具栏按钮的信号连接状态。"""

    def test_btn_select_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_select)

    def test_btn_query_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_query)

    def test_btn_download_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_download)

    def test_btn_normalize_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_normalize)

    def test_btn_save_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_save)

    def test_btn_auto_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_auto)

    def test_btn_announce_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_announce)

    def test_btn_pause_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_pause)

    def test_btn_cancel_is_bound(self, mock_main_window):
        _assert_bound(mock_main_window.btn_cancel)

    def test_notification_bell_inner_button_is_bound(self, mock_main_window):
        """notification_bell 是自定义 QWidget，内部含一个 QPushButton。"""
        bell = mock_main_window.notification_bell
        inner_btn = bell.findChild(QPushButton)
        assert inner_btn is not None, "notification_bell 内部未找到 QPushButton"
        _assert_bound(inner_btn)
