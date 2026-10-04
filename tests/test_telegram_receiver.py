"""阶段 B2b-3：Telegram 接收通道（长轮询默认 / webhook 可选）。

设计依据：裁决 B2b-3。端到端（真实 TG 机器人）标注"部署后取证"，不阻塞本批。
"""

import json
import threading
import time
from unittest.mock import patch

from pilotstd.core.notification.telegram_receiver import (
    MODE_LONG_POLL,
    MODE_WEBHOOK,
    TelegramReceiver,
    mode_from_config,
)


class _Resp:
    """真实上下文管理器替身（`with` 按类型查找 `__enter__`）。"""

    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _update(update_id: int, action: str = "ignore", token: str = "7:1") -> dict:
    return {
        "update_id": update_id,
        "callback_query": {"id": f"cb-{update_id}", "data": f"{action}:{token}", "from": {"id": 9}},
    }


# 模块级离线兜底：本文件任何路径都不得真的连 Telegram（离线 CI 前提）；
# 需要具体响应的用例用更内层的 patch 覆盖它。
_OFFLINE_PATCH = patch(
    "pilotstd.core.notification.telegram_receiver.urlopen",
    side_effect=TimeoutError("offline-test"),
)


def setUpModule() -> None:  # noqa: N802 - unittest 规定的模块级钩子名
    _OFFLINE_PATCH.start()


def tearDownModule() -> None:  # noqa: N802 - unittest 规定的模块级钩子名
    _OFFLINE_PATCH.stop()


class TestFetchUpdates:
    def test_returns_updates_on_success(self):
        receiver = TelegramReceiver("tok", lambda u: None, interval=0.01)
        with patch(
            "pilotstd.core.notification.telegram_receiver.urlopen",
            return_value=_Resp({"ok": True, "result": [_update(1)]}),
        ):
            updates = receiver.fetch_updates()
        assert len(updates) == 1 and updates[0]["update_id"] == 1

    def test_http_error_and_exception_are_isolated(self):
        receiver = TelegramReceiver("tok", lambda u: None)
        with patch(
            "pilotstd.core.notification.telegram_receiver.urlopen",
            return_value=_Resp({}, status=500),
        ):
            assert receiver.fetch_updates() == []
        assert "HTTP 500" in receiver.last_error
        with patch(
            "pilotstd.core.notification.telegram_receiver.urlopen",
            side_effect=TimeoutError("boom"),
        ):
            assert receiver.fetch_updates() == []
        assert "异常" in receiver.last_error

    def test_platform_failure_is_reported(self):
        receiver = TelegramReceiver("tok", lambda u: None)
        with patch(
            "pilotstd.core.notification.telegram_receiver.urlopen",
            return_value=_Resp({"ok": False, "description": "unauthorized"}),
        ):
            assert receiver.fetch_updates() == []
        assert "unauthorized" in receiver.last_error


class TestLifecycle:
    def test_start_requires_token(self):
        receiver = TelegramReceiver("", lambda u: None)
        assert receiver.start() is False
        assert receiver.last_error

    def test_start_stop_and_idempotence(self):
        receiver = TelegramReceiver("tok", lambda u: None, interval=0.01)
        with patch.object(receiver, "fetch_updates", return_value=[]):
            assert receiver.start() is True
            assert receiver.start() is True  # 幂等
            assert receiver.is_running is True
            receiver.stop()
        assert receiver.is_running is False
        receiver.stop()  # 可重入

    def test_loop_dispatches_and_advances_offset(self):
        seen: list[dict] = []
        receiver = TelegramReceiver("tok", seen.append, interval=0.01)
        calls = {"n": 0}

        def _fetch() -> list[dict]:
            calls["n"] += 1
            if calls["n"] == 1:
                return [_update(5)]
            receiver._stop.set()  # 第二次轮询前收停，避免测试长时间挂起
            return []

        with patch.object(receiver, "fetch_updates", side_effect=_fetch):
            assert receiver.start() is True
            thread = receiver._thread
        assert thread is not None
        thread.join(timeout=5)
        assert [u["update_id"] for u in seen] == [5]
        assert receiver._offset == 6  # offset 推进，避免重复处理

    def test_dispatch_failure_does_not_kill_loop(self):
        def _bad(update: dict) -> None:
            raise RuntimeError("dispatch boom")

        receiver = TelegramReceiver("tok", _bad, interval=0.01)
        calls = {"n": 0}

        def _fetch() -> list[dict]:
            calls["n"] += 1
            if calls["n"] >= 2:
                receiver._stop.set()
                return []
            return [_update(7)]

        with patch.object(receiver, "fetch_updates", side_effect=_fetch):
            receiver.start()
            thread = receiver._thread
            assert thread is not None
            # 等待式断言：轮询在子线程里跑，直接断言会与线程调度赛跑
            deadline = time.monotonic() + 5
            while calls["n"] < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            thread.join(timeout=5)
        assert calls["n"] >= 2  # 抛错后仍在轮询


