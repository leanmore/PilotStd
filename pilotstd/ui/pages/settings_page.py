# pilotstd/ui/pages/settings_page.py
# 设置页：左侧导航 + 右侧堆叠内容

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...i18n import _

ICON_OPTIONS = {
    "默认": "default",
    "指南针": "compass_book",
    "放大镜": "magnifier_check",
    "灯塔": "lighthouse_folder",
}


class SettingsPage(QWidget):
    """设置表单，左侧导航列表 + 右侧 QStackedWidget。"""

    def __init__(self, config_manager: Any = None) -> None:
        super().__init__()
        self._config = config_manager

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 左侧导航 ──
        self._nav = QListWidget()
        self._nav.setFixedWidth(120)
        self._nav.setSpacing(0)
        self._nav.setStyleSheet("QListWidget { border: none; border-right: 1px solid #ddd; }")

        # ── 右侧堆叠 ──
        self._stack = QStackedWidget()

        self._build_storage_page()
        self._build_network_page()
        self._build_ui_page()
        self._build_scan_page()
        self._build_compat_page()
        self._build_ocr_page()
        self._build_columns_page()

        main_layout.addWidget(self._nav)
        main_layout.addWidget(self._stack, 1)

        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)

        if self._config:
            self._load_from_config()

    # ── 辅助：添加页面到导航和堆叠 ──

    def _add_page(self, name: str, widget: QWidget) -> None:
        item = QListWidgetItem(name)
        self._nav.addItem(item)
        self._stack.addWidget(widget)

    # ═══════════════════════════════════════
    # 各分组页面
    # ═══════════════════════════════════════

    def _build_storage_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("storage_group"))
        form = QFormLayout(gb)
        self.root_dir = QLineEdit()
        self.root_dir.setPlaceholderText("默认为当前用户文档目录")
        root_layout = QHBoxLayout()
        root_layout.addWidget(self.root_dir)
        btn_browse = QPushButton(_("btn_browse"))
        btn_browse.clicked.connect(self._browse_root)
        root_layout.addWidget(btn_browse)
        form.addRow(_("storage_root"), root_layout)
        note = QLabel(_("storage_note"))
        note.setStyleSheet("color: #888; font-size: 9pt;")
        form.addRow(note)
        self.expire_name = QLineEdit()
        form.addRow(_("expire_folder"), self.expire_name)
        self.auto_clean_cb = QCheckBox(_("auto_clean_source"))
        form.addRow(self.auto_clean_cb)
        self.clear_readonly_cb = QCheckBox(_("clear_readonly"))
        form.addRow(self.clear_readonly_cb)
        self.mirror_skipped_cb = QCheckBox(_("mirror_skipped_dirs"))
        form.addRow(self.mirror_skipped_cb)
        self.mirror_fallback_cb = QCheckBox(_("mirror_fallback"))
        form.addRow(self.mirror_fallback_cb)
        self.watchdog_cb = QCheckBox(_("watchdog_enabled"))
        form.addRow(self.watchdog_cb)
        self.downloads_dir = QLineEdit()
        dl_layout = QHBoxLayout()
        dl_layout.addWidget(self.downloads_dir)
        btn_dl_browse = QPushButton(_("btn_browse"))
        btn_dl_browse.clicked.connect(self._browse_downloads_dir)
        dl_layout.addWidget(btn_dl_browse)
        form.addRow(_("download_dir_label"), dl_layout)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("storage_group"), w)

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

    def _build_ocr_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        gb = QGroupBox(_("ocr_group"))
        form = QFormLayout(gb)
        self.ocr_api_key = QLineEdit()
        self.ocr_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_api_key.setPlaceholderText("百度云 API Key")
        form.addRow(_("ocr_baidu_api_key"), self.ocr_api_key)
        self.ocr_secret_key = QLineEdit()
        self.ocr_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_secret_key.setPlaceholderText("百度云 Secret Key")
        form.addRow(_("ocr_baidu_secret_key"), self.ocr_secret_key)
        self.ocr_secret_id = QLineEdit()
        self.ocr_secret_id.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_secret_id.setPlaceholderText("腾讯云 Secret ID")
        form.addRow(_("ocr_tencent_secret_id"), self.ocr_secret_id)
        self.ocr_tencent_secret_key = QLineEdit()
        self.ocr_tencent_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_tencent_secret_key.setPlaceholderText("腾讯云 Secret Key")
        form.addRow(_("ocr_tencent_secret_key"), self.ocr_tencent_secret_key)
        self.ocr_access_key_id = QLineEdit()
        self.ocr_access_key_id.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_access_key_id.setPlaceholderText("阿里云 Access Key ID")
        form.addRow(_("ocr_aliyun_access_key_id"), self.ocr_access_key_id)
        self.ocr_access_key_secret = QLineEdit()
        self.ocr_access_key_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_access_key_secret.setPlaceholderText("阿里云 Access Key Secret")
        form.addRow(_("ocr_aliyun_access_key_secret"), self.ocr_access_key_secret)
        note = QLabel(_("ocr_note"))
        note.setWordWrap(True)
        form.addRow(note)
        layout.addWidget(gb)
        layout.addStretch()
        self._add_page(_("ocr_group"), w)

    def _build_columns_page(self) -> None:
        from PyQt6.QtWidgets import QGridLayout

        from ..table_mixin import TOGGLEABLE_COLS, WORK_COLUMN_KEYS

        w = QWidget()
        layout = QVBoxLayout(w)
        col_gb = QGroupBox(_("columns_group"))
        col_layout = QGridLayout()
        self._col_checkboxes: dict[int, Any] = {}
        for i, c in enumerate(TOGGLEABLE_COLS):
            cb = QCheckBox(_(WORK_COLUMN_KEYS[c]))
            col_layout.addWidget(cb, i // 3, i % 3)
            self._col_checkboxes[c] = cb
        col_gb.setLayout(col_layout)
        layout.addWidget(col_gb)
        layout.addStretch()
        self._add_page(_("columns_group"), w)

    # ═══════════════════════════════════════
    # 配置加载 / 保存
    # ═══════════════════════════════════════

    def _load_from_config(self) -> None:
        from PyQt6.QtCore import QStandardPaths

        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self.root_dir.setText(self._config.get("storage.root_dir", default_root))
        self.expire_name.setText(self._config.get("storage.expire_folder", "过期作废"))
        self.auto_clean_cb.setChecked(self._config.get("organize.auto_clean_source", False))
        self.mirror_skipped_cb.setChecked(self._config.get("storage.mirror_skipped_dirs", True))
        self.mirror_fallback_cb.setChecked(self._config.get("storage.mirror_fallback", True))
        self.watchdog_cb.setChecked(self._config.get("watchdog.enabled", False))
        self.proxy.setText(self._config.get("network.proxy", ""))
        self.ua_cb.setChecked(self._config.get("network.ua_rotation", True))
        self.announcement_cb.setChecked(self._config.get("announcement.enabled", False))
        self.ocr_api_key.setPlaceholderText("已保存" if self._config.get("ocr.baidu_api_key", "") else "百度云 API Key")
        self.ocr_secret_key.setPlaceholderText(
            "已保存" if self._config.get("ocr.baidu_secret_key", "") else "百度云 Secret Key"
        )
        self.ocr_secret_id.setPlaceholderText(
            "已保存" if self._config.get("ocr.tencent_secret_id", "") else "腾讯云 Secret ID"
        )
        self.ocr_tencent_secret_key.setPlaceholderText(
            "已保存" if self._config.get("ocr.tencent_secret_key", "") else "腾讯云 Secret Key"
        )
        self.ocr_access_key_id.setPlaceholderText(
            "已保存" if self._config.get("ocr.aliyun_access_key_id", "") else "阿里云 Access Key ID"
        )
        self.ocr_access_key_secret.setPlaceholderText(
            "已保存" if self._config.get("ocr.aliyun_access_key_secret", "") else "阿里云 Access Key Secret"
        )
        self.dash_cb.setChecked(True)  # 已锁定，始终使用短横
        self.clear_readonly_cb.setChecked(self._config.get("file.clear_readonly", True))
        self.downloads_dir.setText(self._config.get("storage.downloads_dir", ""))
        self.skip_welcome_cb.setChecked(self._config.get("appearance.skip_welcome", False))
        self.cache_cb.setChecked(self._config.get("query.use_cache", True))
        self.announce_cache_cb.setChecked(self._config.get("query.use_announcement_cache", False))
        self.announce_url_edit.setText(self._config.get("query.announcement_url", "http://localhost:9028"))
        self.announce_url_edit.setEnabled(self._config.get("query.use_announcement_cache", False))
        self.announce_api_key_edit.setText(self._config.get("query.announcement_api_key", ""))
        self.skip_folders.setText(", ".join(self._config.get("scan.skip_folders", ["过期作废"])))
        self.scan_extensions.setText(", ".join(self._config.get("scan.extensions", [".pdf", ".doc", ".docx", ".txt"])))
        self.skip_file_keywords.setText(
            ", ".join(
                self._config.get(
                    "scan.exclude_patterns",
                    [
                        "征求意见稿",
                        "培训课件",
                        "建设项目过程资料及交工资料标准",
                        "吊车性能",
                        "标准图集",
                    ],
                )
            )
        )
        theme = self._config.get("appearance.theme", "经典白")
        self.theme_combo.setCurrentText(theme)
        icon_theme = self._config.get("appearance.icon_theme", "default")
        icon_display = {v: k for k, v in ICON_OPTIONS.items()}.get(icon_theme, "默认")
        self.icon_combo.setCurrentText(icon_display)
        lang_map = {
            "zh_CN": _("lang_zh_CN"),
            "zh_TW": _("lang_zh_TW"),
            "en": _("lang_en"),
        }
        lang = self._config.get("appearance.language", "zh_CN")
        self.lang_combo.setCurrentText(lang_map.get(lang, _("lang_zh_CN")))
        # 列可见性
        default_vis = [True] * 9
        visible = self._config.get("appearance.column_visibility", default_vis) or default_vis
        for c, cb in self._col_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(visible[c] if c < len(visible) else True)
            cb.blockSignals(False)

    def save_to_config(self) -> None:
        if not self._config:
            return
        from PyQt6.QtCore import QStandardPaths

        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self._config.set("storage.root_dir", self.root_dir.text().strip() or default_root)
        self._config.set("storage.expire_folder", self.expire_name.text().strip() or "过期作废")
        self._config.set("organize.auto_clean_source", self.auto_clean_cb.isChecked())
        self._config.set("storage.mirror_skipped_dirs", self.mirror_skipped_cb.isChecked())
        self._config.set("storage.mirror_fallback", self.mirror_fallback_cb.isChecked())
        self._config.set("watchdog.enabled", self.watchdog_cb.isChecked())
        self._config.set("network.proxy", self.proxy.text().strip())
        self._config.set("network.ua_rotation", self.ua_cb.isChecked())
        self._config.set("announcement.enabled", self.announcement_cb.isChecked())
        self._config.set("ocr.baidu_api_key", self.ocr_api_key.text().strip())
        self._config.set("ocr.baidu_secret_key", self.ocr_secret_key.text().strip())
        self._config.set("ocr.tencent_secret_id", self.ocr_secret_id.text().strip())
        self._config.set("ocr.tencent_secret_key", self.ocr_tencent_secret_key.text().strip())
        self._config.set("ocr.aliyun_access_key_id", self.ocr_access_key_id.text().strip())
        self._config.set("ocr.aliyun_access_key_secret", self.ocr_access_key_secret.text().strip())
        # 保存后清空敏感字段，防止被复制
        self.ocr_api_key.clear()
        self.ocr_secret_key.clear()
        self.ocr_secret_id.clear()
        self.ocr_tencent_secret_key.clear()
        self.ocr_access_key_id.clear()
        self.ocr_access_key_secret.clear()
        self.ocr_api_key.setPlaceholderText("已保存")
        self.ocr_secret_key.setPlaceholderText("已保存")
        self.ocr_secret_id.setPlaceholderText("已保存")
        self.ocr_tencent_secret_key.setPlaceholderText("已保存")
        self.ocr_access_key_id.setPlaceholderText("已保存")
        self.ocr_access_key_secret.setPlaceholderText("已保存")
        self._config.set("appearance.hyphen_style", True)  # 已锁定，始终使用短横
        self._config.set("file.clear_readonly", self.clear_readonly_cb.isChecked())
        self._config.set("storage.downloads_dir", self.downloads_dir.text().strip())
        self._config.set("appearance.skip_welcome", self.skip_welcome_cb.isChecked())
        self._config.set("query.use_cache", self.cache_cb.isChecked())
        self._config.set("query.use_announcement_cache", self.announce_cache_cb.isChecked())
        self._config.set("query.announcement_url", self.announce_url_edit.text().strip())
        self._config.set("query.announcement_api_key", self.announce_api_key_edit.text().strip())
        self._config.set("appearance.theme", self.theme_combo.currentText())
        icon_key = ICON_OPTIONS.get(self.icon_combo.currentText(), "default")
        self._config.set("appearance.icon_theme", icon_key)
        # 通过索引取值，避免界面文本翻译导致匹配失败
        lang_codes = ["zh_CN", "zh_TW", "en"]
        self._config.set("appearance.language", lang_codes[self.lang_combo.currentIndex()])
        # 扫描配置
        skip = [s.strip() for s in self.skip_folders.text().split(",") if s.strip()]
        self._config.set("scan.skip_folders", skip or ["过期作废"])
        exts = [s.strip() for s in self.scan_extensions.text().split(",") if s.strip()]
        self._config.set("scan.extensions", exts or [".pdf", ".doc", ".docx", ".txt"])
        # 排除关键词
        keywords = [s.strip() for s in self.skip_file_keywords.text().split(",") if s.strip()]
        self._config.set(
            "scan.exclude_patterns",
            keywords
            or [
                "征求意见稿",
                "培训课件",
                "建设项目过程资料及交工资料标准",
                "吊车性能",
                "标准图集",
            ],
        )
        # 列可见性
        visible = []
        for c in range(9):
            if c in self._col_checkboxes:
                visible.append(self._col_checkboxes[c].isChecked())
            else:
                visible.append(True)
        self._config.set("appearance.column_visibility", visible)
        # 即时应用到主窗口
        mw = self.window()
        if mw and hasattr(mw, "_apply_column_visibility"):
            mw._apply_column_visibility(visible)
        if mw and hasattr(mw, "_apply_icon"):
            mw._apply_icon()
        if mw and hasattr(mw, "_apply_announce_cache_mode"):
            mw._apply_announce_cache_mode(self.announce_cache_cb.isChecked())
        self._config.save()

    def _browse_root(self) -> None:
        path = QFileDialog.getExistingDirectory(None, _("dialog_select_library"))
        if path:
            self.root_dir.setText(path)

    def _browse_downloads_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(None, _("dialog_select_temp_dl"))
        if path:
            self.downloads_dir.setText(path)

    # ── 公告缓存控件即时写入回调 ──

    def _on_announce_cache_toggled(self, checked: bool) -> None:
        """复选框切换：即时写入配置并联动地址输入框启用/禁用。"""
        if not self._config:
            return
        self.announce_url_edit.setEnabled(checked)
        self._config.set("query.use_announcement_cache", checked)
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


class SettingsDialog(QDialog):
    """设置对话框，包裹 SettingsPage + 确定/取消按钮。"""

    def __init__(self, config_manager: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("settings_title"))
        self.resize(600, 420)

        layout = QVBoxLayout(self)
        self.page = SettingsPage(config_manager)
        layout.addWidget(self.page)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton(_("btn_ok"))
        btn_ok.clicked.connect(self._on_accept)
        btn_layout.addWidget(btn_ok)
        btn_cancel = QPushButton(_("btn_cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_accept(self) -> None:
        self.page.save_to_config()
        QMessageBox.information(None, _("settings_title"), _("settings_saved"))
        self.accept()
