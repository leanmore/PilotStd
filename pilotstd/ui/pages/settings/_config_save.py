# pilotstd/ui/pages/settings/_config_save.py
# 配置保存 mixin — 将所有设置写回 ConfigManager

from ._appearance import ICON_OPTIONS


class _ConfigSaveTab:
    """将 UI 控件值持久化到 ConfigManager。"""

    def _save_storage_and_appearance(self) -> None:
        """保存存储路径、网络代理、外观、缓存等通用设置。"""
        from PyQt6.QtCore import QStandardPaths

        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self._config.set(
            "storage.root_dir",
            self.root_dir.text().strip() or default_root,
        )
        self._config.set(
            "storage.expire_folder",
            self.expire_name.text().strip() or "过期作废",
        )
        self._config.set("organize.auto_clean_source", self.auto_clean_cb.isChecked())
        self._config.set("storage.mirror_skipped_dirs", self.mirror_skipped_cb.isChecked())
        self._config.set("storage.mirror_fallback", self.mirror_fallback_cb.isChecked())
        self._config.set("watchdog.enabled", self.watchdog_cb.isChecked())
        self._config.set("network.proxy", self.proxy.text().strip())
        self._config.set("network.ua_rotation", self.ua_cb.isChecked())
        self._config.set("announcement.enabled", self.announcement_cb.isChecked())
        self._config.set("appearance.hyphen_style", True)
        self._config.set("file.clear_readonly", self.clear_readonly_cb.isChecked())
        self._config.set("storage.downloads_dir", self.downloads_dir.text().strip())
        self._config.set("appearance.skip_welcome", self.skip_welcome_cb.isChecked())
        self._config.set("query.use_cache", self.cache_cb.isChecked())
        self._config.set("query.use_announcement_match", self.announce_cache_cb.isChecked())
        self._config.set("query.announcement_url", self.announce_url_edit.text().strip())
        self._config.set(
            "query.announcement_api_key",
            self.announce_api_key_edit.text().strip(),
        )
        self._config.set("appearance.theme", self.theme_combo.currentText())
        icon_key = ICON_OPTIONS.get(self.icon_combo.currentText(), "default")
        self._config.set("appearance.icon_theme", icon_key)
        lang_codes = ["zh_CN", "zh_TW", "en"]
        self._config.set("appearance.language", lang_codes[self.lang_combo.currentIndex()])

    def _save_ocr_credentials(self) -> None:
        """保存百度/腾讯/阿里云 OCR 密钥，保存后清空输入框并标记"已保存"。"""
        self._config.set("ocr.baidu_api_key", self.ocr_api_key.text().strip())
        self._config.set("ocr.baidu_secret_key", self.ocr_secret_key.text().strip())
        self._config.set("ocr.tencent_secret_id", self.ocr_secret_id.text().strip())
        self._config.set("ocr.tencent_secret_key", self.ocr_tencent_secret_key.text().strip())
        self._config.set("ocr.aliyun_access_key_id", self.ocr_access_key_id.text().strip())
        self._config.set(
            "ocr.aliyun_access_key_secret",
            self.ocr_access_key_secret.text().strip(),
        )
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

    def _save_scan_and_columns(self) -> None:
        """保存扫描配置（跳过文件夹/扩展名/排除关键词）和工作表列可见性。"""
        skip = [s.strip() for s in self.skip_folders.text().split(",") if s.strip()]
        self._config.set("scan.skip_folders", skip or ["过期作废"])
        exts = [s.strip() for s in self.scan_extensions.text().split(",") if s.strip()]
        self._config.set("scan.extensions", exts or [".pdf", ".doc", ".docx", ".txt"])
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
        visible = []
        for c in range(9):
            if c in self._col_checkboxes:
                visible.append(self._col_checkboxes[c].isChecked())
            else:
                visible.append(True)
        self._config.set("appearance.column_visibility", visible)
        mw = self.window()
        if mw and hasattr(mw, "_apply_column_visibility"):
            mw._apply_column_visibility(visible)

    def save_to_config(self) -> None:
        if not self._config:
            return

        self._save_storage_and_appearance()
        self._save_ocr_credentials()
        self._save_scan_and_columns()

        mw = self.window()
        if mw and hasattr(mw, "_apply_icon"):
            mw._apply_icon()
        if mw and hasattr(mw, "_apply_announce_cache_mode"):
            mw._apply_announce_cache_mode(self.announce_cache_cb.isChecked())
        self._config.save()
