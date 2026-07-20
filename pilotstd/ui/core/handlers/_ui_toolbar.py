# pilotstd/ui/core/handlers/_ui_toolbar.py
# 工具栏/菜单栏构建混入 — 从 _ui_setup.py 提取

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QPushButton,
    QToolBar,
)

from ....i18n import _


class _UISetupToolbarMixin:
    """菜单栏与工具栏构建方法集合。"""

    def setup_menu(self, window: Any, action_callbacks: dict[str, Any]) -> None:
        """构建菜单栏：文件 | 工具 | 设置 | 帮助。"""
        mb = window.menuBar()
        assert mb is not None, "menuBar() 不应为 None"

        # ── 文件 ──
        file_menu = mb.addMenu(_("file"))

        a = file_menu.addAction(_("open_file"), action_callbacks["on_open_file"])
        a.setToolTip("选择单个标准文件并导入项目")
        a = file_menu.addAction(_("open_folder"), action_callbacks["on_open_folder"])
        a.setToolTip("选择文件夹（含子文件夹）并导入项目")
        file_menu.addSeparator()

        save_result_menu = file_menu.addMenu(_("export_sheet"))
        save_result_menu.setToolTip("将工作区表格导出为文件")
        save_result_menu.addAction(_("export_txt"), action_callbacks["on_save_result_txt"])
        save_result_menu.addAction(_("export_csv"), action_callbacks["on_save_result_csv"])

        file_menu.addSeparator()
        a = file_menu.addAction(_("export_file_list"), action_callbacks["on_export_file_list"])
        a.setToolTip("将选中文件夹内所有文件名导出为列表（可选是否含完整路径）")
        a = file_menu.addAction(_("export_folder_tree"), action_callbacks["on_export_folder_tree"])
        a.setToolTip("将选中文件夹的目录树形结构导出为文本")
        file_menu.addSeparator()
        a = file_menu.addAction(_("save_query_project"), action_callbacks["on_save_query_project"])
        a.setToolTip("将当前查询列表保存为 .pilotstd 项目文件，便于下次恢复")
        a = file_menu.addAction(_("save_download_project"), action_callbacks["on_save_download_project"])
        a.setToolTip("将当前下载队列保存为 .pilotstd 项目文件，便于下次恢复")
        a = file_menu.addAction(_("import_download"), action_callbacks["on_import_download"])
        a.setToolTip("从文件导入标准号列表并直接下载，无需先查询")
        file_menu.addSeparator()
        a = file_menu.addAction(_("open_project"), action_callbacks["on_open_project"])
        a.setToolTip("从 .pilotstd 项目文件恢复之前保存的工作状态")
        file_menu.addSeparator()
        a = file_menu.addAction(_("exit"), window.close)
        a.setToolTip("退出 PilotStd（未保存的工作状态将自动保存）")

        # ── 工具 ──
        tool_menu = mb.addMenu(_("tools"))

        rule_action = tool_menu.addAction(_("query_rules"), action_callbacks["on_rule_query"])
        rule_action.setToolTip("管理查询/下载网站适配规则，支持 JSON 导入导出")

        tool_menu.addAction(_("task_center"), action_callbacks["on_task_center"])
        tool_menu.addSeparator()
        tool_menu.addAction(_("cleanup_empty_dirs"), action_callbacks["on_cleanup_empty_dirs"])
        tool_menu.addAction(_("collect_unrecognized"), action_callbacks["on_collect_unrecognized"])
        tool_menu.addSeparator()
        tool_menu.addAction(_("export_diag"), action_callbacks["on_export_diag"])
        tool_menu.addSeparator()
        tool_menu.addAction(_("pending_query"), action_callbacks["on_pending_query"])

        # ── 设置 ──
        settings_menu = mb.addMenu(_("settings"))
        settings_menu.addAction(_("preferences"), action_callbacks["on_settings"])

        # ── 帮助 ──
        help_menu = mb.addMenu(_("help"))
        help_menu.addAction(_("check_update"), action_callbacks["on_check_update"])
        help_menu.addAction(_("about"), action_callbacks["on_about"])

    def _make_toolbar_btn(
        self, toolbar: Any, style: Any, text_key: str, icon_sp: Any, tooltip: str, callback: Any
    ) -> Any:
        """创建单个工具栏按钮并添加到工具栏。"""
        btn = QPushButton(_(text_key))
        btn.setIcon(style.standardIcon(icon_sp))
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        toolbar.addWidget(btn)
        return btn

    def setup_toolbar(self, window: Any, action_callbacks: dict[str, Any]) -> dict[str, Any]:
        """构建工具栏，返回按钮字典供状态控制。"""
        toolbar = QToolBar(_("toolbar_main"))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        style = window.style()
        assert style is not None, "style() 不应为 None"
        SP = style.StandardPixmap

        btn_specs = {
            "btn_select": ("toolbar_import", SP.SP_DirOpenIcon, "导入文件夹到项目中", "on_select"),
            "btn_query": (
                "toolbar_query",
                SP.SP_FileDialogContentsView,
                "对扫描后的标准号在网站上查询有效性",
                "on_query",
            ),
            "btn_download": ("toolbar_download", SP.SP_ArrowDown, "对已有新版本的标准进行下载", "on_download"),
            "btn_normalize": (
                "toolbar_normalize",
                SP.SP_FileDialogDetailedView,
                "对扫描结果生成规范标准文件名",
                "on_normalize",
            ),
            "btn_save": ("toolbar_save", SP.SP_DriveFDIcon, "将文件以规范名称保存到设定文件夹", "on_save_to_folder"),
            "btn_auto": ("toolbar_auto", SP.SP_MediaPlay, "自动依次执行全流程", "on_auto_run"),
            "btn_announce": (
                "toolbar_announce",
                SP.SP_MessageBoxWarning,
                "抓取国家标准公告，检测本地标准变更",
                "on_check_announcements",
            ),
        }
        buttons: dict[str, Any] = {}
        for name, (text_key, icon_sp, tip, cb_key) in btn_specs.items():
            cb = action_callbacks[cb_key]
            buttons[name] = self._make_toolbar_btn(toolbar, style, text_key, icon_sp, tip, cb)

        toolbar.addSeparator()

        pause_btn = QPushButton(_("toolbar_pause"))
        pause_btn.setIcon(SP.SP_MediaPause)
        pause_btn.setToolTip("暂停/继续当前任务")
        pause_btn.clicked.connect(action_callbacks["on_pause_toggle"])
        toolbar.addWidget(pause_btn)
        pause_btn.setEnabled(False)
        buttons["btn_pause"] = pause_btn

        cancel_btn = QPushButton(_("toolbar_cancel"))
        cancel_btn.setIcon(SP.SP_DialogCancelButton)
        cancel_btn.setToolTip("取消当前任务")
        cancel_btn.clicked.connect(action_callbacks["on_cancel"])
        toolbar.addWidget(cancel_btn)
        cancel_btn.setEnabled(False)
        buttons["btn_cancel"] = cancel_btn

        toolbar.addSeparator()

        return buttons
