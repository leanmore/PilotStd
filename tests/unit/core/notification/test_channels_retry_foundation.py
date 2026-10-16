"""渠道基座「统一重试/限流退避」的受控测试（2026-10-17）。

背景：重试/退避此前只长在 `telegram.py`（该文件 27 处相关命中），而 `dingtalk`/`feishu`/`wechat`
各仅 0~1 处、`base.py` 为 0 ⇒ 同样一次 429 或网络抖动，只有 telegram 会退避重试，
其余三家**当场丢通知**。本文件锁定提升到基座后的行为，防止再次"只修一家"。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.core.notification.channels.base import (
    MAX_ATTEMPTS,
    NotificationChannel,
    is_retryable_http_status,
    looks_rate_limited,
    parse_retry_after,
)

BASE_SLEEP = "pilotstd.core.notification.channels.base.time.sleep"


class _StubChannel(NotificationChannel):
    """最小可实例化渠道：只实现基类抽象成员。"""

    @property
    def name(self) -> str:
        return "stub"

    def send(self, message) -> bool:  # pragma: no cover - 本测试不用
        return True

    def test(self) -> bool:  # pragma: no cover - 本测试不用
        return True

    def get_config_schema(self) -> dict:
        return {}


class TestRetryHelpers:
    def test_parse_retry_after_reads_server_hint(self):
        assert parse_retry_after("HTTP 429: Too Many Requests: retry after 32") == 32.0

    def test_parse_retry_after_is_capped_and_rejects_junk(self):
        assert parse_retry_after("retry after 9999") == 60.0  # 上限 60s，防异常值挂住线程
        assert parse_retry_after("retry after 0") is None
        assert parse_retry_after("no hint here") is None
        assert parse_retry_after("") is None

    def test_retryable_http_status(self):
        assert is_retryable_http_status(429) is True
        assert is_retryable_http_status(500) is True
        assert is_retryable_http_status(503) is True
        assert is_retryable_http_status(400) is False
        assert is_retryable_http_status(401) is False
        assert is_retryable_http_status(200) is False

    def test_looks_rate_limited_keywords(self):
        assert looks_rate_limited("系统繁忙，请求过于频繁") is True
        assert looks_rate_limited("too many request") is True
        assert looks_rate_limited("Rate Limit exceeded") is True
        assert looks_rate_limited("参数错误") is False


class TestWithRetryDriver:
    """`_with_retry`：节奏、上限、可重试判据与服务端建议等待。"""

    def test_success_on_first_attempt(self):
        ch = _StubChannel()
        fn = MagicMock(return_value=(True, False))
        assert ch._with_retry(fn) is True
        assert fn.call_count == 1

    def test_retries_until_success(self):
        ch = _StubChannel()
        fn = MagicMock(side_effect=[(False, True), (False, True), (True, False)])
        with patch(BASE_SLEEP) as sleep:
            assert ch._with_retry(fn) is True
        assert fn.call_count == 3
        assert sleep.call_count == 2  # 2+4 秒退避被桩掉

    def test_stops_when_not_retryable(self):
        """配置类错误（401/400 等）不得重试——否则会把"token 无效"重试 3 次拖慢链路。"""
        ch = _StubChannel()
        fn = MagicMock(return_value=(False, False))
        with patch(BASE_SLEEP) as sleep:
            assert ch._with_retry(fn) is False
        assert fn.call_count == 1
        sleep.assert_not_called()

    def test_exhausts_attempts(self):
        ch = _StubChannel()
        fn = MagicMock(return_value=(False, True))
        with patch(BASE_SLEEP) as sleep:
            assert ch._with_retry(fn) is False
        assert fn.call_count == MAX_ATTEMPTS
        assert sleep.call_count == MAX_ATTEMPTS - 1

    def test_server_hint_overrides_local_backoff(self):
        """服务端给了 `retry after` 时必须用它（本地 2 秒远小于实测 3~44 秒）。"""
        ch = _StubChannel()

        def _fn(_attempt: int) -> tuple[bool, bool]:
            ch.last_error = "HTTP 429: retry after 30"
            return False, True

        with patch(BASE_SLEEP) as sleep:
            ch._with_retry(_fn)
        assert [c.args[0] for c in sleep.call_args_list] == [30.0, 30.0]

    def test_success_resets_error_debounce(self):
        """成功后清空去重状态：下一次失败必须能立刻打日志（原 telegram 同口径）。"""
        ch = _StubChannel()
        ch._last_error_key = "stale"
        ch._last_error_time = 1.0
        with patch(BASE_SLEEP):
            assert ch._with_retry(MagicMock(return_value=(True, False))) is True
        assert ch._last_error_key == ""
        assert ch._last_error_time == 0.0

    def test_log_dedup_works_without_base_init(self):
        """历史渠道的 `__init__` 未调用 `super().__init__()`，去重不得因缺属性而抛。"""
        ch = _StubChannel()
        del ch.last_error  # 模拟未初始化状态
        with patch("pilotstd.core.notification.channels.base.logger") as lg:
            ch._log_dedup("same")
            ch._log_dedup("same")  # 去重窗口内第二次不再记
        assert lg.error.call_count == 1


@pytest.mark.parametrize("channel_name", ["telegram", "dingtalk", "feishu", "wechat"])
def test_every_channel_uses_the_shared_retry_driver(channel_name):
    """四家渠道都必须复用基座重试——防止再次出现"只有 telegram 会退避重试"。

    按源码断言其 send 路径引用 `_with_retry`（行为级用例见各渠道自身测试与本文件上半部分）。
    """
    import pilotstd

    channels_dir = Path(pilotstd.__file__).parent / "core" / "notification" / "channels"
    text = (channels_dir / f"{channel_name}.py").read_text(encoding="utf-8")
    assert "_with_retry" in text, f"{channel_name} 未接入基座重试（会当场丢通知）"
