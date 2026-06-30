# pilotstd/ui/pages/settings/_config_load.py
# 配置加载 mixin — 从 ConfigManager 读回所有设置到 UI 控件

from ....i18n import _


class _ConfigLoadTab:
    """从 ConfigManager 加载所有设置到对应的 UI 控件。"""

    def _load_storage_config(self, default_root: str) -> None:
        """加载存储相关设置：根目录、过期文件夹、自动清理、镜像、看门狗、下载目录。"""
        self.root_dir.setText(self._config.get("storage.root_dir", default_root))
        self.expire_name.setText(self._config.get("storage.expire_folder", "过期作废"))
        self.auto_clean_cb.setChecked(self._config.get("organize.auto_clean_source", False))
        self.mirror_skipped_cb.setChecked(self._config.get("storage.mirror_skipped_dirs", True))
        self.mirror_fallback_cb.setChecked(self._config.get("storage.mirror_fallback", True))
        self.watchdog_cb.setChecked(self._config.get("watchdog.enabled", False))
        self.clear_readonly_cb.setChecked(self._config.get("file.clear_readonly", True))
        self.downloads_dir.setText(self._config.get("storage.downloads_dir", ""))

    def _load_network_ocr_config(self) -> None:
        """加载网络代理、公告开关、OCR 密钥设置。"""
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

    def _load_query_ui_config(self) -> None:
        """加载查询与界面杂项设置。"""
        self.dash_cb.setChecked(True)  # 已锁定，始终使用短横
        self.skip_welcome_cb.setChecked(self._config.get("appearance.skip_welcome", False))
        self.cache_cb.setChecked(self._config.get("query.use_cache", True))
        self.announce_cache_cb.setChecked(self._config.get("query.use_announcement_match", False))
        self.announce_url_edit.setText(self._config.get("query.announcement_url", "http://localhost:9028"))
        self.announce_url_edit.setEnabled(self._config.get("query.use_announcement_match", False))
        self.announce_api_key_edit.setText(self._config.get("query.announcement_api_key", ""))

    def _load_scan_config(self) -> None:
        """加载扫描相关设置：跳过的文件夹、文件扩展名、排除关键词。"""
        self.skip_folders.setText(", ".join(self._config.get("scan.skip_folders", ["过期作废"])))
        self.scan_extensions.setText(
            ", ".join(
                self._config.get(
                    "scan.extensions",
                    [".pdf", ".doc", ".docx", ".txt"],
                )
            )
        )
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

    def _load_appearance_config(self) -> None:
        """加载外观设置：主题、图标、语言、列可见性。"""
        from ._appearance import ICON_OPTIONS

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

    def _load_from_config(self) -> None:
        from PyQt6.QtCore import QStandardPaths

        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self._load_storage_config(default_root)
        self._load_network_ocr_config()
        self._load_query_ui_config()
        self._load_scan_config()
        self._load_appearance_config()
