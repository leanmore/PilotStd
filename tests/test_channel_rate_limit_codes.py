"""T-42：限流码优先、关键词兜底。"""

from pilotstd.core.notification.channels.base import is_rate_limited, looks_rate_limited


def test_wechat_code_wins_without_keyword():
    assert is_rate_limited("wechat", 45009, "system error") is True


def test_feishu_code_wins_without_keyword():
    assert is_rate_limited("feishu", 99991400, "oops") is True


def test_unknown_code_falls_back_to_keyword():
    assert is_rate_limited("dingtalk", 12345, "rate limit exceeded") is True


def test_unknown_code_without_keyword_is_not_rate_limited():
    assert is_rate_limited("dingtalk", 12345, "invalid parameter") is False
    assert looks_rate_limited("invalid parameter") is False


def test_logs_hit_path(caplog):
    import logging

    with caplog.at_level(logging.INFO):
        is_rate_limited("wechat", 45009, "x")
        is_rate_limited("dingtalk", 1, "rate limit")
    assert "rate_limited_by=code" in caplog.text
    assert "rate_limited_by=keyword" in caplog.text

def test_dingtalk_code_wins_without_keyword():
    """T-42：钉钉 90018（官方「触发限流」码）应直接判为限流，不依赖关键词。"""
    assert is_rate_limited("dingtalk", 90018, "invalid parameter") is True
