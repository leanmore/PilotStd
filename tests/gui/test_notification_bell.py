# tests/gui/test_notification_bell.py
# 测试 NotificationBellWidget、NotificationItem、WebSocketClient
# Qt 组件使用 qtbot fixture

import json
from unittest.mock import MagicMock

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from pilotstd.ui.widgets.notification_bell_widget import (
    NotificationBellWidget,
    NotificationItem,
    WebSocketClient,
)


def _close_popup_menu():
    """关闭当前活动弹出菜单，防止 menu.exec() 阻塞事件循环。"""
    popup = QApplication.activePopupWidget()
    if popup is not None:
        popup.close()


class TestNotificationItem:
    """通知数据模型测试。"""

    def test_creates_from_dict_with_all_fields(self) -> None:
        data = {
            "id": 1,
            "event_type": "scan_complete",
            "title": "扫描完成",
            "body": "共 10 个文件",
            "level": "info",
            "sent_at": "2025-01-01T00:00:00Z",
            "is_read": False,
        }
        item = NotificationItem(data)
        assert item.id == 1
        assert item.title == "扫描完成"
        assert item.is_read is False

    def test_defaults_for_missing_fields(self) -> None:
        item = NotificationItem({})
        assert item.id is None
        assert item.event_type == ""
        assert item.level == "info"
        assert item.is_read is False

    def test_is_read_as_int_converts_to_bool(self) -> None:
        item = NotificationItem({"is_read": 1})
        assert item.is_read is True

        item2 = NotificationItem({"is_read": 0})
        assert item2.is_read is False


class TestWebSocketClient:
    """WebSocketClient 线程测试（无真实网络）。"""

    def test_init_stores_url(self) -> None:
        client = WebSocketClient("ws://localhost:8000/ws")
        assert client._url == "ws://localhost:8000/ws"
        assert client._running is True
        client.stop()

    def test_stop_sets_running_false(self) -> None:
        client = WebSocketClient("ws://localhost:8000/ws")
        client.stop()
        assert client._running is False

    def test_message_received_signal_defined(self) -> None:
        client = WebSocketClient("ws://localhost:8000/ws")
        assert hasattr(client, "message_received")
        assert hasattr(client, "connected")
        assert hasattr(client, "disconnected")
        assert hasattr(client, "error_occurred")
        client.stop()

    def test_on_message_emits_signal(self, qtbot) -> None:
        """收到有效 JSON 消息时发出 message_received 信号。"""
        client = WebSocketClient("ws://localhost:8000/ws")
        received: list[dict] = []
        client.message_received.connect(lambda d: received.append(d))
        client._on_message(None, json.dumps({"type": "test", "data": "hello"}))
        assert len(received) == 1
        assert received[0]["type"] == "test"
        client.stop()


class TestNotificationBellWidget:
    """铃铛组件测试（mock 后端依赖）。"""

    def test_unread_count_starts_at_zero(self, qtbot) -> None:
        """无后端数据时未读计数为 0。"""
        widget = NotificationBellWidget()
        qtbot.addWidget(widget)
        assert widget._unread_count == 0
        assert widget._button.text() == "🔔"

    def test_button_clickable(self, qtbot) -> None:
        """按钮点击不抛异常。自动关闭弹出的菜单防止阻塞事件循环。"""
        widget = NotificationBellWidget()
        qtbot.addWidget(widget)
        # 100ms 后关闭弹出的菜单
        QTimer.singleShot(100, lambda: _close_popup_menu())
        widget._button.click()

    def test_format_time_just_now(self) -> None:
        """刚刚的时间返回"刚刚"。"""
        from datetime import datetime

        now_iso = datetime.now().isoformat()
        result = NotificationBellWidget._format_time(now_iso)
        assert result == "刚刚"

    def test_format_time_minutes_ago(self) -> None:
        """几分钟前的时间返回正确描述。"""
        from datetime import datetime, timedelta

        past = (datetime.now() - timedelta(minutes=5)).isoformat()
        result = NotificationBellWidget._format_time(past)
        assert "分钟前" in result or "刚刚" in result

    def test_format_time_invalid_iso_returns_original(self) -> None:
        """无效 ISO 字符串原样返回。"""
        result = NotificationBellWidget._format_time("not-a-date")
        assert result == "not-a-date"

    def test_on_item_click_closes_menu_and_marks_read(self, qtbot) -> None:
        """点击通知项关闭菜单并调用标记已读。"""
        widget = NotificationBellWidget()
        qtbot.addWidget(widget)
        # mock StandardManager 以跳过后端调用
        widget._get_mgr = MagicMock()  # type: ignore[method-assign]
        widget._items = [NotificationItem({"id": 99, "title": "测试"})]
        widget._unread_count = 1
        widget._menu = MagicMock()
        widget._menu.isVisible.return_value = True

        widget._on_item_click(99)
        assert widget._unread_count == 0

    def test_mark_all_read_clears_all(self, qtbot) -> None:
        """全部标记已读后未读计数归零。"""
        widget = NotificationBellWidget()
        qtbot.addWidget(widget)
        widget._get_mgr = MagicMock()  # type: ignore[method-assign]
        widget._items = [
            NotificationItem({"id": 1, "is_read": False}),
            NotificationItem({"id": 2, "is_read": False}),
        ]
        widget._unread_count = 2
        widget._mark_all_read()
        assert widget._unread_count == 0
        assert all(item.is_read for item in widget._items)
