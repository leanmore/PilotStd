"""Extracted theme/language methods for MainWindow."""

from __future__ import annotations

import logging
import os
import sys

from PyQt6.QtCore import QLibraryInfo, QTranslator
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ....core.frozen import is_frozen
from ....i18n import _

logger = logging.getLogger("pilotstd.ui")


# ── 图标加载 ──


def _apply_icon(self) -> None:
    """根据当前 icon_theme 设置加载对应的 .ico 文件作为窗口图标。"""
    theme = self._config.get("appearance.icon_theme", "default")
    if is_frozen():
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "desktop")
    if theme == "default":
        ico = os.path.join(base, "icon.ico")
    else:
        ico = os.path.join(base, "assets", "icons", f"{theme}.ico")
    if os.path.exists(ico):
        self.setWindowIcon(QIcon(ico))


# ── 主题应用 ──


def _apply_theme(self) -> None:
    """根据当前 theme 配置应用 QSS 样式表。"""
    from ...themes import apply_theme

    theme = self._config.get("appearance.theme", "经典白")
    apply_theme(QApplication.instance(), theme)


# ──界面框架翻译器加载──


def _load_qt_translator(self) -> None:
    """加载 Qt 内置翻译文件（qtbase_*.qm），实现内建控件汉化。"""
    lang = self._config.get("appearance.language", "zh_CN")
    # 幂等保护：同语言已加载则跳过，避免重复/+全树遍历
    if getattr(self, "_loaded_qt_lang", None) == lang:
        return
    from ....i18n import set_language

    set_language(lang)
    if lang in ("zh_CN", "zh_TW"):
        for attr in ("_qt_translator", "_widgets_translator"):
            old = getattr(self, attr, None)
            if old:
                QApplication.instance().removeTranslator(old)
                setattr(self, attr, None)
        if is_frozen():
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            qt_trans_dir = os.path.join(base, "qt_translations")
        else:
            qt_trans_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        for qm_name in (f"qtbase_{lang}.qm", f"qt_{lang}.qm"):
            qt_qm = os.path.join(qt_trans_dir, qm_name)
            if os.path.exists(qt_qm):
                translator = QTranslator(self)
                if translator.load(qt_qm):
                    QApplication.instance().installTranslator(translator)
                    if qm_name.startswith("qtbase"):
                        self._qt_translator = translator
                    else:
                        self._widgets_translator = translator
                    logger.info("Qt 翻译已加载: %s", qt_qm)
                else:
                    logger.warning("Qt 翻译加载失败: %s", qt_qm)
    else:
        for attr in ("_qt_translator", "_widgets_translator"):
            old = getattr(self, attr, None)
            if old:
                QApplication.instance().removeTranslator(old)
                setattr(self, attr, None)
    self._loaded_qt_lang = lang


# ── 语言切换入口 ──


def _apply_language(self) -> None:
    """加载 Qt 翻译并刷新所有 UI 文本。"""
    self._load_qt_translator()
    self._retranslate_ui()


# ──用户界面文本刷新──


def _retranslate_ui(self) -> None:
    """遍历所有可见 UI 控件，重新设置当前语言的文本。"""
    if not getattr(self, "_ui_translatable", False):
        return
    self.setWindowTitle(_("app.title"))
    self.file_tree.setHeaderLabel(_("file_nav"))
    self.btn_select.setText(_("toolbar_import"))
    self.btn_query.setText(_("toolbar_query"))
    self.btn_download.setText(_("toolbar_download"))
    self.btn_normalize.setText(_("toolbar_normalize"))
    self.btn_save.setText(_("toolbar_save"))
    self.btn_auto.setText(_("toolbar_auto"))
    self.btn_announce.setText(_("toolbar_announce"))
    if self._paused:
        self.btn_pause.setText(_("toolbar_continue"))
    else:
        self.btn_pause.setText(_("toolbar_pause"))
    self.btn_cancel.setText(_("toolbar_cancel"))
    self.status_bar.showMessage(_("ready"))
    if hasattr(self, "_log_label"):
        self._log_label.setText(_("work_log"))
    self._retranslate_file_tree()
    mb = self.menuBar()
    mb.clear()
    self._setup_menu()
    cols = [
        _("col_seq"),
        _("col_work_status"),
        _("col_std_number"),
        _("col_std_name"),
        _("col_effect_status"),
        _("col_replaces"),
        _("col_publish_date"),
        _("col_impl_date"),
        _("col_responsible_dept"),
        _("col_adopted"),
    ]
    self.work_table.setHorizontalHeaderLabels(cols)
