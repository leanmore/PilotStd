# 模块：项目//页面//_脚本
# 包裹的对话框

from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ....i18n import _
from ._core import SettingsPage


class SettingsDialog(QDialog):
    """设置对话框，包裹 SettingsPage + 确定/取消按钮。"""

    def __init__(self, config_manager: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("settings_title"))
        self.resize(600, 420)

        layout = QVBoxLayout(self)
        self.page = SettingsPage(config_manager)
        layout.addWidget(self.page)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton(_("btn_ok"))
        btn_ok.clicked.connect(self._on_accept)
        btn_layout.addWidget(btn_ok)
        btn_cancel = QPushButton(_("btn_cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def closeEvent(self, event) -> None:
        """模型下载线程运行中时不允许关闭对话框（QThread 运行中被销毁会崩溃）。"""
        if self.page.has_running_workers():
            QMessageBox.information(self, _("settings_title"), _("settings_download_in_progress"))
            event.ignore()
            return
        self.page.stop_workers()
        super().closeEvent(event)

    def _on_accept(self) -> None:
        self.page.save_to_config()
        QMessageBox.information(self, _("settings_title"), _("settings_saved"))
        self.accept()
