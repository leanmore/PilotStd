# pilotstd/ui/core/handlers/_settings_io.py
"""SettingsConfigIO — 配置加载/保存，从 SettingsHandler 拆分以控制文件大小。

薄包装层：仅负责 Qt 控件 ↔ dict 数据搬运，序列化/反序列化委托给 SettingsConfigIOEngine。
"""

from typing import Any

from PyQt6.QtCore import QStandardPaths

from ....i18n import _
from .settings_io_flow_engine import SettingsConfigIOEngine

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
        self._engine = SettingsConfigIOEngine()

    # ── 公共 API ──

    def load_all_configs(self) -> None:
        """从 ConfigManager 加载所有设置到 UI 控件。"""
        self._load_general()
        self._load_appearance()
        self._load_library()
        self._load_advanced()

    def save_all_configs(self) -> None:
        """将所有 UI 控件值保存到 ConfigManager。"""
        self._save_general()
        self._save_appearance()
        self._save_library()
        self._save_advanced()
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
    # General — 语言、启动行为、列可见性
    # ================================================================

    def _load_general(self) -> None:
        """加载通用设置：语言、启动行为、列可见性。"""
        h = self._h
        if not all([h._lang_combo, h._skip_welcome_cb, h._dash_cb]):
            return

        raw = {
            "appearance.language": self._config.get(
                "appearance.language", self._engine.DEFAULT_GENERAL["appearance.language"]
            ),
            "appearance.skip_welcome": self._config.get(
                "appearance.skip_welcome", self._engine.DEFAULT_GENERAL["appearance.skip_welcome"]
            ),
            "appearance.column_visibility": self._config.get(
                "appearance.column_visibility",
                self._engine.DEFAULT_GENERAL["appearance.column_visibility"],
            ),
        }
        result = self._engine.deserialize_general(raw)

        lang_map = {
            "zh_CN": _("lang_zh_CN"),
            "zh_TW": _("lang_zh_TW"),
            "en": _("lang_en"),
        }
        h._lang_combo.setCurrentText(lang_map.get(result["appearance.language"], _("lang_zh_CN")))
        h._skip_welcome_cb.setChecked(result["appearance.skip_welcome"])
        h._dash_cb.setChecked(True)

        visible = result["appearance.column_visibility"]
        if not visible:
            visible = self._engine.DEFAULT_GENERAL["appearance.column_visibility"]
        for c, cb in h._col_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(visible[c] if c < len(visible) else True)
            cb.blockSignals(False)

    def _save_general(self) -> None:
        """保存通用设置。"""
        h = self._h
        data = {"appearance.hyphen_style": True}

        if h._lang_combo:
            idx = h._lang_combo.currentIndex()
            if 0 <= idx < len(LANG_CODES):
                data["appearance.language"] = LANG_CODES[idx]
        if h._skip_welcome_cb:
            data["appearance.skip_welcome"] = h._skip_welcome_cb.isChecked()

        visible = []
        for c in range(9):
            visible.append(h._col_checkboxes[c].isChecked() if c in h._col_checkboxes else True)
        data["appearance.column_visibility"] = visible

        result = self._engine.serialize_general(data)
        for key, value in result.items():
            self._config.set(key, value)
        # 列可见性副作用
        mw = h._parent.window() if h._parent else None
        if mw and hasattr(mw, "_apply_column_visibility"):
            mw._apply_column_visibility(result["appearance.column_visibility"])

    # ================================================================
    # Appearance — 主题、图标
    # ================================================================

    def _load_appearance(self) -> None:
        """加载外观设置：主题、图标。"""
        h = self._h
        if not all([h._theme_combo, h._icon_combo]):
            return

        raw = {
            "appearance.theme": self._config.get(
                "appearance.theme", self._engine.DEFAULT_APPEARANCE["appearance.theme"]
            ),
            "appearance.icon_theme": self._config.get(
                "appearance.icon_theme", self._engine.DEFAULT_APPEARANCE["appearance.icon_theme"]
            ),
        }
        result = self._engine.deserialize_appearance(raw)

        h._theme_combo.setCurrentText(result["appearance.theme"])
        icon_display = {v: k for k, v in ICON_OPTIONS.items()}.get(result["appearance.icon_theme"], "默认")
        h._icon_combo.setCurrentText(icon_display)

    def _save_appearance(self) -> None:
        """保存外观设置。"""
        h = self._h
        data: dict[str, Any] = {}
        if h._theme_combo:
            data["appearance.theme"] = h._theme_combo.currentText()
        if h._icon_combo:
            data["appearance.icon_theme"] = ICON_OPTIONS.get(h._icon_combo.currentText(), "default")

        result = self._engine.serialize_appearance(data)
        for key, value in result.items():
            self._config.set(key, value)

    # ================================================================
    # Library — 存储路径、扫描选项
    # ================================================================

    def _load_library(self) -> None:
        """加载资源库设置：存储路径、扫描选项。"""
        h = self._h
        if not all([h._root_dir, h._expire_name, h._auto_clean_cb]):
            return

        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        raw = {
            "storage.root_dir": self._config.get("storage.root_dir", default_root),
            "storage.expire_folder": self._config.get(
                "storage.expire_folder", self._engine.DEFAULT_LIBRARY["storage.expire_folder"]
            ),
            "storage.downloads_dir": self._config.get(
                "storage.downloads_dir", self._engine.DEFAULT_LIBRARY["storage.downloads_dir"]
            ),
            "organize.auto_clean_source": self._config.get(
                "organize.auto_clean_source", self._engine.DEFAULT_LIBRARY["organize.auto_clean_source"]
            ),
            "storage.mirror_skipped_dirs": self._config.get(
                "storage.mirror_skipped_dirs", self._engine.DEFAULT_LIBRARY["storage.mirror_skipped_dirs"]
            ),
            "storage.mirror_fallback": self._config.get(
                "storage.mirror_fallback", self._engine.DEFAULT_LIBRARY["storage.mirror_fallback"]
            ),
            "watchdog.enabled": self._config.get(
                "watchdog.enabled", self._engine.DEFAULT_LIBRARY["watchdog.enabled"]
            ),
            "file.clear_readonly": self._config.get(
                "file.clear_readonly", self._engine.DEFAULT_LIBRARY["file.clear_readonly"]
            ),
        }
        # 扫描字段用 Engine 默认值兜底
        raw["scan.skip_folders"] = self._config.get(
            "scan.skip_folders", self._engine.DEFAULT_LIBRARY["scan.skip_folders"]
        )
        raw["scan.extensions"] = self._config.get(
            "scan.extensions", self._engine.DEFAULT_LIBRARY["scan.extensions"]
        )
        raw["scan.exclude_patterns"] = self._config.get(
            "scan.exclude_patterns", self._engine.DEFAULT_LIBRARY["scan.exclude_patterns"]
        )

        # storage.root_dir 用运行时默认值覆盖 Engine 静态默认值
        overrides = {"storage.root_dir": default_root}
        result = self._engine.deserialize_library(raw, overrides)

        h._root_dir.setText(result["storage.root_dir"])
        h._expire_name.setText(result["storage.expire_folder"])
        h._downloads_dir.setText(result["storage.downloads_dir"])
        h._auto_clean_cb.setChecked(result["organize.auto_clean_source"])
        if h._mirror_skipped_cb:
            h._mirror_skipped_cb.setChecked(result["storage.mirror_skipped_dirs"])
        if h._mirror_fallback_cb:
            h._mirror_fallback_cb.setChecked(result["storage.mirror_fallback"])
        if h._watchdog_cb:
            h._watchdog_cb.setChecked(result["watchdog.enabled"])
        if h._clear_readonly_cb:
            h._clear_readonly_cb.setChecked(result["file.clear_readonly"])
        if h._skip_folders:
            h._skip_folders.setText(", ".join(result["scan.skip_folders"]))
        if h._scan_extensions:
            h._scan_extensions.setText(", ".join(result["scan.extensions"]))
        if h._skip_file_keywords:
            h._skip_file_keywords.setText(", ".join(result["scan.exclude_patterns"]))

    def _save_library(self) -> None:
        """保存资源库设置。"""
        h = self._h
        data: dict[str, Any] = {}

        default_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if h._root_dir:
            data["storage.root_dir"] = h._root_dir.text().strip() or default_root
        if h._expire_name:
            data["storage.expire_folder"] = (
                h._expire_name.text().strip() or self._engine.DEFAULT_LIBRARY["storage.expire_folder"]
            )
        if h._downloads_dir:
            data["storage.downloads_dir"] = h._downloads_dir.text().strip()
        if h._auto_clean_cb:
            data["organize.auto_clean_source"] = h._auto_clean_cb.isChecked()
        if h._mirror_skipped_cb:
            data["storage.mirror_skipped_dirs"] = h._mirror_skipped_cb.isChecked()
        if h._mirror_fallback_cb:
            data["storage.mirror_fallback"] = h._mirror_fallback_cb.isChecked()
        if h._watchdog_cb:
            data["watchdog.enabled"] = h._watchdog_cb.isChecked()
        if h._clear_readonly_cb:
            data["file.clear_readonly"] = h._clear_readonly_cb.isChecked()
        if h._skip_folders:
            skip = [s.strip() for s in h._skip_folders.text().split(",") if s.strip()]
            data["scan.skip_folders"] = skip or self._engine.DEFAULT_LIBRARY["scan.skip_folders"]
        if h._scan_extensions:
            exts = [s.strip() for s in h._scan_extensions.text().split(",") if s.strip()]
            data["scan.extensions"] = exts or self._engine.DEFAULT_LIBRARY["scan.extensions"]
        if h._skip_file_keywords:
            keywords = [s.strip() for s in h._skip_file_keywords.text().split(",") if s.strip()]
            data["scan.exclude_patterns"] = keywords or self._engine.DEFAULT_LIBRARY["scan.exclude_patterns"]

        result = self._engine.serialize_library(data)
        for key, value in result.items():
            self._config.set(key, value)

    # ================================================================
    # Advanced — 网络代理、OCR 密钥、缓存、公告
    # ================================================================

    def _load_advanced(self) -> None:
        """加载高级设置：网络代理、公告、缓存、OCR 密钥。"""
        h = self._h
        if not all([h._proxy, h._ua_cb, h._announcement_cb, h._cache_cb]):
            return

        raw = {
            "network.proxy": self._config.get(
                "network.proxy", self._engine.DEFAULT_ADVANCED["network.proxy"]
            ),
            "network.ua_rotation": self._config.get(
                "network.ua_rotation", self._engine.DEFAULT_ADVANCED["network.ua_rotation"]
            ),
            "announcement.enabled": self._config.get(
                "announcement.enabled", self._engine.DEFAULT_ADVANCED["announcement.enabled"]
            ),
            "query.use_cache": self._config.get(
                "query.use_cache", self._engine.DEFAULT_ADVANCED["query.use_cache"]
            ),
        }
        if h._announce_cache_cb:
            raw["query.use_announcement_match"] = self._config.get(
                "query.use_announcement_match",
                self._engine.DEFAULT_ADVANCED["query.use_announcement_match"],
            )
        if h._announce_url_edit:
            raw["query.announcement_url"] = self._config.get(
                "query.announcement_url", self._engine.DEFAULT_ADVANCED["query.announcement_url"]
            )
        if h._announce_api_key_edit:
            raw["query.announcement_api_key"] = self._config.get(
                "query.announcement_api_key", self._engine.DEFAULT_ADVANCED["query.announcement_api_key"]
            )

        result = self._engine.deserialize_advanced(raw)

        h._proxy.setText(result["network.proxy"])
        h._ua_cb.setChecked(result["network.ua_rotation"])

        h._announcement_cb.blockSignals(True)
        h._announcement_cb.setChecked(result["announcement.enabled"])
        h._announcement_cb.blockSignals(False)

        h._cache_cb.setChecked(result["query.use_cache"])

        if h._announce_cache_cb:
            h._announce_cache_cb.blockSignals(True)
            h._announce_cache_cb.setChecked(result["query.use_announcement_match"])
            h._announce_cache_cb.blockSignals(False)
        if h._announce_url_edit:
            h._announce_url_edit.setText(result["query.announcement_url"])
        if h._announce_api_key_edit:
            h._announce_api_key_edit.setText(result["query.announcement_api_key"])

        # 脏数据仲裁：公告和公告缓存不能同时开启
        if h._announcement_cb.isChecked() and h._announce_cache_cb and h._announce_cache_cb.isChecked():
            h._announce_cache_cb.blockSignals(True)
            h._announce_cache_cb.setChecked(False)
            h._announce_cache_cb.blockSignals(False)
            if h._announce_url_edit:
                h._announce_url_edit.setEnabled(False)
            self._config.set("query.use_announcement_match", False)
            self._config.save()

        # OCR 密钥占位符（不加载实际值到文本框，只显示提示）
        if all(
            [
                h._ocr_api_key,
                h._ocr_secret_key,
                h._ocr_secret_id,
                h._ocr_tencent_secret_key,
                h._ocr_access_key_id,
                h._ocr_access_key_secret,
            ]
        ):
            for attr, key, hint in [
                ("_ocr_api_key", "ocr.baidu_api_key", "百度云 API Key"),
                ("_ocr_secret_key", "ocr.baidu_secret_key", "百度云 Secret Key"),
                ("_ocr_secret_id", "ocr.tencent_secret_id", "腾讯云 Secret ID"),
                ("_ocr_tencent_secret_key", "ocr.tencent_secret_key", "腾讯云 Secret Key"),
                ("_ocr_access_key_id", "ocr.aliyun_access_key_id", "阿里云 Access Key ID"),
                ("_ocr_access_key_secret", "ocr.aliyun_access_key_secret", "阿里云 Access Key Secret"),
            ]:
                widget = getattr(h, attr)
                widget.setPlaceholderText("已保存" if self._config.get(key, "") else hint)

    def _save_advanced(self) -> None:
        """保存高级设置：网络代理、OCR 密钥、缓存、公告。"""
        h = self._h
        data: dict[str, Any] = {}

        if h._proxy:
            data["network.proxy"] = h._proxy.text().strip()
        if h._ua_cb:
            data["network.ua_rotation"] = h._ua_cb.isChecked()
        if h._announcement_cb:
            data["announcement.enabled"] = h._announcement_cb.isChecked()
        if h._cache_cb:
            data["query.use_cache"] = h._cache_cb.isChecked()
        if h._announce_cache_cb:
            data["query.use_announcement_match"] = h._announce_cache_cb.isChecked()
        if h._announce_url_edit:
            data["query.announcement_url"] = h._announce_url_edit.text().strip()
        if h._announce_api_key_edit:
            data["query.announcement_api_key"] = h._announce_api_key_edit.text().strip()

        # OCR 密钥
        if all(
            [
                h._ocr_api_key,
                h._ocr_secret_key,
                h._ocr_secret_id,
                h._ocr_tencent_secret_key,
                h._ocr_access_key_id,
                h._ocr_access_key_secret,
            ]
        ):
            data["ocr.baidu_api_key"] = h._ocr_api_key.text().strip()
            data["ocr.baidu_secret_key"] = h._ocr_secret_key.text().strip()
            data["ocr.tencent_secret_id"] = h._ocr_secret_id.text().strip()
            data["ocr.tencent_secret_key"] = h._ocr_tencent_secret_key.text().strip()
            data["ocr.aliyun_access_key_id"] = h._ocr_access_key_id.text().strip()
            data["ocr.aliyun_access_key_secret"] = h._ocr_access_key_secret.text().strip()

            for attr, hint in [
                ("_ocr_api_key", "已保存"),
                ("_ocr_secret_key", "已保存"),
                ("_ocr_secret_id", "已保存"),
                ("_ocr_tencent_secret_key", "已保存"),
                ("_ocr_access_key_id", "已保存"),
                ("_ocr_access_key_secret", "已保存"),
            ]:
                w = getattr(h, attr)
                w.clear()
                w.setPlaceholderText(hint)

        result = self._engine.serialize_advanced(data)
        for key, value in result.items():
            self._config.set(key, value)
