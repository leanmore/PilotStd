# tests/test_telegram_backoff.py
"""Telegram 渠道的**退避对齐**测试（限流自伤 P0）。

## 被修复的缺陷（生产实测）

`pilotstd/core/notification/channels/telegram.py` 原先只用**本地固定退避**
（`_RETRY_BACKOFF_SECONDS = (2, 4)`，合计 6 秒）。而 Telegram 在 429 响应里
**会给出建议等待时间**：

```
HTTP 429: Too Many Requests: retry after 32
```

实测 599 条限流失败记录的 `retry after` 范围为 **3 ~ 44 秒**，常见值 36/34/32/25/16。
本地只等 6 秒 → 3 次尝试全部撞在限流上 → **通知丢失**（占全部发送失败的 95.2%）。

## 修复后的契约

1. 限流（或任何带 `retry after N` 的失败）时，**退避优先取服务端建议值**；
2. 无建议值（如纯 5xx / 网络异常）时**回退本地固定退避**（2、4 秒）；
3. 服务端建议值超过上限（60 秒）时按上限截断，避免异常值把线程挂住。

判别力：把 `send()` 改回"只用本地固定退避" → `test_uses_server_retry_after` FAIL。
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.notification.channel import NotificationMessage  # noqa: E402
from pilotstd.core.notification.channels.telegram import (  # noqa: E402
    _MAX_ATTEMPTS,
    _RETRY_AFTER_CAP_SECONDS,
    _RETRY_BACKOFF_SECONDS,
    TelegramChannel,
    _parse_retry_after,
)


class TestParseRetryAfter(unittest.TestCase):
    """服务端建议值的解析。"""

    def test_parses_integer_seconds(self):
        self.assertEqual(_parse_retry_after("HTTP 429: Too Many Requests: retry after 32"), 32.0)

    def test_parses_small_and_large(self):
        self.assertEqual(_parse_retry_after("retry after 3"), 3.0)
        self.assertEqual(_parse_retry_after("retry after 44"), 44.0)

    def test_case_insensitive(self):
        self.assertEqual(_parse_retry_after("Retry After 7"), 7.0)

    def test_returns_none_when_absent(self):
        """无建议值 → None（调用方据此回退固定退避）。"""
        self.assertIsNone(_parse_retry_after("HTTP 500: Internal Server Error"))
        self.assertIsNone(_parse_retry_after(""))
        self.assertIsNone(_parse_retry_after("connection reset"))

    def test_returns_none_for_zero_or_negative(self):
        self.assertIsNone(_parse_retry_after("retry after 0"))

    def test_caps_at_upper_bound(self):
        """异常大的值按上限截断（避免把线程挂住过久）。"""
        self.assertEqual(_parse_retry_after("retry after 9999"), _RETRY_AFTER_CAP_SECONDS)
        self.assertEqual(_parse_retry_after("retry after 60"), 60.0)
        self.assertLessEqual(_parse_retry_after("retry after 3600"), _RETRY_AFTER_CAP_SECONDS)


class TestSendBackoff(unittest.TestCase):
    """`send()` 的退避行为。"""

    def setUp(self):
        self.ch = TelegramChannel("token", "chat")
        self.msg = NotificationMessage(title="T", body="B")

    def _run_with_failure(self, error: str, retryable: bool = True) -> list:
        """让 `_post_once` 始终失败，捕获每次 `time.sleep` 的入参。"""
        sleeps: list = []

        def _post_once(_text):
            self.ch.last_error = error
            return False, retryable

        with patch.object(self.ch, "_post_once", side_effect=_post_once), patch(
            "pilotstd.core.notification.channels.telegram.time.sleep",
            side_effect=lambda s: sleeps.append(s),
        ):
            ok = self.ch.send(self.msg)
        self.assertFalse(ok)
        return sleeps

    def test_uses_server_retry_after(self):
        """★ 核心：限流时退避取**服务端建议值**（不是本地 2/4 秒）。

        判别力：改回只用 `_RETRY_BACKOFF_SECONDS` → 本用例 FAIL。
        """
        sleeps = self._run_with_failure("HTTP 429: Too Many Requests: retry after 32")
        self.assertEqual(len(sleeps), _MAX_ATTEMPTS - 1, "应重试 %d 次" % (_MAX_ATTEMPTS - 1))
        for s in sleeps:
            self.assertEqual(s, 32.0, f"退避应为服务端建议的 32 秒，实际 {s}")
        self.assertNotIn(
            _RETRY_BACKOFF_SECONDS[0], sleeps,
            "不得回退到本地固定退避（服务端已给出建议值）",
        )

    def test_uses_server_value_when_larger_than_local(self):
        """服务端值大于本地时，必须听服务端的（这正是原缺陷所在）。"""
        sleeps = self._run_with_failure("HTTP 429: Too Many Requests: retry after 44")
        self.assertTrue(all(s == 44.0 for s in sleeps), f"实际 {sleeps}")
        self.assertTrue(
            all(s > max(_RETRY_BACKOFF_SECONDS) for s in sleeps),
            "服务端要求的等待必须大于本地固定退避",
        )

    def test_falls_back_to_local_backoff_without_server_hint(self):
        """无建议值（纯 5xx）→ 回退本地固定退避。"""
        sleeps = self._run_with_failure("HTTP 500: Internal Server Error")
        self.assertEqual(sleeps, list(_RETRY_BACKOFF_SECONDS))

    def test_falls_back_for_network_error(self):
        """网络类异常（无 retry after）→ 回退本地固定退避。"""
        sleeps = self._run_with_failure("Telegram 发送异常: The read operation timed out")
        self.assertEqual(sleeps, list(_RETRY_BACKOFF_SECONDS))

    def test_caps_absurd_server_value(self):
        """服务端给出异常大值时按上限截断。"""
        sleeps = self._run_with_failure("HTTP 429: Too Many Requests: retry after 9999")
        self.assertTrue(all(s == _RETRY_AFTER_CAP_SECONDS for s in sleeps), f"实际 {sleeps}")

    def test_non_retryable_does_not_sleep(self):
        """不可重试（如 400 格式错误）→ 不重试、不等待。"""
        sleeps = self._run_with_failure("HTTP 400: can't parse entities", retryable=False)
        self.assertEqual(sleeps, [])

    def test_success_on_second_attempt_sleeps_once(self):
        """第二次成功 → 只等待一次。"""
        sleeps: list = []
        calls = {"n": 0}

        def _post_once(_text):
            calls["n"] += 1
            if calls["n"] == 1:
                self.ch.last_error = "HTTP 429: Too Many Requests: retry after 11"
                return False, True
            return True, False

        with patch.object(self.ch, "_post_once", side_effect=_post_once), patch(
            "pilotstd.core.notification.channels.telegram.time.sleep",
            side_effect=lambda s: sleeps.append(s),
        ):
            ok = self.ch.send(self.msg)
        self.assertTrue(ok)
        self.assertEqual(sleeps, [11.0])
