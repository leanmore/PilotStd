# pilotstd/ui/pending_query_dialog.py
# 待确认二次查询对话框 — 从 main_window.py 提取

import logging
from typing import Any, Optional

from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ..i18n import _
from .workers import QueryWorker

logger = logging.getLogger(__name__)


class PendingQueryDialog(QDialog):
    """待确认二次查询对话框：选择网站/本地数据库、等待冷却、执行查询。"""

    LOCAL_DB_KEY = "_local_db"  # 本地数据库选项的内部标识

    def __init__(self, manager: Any, parsed_list: Any, parent: Any = None) -> None:
        """manager: StandardManager 实例，用于查询及站点管理。"""
        self._init_fields(manager, parsed_list, parent)

        self.setWindowTitle(_("title_pending_query"))
        self.setMinimumSize(540, 320)
        layout = QVBoxLayout(self)

        layout.addWidget(self._build_info_label())
        layout.addWidget(self._build_site_selection_group())

        progress, btn_row, cancel_btn = self._build_progress_and_buttons()
        layout.addWidget(progress)
        layout.addLayout(btn_row)

        self._connect_signals_and_timer(cancel_btn)

    def _init_fields(self, manager: Any, parsed_list: Any, parent: Any) -> None:
        """基类构造 + 成员变量初始化。"""
        super().__init__(parent)
        self._mgr = manager
        self._parsed_list = parsed_list
        self._selected_site: str = ""
        self._results: list[Any] = []
        self._worker: Optional[QThread] = None
        self._countdown_active = False
        self._has_local_db = self._check_local_db_available()

    def _build_info_label(self) -> QLabel:
        """创建信息栏 QLabel。"""
        info = QLabel(_("pq_info_count").format(count=len(self._parsed_list)))
        info.setStyleSheet("font-weight: bold;")
        return info

    def _build_site_selection_group(self) -> QGroupBox:
        """创建站点单选按钮组（QGroupBox + QGridLayout）。"""
        len(self._mgr.get_query_sites()) + (1 if self._has_local_db else 0)
        gb = QGroupBox(_("pq_source_group"))
        gb_layout = QGridLayout(gb)
        gb_layout.setColumnStretch(0, 1)
        gb_layout.setColumnStretch(1, 1)
        self._radio_group: dict[str, QRadioButton] = {}
        self._cooldown_labels: dict[str, QLabel] = {}

        all_sites = self._mgr.get_query_sites()
        self._build_site_grid(gb_layout, all_sites)
        if self._has_local_db:
            self._build_local_db_option(gb_layout, all_sites)
        return gb

    def _build_site_grid(self, gb_layout: QGridLayout, all_sites: list[str]) -> None:
        """在网格中排列各站点单选按钮。"""
        for i, name in enumerate(all_sites):
            adapter = self._mgr.get_site_adapter(name)
            label = adapter.site_label if adapter else name
            row, col = i // 2, i % 2
            item_layout = QHBoxLayout()
            rb = QRadioButton(label)
            self._radio_group[name] = rb
            cd_label = QLabel("")
            cd_label.setStyleSheet("color: #999; font-size: 9pt;")
            self._cooldown_labels[name] = cd_label
            item_layout.addWidget(rb)
            item_layout.addStretch()
            item_layout.addWidget(cd_label)
            gb_layout.addLayout(item_layout, row, col)

    def _build_local_db_option(self, gb_layout: QGridLayout, all_sites: list[str]) -> None:
        """添加本地数据库单选选项。"""
        i = len(all_sites)
        row, col = i // 2, i % 2
        item_layout = QHBoxLayout()
        rb = QRadioButton(_("pq_local_db_label"))
        tip = QLabel(_("pq_cached_label"))
        tip.setStyleSheet("color: #2a7d2a; font-size: 9pt;")
        self._radio_group[self.LOCAL_DB_KEY] = rb
        self._cooldown_labels[self.LOCAL_DB_KEY] = QLabel("")
        item_layout.addWidget(rb)
        item_layout.addStretch()
        item_layout.addWidget(tip)
        gb_layout.addLayout(item_layout, row, col)

    def _build_progress_and_buttons(self) -> tuple[QProgressBar, QHBoxLayout, QPushButton]:
        """创建进度条 + 按钮行。返回 (progress, btn_row, cancel_btn)。"""
        self._progress = QProgressBar()
        self._progress.setVisible(False)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton(_("pq_start_query_btn"))
        cancel_btn = QPushButton(_("btn_cancel"))
        btn_row.addStretch()
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(cancel_btn)

        return self._progress, btn_row, cancel_btn

    def _connect_signals_and_timer(self, cancel_btn: QPushButton) -> None:
        """连接按钮信号 + 启动冷却刷新定时器。"""
        self._start_btn.clicked.connect(self._on_start)
        cancel_btn.clicked.connect(self.reject)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_cooldown)
        self._refresh_timer.start(1000)
        self._refresh_cooldown()

    def reject(self) -> None:
        self._cleanup()
        super().reject()

    def closeEvent(self, event: Any) -> None:
        self._cleanup()
        super().closeEvent(event)

    def _cleanup(self) -> None:
        self._refresh_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            if not self._worker.wait(3000):
                self._worker.terminate()
                self._worker.wait()

    def _refresh_cooldown(self) -> None:
        """每秒刷新冷却显示。若所选站点冷却结束则自动发起查询。"""
        all_sites = self._mgr.get_query_sites()
        for name in all_sites:
            remaining = self._mgr.get_site_cooldown(name)
            rb = self._radio_group.get(name)
            cd_label = self._cooldown_labels.get(name)
            if not rb or not cd_label:
                continue
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                cd_label.setText(_("pq_wait_cooldown_btn").format(min=mins, sec=secs))
                rb.setEnabled(False)
            else:
                cd_label.setText("")
                rb.setEnabled(True)

        # 用户选中了冷却站点 → 冷却结束自动查询
        if self._countdown_active and self._selected_site:
            if self._mgr.get_site_cooldown(self._selected_site) <= 0:
                self._countdown_active = False
                self._start_btn.setEnabled(True)
                self._start_btn.setText(_("pq_start_query_btn"))
                self._do_query()

    def _on_start(self) -> None:
        """用户点击开始查询。"""
        for name, rb in self._radio_group.items():
            if rb.isChecked():
                self._selected_site = name
                break
        if not self._selected_site:
            QMessageBox.warning(self, _("title_hint"), _("select_site_first"))
            return

        # 检查重试次数限制（每个待确认标准最多自动查询 3 次）
        for parsed in self._parsed_list:
            num = parsed.get_full_number()
            if self._mgr.is_requery_exhausted(num):
                QMessageBox.warning(
                    self,
                    _("title_hint"),
                    f"「{num}」已查询 3 次仍无匹配，请手动搜索确认。",
                )
                return
            count = self._mgr.get_requery_count(num)
            if count >= 2:
                reply = QMessageBox.question(
                    self,
                    _("title_hint"),
                    f"「{num}」已查询 {count} 次仍无匹配，是否继续？",
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        # 本地数据库直接查询，无冷却
        if self._selected_site == self.LOCAL_DB_KEY:
            self._do_local_query()
            return

        remaining = self._mgr.get_site_cooldown(self._selected_site)
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            if remaining > 14400:
                hours = int(remaining // 3600)
                QMessageBox.information(
                    self,
                    _("title_site_cooldown"),
                    _("msg_cool_down_info").format(hours=hours),
                )
            self._countdown_active = True
            self._start_btn.setEnabled(False)
            self._start_btn.setText(_("pq_wait_cooldown_btn").format(min=mins, sec=secs))
            self._refresh_timer.start(1000)
            return

        self._do_query()

    def _do_query(self) -> None:
        """执行查询。"""
        self._start_btn.setEnabled(False)
        self._start_btn.setText(_("pq_querying_btn"))
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._parsed_list))

        # 禁用站点选择
        for rb in self._radio_group.values():
            rb.setEnabled(False)

        # 验证所选站点适配器存在
        adapter = self._mgr.query_engine.get_adapter(self._selected_site)
        if not adapter:
            QMessageBox.critical(self, _("title_error"), f"查询站点不可用: {self._selected_site}")
            self.reject()
            return

        # QueryWorker 接收 site 参数，由 manager.query() 透传给路由引擎
        self._results = []
        self._worker = QueryWorker(self._mgr, self._parsed_list, site=self._selected_site, parent=self)
        self._worker.result_ready.connect(self._on_single_result)
        self._worker.finished_signal.connect(self._on_query_finished)
        self._worker.error.connect(lambda msg: self._notify_error("query_pending", msg))
        self._worker.start()

    def _notify_error(self, worker_name: str, error_msg: str) -> None:
        """Worker 异常时发送通知（失败静默）。"""
        try:
            if hasattr(self._mgr, "notification_mgr"):
                self._mgr.notification_mgr.send_event("worker_error", {"worker": worker_name, "error": error_msg})
        except Exception:
            pass

    def _check_local_db_available(self) -> bool:
        """检查用户是否已开启公告数据库（设置→网络→标准公告自动更新）。"""
        try:
            from ..core.config import ConfigManager

            cfg = ConfigManager()
            return cfg.get("announcement.enabled", False)
        except Exception:
            logger.debug("待确认查询公告设置失败", exc_info=True)
            return False

    def _do_local_query(self) -> None:
        """本地数据库查询（委托 manager）。"""
        self._start_btn.setEnabled(False)
        self._start_btn.setText(_("pq_query_local_btn"))
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._parsed_list))

        self._results = self._mgr.query_local_cache(self._parsed_list)
        self._progress.setValue(len(self._parsed_list))
        self._on_query_finished(None)

    def _on_single_result(self, idx: int, result: Any) -> None:
        self._results.append((idx, result))
        self._progress.setValue(len(self._results))

    def _on_query_finished(self, _results: Any) -> None:
        self._refresh_timer.stop()
        self._start_btn.setText(_("completed"))
        total = len(self._parsed_list)
        found = sum(1 for _, r in self._results if r.standard_name)
        failed = total - found
        # 更新重试计数
        for idx, result in self._results:
            parsed = self._parsed_list[idx]
            num = parsed.get_full_number()
            if not (result and result.standard_name):
                new_count = self._mgr.increment_requery_count(num)
                if new_count >= 3:
                    self._mgr.mark_manual_required(num)
        QMessageBox.information(
            self,
            _("title_pending_query_complete"),
            _("msg_pending_query_complete").format(found=found, failed=failed),
        )
        self.accept()

    def get_results(self) -> list[Any]:
        return self._results
