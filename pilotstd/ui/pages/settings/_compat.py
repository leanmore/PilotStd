# pilotstd/ui/pages/settings/_compat.py
# 兼容设置 Tab 构建 mixin — 短横标准号

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _


class _CompatTab:
    """兼容性选项（短横标准号）。"""

    def _build_compat_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("compat_group"))
        form = QFormLayout(gb)
        self.dash_cb = QCheckBox(_("dash_cb"))
        self.dash_cb.setChecked(True)
        self.dash_cb.setEnabled(False)  # 已统一为短横，不可更改
        form.addRow(self.dash_cb)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("compat_group"), w)
