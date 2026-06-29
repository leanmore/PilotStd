# pilotstd/ui/widgets/notification_bell_widget.py
# WinUI 端通知铃铛组件 + WebSocket 客户端 + 本地 SQLite 缓存
import json
import os
import sqlite3
from datetime import datetime

import websocket
from PyQt6.QtCore import QPoint, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)


class NotificationItem:
    """通知数据模型。"""

    def __init__(self, data: dict):
        self.id = data.get("id")
        self.event_type = data.get("event_type", "")
        self.title = data.get("title", "")
        self.body = data.get("body", "")
        self.level = data.get("level", "info")
        self.sent_at = data.get("sent_at", "")
        self.is_read = data.get("is_read", False)


class LocalNotificationCache:
    """本地 SQLite 缓存，支持离线查看历史通知。"""

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "notification_cache.db")
            db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                level TEXT DEFAULT 'info',
                sent_at TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_sent_at ON notification_cache(sent_at DESC)")
        conn.commit()
        conn.close()

    def save(self, item: NotificationItem) -> int:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO notification_cache "
            "(event_type, title, body, level, sent_at, is_read) VALUES (?, ?, ?, ?, ?, ?)",
            (item.event_type, item.title, item.body, item.level, item.sent_at, 1 if item.is_read else 0),
        )
        item_id = cursor.lastrowid or 0
        conn.commit()
        conn.close()
        return item_id

    def get_recent(self, limit: int = 20) -> list:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, event_type, title, body, level, sent_at, is_read "
            "FROM notification_cache ORDER BY sent_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            NotificationItem(
                {
                    "id": r[0],
                    "event_type": r[1],
                    "title": r[2],
                    "body": r[3],
                    "level": r[4],
                    "sent_at": r[5],
                    "is_read": bool(r[6]),
                }
            )
            for r in rows
        ]

    def mark_read(self, item_id: int) -> None:
        if not item_id:
            return
        conn = sqlite3.connect(self._db_path)
        conn.execute("UPDATE notification_cache SET is_read = 1 WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

    def mark_all_read(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute("UPDATE notification_cache SET is_read = 1")
        conn.commit()
        conn.close()

    def get_unread_count(self) -> int:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notification_cache WHERE is_read = 0")
        count = cursor.fetchone()[0]
        conn.close()
        return count


class WebSocketClient(QThread):
    """WebSocket 客户端线程，支持自动重连。"""

    message_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url
        self._ws: websocket.WebSocketApp | None = None
        self._running = True
        self._reconnect_delay = 5
        self._max_attempts = 10
        self._attempts = 0

    def run(self) -> None:
        self._connect()

    def _connect(self) -> None:
        while self._running and self._attempts < self._max_attempts:
            try:
                self._ws = websocket.WebSocketApp(
                    self._url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever()
            except Exception as e:
                self.error_occurred.emit(str(e))

            if self._running:
                self._attempts += 1
                self.disconnected.emit(f"断开连接，{self._reconnect_delay}秒后重试...")
                QThread.msleep(self._reconnect_delay * 1000)

    def _on_open(self, _ws: websocket.WebSocketApp) -> None:
        self._attempts = 0
        self.connected.emit()

    def _on_message(self, _ws: websocket.WebSocketApp, message: str) -> None:
        try:
            data = json.loads(message)
            self.message_received.emit(data)
        except Exception as e:
            print(f"解析通知消息失败: {e}")

    def _on_error(self, _ws: websocket.WebSocketApp, error: str) -> None:
        self.error_occurred.emit(str(error))

    def _on_close(self, _ws: websocket.WebSocketApp, status_code: int, msg: str) -> None:
        self.disconnected.emit("连接已断开")

    def stop(self) -> None:
        self._running = False
        if self._ws:
            self._ws.close()
        self.quit()
        self.wait()


class NotificationBellWidget(QWidget):
    """WinUI 通知铃铛组件——工具栏按钮 + 下拉菜单 + WebSocket 实时推送。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cache = LocalNotificationCache()
        self._items: list[NotificationItem] = []
        self._unread_count = self._cache.get_unread_count()
        self._menu: QMenu | None = None

        self._setup_ui()
        self._setup_websocket()
        self._load_cached()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._button = QPushButton("🔔")
        self._button.setFixedSize(36, 36)
        self._button.setStyleSheet("""
            QPushButton {
                font-size: 18px; border: none; background: transparent;
            }
            QPushButton:hover {
                background: rgba(64, 158, 255, 0.1); border-radius: 4px;
            }
        """)
        self._button.clicked.connect(self._toggle_menu)
        layout.addWidget(self._button)
        self._update_badge()

    def _update_badge(self) -> None:
        if self._unread_count > 0:
            self._button.setText(f"🔔 {self._unread_count}")
            self._button.setStyleSheet(
                self._button.styleSheet()
                + """
                QPushButton { color: #409eff; }
            """
            )
        else:
            self._button.setText("🔔")

    def _setup_websocket(self) -> None:
        self._ws_client = WebSocketClient("ws://localhost:8000/api/notification/ws")
        self._ws_client.message_received.connect(self._on_message)
        self._ws_client.connected.connect(self._on_connected)
        self._ws_client.disconnected.connect(self._on_disconnected)
        self._ws_client.error_occurred.connect(self._on_error)
        self._ws_client.start()

    def _load_cached(self) -> None:
        self._items = self._cache.get_recent(20)
        self._unread_count = self._cache.get_unread_count()
        self._update_badge()

    def _on_message(self, data: dict) -> None:
        item = NotificationItem(data)
        item.id = self._cache.save(item)
        self._items.insert(0, item)
        self._unread_count += 1
        self._update_badge()
        if self._menu and self._menu.isVisible():
            self._update_menu()

    def _on_connected(self) -> None:
        print("WebSocket 通知连接成功")

    def _on_disconnected(self, msg: str) -> None:
        print(f"WebSocket 通知断开: {msg}")

    def _on_error(self, msg: str) -> None:
        print(f"WebSocket 通知错误: {msg}")

    def _toggle_menu(self) -> None:
        if self._menu is None:
            self._menu = self._create_menu()
        self._update_menu()
        pos = self._button.mapToGlobal(QPoint(0, self._button.height()))
        self._menu.exec(pos)

    def _create_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setMinimumWidth(380)
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px 0;
            }
        """)
        return menu

    def _update_menu(self) -> None:
        if self._menu is None:
            return
        self._menu.clear()

        # 标题行
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel("通知")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title)
        if self._unread_count > 0:
            mark_all = QPushButton("全部标记已读")
            mark_all.setStyleSheet("font-size: 12px; color: #409eff; background: none; border: none;")
            mark_all.clicked.connect(self._mark_all_read)
            header_layout.addWidget(mark_all)
        header_action = QWidgetAction(self._menu)
        header_action.setDefaultWidget(header)
        self._menu.addAction(header_action)
        self._menu.addSeparator()

        # 列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(300)
        scroll.setStyleSheet("border: none; background: transparent;")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        for item in self._items[:10]:
            content_layout.addWidget(self._create_item_widget(item))
        if not self._items:
            empty = QLabel("暂无通知")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("padding: 40px 0; color: #999;")
            content_layout.addWidget(empty)
        scroll.setWidget(content)
        scroll_action = QWidgetAction(self._menu)
        scroll_action.setDefaultWidget(scroll)
        self._menu.addAction(scroll_action)

        # 底部
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        view_all = QPushButton("查看全部通知 →")
        view_all.setStyleSheet("font-size: 12px; color: #409eff; background: none; border: none;")
        view_all.clicked.connect(self._view_all)
        footer_layout.addWidget(view_all, alignment=Qt.AlignmentFlag.AlignCenter)
        footer_action = QWidgetAction(self._menu)
        footer_action.setDefaultWidget(footer)
        self._menu.addAction(footer_action)

    def _create_item_widget(self, item: NotificationItem) -> QWidget:
        widget = QWidget()
        base_style = "padding: 8px 12px; border-bottom: 1px solid #f0f0f0;"
        hover_style = "QWidget:hover { background: #f0f7ff; }"
        if not item.is_read:
            widget.setStyleSheet(f"QWidget {{ {base_style} background: #f0f7ff; }} {hover_style}")
        else:
            widget.setStyleSheet(f"QWidget {{ {base_style} }} {hover_style}")

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 6, 12, 6)

        if not item.is_read:
            dot = QLabel("●")
            dot.setStyleSheet("color: #409eff; font-size: 10px; border: none; background: transparent;")
            layout.addWidget(dot)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(2)
        content_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(item.title)
        title_label.setStyleSheet("font-weight: 500; font-size: 13px; color: #333; border: none;")
        content_layout.addWidget(title_label)

        body_text = item.body[:60] + ("..." if len(item.body) > 60 else "")
        body_label = QLabel(body_text)
        body_label.setStyleSheet("font-size: 12px; color: #666; border: none;")
        content_layout.addWidget(body_label)

        time_label = QLabel(self._format_time(item.sent_at))
        time_label.setStyleSheet("font-size: 11px; color: #999; border: none;")
        content_layout.addWidget(time_label)
        layout.addWidget(content)

        if not item.is_read:
            mark_btn = QPushButton("✓")
            mark_btn.setFixedSize(24, 24)
            mark_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #d9d9d9; border-radius: 4px;
                    background: white; font-size: 12px; color: #409eff;
                }
                QPushButton:hover {
                    background: #409eff; color: white;
                }
            """)
            # 用默认参数捕获当前 item，避免闭包延迟绑定
            iid = item.id
            mark_btn.clicked.connect(lambda checked, iid=iid: self._mark_read_by_id(iid))
            layout.addWidget(mark_btn)

        iid = item.id
        widget.mousePressEvent = lambda e, iid=iid: self._on_item_click(iid)
        return widget

    @staticmethod
    def _format_time(iso_string: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            now = datetime.now()
            diff = (now - dt).total_seconds()
            if diff < 60:
                return "刚刚"
            if diff < 3600:
                return f"{int(diff / 60)}分钟前"
            if diff < 86400:
                return f"{int(diff / 3600)}小时前"
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return iso_string

    def _on_item_click(self, item_id: int) -> None:
        if self._menu:
            self._menu.close()
        self._mark_read_by_id(item_id)
        # TODO: 未来可扩展跳转到通知详情

    def _mark_read_by_id(self, item_id: int) -> None:
        if not item_id:
            return
        self._cache.mark_read(item_id)
        for item in self._items:
            if item.id == item_id:
                item.is_read = True
                break
        self._unread_count = max(0, self._unread_count - 1)
        self._update_badge()
        if self._menu and self._menu.isVisible():
            self._update_menu()

    def _mark_all_read(self) -> None:
        self._cache.mark_all_read()
        for item in self._items:
            item.is_read = True
        self._unread_count = 0
        self._update_badge()
        if self._menu and self._menu.isVisible():
            self._update_menu()

    def _view_all(self) -> None:
        if self._menu:
            self._menu.close()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_ws_client"):
            self._ws_client.stop()
        event.accept()
