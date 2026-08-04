# 模块：项目//核心/处理器/_查询_脚本
"""QuerySummaryHandler — 查询汇总弹窗管理，从 QueryUIHandler 拆分以控制文件大小。

薄包装层：UI 构建 + 文件保存 + 弹窗管理。纯逻辑委托给 QuerySummaryFlowEngine。
"""
# 输入输出_控制分栏显示顺序和图标，→(图标,18键名)

from __future__ import annotations

import csv
import logging
import os
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    pass

from ....i18n import _ as tr
from ....models import ParsedStdInfo
from .query_summary_flow_engine import QuerySummaryFlowEngine

logger = logging.getLogger(__name__)

# ── 分栏元数据 ──

SECTION_META = {
    # 分栏元数据：→(图标,18键名)
    "organize": ("📁", "section_organize"),
    "normalize": ("📝", "section_normalize"),
    "expire": ("🗑️", "section_expire"),
    "pending": ("⚠️", "section_pending"),
    "manual_download": ("🌐", "section_manual_download"),
    "download": ("⬇️", "section_download"),
    "not_found": ("❓", "section_not_found"),
}


class QuerySummaryHandler:
    """查询汇总弹窗管理：分栏构建、CSV 保存、汇总展示。"""

    def __init__(
        self,
        mgr: Any,
        parent: QWidget | None,
        work_table: QTableWidget,
        parsed_results: list[ParsedStdInfo],
        suppress_dialogs: Callable[[], bool] | None,
        register_task: Callable[..., None],
        project_mark_dirty: Callable[[], None],
        status_cb: Callable[[str], None],
        on_download_cb: Callable[[], None] | None,
        export_pending_csv: Callable[[], str | None],
        write_pending_to_db: Callable[[list[Any]], None],
    ) -> None:
        self._mgr = mgr
        self._parent = parent
        self._work_table = work_table
        self._parsed_results = parsed_results
        self._suppress_dialogs = suppress_dialogs
        self._register_task = register_task
        self._project_mark_dirty = project_mark_dirty
        self._status_cb = status_cb
        self._on_download_cb = on_download_cb
        self._export_pending_csv_cb = export_pending_csv
        self._write_pending_to_db_cb = write_pending_to_db
        self._engine = QuerySummaryFlowEngine()
        # 汇总弹窗临时状态
        self._summary_sections: dict[str, QFrame] = {}
        self._summary_container_layout: QVBoxLayout | None = None
        self._summary_total_label: QLabel | None = None

    # _—将解析结果按_分桶
    def build_buckets(self) -> dict[str, list[Any]]:
        """将 _parsed_results 按 next_action 分组。委托 Engine。"""
        return self._engine.build_buckets(self._parsed_results)

    def create_section(
        self,
        key: str,
        items: list[Any],
        parent: QWidget | None = None,
        extra_buttons: list[tuple[str, Any]] | None = None,
    ) -> QFrame:
        """构建单个分栏 widget：标题行 + 条目列表 + 可选操作按钮。"""
        meta = SECTION_META.get(key, ("", key))
        icon, title_key = meta
        count = len(items)

        frame = QFrame(parent)
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_label = QLabel(f"{icon} {tr(title_key)}    [ {count} 条 ]")
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        title_row.addWidget(title_label)
        title_row.addStretch()
        layout.addLayout(title_row)

        list_widget = QListWidget()
        list_widget.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        list_widget.setMaximumHeight(120)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        for item in items:
            fname = (
                os.path.basename(self._engine.safe_str(getattr(item, "source_path", "")))
                or self._engine.safe_str(getattr(item, "raw_filename", ""))
                or self._engine.safe_str(getattr(item, "std_name", ""))
                or item.get_full_number()
            )
            if key == "pending":
                reason = self._get_pending_reason(item)
                if reason:
                    fname = f"{fname}  （{reason}）"
            list_widget.addItem(fname)
        layout.addWidget(list_widget)

        action_area = QHBoxLayout()
        action_area.addStretch()
        if extra_buttons:
            for btn_text, callback in extra_buttons:
                btn = QPushButton(btn_text)
                btn.clicked.connect(callback)
                action_area.addWidget(btn)
        layout.addLayout(action_area)

        return frame

    # ──原因提取──

    def _get_pending_reason(self, item: Any) -> str:
        """获取 pending 条目的冲突原因。委托 Engine。"""
        status = getattr(item, "stage_status", "") or ""
        reason = self._engine.get_pending_reason(status)
        if reason:
            return reason
        ms = getattr(item, "match_status", "") or ""
        return self._engine.get_pending_reason(ms)

    # ──数据保存与用户界面更新──

    # _—将条目列表导出为文件，含完整标准信息列
    def save_csv(self, path: str, items: list[Any]) -> None:
        """保存条目列表为 CSV 文件。"""
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "标准号",
                    "标准名称",
                    "状态",
                    "生效状态",
                    "替代标准",
                    "发布日期",
                    "实施日期",
                    "发布部门",
                    "采标",
                    "文件路径",
                ]
            )
            for item in items:
                adopted = "是" if getattr(item, "is_adopted", False) else "否"
                writer.writerow(
                    [
                        self._engine.safe_str(item.get_full_number()),
                        self._engine.safe_str(getattr(item, "std_name", "")),
                        self._engine.safe_str(getattr(item, "next_action", "")),
                        self._engine.safe_str(getattr(item, "effect_status", "")),
                        self._engine.safe_str(getattr(item, "found_replaces", "")),
                        self._engine.safe_str(getattr(item, "found_publish_date", "")),
                        self._engine.safe_str(getattr(item, "found_impl_date", "")),
                        self._engine.safe_str(getattr(item, "found_responsible_dept", "")),
                        self._engine.safe_str(adopted),
                        self._engine.safe_str(getattr(item, "source_path", "")),
                    ]
                )

    def remove_section_widget(self, key: str) -> None:
        """从汇总弹窗中移除指定分栏 widget。"""
        widget = self._summary_sections.get(key)
        if widget is None:
            return
        layout = self._summary_container_layout
        if layout is not None:
            layout.removeWidget(widget)
        widget.setParent(None)
        widget.deleteLater()
        del self._summary_sections[key]
        if layout is not None:
            layout.invalidate()
            layout.activate()
            if layout.parentWidget():
                layout.parentWidget().update()
        remaining = len(self._parsed_results)
        if self._summary_total_label is not None:
            self._summary_total_label.setText(tr("summary_total_records").format(count=remaining))

    def on_save_section_csv(self, key: str, items: list[Any]) -> None:
        """保存分栏条目为 CSV → 移除 UI 分栏（不修改共享 _parsed_results）。"""
        if key == "pending":
            path = self._export_pending_csv_cb()
            if not path:
                return
            self._write_pending_to_db_cb(items)
            self.remove_section_widget(key)
            self._status_cb(tr("msg_pending_saved").format(count=len(items)))
            return

        if not items:
            return

        from pilotstd.core.export_utils import generate_export_batch_timestamp, get_export_filename

        ts = generate_export_batch_timestamp()
        default_name = get_export_filename(tr("export_manual_download_list"), ts)
        path, _ = QFileDialog.getSaveFileName(None, tr("title_save_csv"), default_name, tr("filter_csv_files"))
        if not path:
            return
        try:
            self.save_csv(path, items)
        except OSError as e:
            QMessageBox.warning(self._parent, tr("title_save_failed"), tr("msg_save_failed").format(error=e))
            return
        self.remove_section_widget(key)
        self._status_cb(tr("msg_manual_saved").format(count=len(items)))

    # ── 汇总弹窗构建与销毁 ──

    def build_summary_dialog(self, buckets: dict, total: int, has_download: bool) -> QDialog:
        """构建分栏式汇总弹窗。"""
        section_order = ["organize", "normalize", "expire", "pending", "manual_download", "download"]
        self._summary_sections = {}

        dlg = QDialog(self._parent)
        dlg.setWindowTitle(tr("summary_title"))
        dlg.resize(800, 600)
        dlg.setSizeGripEnabled(False)
        main_layout = QVBoxLayout(dlg)

        self._summary_total_label = QLabel(tr("summary_total_records").format(count=total))
        font = self._summary_total_label.font()
        font.setPointSize(11)
        self._summary_total_label.setFont(font)
        main_layout.addWidget(self._summary_total_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        self._summary_container_layout = container_layout
        container_layout.setSpacing(6)
        for key in section_order:
            items = buckets.get(key, [])
            if not items:
                continue
            extra_buttons = None
            if key in ("pending", "manual_download"):
                btn_key = "btn_save_pending_csv" if key == "pending" else "btn_save_manual_csv"
                extra_buttons = [
                    (tr(btn_key), lambda _c=False, k=key, it=items: self.on_save_section_csv(k, it)),
                ]
            section = self.create_section(key, items, dlg, extra_buttons=extra_buttons)
            self._summary_sections[key] = section
            container_layout.addWidget(section)
        container_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        download_btn = QPushButton(tr("btn_enter_download"))
        download_btn.setDefault(True)
        download_btn.setEnabled(has_download)

        def on_download_clicked() -> None:
            """关闭汇总弹窗并触发下载流程。"""
            dlg.accept()
            if self._on_download_cb:
                self._on_download_cb()

        download_btn.clicked.connect(on_download_clicked)
        close_btn = QPushButton(tr("btn_close"))
        close_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(download_btn)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)
        return dlg

    def show_query_summary(self) -> None:
        """查询完成汇总入口：持久化 pending → 通知 → 构建分栏弹窗。"""
        if not self._parsed_results:
            return
        total = len(self._parsed_results)

        pending = [p for p in self._parsed_results if p.next_action == "pending"]
        if pending:
            self._write_pending_to_db_cb(pending)

        self._status_cb(tr("query_complete").format(total))
        if self._project_mark_dirty:
            self._project_mark_dirty()
        self._register_task("查询", total, total)

        from ....platform.notify import NotifyService

        buckets = self.build_buckets()
        summary = self._engine.build_summary_message(buckets, total)
        NotifyService.get().show(tr("query_toast_title"), summary)

        # 检查__（需要调用才能得到布尔值）
        if callable(self._suppress_dialogs) and self._suppress_dialogs():
            return

        has_download = len(buckets.get("download", [])) > 0
        dlg = self.build_summary_dialog(buckets, total, has_download)
        dlg.exec()

        self._summary_sections = {}
        self._summary_total_label = None
