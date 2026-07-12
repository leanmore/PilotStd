# pilotstd/ui/core/handlers/_settings_io.py
"""SettingsConfigIO — 配置加载/保存，从 SettingsHandler 拆分以控制文件大小。"""

from typing import Any

from PyQt6.QtCore import QStandardPaths

from ....i18n import _

# 图标主题选项映射（显示名 → 内部键）
ICON_OPTIONS = {
    "默认": "default",
    "指南针": "compass_book",
    "放大镜": "magnifier_check",
    "灯塔": "lighthouse_folder",
}

# 语言代码列表，按 ComboBox 索引对应
LANG_CODES = ["zh_CN", "zh_TW", "en"]


class SettingsConfigIO:
    """设置配置 IO：从 SettingsHandler 实例读取/写入控件值。"""

    def __init__(self, config: Any, handler: Any) -> None:
        self._config = config
        self._h = handler  # SettingsHandler 实例

    # ── 公共 API ──

    def load_all_configs(self) -> None:
        """从 ConfigManager 加载所有设置到 UI 控件。"""
        self._load_storage_config()
        self._load_network_ocr_config()
        self._load_query_ui_config()
        self._load_scan_config()
        self._load_appearance_config()

    def save_all_configs(self) -> None:
        """将所有 UI 控件值保存到 ConfigManager。"""
        self._save_storage_appearance()
        self._save_ocr_credentials()
        self._save_scan_columns()
        self._config.save()

        # 触发窗口级副作用
        mw = self._h._parent.window() if self._h._parent else None
        if mw:
            if hasattr(mw, "_apply_icon"):
                mw._apply_icon()
            if hasattr(mw, "_apply_announce_cache_mode"):
                mw._apply_announce_cache_mode(
                    self._h._announce_cache_cb.isChecked() if self._h._announce_cache_cb else False
                )

    # ================================================================
    # 配置加载
    # ================================================================

    def _load_storage_config(self) -> None:
        """加载存储相关设置：根目录、过期文件夹、自动清理等。"""
        if not all(
            [
                self._h._root_dir,
                self._h._expire_name,
                self._h._auto_clean_cb,
                self._h._mirror_skipped_cb,
                self._h._mirror_fallback_cb,
                self._h._watchdog_cb,
                self._h._clear_readonly_cb,
                self._h._downloads_dir,
            ]
        ):
            return

        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self._h._root_dir.setText(self._config.get("storage.root_dir", default_root))
        self._h._expire_name.setText(self._config.get("storage.expire_folder", "过期作废"))
        self._h._auto_clean_cb.setChecked(self._config.get("organize.auto_clean_source", False))
        self._h._mirror_skipped_cb.setChecked(self._config.get("storage.mirror_skipped_dirs", True))
        self._h._mirror_fallback_cb.setChecked(self._config.get("storage.mirror_fallback", True))
        self._h._watchdog_cb.setChecked(self._config.get("watchdog.enabled", False))
        self._h._clear_readonly_cb.setChecked(self._config.get("file.clear_readonly", True))
        self._h._downloads_dir.setText(self._config.get("storage.downloads_dir", ""))

    def _load_network_ocr_config(self) -> None:
        """加载网络代理、公告开关、OCR 密钥设置。"""
        if not all(
            [
                self._h._proxy,
                self._h._ua_cb,
                self._h._announcement_cb,
                self._h._ocr_api_key,
                self._h._ocr_secret_key,
                self._h._ocr_secret_id,
                self._h._ocr_tencent_secret_key,
                self._h._ocr_access_key_id,
                self._h._ocr_access_key_secret,
            ]
        ):
            return

        self._h._proxy.setText(self._config.get("network.proxy", ""))
        self._h._ua_cb.setChecked(self._config.get("network.ua_rotation", True))
        self._h._announcement_cb.blockSignals(True)
        self._h._announcement_cb.setChecked(self._config.get("announcement.enabled", False))
        self._h._announcement_cb.blockSignals(False)

        for attr, key, hint in [
            ("_ocr_api_key", "ocr.baidu_api_key", "百度云 API Key"),
            ("_ocr_secret_key", "ocr.baidu_secret_key", "百度云 Secret Key"),
            ("_ocr_secret_id", "ocr.tencent_secret_id", "腾讯云 Secret ID"),
            ("_ocr_tencent_secret_key", "ocr.tencent_secret_key", "腾讯云 Secret Key"),
            ("_ocr_access_key_id", "ocr.aliyun_access_key_id", "阿里云 Access Key ID"),
            ("_ocr_access_key_secret", "ocr.aliyun_access_key_secret", "阿里云 Access Key Secret"),
        ]:
            widget = getattr(self._h, attr)
            widget.setPlaceholderText("已保存" if self._config.get(key, "") else hint)

    def _load_query_ui_config(self) -> None:
        """加载查询与界面杂项设置。"""
        if not all(
            [
                self._h._dash_cb,
                self._h._skip_welcome_cb,
                self._h._cache_cb,
                self._h._announce_cache_cb,
                self._h._announce_url_edit,
                self._h._announce_api_key_edit,
                self._h._announcement_cb,
            ]
        ):
            return

        self._h._dash_cb.setChecked(True)
        self._h._skip_welcome_cb.setChecked(self._config.get("appearance.skip_welcome", False))
        self._h._cache_cb.setChecked(self._config.get("query.use_cache", True))
        self._h._announce_cache_cb.blockSignals(True)
        self._h._announce_cache_cb.setChecked(self._config.get("query.use_announcement_match", False))
        self._h._announce_cache_cb.blockSignals(False)
        self._h._announce_url_edit.setText(self._config.get("query.announcement_url", "http://localhost:9028"))
        self._h._announce_api_key_edit.setText(self._config.get("query.announcement_api_key", ""))
        # 脏数据仲裁
        if self._h._announcement_cb.isChecked() and self._h._announce_cache_cb.isChecked():
            self._h._announce_cache_cb.blockSignals(True)
            self._h._announce_cache_cb.setChecked(False)
            self._h._announce_cache_cb.blockSignals(False)
            self._h._announce_url_edit.setEnabled(False)
            self._config.set("query.use_announcement_match", False)
            self._config.save()

    def _load_scan_config(self) -> None:
        """加载扫描相关设置。"""
        if not all([self._h._skip_folders, self._h._scan_extensions, self._h._skip_file_keywords]):
            return

        self._h._skip_folders.setText(", ".join(self._config.get("scan.skip_folders", ["过期作废"])))
        self._h._scan_extensions.setText(
            ", ".join(self._config.get("scan.extensions", [".pdf", ".doc", ".docx", ".txt"]))
        )
        self._h._skip_file_keywords.setText(
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

    def _load_appearance_config(self) -> None:
        """加载外观设置：主题、图标、语言、列可见性。"""
        if not all([self._h._theme_combo, self._h._icon_combo, self._h._lang_combo]):
            return

        theme = self._config.get("appearance.theme", "经典白")
        self._h._theme_combo.setCurrentText(theme)
        icon_theme = self._config.get("appearance.icon_theme", "default")
        icon_display = {v: k for k, v in ICON_OPTIONS.items()}.get(icon_theme, "默认")
        self._h._icon_combo.setCurrentText(icon_display)
        lang_map = {
            "zh_CN": _("lang_zh_CN"),
            "zh_TW": _("lang_zh_TW"),
            "en": _("lang_en"),
        }
        lang = self._config.get("appearance.language", "zh_CN")
        self._h._lang_combo.setCurrentText(lang_map.get(lang, _("lang_zh_CN")))

        default_vis = [True] * 9
        visible = self._config.get("appearance.column_visibility", default_vis) or default_vis
        for c, cb in self._h._col_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(visible[c] if c < len(visible) else True)
            cb.blockSignals(False)

    # ================================================================
    # 配置保存
    # ================================================================

    def _save_storage_appearance(self) -> None:
        """保存存储路径、网络代理、外观、缓存等通用设置。"""
        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if self._h._root_dir:
            self._config.set("storage.root_dir", self._h._root_dir.text().strip() or default_root)
        if self._h._expire_name:
            self._config.set("storage.expire_folder", self._h._expire_name.text().strip() or "过期作废")
        if self._h._auto_clean_cb:
            self._config.set("organize.auto_clean_source", self._h._auto_clean_cb.isChecked())
        if self._h._mirror_skipped_cb:
            self._config.set("storage.mirror_skipped_dirs", self._h._mirror_skipped_cb.isChecked())
        if self._h._mirror_fallback_cb:
            self._config.set("storage.mirror_fallback", self._h._mirror_fallback_cb.isChecked())
        if self._h._watchdog_cb:
            self._config.set("watchdog.enabled", self._h._watchdog_cb.isChecked())
        if self._h._proxy:
            self._config.set("network.proxy", self._h._proxy.text().strip())
        if self._h._ua_cb:
            self._config.set("network.ua_rotation", self._h._ua_cb.isChecked())
        if self._h._announcement_cb:
            self._config.set("announcement.enabled", self._h._announcement_cb.isChecked())
        self._config.set("appearance.hyphen_style", True)
        if self._h._clear_readonly_cb:
            self._config.set("file.clear_readonly", self._h._clear_readonly_cb.isChecked())
        if self._h._downloads_dir:
            self._config.set("storage.downloads_dir", self._h._downloads_dir.text().strip())
        if self._h._skip_welcome_cb:
            self._config.set("appearance.skip_welcome", self._h._skip_welcome_cb.isChecked())
        if self._h._cache_cb:
            self._config.set("query.use_cache", self._h._cache_cb.isChecked())
        if self._h._announce_cache_cb:
            self._config.set("query.use_announcement_match", self._h._announce_cache_cb.isChecked())
        if self._h._announce_url_edit:
            self._config.set("query.announcement_url", self._h._announce_url_edit.text().strip())
        if self._h._announce_api_key_edit:
            self._config.set("query.announcement_api_key", self._h._announce_api_key_edit.text().strip())
        if self._h._theme_combo:
            self._config.set("appearance.theme", self._h._theme_combo.currentText())
        if self._h._icon_combo:
            icon_key = ICON_OPTIONS.get(self._h._icon_combo.currentText(), "default")
            self._config.set("appearance.icon_theme", icon_key)
        if self._h._lang_combo:
            self._config.set("appearance.language", LANG_CODES[self._h._lang_combo.currentIndex()])

    def _save_ocr_credentials(self) -> None:
        """保存 OCR 密钥，保存后清空输入框并标记已保存。"""
        if not all(
            [
                self._h._ocr_api_key,
                self._h._ocr_secret_key,
                self._h._ocr_secret_id,
                self._h._ocr_tencent_secret_key,
                self._h._ocr_access_key_id,
                self._h._ocr_access_key_secret,
            ]
        ):
            return

        self._config.set("ocr.baidu_api_key", self._h._ocr_api_key.text().strip())
        self._config.set("ocr.baidu_secret_key", self._h._ocr_secret_key.text().strip())
        self._config.set("ocr.tencent_secret_id", self._h._ocr_secret_id.text().strip())
        self._config.set("ocr.tencent_secret_key", self._h._ocr_tencent_secret_key.text().strip())
        self._config.set("ocr.aliyun_access_key_id", self._h._ocr_access_key_id.text().strip())
        self._config.set("ocr.aliyun_access_key_secret", self._h._ocr_access_key_secret.text().strip())

        for attr, hint in [
            ("_ocr_api_key", "已保存"),
            ("_ocr_secret_key", "已保存"),
            ("_ocr_secret_id", "已保存"),
            ("_ocr_tencent_secret_key", "已保存"),
            ("_ocr_access_key_id", "已保存"),
            ("_ocr_access_key_secret", "已保存"),
        ]:
            w = getattr(self._h, attr)
            w.clear()
            w.setPlaceholderText(hint)

    def _save_scan_columns(self) -> None:
        """保存扫描配置和工作表列可见性。"""
        if self._h._skip_folders:
            skip = [s.strip() for s in self._h._skip_folders.text().split(",") if s.strip()]
            self._config.set("scan.skip_folders", skip or ["过期作废"])
        if self._h._scan_extensions:
            exts = [s.strip() for s in self._h._scan_extensions.text().split(",") if s.strip()]
            self._config.set("scan.extensions", exts or [".pdf", ".doc", ".docx", ".txt"])
        if self._h._skip_file_keywords:
            keywords = [s.strip() for s in self._h._skip_file_keywords.text().split(",") if s.strip()]
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

        visible = []
        for c in range(9):
            visible.append(self._h._col_checkboxes[c].isChecked() if c in self._h._col_checkboxes else True)
        self._config.set("appearance.column_visibility", visible)
        mw = self._h._parent.window() if self._h._parent else None
        if mw and hasattr(mw, "_apply_column_visibility"):
            mw._apply_column_visibility(visible)
