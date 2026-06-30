# pilotstd/ui/pages/settings/_compat.py
# 兼容 + 查询设置 Tab 构建 mixin — 短横、缓存、公告缓存匹配

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _


class _CompatTab:
    """兼容性选项（短横标准号）、查询缓存、公告匹配服务设置。"""

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
        # 查询设置
        query_gb = QGroupBox(_("query_rules"))
        query_form = QFormLayout(query_gb)
        self.cache_cb = QCheckBox(_("query_cache"))
        query_form.addRow(self.cache_cb)
        # 公告缓存查询模式
        self.announce_cache_cb = QCheckBox("启用 Web 端公告缓存")
        self.announce_cache_cb.toggled.connect(self._on_announce_cache_toggled)
        query_form.addRow(self.announce_cache_cb)
        self.announce_url_edit = QLineEdit()
        self.announce_url_edit.setPlaceholderText("http://localhost:9028")
        self.announce_url_edit.textChanged.connect(self._on_announce_url_changed)
        query_form.addRow("Web 端公告服务地址", self.announce_url_edit)
        self.announce_api_key_edit = QLineEdit()
        self.announce_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.announce_api_key_edit.setPlaceholderText("API Key（用于 Web 端认证）")
        self.announce_api_key_edit.textChanged.connect(self._on_announce_api_key_changed)
        query_form.addRow("Web 端 API Key", self.announce_api_key_edit)
        layout.addWidget(query_gb)
        layout.addStretch()
        self._add_page(_("compat_group"), w)

    # ── 公告缓存控件即时写入回调 ──

    def _on_announce_cache_toggled(self, checked: bool) -> None:
        """复选框切换：即时写入配置并联动地址输入框启用/禁用。"""
        if not self._config:
            return
        self.announce_url_edit.setEnabled(checked)
        self._config.set("query.use_announcement_match", checked)
        self._config.save()
        mw = self.window()
        if mw and hasattr(mw, "_apply_announce_cache_mode"):
            mw._apply_announce_cache_mode(checked)

    def _on_announce_url_changed(self, text: str) -> None:
        """地址输入框变化：即时写入配置。"""
        if not self._config:
            return
        self._config.set("query.announcement_url", text.strip())
        self._config.save()

    def _on_announce_api_key_changed(self, text: str) -> None:
        """API Key 输入框变化：即时写入配置。"""
        if not self._config:
            return
        self._config.set("query.announcement_api_key", text.strip())
        self._config.save()
