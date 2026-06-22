# pilotstd/ui/dialogs.py
# 通用小对话框 — 从 main_window.py 提取

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import _


class ConfigPageDialog(QDialog):
    """通用配置页面对话框，包裹任意 QWidget。"""

    def __init__(self, page: Any, title: str, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(650, 480)
        layout = QVBoxLayout(self)
        layout.addWidget(page)
        btn_close = QPushButton(_("btn_close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class ExportFileListDialog(QDialog):
    """导出文件名清单选项对话框：选择源路径、是否包含路径。"""

    def __init__(self, parent: Any, source_path: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("导出文件列表")
        self.source_path = source_path
        self.include_path = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"源文件夹: {source_path}"))

        self.include_cb = QCheckBox(_("cb_include_path"))
        layout.addWidget(self.include_cb)

        btn_layout = QHBoxLayout()
        btn_change = QPushButton("更改文件夹")
        btn_change.clicked.connect(self._change_folder)
        btn_layout.addWidget(btn_change)
        btn_layout.addStretch()

        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self._on_accept)
        btn_layout.addWidget(btn_ok)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _change_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(None,"选择文件夹")
        if path:
            self.source_path = path
            self.layout().itemAt(0).widget().setText(f"源文件夹: {path}")

    def _on_accept(self) -> None:
        self.include_path = self.include_cb.isChecked()
        self.accept()
