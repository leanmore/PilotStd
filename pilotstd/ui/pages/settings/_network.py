# pilotstd/ui/pages/settings/_network.py
# 网络设置 Tab 构建 mixin — 代理、UA 轮换、公告抓取、查询缓存

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
    """网络代理、UA 轮换、公告抓取、查询缓存设置。"""

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
        self.announcement_cb.toggled.connect(self._on_announcement_toggled)
        form.addRow(self.announcement_cb)
        layout.addWidget(gb)
        # 查询规则
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
        self._add_page(_("network_group"), w)

    # ── 公告缓存 + 本地公告互斥（勾选一方则另一方不可选）──

    def _on_announce_cache_toggled(self, checked: bool) -> None:
        """Web 端公告缓存切换：与本地公告检查互斥。"""
        if not self._config:
            return
        self.announce_url_edit.setEnabled(checked)
        self._config.set("query.use_announcement_match", checked)
        self._config.save()
        self.announcement_cb.setEnabled(not checked)
        mw = self.window()
        if mw and hasattr(mw, "_apply_announce_cache_mode"):
            mw._apply_announce_cache_mode(checked)

    def _on_announcement_toggled(self, checked: bool) -> None:
        """本地公告检查切换：与 Web 端公告缓存互斥。"""
        if not self._config:
            return
        self.announce_cache_cb.setEnabled(not checked)

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
