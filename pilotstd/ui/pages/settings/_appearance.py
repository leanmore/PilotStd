# pilotstd/ui/pages/settings/_appearance.py
# 外观设置 Tab 构建 mixin — 主题、图标、语言、欢迎页

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _

# 图标主题选项映射（显示名 → 内部键）
ICON_OPTIONS = {
    "默认": "default",
    "指南针": "compass_book",
    "放大镜": "magnifier_check",
    "灯塔": "lighthouse_folder",
}


class _AppearanceTab:
    """主题、图标、语言、跳过欢迎页设置。"""

    def _build_ui_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("ui_group"))
        form = QFormLayout(gb)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["经典白", "暗夜黑", "护眼绿", "科技蓝"])
        form.addRow(_("theme_label"), self.theme_combo)
        self.icon_combo = QComboBox()
        self.icon_combo.addItems(list(ICON_OPTIONS.keys()))
        form.addRow(_("icon_label"), self.icon_combo)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([_("lang_zh_CN"), _("lang_zh_TW"), _("lang_en")])
        form.addRow(_("lang_label"), self.lang_combo)
        self.skip_welcome_cb = QCheckBox(_("skip_welcome"))
        form.addRow(self.skip_welcome_cb)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("ui_group"), w)
