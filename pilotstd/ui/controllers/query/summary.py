# pilotstd/ui/controllers/query/summary.py
# 查询结果摘要展示 — 分栏式汇总弹窗（规格 v1.0）

import csv
import os
from typing import Any

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
    QVBoxLayout,
    QWidget,
)

from ....i18n import _
from ....platform.notify import NotifyService

# stage_status → 用户可读描述 i18n key
_PENDING_REASON_KEYS = {
    "chain_exhausted": "reason_chain_exhausted",
    "match_not_exact": "reason_match_not_exact",
    "name_conflict": "reason_name_conflict",
    "source_path_empty": "reason_source_path_empty",
    "replacement_manual": "reason_replacement_manual",
    "user_retained": "reason_user_retained",
    "version_mismatch": "reason_match_not_exact",
}


class QuerySummaryMethods:
    """查询完成后的分栏式汇总弹窗。"""

    # ── 分栏骨架 ──────────────────────────────────────────

    _BUCKET_NAMES = ("organize", "normalize", "expire", "download", "manual_download", "pending", "not_found")

    _ACTION_TO_BUCKET = {
        "archive": "organize",
        "normalize": "normalize",
        "expire": "expire",
        "download": "download",
        "manual_download": "manual_download",
        "pending": "pending",
        "not_found": "not_found",
    }

    # 分栏 key → (图标, i18n key)
    _SECTION_META = {
        "organize": ("📁", "section_organize"),
        "normalize": ("📝", "section_normalize"),
        "expire": ("🗑️", "section_expire"),
        "pending": ("⚠️", "section_pending"),
        "manual_download": ("🌐", "section_manual_download"),
        "download": ("⬇️", "section_download"),
        "not_found": ("❓", "section_not_found"),
    }

    @staticmethod
    def _get_pending_reason(item: Any) -> str:
        """获取 pending 条目的冲突原因（翻译后）。"""
        status = getattr(item, "stage_status", "") or ""
        if status in _PENDING_REASON_KEYS:
            return _(_PENDING_REASON_KEYS[status])
        ms = getattr(item, "match_status", "") or ""
        if ms in _PENDING_REASON_KEYS:
            return _(_PENDING_REASON_KEYS[ms])
        return ""

    def _build_buckets(self) -> dict[str, list[Any]]:
        """将 _parsed_results 按 next_action 分组。
        Router 将 organize 桶的 next_action 设为 "archive"，
        这里映射回 "organize" 用于前端展示。
        """
        buckets: dict[str, list[Any]] = {k: [] for k in self._BUCKET_NAMES}
        for p in self._parsed_results:
            action = getattr(p, "next_action", "") or ""
            key = self._ACTION_TO_BUCKET.get(action)
            if key is not None:
                buckets[key].append(p)
        return buckets

    def _create_section(
        self, key: str, items: list[Any], parent: Any = None, extra_buttons: list[tuple[str, Any]] | None = None
    ) -> QFrame:
        """构建单个分栏 widget：标题行 + 条目列表 + 可选操作按钮。"""
        meta = self._SECTION_META.get(key, ("", key))
        icon, title_key = meta
        count = len(items)

        frame = QFrame(parent)
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # 标题行：图标 + 名称 + 计数
        title_row = QHBoxLayout()
        title_label = QLabel(f"{icon} {_(title_key)}    [ {count} 条 ]")
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        title_row.addWidget(title_label)
        title_row.addStretch()
        layout.addLayout(title_row)

        # 条目列表（只读，最大高度 120px）
        list_widget = QListWidget()
        list_widget.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        list_widget.setMaximumHeight(120)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        for item in items:
            fname = (
                os.path.basename(self._safe_str(getattr(item, "source_path", "")))
                or self._safe_str(getattr(item, "raw_filename", ""))
                or self._safe_str(getattr(item, "std_name", ""))
                or item.get_full_number()
            )
            # pending 分栏追加冲突原因
            if key == "pending":
                reason = self._get_pending_reason(item)
                if reason:
                    fname = f"{fname}  （{reason}）"
            list_widget.addItem(fname)
        layout.addWidget(list_widget)

        # 操作区域
        action_area = QHBoxLayout()
        action_area.addStretch()
        if extra_buttons:
            for btn_text, callback in extra_buttons:
                btn = QPushButton(btn_text)
                btn.clicked.connect(callback)
                action_area.addWidget(btn)
        layout.addLayout(action_area)

        return frame

    @staticmethod
    def _safe_str(value: Any) -> str:
        """确保值为字符串，防止布尔值 False 被隐式转换为 'False' 前缀。"""
        if isinstance(value, bool):
            return ""
        return str(value) if value else ""

    @staticmethod
    def _save_csv(filepath: str, items: list[Any]) -> None:
        """保存条目列表为 CSV 文件。"""
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["标准号", "标准名称", "状态", "文件路径"])
            for item in items:
                writer.writerow(
                    [
                        item.get_full_number(),
                        QuerySummaryMethods._safe_str(getattr(item, "std_name", "")),
                        QuerySummaryMethods._safe_str(getattr(item, "next_action", "")),
                        QuerySummaryMethods._safe_str(getattr(item, "source_path", "")),
                    ]
                )

    def _remove_section_widget(self, key: str) -> None:
        """从汇总弹窗中移除指定分栏 widget（同步删除 + 强制重排）。"""
        widget = self._summary_sections.get(key)
        if widget is None:
            return
        layout = self._summary_container_layout
        if layout is not None:
            layout.removeWidget(widget)
        widget.setParent(None)  # 同步解除父子关系，立即从视觉上移除
        widget.deleteLater()
        del self._summary_sections[key]
        # 强制容器重排布局，消除空白间隙
        if layout is not None:
            layout.invalidate()
            layout.activate()
            if layout.parentWidget():
                layout.parentWidget().update()
        # 更新顶部总条目数
        remaining = len(self._parsed_results)
        if hasattr(self, "_summary_total_label") and self._summary_total_label is not None:
            self._summary_total_label.setText(_("summary_total_records").format(count=remaining))

    def _on_save_section_csv(self, key: str, items: list[Any]) -> None:
        """保存分栏条目为 CSV → 从 _parsed_results 移除 → 移除分栏 UI。"""
        if not items:
            return
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_map = {"pending": f"待确认列表_{ts}.csv", "manual_download": f"手动下载清单_{ts}.csv"}
        default_name = name_map.get(str(key), f"{self._safe_str(key)}_{ts}.csv")
        path, __ = QFileDialog.getSaveFileName(None, _("title_save_csv"), default_name, _("filter_csv_files"))
        if not path:
            return
        try:
            self._save_csv(path, items)
        except OSError as e:
            QMessageBox.warning(None, _("title_save_failed"), _("msg_save_failed").format(error=e))
            return
        action_map = {"pending": "pending", "manual_download": "manual_download"}
        target_action = action_map.get(key, key)
        self._parsed_results = [p for p in self._parsed_results if p.next_action != target_action]
        if key == "pending":
            self._write_pending_to_db(items)
        self._remove_section_widget(key)
        count = len(items)
        msg_key = "msg_pending_saved" if key == "pending" else "msg_manual_saved"
        self.status_changed.emit(_(msg_key).format(count=count))

    def _build_summary_dialog(self, buckets: dict, total: int, has_download: bool) -> QDialog:
        """构建分栏式汇总弹窗。"""
        section_order = ["organize", "normalize", "expire", "pending", "manual_download", "download"]
        self._summary_sections = {}

        dlg = QDialog(self)
        dlg.setWindowTitle(_("summary_title"))
        dlg.resize(800, 600)
        # 禁用 size grip：Windows 深色主题下会渲染为右下角异常像素方块
        dlg.setSizeGripEnabled(False)
        main_layout = QVBoxLayout(dlg)

        self._summary_total_label = QLabel(_("summary_total_records").format(count=total))
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
            if key == "pending":
                extra_buttons = [(_("btn_save_pending_csv"), lambda k=key, it=items: self._on_save_section_csv(k, it))]
            elif key == "manual_download":
                extra_buttons = [(_("btn_save_manual_csv"), lambda k=key, it=items: self._on_save_section_csv(k, it))]
            section = self._create_section(key, items, dlg, extra_buttons=extra_buttons)
            self._summary_sections[key] = section
            container_layout.addWidget(section)
        container_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        download_btn = QPushButton(_("btn_enter_download"))
        download_btn.setDefault(True)
        download_btn.setEnabled(has_download)

        def on_download() -> None:
            dlg.accept()
            self._on_download()

        download_btn.clicked.connect(on_download)
        close_btn = QPushButton(_("btn_close"))
        close_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(download_btn)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)
        return dlg

    def _show_query_summary(self: Any) -> None:
        if not self._parsed_results:
            return
        total = len(self._parsed_results)

        # 将 pending 写入数据库（供"待确认查询"工具使用）
        pending = [p for p in self._parsed_results if p.next_action == "pending"]
        if pending:
            self._write_pending_to_db(pending)

        # 状态通知 + 任务注册
        self.status_changed.emit(_("query_complete").format(total))
        self._project.mark_dirty()
        self._register_task("查询", total, total)
        NotifyService.get().show(
            _("query_toast_title"),
            _("query_toast_msg").format(
                total=total,
                archive=sum(1 for p in self._parsed_results if p.next_action == "archive"),
                pending=sum(1 for p in self._parsed_results if p.next_action == "pending"),
                expire=sum(1 for p in self._parsed_results if p.next_action == "expire"),
            ),
        )

        if self._suppress_dialogs:
            return

        buckets = self._build_buckets()
        has_download = len(buckets.get("download", [])) > 0
        dlg = self._build_summary_dialog(buckets, total, has_download)
        dlg.exec()

        # 清理临时引用
        self._summary_sections = {}
        self._summary_total_label = None
