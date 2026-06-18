# pilotstd/ui/controllers/announce_mixin.py
# 标准公告更新检查 — 从 main_window.py 提取

import logging
import os

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ...core.config import get_data_dir
from ...i18n import _
from ..workers import AnnounceWorker

logger = logging.getLogger(__name__)


class AnnounceMixin:
    """公告更新检查。依赖 self._mgr.file_index, self._pause_event。"""

    # ── 公告检查 ─────────────────────────────────────────

    def _on_check_announcements(self):
        """手动检查标准公告更新（工具菜单触发）。
        弹出进度对话框，后台分批抓取公告、解析标准、比对缓存。"""
        if not self._mgr_ready:
            return
        # 进度对话框
        dlg = QDialog(self)
        dlg.setWindowTitle(_("announcement_check"))
        dlg.setMinimumWidth(450)
        layout = QVBoxLayout(dlg)
        enabled = self._config.get("announcement.enabled", False)
        if enabled:
            self._ann_progress_label = QLabel(_("announcement_checking"))
        else:
            self._ann_progress_label = QLabel(_("announcement_disabled"))
        layout.addWidget(self._ann_progress_label)

        # 起始日期筛选 — 默认往前3个月
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel(_("start_date")))
        self._ann_start_date = QDateEdit()
        self._ann_start_date.setCalendarPopup(True)
        self._ann_start_date.setDate(QDate.currentDate().addMonths(-3))
        date_layout.addWidget(self._ann_start_date)
        date_layout.addStretch()
        layout.addLayout(date_layout)

        self._ann_progress_bar = QProgressBar()
        layout.addWidget(self._ann_progress_bar)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton(_("btn_cancel"))
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # 后台线程
        since_date = self._ann_start_date.date().toString("yyyy-MM-dd")
        self._ann_worker = AnnounceWorker(self._mgr, since_date=since_date, pause_event=self._pause_event, parent=self)
        self._ann_worker.progress.connect(self._on_ann_progress)
        self._ann_worker.finished_signal.connect(dlg.accept)
        cancel_btn.clicked.connect(self._ann_worker.stop)
        self._ann_worker.start()
        dlg.exec()

        # 弹窗汇总
        if self._ann_worker._stopped:
            QMessageBox.information(self, _("announcement_check"),
                                    _("announcement_cancelled"))
        elif self._ann_worker._error and not self._ann_worker._matched:
            QMessageBox.warning(self, _("announcement_check"),
                                self._ann_worker._error)
        else:
            failures = getattr(self._ann_worker, '_failures', [])
            fail_msg = ""
            if failures:
                import json
                fail_path = os.path.join(get_data_dir(), "announce_failures.json")
                os.makedirs(os.path.dirname(fail_path), exist_ok=True)
                with open(fail_path, "w", encoding="utf-8") as f:
                    json.dump(failures, f, ensure_ascii=False, indent=2)
                fail_msg = _("announcement_failures").format(
                    count=len(failures), path=fail_path)
            QMessageBox.information(self, _("announcement_check"),
                _("announcement_complete").format(
                    total=self._ann_worker._total,
                    matched=self._ann_worker._matched) + fail_msg)
            # Toast 通知
            from ...core.notify import NotifyService
            if self._ann_worker._matched > 0:
                NotifyService.get().show(
                    _("announcement_complete_toast"),
                    _("announcement_complete_detail").format(
                        total=self._ann_worker._total,
                        matched=self._ann_worker._matched))

    def _on_ann_progress(self, current: int, total: int, matched: int):
        """更新公告检查进度。"""
        self._ann_progress_bar.setMaximum(total)
        self._ann_progress_bar.setValue(current)
        self._ann_progress_label.setText(
            _("announcement_progress").format(current=current, total=total, matched=matched))
