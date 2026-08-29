# 模块：项目//核心/处理器/_脚本
"""SettingsHandler — 设置页面 Tab 构建、配置加载/保存，替代原有 Mixin 多重继承。"""

from typing import Any, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ....core.settings_utils import sanitize_setting_value  # noqa: F401  # re-exported for backward compat
from ....i18n import _, t
from ._settings_io import SettingsConfigIO
from .settings_io_flow_engine import ICON_OPTIONS


class SettingsHandler:
    """设置页 Handler：构建所有 Tab 的 UI 控件、加载/保存配置。"""

    def __init__(
        self,
        config: Any,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._parent = parent

        # 存储构建好的页面（由___填充）
        self._pages: list[QWidget] = []
        self._page_names: list[str] = []

        # ──用户界面控件引用（由___创建，供/使用）──
        self._theme_combo: Optional[QComboBox] = None
        self._icon_combo: Optional[QComboBox] = None
        self._lang_combo: Optional[QComboBox] = None
        self._skip_welcome_cb: Optional[QCheckBox] = None
        self._col_checkboxes: dict[int, QCheckBox] = {}
        self._root_dir: Optional[QLineEdit] = None
        self._expire_name: Optional[QLineEdit] = None
        self._auto_clean_cb: Optional[QCheckBox] = None
        self._clear_readonly_cb: Optional[QCheckBox] = None
        self._mirror_skipped_cb: Optional[QCheckBox] = None
        self._mirror_fallback_cb: Optional[QCheckBox] = None
        self._watchdog_cb: Optional[QCheckBox] = None
        self._downloads_dir: Optional[QLineEdit] = None
        self._proxy: Optional[QLineEdit] = None
        self._ua_cb: Optional[QCheckBox] = None
        self._announcement_cb: Optional[QCheckBox] = None
        self._cache_cb: Optional[QCheckBox] = None
        self._announce_cache_cb: Optional[QCheckBox] = None
        self._announce_url_edit: Optional[QLineEdit] = None
        self._announce_api_key_edit: Optional[QLineEdit] = None
        self._dash_cb: Optional[QCheckBox] = None
        self._auto_pause_cb: Optional[QCheckBox] = None
        self._pause_status_label: Optional[QLabel] = None
        self._resume_btn: Optional[QPushButton] = None
        self._ocr_api_key: Optional[QLineEdit] = None
        self._ocr_secret_key: Optional[QLineEdit] = None
        self._ocr_secret_id: Optional[QLineEdit] = None
        self._ocr_tencent_secret_key: Optional[QLineEdit] = None
        self._ocr_access_key_id: Optional[QLineEdit] = None
        self._ocr_access_key_secret: Optional[QLineEdit] = None
        self._skip_folders: Optional[QLineEdit] = None
        self._scan_extensions: Optional[QLineEdit] = None
        self._skip_file_keywords: Optional[QLineEdit] = None

        # 配置输入输出委托
        self._io = SettingsConfigIO(config, self)

    # ── 页面注册 ──

    def _add_page(self, name: str, widget: QWidget) -> None:
        """注册一个设置页面到内部列表，供 build_all_pages 使用。"""
        self._page_names.append(name)
        self._pages.append(widget)

    @property
    def page_names(self) -> list[str]:
        return list(self._page_names)

    # ──公共接口──

    def build_all_pages(self, stack: QStackedWidget) -> None:
        """构建所有 8 个 Tab 页面并加入 QStackedWidget。"""
        self._build_storage_page()
        self._build_network_page()
        self._build_appearance_page()
        self._build_scan_page()
        self._build_compat_page()
        self._build_notification_page()
        self._build_ocr_page()
        self._build_columns_page()

        for page in self._pages:
            stack.addWidget(page)

    def load_all_configs(self) -> None:
        """委托 SettingsConfigIO 加载所有设置。"""
        self._io.load_all_configs()

    def save_all_configs(self) -> None:
        """委托 SettingsConfigIO 保存所有设置。"""
        self._io.save_all_configs()

    def update_pause_status(self) -> None:
        """更新通知暂停状态（由外部定时器定期调用）。"""
        if not self._pause_status_label or not self._resume_btn:
            return
        try:
            from pilotstd.core.notification_aggregator import NotificationAggregator

            state = NotificationAggregator().get_pause_state()
            if state["is_paused"]:
                self._pause_status_label.setText(f"通知已暂停，剩余 {state['remaining_seconds']} 秒后自动恢复")
                self._pause_status_label.show()
                self._resume_btn.show()
            else:
                self._pause_status_label.hide()
                self._resume_btn.hide()
        except Exception:
            self._pause_status_label.hide()
            self._resume_btn.hide()

    # ================================================================ 分隔
    # 页面构建方法
    # ================================================================ 分隔

    def _build_storage_page(self) -> None:
        """构建存储设置页：根目录、过期文件夹名、自动清理、只读清除、镜像、看门狗、下载目录。"""
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("storage_group"))
        form = QFormLayout(gb)
        self._root_dir = QLineEdit()
        self._root_dir.setPlaceholderText("默认为当前用户文档目录")
        root_layout = QHBoxLayout()
        root_layout.addWidget(self._root_dir)
        btn_browse = QPushButton(_("btn_browse"))
        btn_browse.clicked.connect(self._browse_root)
        root_layout.addWidget(btn_browse)
        form.addRow(_("storage_root"), root_layout)
        note = QLabel(_("storage_note"))
        note.setStyleSheet("color: #888; font-size: 9pt;")
        form.addRow(note)
        self._expire_name = QLineEdit()
        form.addRow(_("expire_folder"), self._expire_name)
        self._auto_clean_cb = QCheckBox(_("auto_clean_source"))
        form.addRow(self._auto_clean_cb)
        self._clear_readonly_cb = QCheckBox(_("clear_readonly"))
        form.addRow(self._clear_readonly_cb)
        self._mirror_skipped_cb = QCheckBox(_("mirror_skipped_dirs"))
        form.addRow(self._mirror_skipped_cb)
        self._mirror_fallback_cb = QCheckBox(_("mirror_fallback"))
        form.addRow(self._mirror_fallback_cb)
        self._watchdog_cb = QCheckBox(_("watchdog_enabled"))
        form.addRow(self._watchdog_cb)
        self._downloads_dir = QLineEdit()
        dl_layout = QHBoxLayout()
        dl_layout.addWidget(self._downloads_dir)
        btn_dl_browse = QPushButton(_("btn_browse"))
        btn_dl_browse.clicked.connect(self._browse_downloads_dir)
        dl_layout.addWidget(btn_dl_browse)
        form.addRow(_("download_dir_label"), dl_layout)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("storage_group"), w)

    def _build_network_page(self) -> None:
        """构建网络设置页：代理、UA 轮换、公告检查、查询缓存、Web 端公告服务地址。"""
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("network_group"))
        form = QFormLayout(gb)
        self._proxy = QLineEdit()
        self._proxy.setPlaceholderText("http://127.0.0.1:8080")
        form.addRow(_("proxy_label"), self._proxy)
        self._ua_cb = QCheckBox(_("ua_rotation"))
        form.addRow(self._ua_cb)
        self._announcement_cb = QCheckBox(_("announcement_checkbox"))
        self._announcement_cb.toggled.connect(self._on_announcement_toggled)
        form.addRow(self._announcement_cb)
        layout.addWidget(gb)
        # 查询规则
        query_gb = QGroupBox(_("query_rules"))
        query_form = QFormLayout(query_gb)
        self._cache_cb = QCheckBox(_("query_cache"))
        query_form.addRow(self._cache_cb)
        self._announce_cache_cb = QCheckBox("启用 Web 端公告缓存")
        self._announce_cache_cb.toggled.connect(self._on_announce_cache_toggled)
        query_form.addRow(self._announce_cache_cb)
        self._announce_url_edit = QLineEdit()
        self._announce_url_edit.setPlaceholderText("http://localhost:9028")
        self._announce_url_edit.textChanged.connect(self._on_announce_url_changed)
        query_form.addRow("Web 端公告服务地址", self._announce_url_edit)
        self._announce_api_key_edit = QLineEdit()
        self._announce_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._announce_api_key_edit.setPlaceholderText("API Key（用于 Web 端认证）")
        self._announce_api_key_edit.textChanged.connect(self._on_announce_api_key_changed)
        query_form.addRow("Web 端 API Key", self._announce_api_key_edit)
        layout.addWidget(query_gb)
        layout.addStretch()
        self._add_page(_("network_group"), w)

    def _build_appearance_page(self) -> None:
        """构建外观设置页：主题、图标、语言、跳过欢迎页。"""
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("ui_group"))
        form = QFormLayout(gb)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["经典白", "暗夜黑", "护眼绿", "科技蓝"])
        form.addRow(_("theme_label"), self._theme_combo)
        self._icon_combo = QComboBox()
        self._icon_combo.addItems(list(ICON_OPTIONS.keys()))
        form.addRow(_("icon_label"), self._icon_combo)
        self._lang_combo = QComboBox()
        self._lang_combo.addItems([_("lang_zh_CN"), _("lang_zh_TW"), _("lang_en")])
        form.addRow(_("lang_label"), self._lang_combo)
        self._skip_welcome_cb = QCheckBox(_("skip_welcome"))
        form.addRow(self._skip_welcome_cb)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("ui_group"), w)

    def _build_scan_page(self) -> None:
        """构建扫描设置页：跳过文件夹、文件扩展名、跳过关键词。"""
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("scan_group"))
        form = QFormLayout(gb)
        self._skip_folders = QLineEdit()
        self._skip_folders.setPlaceholderText("用逗号分隔，如: 过期作废,备份")
        form.addRow(_("skip_folders"), self._skip_folders)
        self._scan_extensions = QLineEdit()
        self._scan_extensions.setPlaceholderText("用逗号分隔，如: .pdf,.doc,.txt")
        form.addRow(_("scan_extensions"), self._scan_extensions)
        self._skip_file_keywords = QLineEdit()
        self._skip_file_keywords.setPlaceholderText("用逗号分隔，如: 征求意见稿,培训课件,标准图集")
        form.addRow(_("scan_skip_keywords"), self._skip_file_keywords)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("scan_group"), w)

    def _build_compat_page(self) -> None:
        """构建兼容性设置页：标准号横杠格式等兼容选项。"""
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("compat_group"))
        form = QFormLayout(gb)
        self._dash_cb = QCheckBox(_("dash_cb"))
        self._dash_cb.setChecked(True)
        self._dash_cb.setEnabled(False)
        form.addRow(self._dash_cb)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("compat_group"), w)

    def _build_notification_page(self) -> None:
        """构建通知设置页：通知智能聚合、自动暂停、立即恢复。"""
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox("通知智能聚合")
        form = QFormLayout(gb)
        self._auto_pause_cb = QCheckBox("启用自动暂停")
        self._auto_pause_cb.setChecked(True)
        from pilotstd.core.notification_aggregator import NotificationAggregator

        try:
            agg = NotificationAggregator()
            self._auto_pause_cb.setChecked(agg.auto_pause_enabled)
        except Exception:
            pass
        self._auto_pause_cb.toggled.connect(self._on_auto_pause_toggled)
        hint = QLabel("连续 3 次警告/错误在 30 秒内自动暂停所有弹窗，5 分钟后自动恢复")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(self._auto_pause_cb)
        form.addRow(hint)
        layout.addWidget(gb)

        self._pause_status_label = QLabel("")
        self._pause_status_label.setStyleSheet(
            "color: #856404; background: #fff3cd; padding: 6px 10px; border-radius: 4px;"
        )
        self._pause_status_label.setWordWrap(True)
        self._pause_status_label.hide()
        layout.addWidget(self._pause_status_label)

        self._resume_btn = QPushButton("立即恢复通知")
        self._resume_btn.clicked.connect(self._resume_notifications)
        self._resume_btn.hide()
        layout.addWidget(self._resume_btn)
        layout.addStretch()
        self._add_page(t("gui.settings.notification"), w)

    def _build_ocr_page(self) -> None:
        """构建 OCR 设置页：百度云/腾讯云/阿里云 OCR 凭证配置。"""
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("ocr_group"))
        form = QFormLayout(gb)
        self._ocr_api_key = QLineEdit()
        self._ocr_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._ocr_api_key.setPlaceholderText("百度云 API Key")
        form.addRow(_("ocr_baidu_api_key"), self._ocr_api_key)
        self._ocr_secret_key = QLineEdit()
        self._ocr_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._ocr_secret_key.setPlaceholderText("百度云 Secret Key")
        form.addRow(_("ocr_baidu_secret_key"), self._ocr_secret_key)
        self._ocr_secret_id = QLineEdit()
        self._ocr_secret_id.setEchoMode(QLineEdit.EchoMode.Password)
        self._ocr_secret_id.setPlaceholderText("腾讯云 Secret ID")
        form.addRow(_("ocr_tencent_secret_id"), self._ocr_secret_id)
        self._ocr_tencent_secret_key = QLineEdit()
        self._ocr_tencent_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._ocr_tencent_secret_key.setPlaceholderText("腾讯云 Secret Key")
        form.addRow(_("ocr_tencent_secret_key"), self._ocr_tencent_secret_key)
        self._ocr_access_key_id = QLineEdit()
        self._ocr_access_key_id.setEchoMode(QLineEdit.EchoMode.Password)
        self._ocr_access_key_id.setPlaceholderText("阿里云 Access Key ID")
        form.addRow(_("ocr_aliyun_access_key_id"), self._ocr_access_key_id)
        self._ocr_access_key_secret = QLineEdit()
        self._ocr_access_key_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._ocr_access_key_secret.setPlaceholderText("阿里云 Access Key Secret")
        form.addRow(_("ocr_aliyun_access_key_secret"), self._ocr_access_key_secret)
        note = QLabel(_("ocr_note"))
        note.setWordWrap(True)
        form.addRow(note)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("ocr_group"), w)

    def _build_columns_page(self) -> None:
        """构建列显示设置页：勾选显示/隐藏工作表的哪些列。"""
        from ...table_constants import TOGGLEABLE_COLS, WORK_COLUMN_KEYS

        w = QWidget()
        layout = QVBoxLayout(w)
        col_gb = QGroupBox(_("columns_group"))
        col_layout = QGridLayout()
        self._col_checkboxes = {}
        for i, c in enumerate(TOGGLEABLE_COLS):
            cb = QCheckBox(_(WORK_COLUMN_KEYS[c]))
            col_layout.addWidget(cb, i // 3, i % 3)
            self._col_checkboxes[c] = cb
        col_gb.setLayout(col_layout)
        layout.addWidget(col_gb)
        layout.addStretch()
        self._add_page(_("columns_group"), w)

    # ================================================================ 分隔
    # 辅助回调（目录浏览、网络互斥、通知暂停）
    # ================================================================ 分隔

    def _browse_root(self) -> None:
        path = QFileDialog.getExistingDirectory(None, _("dialog_select_library"))
        if path and self._root_dir:
            self._root_dir.setText(path)

    def _browse_downloads_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(None, _("dialog_select_temp_dl"))
        if path and self._downloads_dir:
            self._downloads_dir.setText(path)

    def _on_announce_cache_toggled(self, checked: bool) -> None:
        """Web 端公告缓存切换：与本地公告检查互斥。"""
        if not self._config or not self._announcement_cb or not self._announce_url_edit:
            return
        if checked:
            self._announcement_cb.blockSignals(True)
            self._announcement_cb.setChecked(False)
            self._announcement_cb.blockSignals(False)
        self._announce_url_edit.setEnabled(checked)
        self._config.set("query.use_announcement_match", checked)
        self._config.save()
        mw = self._parent.window() if self._parent else None
        if mw and hasattr(mw, "_apply_announce_cache_mode"):
            mw._apply_announce_cache_mode(checked)

    def _on_announcement_toggled(self, checked: bool) -> None:
        """本地公告检查切换：与 Web 端公告缓存互斥。"""
        if not self._config or not self._announce_cache_cb:
            return
        if checked:
            self._announce_cache_cb.blockSignals(True)
            self._announce_cache_cb.setChecked(False)
            self._announce_cache_cb.blockSignals(False)
        self._config.set("announcement.enabled", checked)
        self._config.save()

    def _on_announce_url_changed(self, text: str) -> None:
        """地址输入框变化：即时写入配置。"""
        if not self._config:
            return
        self._config.set("query.announcement_url", sanitize_setting_value(text))
        self._config.save()

    def _on_announce_api_key_changed(self, text: str) -> None:
        """API Key 输入框变化：即时写入配置。"""
        if not self._config:
            return
        self._config.set("query.announcement_api_key", sanitize_setting_value(text))
        self._config.save()

    def _on_auto_pause_toggled(self, checked: bool) -> None:
        """自动暂停开关变化。"""
        self._config.set("notification.auto_pause", checked)
        self._config.save()

    def _resume_notifications(self) -> None:
        """立即恢复通知。"""
        from pilotstd.core.notification_aggregator import NotificationAggregator

        NotificationAggregator().resume()
        self.update_pause_status()
