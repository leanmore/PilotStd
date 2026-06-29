# docker/websocket.py
# WebSocket 通知推送服务 — 维护活跃连接池，支持广播推送
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class NotificationConnectionManager:
    """管理所有活跃的 WebSocket 连接。"""

    def __init__(self) -> None:
        self._active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.add(websocket)
        logger.info("WebSocket 连接已建立，当前连接数: %d", len(self._active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._active_connections.discard(websocket)
        logger.info("WebSocket 连接已断开，当前连接数: %d", len(self._active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._active_connections:
            return
        data = json.dumps(message, ensure_ascii=False)
        disconnected: set[WebSocket] = set()
        for conn in self._active_connections:
            try:
                await conn.send_text(data)
            except Exception:
                disconnected.add(conn)
        for conn in disconnected:
            self.disconnect(conn)

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)


# 全局单例
_ws_manager = NotificationConnectionManager()


def get_ws_manager() -> NotificationConnectionManager:
    return _ws_manager


async def websocket_endpoint(websocket: WebSocket) -> None:
    await _ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_manager.disconnect(websocket)
    except Exception as e:
        logger.exception("WebSocket 异常: %s", e)
        _ws_manager.disconnect(websocket)
