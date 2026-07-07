# pilotstd/ui/pages/settings/_notification.py
# 通知设置 Tab 构建 mixin — 智能聚合、自动暂停、手动恢复

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .....i18n import _


class _NotificationTab:
    """通知智能聚合：自动暂停、手动恢复、暂停状态显示。"""

    def _build_notification_page(self) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)

        gb = QGroupBox("通知智能聚合")
        form = QFormLayout(gb)
        self.auto_pause_cb = QCheckBox("启用自动暂停")
        self.auto_pause_cb.setChecked(True)
        from pilotstd.core.notification_aggregator import NotificationAggregator

        try:
            agg = NotificationAggregator()
            self.auto_pause_cb.setChecked(agg.auto_pause_enabled)
        except Exception:
            pass
        self.auto_pause_cb.toggled.connect(self._on_auto_pause_toggled)
        hint = QLabel("连续 3 次警告/错误在 30 秒内自动暂停所有弹窗，5 分钟后自动恢复")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(self.auto_pause_cb)
        form.addRow(hint)
        layout.addWidget(gb)

        self.pause_status_label = QLabel("")
        self.pause_status_label.setStyleSheet(
            "color: #856404; background: #fff3cd; padding: 6px 10px; border-radius: 4px;"
        )
        self.pause_status_label.setWordWrap(True)
        self.pause_status_label.hide()
        layout.addWidget(self.pause_status_label)

        resume_btn = QPushButton("立即恢复通知")
        resume_btn.clicked.connect(self._resume_notifications)
        resume_btn.hide()
        self.resume_btn = resume_btn
        layout.addWidget(resume_btn)

        layout.addStretch()
        self._add_page(_("settings_notification"), w)

    def _on_auto_pause_toggled(self, checked: bool) -> None:
        from pilotstd.core.config.manager import ConfigManager

        ConfigManager().set("notification.auto_pause", checked)
        ConfigManager().save()

    def _resume_notifications(self) -> None:
        from pilotstd.core.notification_aggregator import NotificationAggregator

        NotificationAggregator().resume()
        self._update_pause_status()

    def _update_pause_status(self) -> None:
        try:
            from pilotstd.core.notification_aggregator import NotificationAggregator

            state = NotificationAggregator().get_pause_state()
            if state["is_paused"]:
                self.pause_status_label.setText(f"通知已暂停，剩余 {state['remaining_seconds']} 秒后自动恢复")
                self.pause_status_label.show()
                self.resume_btn.show()
            else:
                self.pause_status_label.hide()
                self.resume_btn.hide()
        except Exception:
            self.pause_status_label.hide()
            self.resume_btn.hide()
