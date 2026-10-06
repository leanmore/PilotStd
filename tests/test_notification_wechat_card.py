"""阶段 3 · Step 4 ①：企微**模板卡片**与应用形态测试。

覆盖两件事（此前的实测缺口是"应用形态只在 spec 里声明、渠道里没实现"）：
1. **渲染器** `WeChatCardRenderer`：产出**已被实证**的 `news_notice` 结构
   （取证：第三方插件 `AWdress/MoviePilot-Plugins` 的 `awembypush`，见渲染器 docstring）；
   站内入口进 `jump_list` / `card_action`；**不臆造** `card_image` 与 `text_notice`；
2. **渠道两形态** `WechatChannel`：应用形态发 `template_card`（缺卡片能力时**降级为文本**，不静默丢）；
   仅配 Webhook 时仍走 markdown（行为不变）；两形态都配好时**优先应用形态**（与 `status_rule` 分支序一致）。
"""

from __future__ import annotations

import json
from typing import Any

from pilotstd.core.notification._links import attach_web_actions
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.channels.wechat import WechatChannel
from pilotstd.core.notification.renderer import split_for_channel
from pilotstd.core.notification.renderer_wecom_card import WeChatCardRenderer

BASE = "https://std.example.com"


class _Cfg:
    def __init__(self, value: str | None = BASE) -> None:
        self._v: dict[str, Any] = {} if value is None else {"notification.web_base_url": value}

    def get(self, key: str, default: Any = None) -> Any:
        return self._v.get(key, default)


def _msg(body: str = "共 10 条，全部成功") -> NotificationMessage:
    msg = NotificationMessage(title="扫描完成")
    msg.body = body
    return msg


# ── 1. 渲染器 ────────────────────────────────────────────────────────────────


def test_card_is_news_notice_with_evidenced_fields_only() -> None:
    """只产出实证过的字段：`source`/`main_title`/`vertical_content_list`；**不含** card_image。"""
    card = WeChatCardRenderer().render_card(_msg())
    assert card["card_type"] == "news_notice"
    assert set(card) == {"card_type", "source", "main_title", "vertical_content_list"}
    assert card["main_title"]["title"] == "扫描完成"
    assert card["vertical_content_list"][0]["desc"] == "共 10 条，全部成功"
    assert "card_image" not in card, "无图时不得臆造 card_image（官方是否必填未取证）"


def test_card_puts_web_links_into_jump_list_and_card_action() -> None:
    """站内入口（Step 1）在企微卡片里是**跳转**，不是 markdown 链接。"""
    msg = _msg()
    attach_web_actions(msg, _Cfg())
    card = WeChatCardRenderer().render_card(msg)
    assert card["jump_list"] == [
        {"type": 1, "url": f"{BASE}/notification-logs", "title": "查看详情"}
    ]
    assert card["card_action"] == {"type": 1, "url": f"{BASE}/notification-logs"}


def test_card_without_links_has_no_jump_list() -> None:
    """地址未配置（降级）⇒ 卡片里不出现 jump_list / card_action（不产生坏链）。"""
    msg = _msg()
    attach_web_actions(msg, _Cfg(None))
    card = WeChatCardRenderer().render_card(msg)
    assert "jump_list" not in card and "card_action" not in card


def test_card_renders_blocks_into_vertical_content() -> None:
    """结构化块（B1 的失败明细列表）逐行进 `vertical_content_list`。"""
    from pilotstd.core.notification.blocks import ListBlock

    msg = _msg(body="")
    msg.blocks = [
        ListBlock(
            title="失败明细",
            items=[{"standard_number": "GB/T 1-2020", "error_type": "not_found"}],
        )
    ]
    card = WeChatCardRenderer().render_card(msg)
    descs = [it["desc"] for it in card["vertical_content_list"]]
    assert any("GB/T 1-2020" in d for d in descs)
    assert all(len(d) <= 140 for d in descs), "单行长度需受控（卡片行宽有限）"


def test_card_renderer_also_produces_degradation_text() -> None:
    """`render()`（str）用于**降级为文本消息**的路径，必须可用。"""
    msg = _msg()
    attach_web_actions(msg, _Cfg())
    text = WeChatCardRenderer().render(msg)
    assert "共 10 条" in text


