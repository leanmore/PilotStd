# pilotstd/ui/pages/settings/_network.py
# 网络设置 Tab 构建 mixin — 代理、UA 轮换、公告抓取

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _


class _NetworkTab:
    """网络代理、UA 轮换、公告抓取设置。"""

    def _build_network_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("network_group"))
        form = QFormLayout(gb)
        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText("http://127.0.0.1:8080")
        form.addRow(_("proxy_label"), self.proxy)
        self.ua_cb = QCheckBox(_("ua_rotation"))
        form.addRow(self.ua_cb)
        self.announcement_cb = QCheckBox(_("announcement_checkbox"))
        form.addRow(self.announcement_cb)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("network_group"), w)
