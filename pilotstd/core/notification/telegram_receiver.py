"""Telegram 接收通道（阶段 B2b-3）：长轮询（默认）与 webhook（可选）。

裁决 B2b-3：两种方案都实现，用 `notification.channels.telegram.receive_mode` 切换；
**默认长轮询**（应用主动连 TG，不需要对外可达地址）；webhook 走 B2b-1 已实现的端点。
`receive_mode` 是**运行时配置**，故落在 `defaults.py`，**不进 channel_spec**（渠道规格不变）。

设计要点：
- 接收线程是**守护线程**并由 `threading.Event` 收停，`start()` 幂等、`stop()` 可重入；
- 归一与动作处理**复用** B2a/B2b 的 `parse_envelope` 与回调服务（不另写一套解析）；
- 单条更新处理失败只记日志、**不中断轮询**（一条脏数据不该让整条通道停摆）；
- `getUpdates` 用 `offset` 推进，保证同一条更新不会被重复处理（与持久化幂等互为双保险）。
"""

import json
import logging
import threading
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

from pilotstd.i18n import t

logger = logging.getLogger(__name__)

# 长轮询参数：服务端等待上限与两次轮询之间的最小间隔
DEFAULT_POLL_TIMEOUT_SECONDS = 25
DEFAULT_POLL_INTERVAL_SECONDS = 1.0

# 接收模式（运行时配置取值闭集）
MODE_LONG_POLL = "long_poll"
MODE_WEBHOOK = "webhook"
RECEIVE_MODES = (MODE_LONG_POLL, MODE_WEBHOOK)


class TelegramReceiver:
    """Telegram 长轮询接收器（webhook 模式不启动本线程）。"""

    def __init__(
        self,
        bot_token: str,
        dispatch: Callable[[dict], Any],
        poll_timeout: int = DEFAULT_POLL_TIMEOUT_SECONDS,
        interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._token = bot_token
        self._dispatch = dispatch
        self._poll_timeout = poll_timeout
        self._interval = interval
        self._offset = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str = ""

    # ── 生命周期 ──

    @property
    def is_running(self) -> bool:
        """线程是否在跑（幂等判定用）。"""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """启动轮询线程（幂等：已在跑则直接返回 True）。"""
        if self.is_running:
            return True
        if not self._token:
            self.last_error = t("notification.telegram.receiver_no_token")
            logger.warning("%s", self.last_error)
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="tg-receiver", daemon=True)
        self._thread.start()
        logger.info(t("notification.telegram.receiver_started"))
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """收停并等待线程结束（可重入；超时不阻塞退出）。"""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        logger.info(t("notification.telegram.receiver_stopped"))

    # ── 轮询 ──

    def fetch_updates(self) -> list[dict]:
        """取一批更新（`getUpdates`）；失败返回空列表并写 `last_error`。"""
        url = f"https://api.telegram.org/bot{self._token}/getUpdates"
        body = json.dumps(
            {
                "offset": self._offset,
                "timeout": self._poll_timeout,
                "allowed_updates": ["callback_query", "message"],
            }
        ).encode("utf-8")
        req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=self._poll_timeout + 10) as resp:
                if resp.status != 200:
                    self.last_error = f"getUpdates HTTP {resp.status}"
                    return []
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            # 网络抖动是常态：只记错误继续轮询，不抛出（否则线程会静默死掉）
            self.last_error = t("notification.telegram.get_updates_exception").format(error=e)
            logger.warning("%s", self.last_error, exc_info=True)
            return []
        if data.get("ok") is not True:
            self.last_error = t("notification.telegram.get_updates_failed").format(
                detail=data.get("description") or ""
            )
            return []
        updates = data.get("result") or []
        return [u for u in updates if isinstance(u, dict)]

    def _loop(self) -> None:
        """轮询主体：取更新 → 分发 → 推进 offset；单条失败不影响后续。"""
        while not self._stop.is_set():
            for update in self.fetch_updates():
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    # 先推进 offset 再分发：即便分发抛错，也不会反复取同一条
                    self._offset = update_id + 1
                try:
                    self._dispatch(update)
                except Exception:
                    logger.warning(
                        t("notification.telegram.receiver_dispatch_failed"), exc_info=True
                    )
            if self._stop.wait(self._interval):
                break

    # ── 归一（复用 B2a 的 parse_envelope，不另写解析） ──

    @staticmethod
    def normalize(update: dict) -> Any:
        """把一条 TG 更新归一为 `CallbackEnvelope`；非回调更新返回 None。"""
        from .callback import parse_envelope

        if "callback_query" not in update:
            return None
        return parse_envelope("telegram", update)


def mode_from_config(config: Any, default: str = MODE_LONG_POLL) -> str:
    """读接收模式；非法值回落默认并记一条警告（不静默错配）。"""
    raw = str(config.get("notification.channels.telegram.receive_mode", default) or default)
    if raw not in RECEIVE_MODES:
        logger.warning(t("notification.telegram.receiver_mode_invalid").format(mode=raw))
        return default
    return raw
