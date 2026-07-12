# pilotstd/ui/core/handlers/_theme.py
"""ThemeHandler — 主题/语言/图标 统一管理，替代 ThemeMixin 多重继承。"""

import logging
import os
import sys
from typing import Any, Optional

from PyQt6.QtCore import QLibraryInfo, QTranslator
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QWidget

from ....core.frozen import is_frozen
from ....i18n import _, set_language

logger = logging.getLogger("pilotstd.ui")


class ThemeHandler:
    """主题/语言/图标 统一管理。

    不继承 QWidget，所有需要窗口引用的操作通过 window 参数传入。
    """

    def __init__(
        self,
        config: Any,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._parent = parent

        # 翻译器引用（防止被 GC 回收）
        self._qt_translator: Optional[QTranslator] = None
        self._widgets_translator: Optional[QTranslator] = None

    def apply_icon(self, window: QWidget) -> None:
        """应用图标主题到窗口。"""
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
            window.setWindowIcon(QIcon(ico))

    def apply_theme(self) -> None:
        """应用主题样式表到全局 QApplication。"""
        from ....themes import apply_theme

        theme = self._config.get("appearance.theme", "经典白")
        apply_theme(QApplication.instance(), theme)

    def load_qt_translator(self, window: QWidget) -> None:
        """加载 Qt 翻译器（须在控件创建前调用，确保内置右键菜单被翻译）。"""
        lang = self._config.get("appearance.language", "zh_CN")
        set_language(lang)

        if lang in ("zh_CN", "zh_TW"):
            # 先移除旧翻译器，避免切换语言时累积
            for name in ("_qt_translator", "_widgets_translator"):
                old = getattr(self, name, None)
                if old:
                    QApplication.instance().removeTranslator(old)
                    setattr(self, name, None)

            if is_frozen():
                base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
                qt_trans_dir = os.path.join(base, "qt_translations")
            else:
                qt_trans_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)

            for qm_name in (f"qtbase_{lang}.qm", f"qt_{lang}.qm"):
                qt_qm = os.path.join(qt_trans_dir, qm_name)
                if os.path.exists(qt_qm):
                    translator = QTranslator(window)
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
                    logger.debug("Qt 翻译文件不存在: %s", qt_qm)
        else:
            # 非中文语言：移除已安装的 Qt 翻译器
            for name in ("_qt_translator", "_widgets_translator"):
                old = getattr(self, name, None)
                if old:
                    QApplication.instance().removeTranslator(old)
                    setattr(self, name, None)

    def apply_language(self, window: QWidget) -> None:
        """语言切换入口：加载 Qt 翻译 + 刷新 UI 文本（控件创建后调用）。"""
        self.load_qt_translator(window)
        self.retranslate_ui(window)

    def retranslate_ui(self, window: QWidget) -> None:
        """语言切换时刷新所有可见文本。"""
        if not getattr(window, "_ui_translatable", False):
            return
        window.setWindowTitle(_("app.title"))
        window.file_tree.setHeaderLabel(_("file_nav"))
        # 工具栏
        window.btn_select.setText(_("toolbar_import"))
        window.btn_query.setText(_("toolbar_query"))
        window.btn_download.setText(_("toolbar_download"))
        window.btn_normalize.setText(_("toolbar_normalize"))
        window.btn_save.setText(_("toolbar_save"))
        window.btn_auto.setText(_("toolbar_auto"))
        window.btn_announce.setText(_("toolbar_announce"))
        if getattr(window, "_paused", False):
            window.btn_pause.setText(_("toolbar_continue"))
        else:
            window.btn_pause.setText(_("toolbar_pause"))
        window.btn_cancel.setText(_("toolbar_cancel"))
        # 状态栏和日志
        window.status_bar.showMessage(_("ready"))
        log_label = getattr(window, "_log_label", None)
        if log_label:
            log_label.setText(_("work_log"))
        # 文件浏览树
        window._populate_quick_access()
        # 菜单
        mb = window.menuBar()
        if mb:
            mb.clear()
            window._setup_menu()
        # 工作表列头
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
        window.work_table.setHorizontalHeaderLabels(cols)
