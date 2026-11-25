"""B3（P1-4）回归：直连安全告警必须认企微**应用形态**（生产实际配置形态）。

缺陷背景：`security_notifier._channel_instance` 对 wechat 只读 `webhook_url`；
生产企微是应用形态（`corpid`/`agentid`/`corpsecret` 齐、`webhook_url` 为空）⇒
直连安全告警被 `continue` 静默跳过，三类安全事件只剩 `manager.send_event` 一条路
（聚合/静音还会推迟它）。证据见 `docs/plans/2026-11-24-p1-notification-parity.md` §4.1-P1-4。
"""

from __future__ import annotations

import json
from typing import Any

from pilotstd.core.notification import security_notifier as sn
from pilotstd.core.notification.channels.wechat import WechatChannel

APP_CREDS = {
    "enabled": "true",
    "webhook_url": "",
    "corpid": "ww1234567890",
    "agentid": "1000001",
    "corpsecret": "secret-value",
}

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x"


class _Resp:
    def __init__(self, payload: dict) -> None:
        self.status = 200
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *a: object) -> None:
        return None


def _stub_http(monkeypatch: Any, sent: list[dict]) -> None:
    """打桩渠道 HTTP：token 与发送分别返回可控响应（不发起真实网络请求）。"""

    def _open(url: str, payload: dict | None = None) -> _Resp:
        if "gettoken" in url:
            return _Resp({"errcode": 0, "access_token": "tok"})
        sent.append(payload or {})
        return _Resp({"errcode": 0, "errmsg": "ok"})

    monkeypatch.setattr(WechatChannel, "_open", lambda self, url, payload=None: _open(url, payload))


def test_app_form_credentials_construct_wechat_channel() -> None:
    """应用形态凭据（webhook_url 为空）必须构造出渠道实例，不能返回 None。"""
    inst = sn._channel_instance("wechat", dict(APP_CREDS))
    assert isinstance(inst, WechatChannel)
    assert inst._app_configured is True


def test_webhook_form_credentials_still_work() -> None:
    """仅配 Webhook 的既有形态不受影响（回归：不得为了应用形态丢掉 Webhook 分支）。"""
    inst = sn._channel_instance("wechat", {"webhook_url": WEBHOOK_URL})
    assert isinstance(inst, WechatChannel)
    assert inst._app_configured is False
    assert inst._url == WEBHOOK_URL


def test_incomplete_credentials_return_none() -> None:
    """两种形态都不完整 ⇒ 仍返回 None（可预期跳过，不猜测形态）。"""
    assert sn._channel_instance("wechat", {"webhook_url": "", "corpid": "ww1"}) is None


def test_notify_security_event_delivers_via_app_form(monkeypatch: Any) -> None:
    """整链路：应用形态凭据下直连投递**确实走应用消息**，不再被静默跳过。

    D1（批次 9）起：直连路径没有站内入口/config 上下文 ⇒ 消息无合法 `card_action`，
    `news_notice` 卡片必填项不满足（且凭空造占位动作等于给用户死链）⇒ 渠道按设计
    改发**应用 markdown 消息**（D3）。核心断言仍是"应用形态参与投递、不静默丢"。
    """
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)

    class _Helper:
        def get_all(self, user_id: int) -> dict[str, dict[str, str]]:
            return {"wechat": dict(APP_CREDS)}

    sent_channels, failed = sn.notify_security_event(
        notification_mgr=None,
        cred_helper=_Helper(),
        user_id=1,
        event_type="security_password_changed",
        payload={"user_id": "1", "from_ip": "10.0.0.1", "sessions_revoked": False},
    )
    assert failed == [], f"应用形态不应计失败：{failed}"
    assert sent_channels == ["wechat"], f"应用形态渠道未参与直连投递：{sent_channels}"
    assert sent, "应用形态未发出任何应用消息"
    assert sent[0]["msgtype"] == "markdown", f"无合法卡片动作时应发 markdown：{sent[0]}"
    assert sent[0]["markdown"]["content"].strip(), "markdown 内容不得为空"


def test_app_form_keeps_webhook_url_for_fallback(monkeypatch: Any) -> None:
    """两种形态都配好 ⇒ 优先应用形态（与 `channels/wechat.py` 的形态选择一致）。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    inst = sn._channel_instance("wechat", {**APP_CREDS, "webhook_url": WEBHOOK_URL})
    assert inst is not None
    assert inst._app_configured is True
    assert inst._url == WEBHOOK_URL