def test_wecom_split_still_covers_webhook_markdown() -> None:
    """Webhook 分段逻辑不受影响（企微文本上限 2048 字节）。"""
    long_text = "行内容 " * 900
    assert len(split_for_channel(long_text, "wecom")) > 1


# ── 2. 渠道两形态 ────────────────────────────────────────────────────────────


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


def _stub_http(monkeypatch: Any, send_payloads: list[dict], token_ok: bool = True) -> None:
    """把渠道的 `_open` 打桩：token 与 send 两次调用分别返回可控响应。"""
    calls: list[str] = []

    def _open(url: str, payload: dict | None = None) -> _Resp:
        calls.append(url)
        if "gettoken" in url:
            return _Resp({"errcode": 0, "access_token": "tok"} if token_ok else {"errcode": 40013})
        send_payloads.append(payload or {})
        return _Resp({"errcode": 0, "errmsg": "ok"})

    monkeypatch.setattr(WechatChannel, "_open", lambda self, url, payload=None: _open(url, payload))
    return None


def test_app_form_sends_template_card(monkeypatch) -> None:
    """应用形态（corpid+corpsecret+agentid）⇒ `msgtype=template_card`，且带上 touser/agentid。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    ch = WechatChannel("", "ww123", "1000001", "secret", "", "@all")
    assert ch.send(_msg()) is True
    assert sent and sent[0]["msgtype"] == "template_card"
    assert sent[0]["touser"] == "@all" and sent[0]["agentid"] == "1000001"
    assert sent[0]["template_card"]["card_type"] == "news_notice"


def test_app_form_degrades_to_text_when_card_rejected(monkeypatch) -> None:
    """卡片被平台拒收（errcode≠0）⇒ **降级为文本消息**，绝不静默丢消息。"""
    sent: list[dict] = []
    state = {"card_failed": False}

    def _open(url: str, payload: dict | None = None) -> _Resp:
        if "gettoken" in url:
            return _Resp({"errcode": 0, "access_token": "tok"})
        sent.append(payload or {})
        if (payload or {}).get("msgtype") == "template_card" and not state["card_failed"]:
            state["card_failed"] = True
            return _Resp({"errcode": 40058, "errmsg": "invalid card"})
        return _Resp({"errcode": 0})

    monkeypatch.setattr(WechatChannel, "_open", lambda self, url, payload=None: _open(url, payload))
    ch = WechatChannel("", "ww123", "1000001", "secret")
    assert ch.send(_msg()) is True
    kinds = [p.get("msgtype") for p in sent]
    assert kinds == ["template_card", "text"], f"应为卡片失败后降级文本，实测 {kinds}"
    assert "共 10 条" in sent[-1]["text"]["content"]


def test_webhook_form_unchanged(monkeypatch) -> None:
    """仅配 Webhook ⇒ 仍走 markdown（形态选择是用户的事，未配应用不得改变既有行为）。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    ch = WechatChannel("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x")
    assert ch.send(_msg()) is True
    assert sent[0]["msgtype"] == "markdown"
    assert "共 10 条" in sent[0]["markdown"]["content"]


def test_app_form_takes_precedence_when_both_configured(monkeypatch) -> None:
    """两形态都配好 ⇒ **优先应用形态**（与 `channel_spec.status_rule` 分支序 app→webhook 一致）。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    ch = WechatChannel("https://hook/x", "ww123", "1000001", "secret")
    assert ch.send(_msg()) is True
    assert sent[0]["msgtype"] == "template_card"


def test_neither_form_configured_reports_error() -> None:
    """两形态都没配全 ⇒ 如实报错（不假装成功）。"""
    ch = WechatChannel("")
    assert ch.send(_msg()) is False
    assert ch.last_error


def test_token_failure_is_reported(monkeypatch) -> None:
    """取 access_token 失败 ⇒ 失败并记录原因（不继续发必然失败的请求）。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent, token_ok=False)
    ch = WechatChannel("", "ww123", "1000001", "bad")
    assert ch.send(_msg()) is False
    assert "令牌" in ch.last_error or "token" in ch.last_error.lower()
