"""钉钉企业级形态（阶段 S）：双读优先级、卡片发送与令牌缓存。

设计依据：docs/plans/notification-system-design/03-impl-design-D.md §1.2（S 行）
与 01-channel-capabilities.md §四（形态差距）。裁决：方案 A1/A2/A3。
"""

from unittest.mock import patch

from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

ENTERPRISE = {
    "app_key": "ak",
    "app_secret": "as",
    "robot_code": "robot-1",
    "card_template_id": "tmpl-1",
    "open_conversation_id": "cid-1",
}


def _msg() -> NotificationMessage:
    return NotificationMessage(title="标题", body="正文", level="info", event_type="scan_complete")


def _channel(**overrides) -> DingTalkChannel:
    kwargs = {"webhook_url": ""}
    kwargs.update(overrides)
    return DingTalkChannel(**kwargs)


class TestDualRead:
    """方案 A2：新字段齐全 → 企业级；否则回落旧 webhook；两者都配 → 企业级优先。"""

    def test_enterprise_complete_uses_card(self):
        ch = _channel(**ENTERPRISE)
        assert ch._enterprise is True
        with patch.object(ch, "_send_card", return_value=True) as card, patch.object(
            ch, "_send_webhook"
        ) as webhook:
            assert ch.send(_msg()) is True
        card.assert_called_once()
        webhook.assert_not_called()

    def test_webhook_only_falls_back(self):
        ch = _channel(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=x")
        assert ch._enterprise is False
        with patch.object(ch, "_send_card") as card, patch.object(
            ch, "_send_webhook", return_value=True
        ) as webhook:
            assert ch.send(_msg()) is True
        webhook.assert_called_once()
        card.assert_not_called()

    def test_both_configured_prefers_enterprise_and_logs(self, caplog):
        import logging

        caplog.set_level(logging.INFO)  # 该日志是 info 级，caplog 默认只收 WARNING
        ch = _channel(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=x", **ENTERPRISE)
        assert ch._enterprise is True
        assert any("双读优先级" in r.message for r in caplog.records)

    def test_partial_enterprise_falls_back(self):
        """企业级字段只填一半 ⇒ 不算企业级（回落旧形态），避免半配置静默失败。"""
        partial = {k: v for k, v in ENTERPRISE.items() if k != "robot_code"}
        ch = _channel(**partial)
        assert ch._enterprise is False

    def test_validate_config_accepts_either_form(self):
        assert DingTalkChannel.validate_config(dict(ENTERPRISE)) is True
        assert DingTalkChannel.validate_config({"webhook_url": "http://x"}) is True
        assert DingTalkChannel.validate_config({}) is False


class TestCardRender:
    """方案 A3：卡片负载结构在渲染层，渠道层只负责投递。"""

    def test_render_card_param_map(self):
        from pilotstd.core.notification.renderer import DingTalkCardRenderer

        payload = DingTalkCardRenderer().render_card(_msg())
        assert set(payload) == {"cardParamMap"}
        params = payload["cardParamMap"]
        assert params["title"] == "标题"
        assert params["content"] == "正文"
        assert params["level"] == "info"


class TestCardSend:
    """企业级发送：取令牌 → 创建卡片 → 投递；令牌进程内缓存；错误写 last_error。"""

    def _responses(self, token_body: dict, status: int = 200, sends: int = 1):
        """构造假响应序列：令牌 1 次 + 每轮发送「创建卡片 / 投递」各 1 次。

        用**真实类**而非 MagicMock：`with` 协议按类型查找 `__enter__`，
        在 MagicMock 实例上赋 `__enter__` 不生效（读回的不是 bytes）。
        """
        import json as _json

        class _Resp:
            def __init__(self, payload: dict, code: int) -> None:
                self.status = code
                self._body = _json.dumps(payload).encode("utf-8")

            def read(self) -> bytes:
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> bool:
                return False

        seq = [_Resp(token_body, 200)]
        for _ in range(sends):
            seq.extend([_Resp({}, status), _Resp({}, status)])
        return seq

    def test_send_card_success_and_token_cache(self):
        ch = _channel(**ENTERPRISE)
        # 两轮发送：令牌只取一次（进程内缓存），创建/投递各两次
        responses = self._responses({"accessToken": "tok", "expireIn": 7200}, sends=2)
        with patch(
            "pilotstd.core.notification.channels.dingtalk.urlopen", side_effect=responses
        ) as mock_open:
            assert ch.send(_msg()) is True, ch.last_error
            assert ch.send(_msg()) is True, ch.last_error
        # 3 次网络调用（令牌 + 创建 + 投递）；第二次发送复用缓存令牌 ⇒ 共 5 次而非 6 次
        assert mock_open.call_count == 5
        assert ch.last_error == ""

    def test_send_card_records_error_when_token_missing(self):
        ch = _channel(**ENTERPRISE)
        import json as _json

        class _Resp:
            status = 200

            def read(self) -> bytes:
                return _json.dumps({"message": "invalid app"}).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> bool:
                return False

        with patch("pilotstd.core.notification.channels.dingtalk.urlopen", return_value=_Resp()):
            assert ch.send(_msg()) is False
        assert "取令牌失败" in ch.last_error  # t() 的中文渲染

    def test_send_card_records_http_error(self):
        ch = _channel(**ENTERPRISE)
        responses = self._responses({"accessToken": "tok", "expireIn": 7200}, status=500)
        with patch("pilotstd.core.notification.channels.dingtalk.urlopen", side_effect=responses):
            assert ch.send(_msg()) is False
        assert "HTTP 500" in ch.last_error
