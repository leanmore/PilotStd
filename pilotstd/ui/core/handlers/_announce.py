# 模块：项目//核心/处理器/_脚本
"""AnnounceUIHandler — 公告检查 UI 状态管理，替代 AnnounceMixin。"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from PyQt6 import sip as _sip

# .()检查++对象存活，防御异步回调中已析构的竞态
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

if TYPE_CHECKING:
    from ....core.config import ConfigManager

from ....i18n import _
from ...workers import AnnounceWorker
from .announce_flow_engine import AnnounceFlowEngine

logger = logging.getLogger(__name__)


class AnnounceUIHandler:
    """公告检查 UI 状态管理。

    职责：
      - 前置条件检查（Web 缓存互斥）
      - 构建进度对话框 + 后台 Worker 管理
      - 结果展示与失败记录落盘

    注入依赖：
      - mgr: 业务门面
      - config: 配置管理器
      - parent_widget: 对话框父窗口（QWidget）
      - pause_event: 暂停事件
    """

    def __init__(
        self,
        mgr: Any,
        config: ConfigManager,
        parent_widget: Any,
        pause_event: Any = None,
    ) -> None:
        self._mgr = mgr
        self._config = config
        self._parent = parent_widget
        self._pause_event = pause_event
        # 实例（壳，在__中创建）
        self._ann_worker: AnnounceWorker | None = None
        # 对话框控件
        self._ann_progress_label: QLabel | None = None
        self._ann_progress_bar: QProgressBar | None = None
        self._ann_start_date: QDateEdit | None = None
        self._engine = AnnounceFlowEngine()

    # ── 公开方法 ─────────────────────────────────────────────

    def on_check_announcements(self) -> None:
        """手动检查标准公告更新（工具菜单触发）。"""
        if not self.check_guard():
            return
        worker = self.run_dialog()
        self.show_result(worker)

    def stop_workers(self) -> None:
        """停止正在运行的公告 Worker（由 MainWindow._stop_workers 委托调用）。"""
        w = self._ann_worker
        if w is not None and w.isRunning():
            w.stop()
            w.quit()
            if not w.wait(5000):
                w.terminate()
                w.wait()

    # ── 内部方法 ─────────────────────────────────────────────

    def _parse_announcement(self, raw: dict[str, Any]) -> dict[str, Any]:
        """委托 AnnounceFlowEngine 标准化原始公告数据。"""
        return self._engine.parse_announcement(raw)

    def _filter_by_status(self, items: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
        """委托 AnnounceFlowEngine 按状态过滤公告。"""
        return self._engine.filter_by_status(items, status)

    def check_guard(self) -> bool:
        """前置检查：Manager 就绪 + Web 公告缓存互斥。返回 True 表示可继续。"""
        if self._config.get("query.use_announcement_match", False):
            logger.info("本地公告检查被禁用（use_announcement_match=True）")
            QMessageBox.information(
                self._parent,
                _("toolbar_announce"),
                "当前已启用 Web 端公告缓存模式，本地公告检查功能已禁用。",
            )
            return False
        return True

    def run_dialog(self) -> AnnounceWorker:
        """构建进度对话框 + 启动后台公告检查 Worker + 模态执行。返回 Worker。"""
        dlg = QDialog(self._parent)
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
            self._mgr, since_date=since_date, pause_event=self._pause_event, parent=self._parent
        )
        self._ann_worker.progress.connect(self._on_progress)
        self._ann_worker.finished_signal.connect(dlg.accept)
        self._ann_worker.error.connect(self._on_worker_error)
        cancel_btn.clicked.connect(self._ann_worker.stop)
        self._ann_worker.start()
        dlg.exec()
        return self._ann_worker

    def _on_worker_error(self, msg: str) -> None:
        """Worker 异常时弹出本地通知。"""
        from ....platform.notify import NotifyService

        NotifyService.get().show("工作线程异常", f"announce: {msg}", duration=5000)

    def show_result(self, worker: AnnounceWorker) -> None:
        """弹窗展示公告检查结果。"""
        from ....core.config import get_data_dir

        if worker._stopped:
            QMessageBox.information(self._parent, _("announcement_check"), _("announcement_cancelled"))
        elif worker._error and not worker._matched:
            QMessageBox.warning(self._parent, _("announcement_check"), worker._error)
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
                self._parent,
                _("announcement_check"),
                _("announcement_complete").format(total=worker._total, matched=worker._matched) + fail_msg,
            )
            from ....platform.notify import NotifyService

            if worker._matched > 0:
                NotifyService.get().show(
                    _("announcement_complete_toast"),
                    _("announcement_complete_detail").format(total=worker._total, matched=worker._matched),
                )

    def _on_progress(self, current: int, total: int, matched: int) -> None:
        """更新公告检查进度——防御 Widget 已销毁的竞态条件。
        sip.isdeleted 检查 C++ 对象是否已析构，比 try/except RuntimeError 更精确。
        """
        if self._ann_progress_bar is not None and not _sip.isdeleted(self._ann_progress_bar):
            self._ann_progress_bar.setMaximum(total)
            self._ann_progress_bar.setValue(current)
        if self._ann_progress_label is not None and not _sip.isdeleted(self._ann_progress_label):
            self._ann_progress_label.setText(
                _("announcement_progress").format(current=current, total=total, matched=matched)
            )
