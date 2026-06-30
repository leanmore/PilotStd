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

    def _check_announce_guard(self) -> bool:
        """前置检查：Manager 就绪 + Web 公告缓存互斥。返回 True 表示可继续。"""
        if not self._mgr_ready:
            return False
        if self._config.get("query.use_announcement_match", False):
            logger.info("本地公告检查被禁用（use_announcement_match=True）")
            QMessageBox.information(
                self, "公告检查", "当前已启用 Web 端公告缓存模式，本地公告检查功能已禁用。"
            )
            return False
        return True

    def _run_announce_dialog(self) -> AnnounceWorker:
        """构建进度对话框 + 启动后台公告检查 Worker + 模态执行。返回 Worker。"""
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

        since_date = self._ann_start_date.date().toString("yyyy-MM-dd")
        self._ann_worker = AnnounceWorker(
            self._mgr, since_date=since_date, pause_event=self._pause_event, parent=self
        )
        self._ann_worker.progress.connect(self._on_ann_progress)
        self._ann_worker.finished_signal.connect(dlg.accept)
        cancel_btn.clicked.connect(self._ann_worker.stop)
        self._ann_worker.start()
        dlg.exec()
        return self._ann_worker

    def _show_announce_result(self, worker: AnnounceWorker) -> None:
        """弹窗展示公告检查结果：取消/异常/完成 + 失败列表落盘 + Toast 通知。"""
        if worker._stopped:
            QMessageBox.information(self, _("announcement_check"), _("announcement_cancelled"))
        elif worker._error and not worker._matched:
            QMessageBox.warning(None, _("announcement_check"), worker._error)
        else:
            failures = getattr(worker, "_failures", [])
            fail_msg = ""
            if failures:
                import json

                fail_path = os.path.join(get_data_dir(), "announce_failures.json")
                os.makedirs(os.path.dirname(fail_path), exist_ok=True)
                with open(fail_path, "w", encoding="utf-8") as f:
                    json.dump(failures, f, ensure_ascii=False, indent=2)
                fail_msg = _("announcement_failures").format(count=len(failures), path=fail_path)
            QMessageBox.information(
                self,
                _("announcement_check"),
                _("announcement_complete").format(total=worker._total, matched=worker._matched) + fail_msg,
            )
            from ...platform.notify import NotifyService

            if worker._matched > 0:
                NotifyService.get().show(
                    _("announcement_complete_toast"),
                    _("announcement_complete_detail").format(total=worker._total, matched=worker._matched),
                )

    def _on_check_announcements(self) -> None:
        """手动检查标准公告更新（工具菜单触发）。"""
        if not self._check_announce_guard():
            return

        worker = self._run_announce_dialog()
        self._show_announce_result(worker)

    def _on_ann_progress(self, current: int, total: int, matched: int) -> None:
        """更新公告检查进度。"""
        self._ann_progress_bar.setMaximum(total)
        self._ann_progress_bar.setValue(current)
        self._ann_progress_label.setText(
            _("announcement_progress").format(current=current, total=total, matched=matched)
        )
