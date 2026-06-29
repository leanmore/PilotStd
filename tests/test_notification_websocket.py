# tests/test_notification_websocket.py
# 通知系统 WebSocket 连接管理测试
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import AsyncMock, MagicMock


class TestNotificationWebSocket(unittest.TestCase):
    """测试 NotificationConnectionManager。"""

    def setUp(self):
        # 每次测试前重新导入以获取新实例
        import docker.websocket as ws_module

        self.ws_module = ws_module

    def test_manager_singleton(self):
        """get_ws_manager 应返回同一实例。"""
        mgr1 = self.ws_module.get_ws_manager()
        mgr2 = self.ws_module.get_ws_manager()
        self.assertIs(mgr1, mgr2)

    def test_connection_count_starts_at_zero(self):
        """初始连接数应为 0。"""
        mgr = self.ws_module.NotificationConnectionManager()
        self.assertEqual(mgr.connection_count, 0)

    def test_connect_increments_count(self):
        """连接后计数应增加。"""
        mgr = self.ws_module.NotificationConnectionManager()
        mock_ws = MagicMock()
        mgr._active_connections.add(mock_ws)
        self.assertEqual(mgr.connection_count, 1)

    def test_disconnect_decrements_count(self):
        """断开后计数应减少。"""
        mgr = self.ws_module.NotificationConnectionManager()
        mock_ws = MagicMock()
        mgr._active_connections.add(mock_ws)
        self.assertEqual(mgr.connection_count, 1)
        mgr.disconnect(mock_ws)
        self.assertEqual(mgr.connection_count, 0)

    def test_broadcast_to_no_connections(self):
        """无连接时广播不应出错。"""
        mgr = self.ws_module.NotificationConnectionManager()
        # 同步执行需要使用 asyncio.run
        import asyncio

        asyncio.run(mgr.broadcast({"test": "data"}))
        # 不应抛出异常

    def test_broadcast_sends_to_all(self):
        """广播应发送到所有活跃连接。"""
        import asyncio

        mgr = self.ws_module.NotificationConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        mgr._active_connections = {mock_ws1, mock_ws2}
        asyncio.run(mgr.broadcast({"event_type": "test"}))
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()

    def test_broadcast_cleans_disconnected(self):
        """发送失败时应清理断开的连接。"""
        import asyncio

        mgr = self.ws_module.NotificationConnectionManager()
        mock_good = AsyncMock()
        mock_good.send_text = AsyncMock()
        mock_bad = AsyncMock()
        mock_bad.send_text = AsyncMock(side_effect=Exception("Connection lost"))
        mgr._active_connections = {mock_good, mock_bad}
        asyncio.run(mgr.broadcast({"test": "data"}))
        mock_good.send_text.assert_called_once()
        self.assertNotIn(mock_bad, mgr._active_connections)
