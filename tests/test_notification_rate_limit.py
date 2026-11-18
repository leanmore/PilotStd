"""T-42 渠道限流：码优先、HTTP 429/5xx 与关键词兜底。"""
from pilotstd.core.notification.channels.base import (
    is_rate_limited,
    is_retryable_http_status,
    looks_rate_limited,
)


def test_rate_limit_by_business_code():
    assert is_rate_limited("wechat", 45009, "") is True
    assert is_rate_limited("feishu", 99991400, "") is True
    assert is_rate_limited("wechat", 0, "") is False


def test_rate_limit_falls_back_to_keywords():
    assert looks_rate_limited("rate limit exceeded") is True
    assert looks_rate_limited("请求过于频繁") is True
    assert looks_rate_limited("ok") is False


def test_retryable_http_status():
    assert is_retryable_http_status(429) is True
    assert is_retryable_http_status(500) is True
    assert is_retryable_http_status(400) is False
