# pilotstd/ui/welcome_dialog.py
# 首次启动欢迎对话框

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import _

WELCOME_TEXT = """
<h2>欢迎使用 PilotStd</h2>

<p><b>PilotStd</b> 是一款标准文件管理工具，帮助你：</p>

<ul>
<li>自动识别文件名中的标准号（GB、GB/T、SH/T 等 76 类行业标准）</li>
<li>批量查询标准有效性（现行 / 废止 / 即将实施）</li>
<li>下载、归类、整理标准文件</li>
<li>监控标准更新并发出提醒</li>
</ul>

<p><b>快速上手：</b></p>
<ol>
<li>在左侧文件导航区定位你的标准文件夹</li>
<li>右键点击文件夹选择「导入工作区」开始文件扫描</li>
<li>扫描结果将显示在工作区表格中</li>
<li>使用工具栏按钮执行查询、下载等后续操作</li>
</ol>
"""


class WelcomeDialog(QDialog):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        super().__init__(parent)
        self.setWindowTitle(_("welcome_title"))
        self.resize(520, 420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.label = QLabel(WELCOME_TEXT)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.label)

        self.skip_cb = QCheckBox(_("welcome_skip"))
        layout.addWidget(self.skip_cb)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton(_("btn_start"))
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def should_skip(self) -> bool:
        return self.skip_cb.isChecked()