class TestNormalize:
    def test_callback_query_normalized(self):
        env = TelegramReceiver.normalize(_update(3, action="retry"))
        assert env is not None
        assert (env.channel, env.action, env.callback_data) == ("telegram", "retry", "7:1")

    def test_plain_message_returns_none(self):
        assert TelegramReceiver.normalize({"update_id": 1, "message": {"text": "hi"}}) is None


class TestModeSelection:
    def test_mode_defaults_to_long_poll(self):
        assert mode_from_config({}) == MODE_LONG_POLL

    def test_webhook_mode_recognized(self):
        assert mode_from_config({"notification.channels.telegram.receive_mode": "webhook"}) == MODE_WEBHOOK

    def test_invalid_mode_falls_back(self):
        assert mode_from_config({"notification.channels.telegram.receive_mode": "carrier_pigeon"}) == MODE_LONG_POLL


class TestManagerIntegration:
    """生命周期纳入管理器：默认不自动起线程，由显式调用启动。"""

    def _manager(self, *, mode: str, token: str = "tok"):
        from types import SimpleNamespace

        from pilotstd.core.notification.manager import NotificationManager

        class _Cfg:
            _filepath = "/tmp/config.json"

            def get(self, key, default=None):
                return mode if key == "notification.channels.telegram.receive_mode" else default

        class _Db:
            def fetchall(self, sql, params=()):  # noqa: ARG002 - 契约签名
                return []

            def execute(self, sql, params=()):  # noqa: ARG002 - 契约签名
                return None

        mgr = NotificationManager.__new__(NotificationManager)  # 跳过真实构造（不连库）
        mgr._cfg = _Cfg()
        mgr._db = _Db()
        mgr._user_id = 1
        mgr._telegram_receiver = None
        mgr._channel_credentials = lambda channel: {"bot_token": token} if token else {}
        return mgr, SimpleNamespace

    def test_init_does_not_start_thread(self):
        mgr, _ = self._manager(mode=MODE_LONG_POLL)
        assert mgr._telegram_receiver is None, "构造管理器不得自动连外网"

    def test_webhook_mode_does_not_start(self):
        mgr, _ = self._manager(mode=MODE_WEBHOOK)
        assert mgr.start_telegram_receiver() is False
        assert mgr._telegram_receiver is None

    def test_long_poll_mode_starts_and_stops(self):
        mgr, _ = self._manager(mode=MODE_LONG_POLL)
        with patch(
            "pilotstd.core.notification.telegram_receiver.TelegramReceiver.fetch_updates",
            return_value=[],
        ):
            assert mgr.start_telegram_receiver() is True
            assert mgr._telegram_receiver.is_running is True
            mgr.shutdown()
        assert mgr._telegram_receiver is None, "shutdown 必须收停线程"

    def test_long_poll_without_credentials_returns_false(self):
        mgr, _ = self._manager(mode=MODE_LONG_POLL, token="")
        assert mgr.start_telegram_receiver() is False

    def test_stop_is_reentrant(self):
        mgr, _ = self._manager(mode=MODE_LONG_POLL)
        mgr.stop_telegram_receiver()
        mgr.stop_telegram_receiver()


class TestThreadSafety:
    def test_stop_from_other_thread_terminates(self):
        receiver = TelegramReceiver("tok", lambda u: None, interval=0.01)
        with patch.object(receiver, "fetch_updates", return_value=[]):
            receiver.start()
            threading.Event().wait(0.05)
            receiver.stop(timeout=2)
        assert receiver.is_running is False
