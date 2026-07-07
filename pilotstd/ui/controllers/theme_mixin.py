# pilotstd/ui/controllers/theme_mixin.py
# 主题/语言/i18n 混入——主题切换 + 语言切换 + 图标 + 全部 UI 文字刷新

import logging
import os
import sys

from PyQt6.QtCore import QLibraryInfo, QTranslator
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ...core.frozen import is_frozen
from ...i18n import _, set_language

logger = logging.getLogger("pilotstd.ui")


class ThemeMixin:
    """主题/语言/图标 统一管理混入。

    依赖 self._config（主题/语言配置项），由 MainWindow.__init__ 提供。
    """

    def _apply_icon(self) -> None:
        theme = self._config.get("appearance.icon_theme", "default")
        # 项目根目录：__file__ 在 pilotstd/ui/controllers/，向上3级
        if is_frozen():
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base = os.path.join(os.path.dirname(__file__), "..", "..", "..", "desktop")
        if theme == "default":
            ico = os.path.join(base, "icon.ico")
        else:
            ico = os.path.join(base, "assets", "icons", f"{theme}.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

    def _apply_theme(self) -> None:
        from ..themes import apply_theme

        theme = self._config.get("appearance.theme", "经典白")
        apply_theme(QApplication.instance(), theme)

    def _load_qt_translator(self) -> None:
        """仅加载 Qt 翻译器（须在控件创建前调用，确保内置右键菜单被翻译）。"""
        lang = self._config.get("appearance.language", "zh_CN")
        set_language(lang)

        if lang in ("zh_CN", "zh_TW"):
            # 先移除旧翻译器，避免切换语言时累积
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
            # 加载 Qt 内置翻译（qtbase + widgets，多翻译器协同）
            for qm_name in (f"qtbase_{lang}.qm", f"qt_{lang}.qm"):
                qt_qm = os.path.join(qt_trans_dir, qm_name)
                if os.path.exists(qt_qm):
                    translator = QTranslator(self)
                    if translator.load(qt_qm):
                        QApplication.instance().installTranslator(translator)
                        # 保存引用防止被 GC 回收
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
            for attr in ("_qt_translator", "_widgets_translator"):
                old = getattr(self, attr, None)
                if old:
                    QApplication.instance().removeTranslator(old)
                    setattr(self, attr, None)

    def _apply_language(self) -> None:
        """语言切换入口：加载 Qt 翻译 + 刷新 UI 文本（控件创建后调用）。"""
        self._load_qt_translator()
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        """语言切换时刷新所有可见文本。

        【重要】新增 i18n 的 UI 元素（按钮、标签、菜单项等）必须在此方法中添加
        对应的 setText/setWindowTitle 调用，否则语言切换时不会更新。
        工具栏按钮和菜单栏在此集中管理，右键菜单项在构建时通过 _() 直接设置。
        """
        # 首次加载时控件文本已由 _() 设置，跳过冗余重建
        if not getattr(self, "_ui_translatable", False):
            return
        self.setWindowTitle(_("app.title"))
        self.file_tree.setHeaderLabel(_("file_nav"))
        # 工具栏
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
        # 状态栏和日志
        self.status_bar.showMessage(_("ready"))
        if hasattr(self, "_log_label"):
            self._log_label.setText(_("work_log"))
        # 文件浏览树
        self._populate_quick_access()
        # 菜单
        mb = self.menuBar()
        mb.clear()
        self._setup_menu()
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
        self.work_table.setHorizontalHeaderLabels(cols)
