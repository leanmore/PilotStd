# 模块：项目//脚本
# 通用小对话框—从入口_脚本提取

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from pilotstd.ui.widgets.base_button import BaseButton
from pilotstd.ui.widgets.base_dialog import BaseDialog

from ..i18n import _


class ConfigPageDialog(BaseDialog):
    """通用配置页面对话框，包裹任意 QWidget。"""

    def __init__(self, page: Any, title: str, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(650, 480)
        layout = QVBoxLayout(self)
        layout.addWidget(page)
        btn_close = BaseButton(_("btn_close"), kind="ghost")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class ExportFileListDialog(BaseDialog):
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
        btn_change = BaseButton("更改文件夹", kind="secondary")
        btn_change.clicked.connect(self._change_folder)
        btn_layout.addWidget(btn_change)
        btn_layout.addStretch()

        btn_ok = BaseButton("确定", kind="primary")
        btn_ok.clicked.connect(self._on_accept)
        btn_layout.addWidget(btn_ok)
        btn_cancel = BaseButton("取消", kind="ghost")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _change_folder(self) -> None:
        """选择源文件夹并刷新界面提示。"""
        path = QFileDialog.getExistingDirectory(None, "选择文件夹")
        if path:
            self.source_path = path
            layout = self.layout()
            item = layout.itemAt(0) if layout is not None else None
            widget = item.widget() if item is not None else None
            if isinstance(widget, QLabel):
                widget.setText(f"源文件夹: {path}")

    def _on_accept(self) -> None:
        self.include_path = self.include_cb.isChecked()
        self.accept()
