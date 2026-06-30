# pilotstd/ui/pages/settings/_scan.py
# 扫描设置 Tab 构建 mixin — 跳过文件夹、扩展名、排除关键词

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _


class _ScanTab:
    """扫描过滤规则设置：跳过文件夹、扩展名过滤、文件名关键词排除。"""

    def _build_scan_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("scan_group"))
        form = QFormLayout(gb)
        self.skip_folders = QLineEdit()
        self.skip_folders.setPlaceholderText("用逗号分隔，如: 过期作废,备份")
        form.addRow(_("skip_folders"), self.skip_folders)
        self.scan_extensions = QLineEdit()
        self.scan_extensions.setPlaceholderText("用逗号分隔，如: .pdf,.doc,.txt")
        form.addRow(_("scan_extensions"), self.scan_extensions)
        self.skip_file_keywords = QLineEdit()
        self.skip_file_keywords.setPlaceholderText("用逗号分隔，如: 征求意见稿,培训课件,标准图集")
        form.addRow(_("scan_skip_keywords"), self.skip_file_keywords)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("scan_group"), w)
