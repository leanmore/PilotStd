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
from pilotstd.core.notification.renderer_base import level_prefix
from pilotstd.core.notification.renderer_wecom_card import WeChatCardRenderer
from pilotstd.i18n import t

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


def _linked(msg: NotificationMessage) -> NotificationMessage:
    """模拟分发层：`_dispatcher.send_now` 会给每条消息挂站内入口动作。

    D1 起卡片仅在**有合法跳转 URL** 时才会被发送（否则渠道改发 markdown），
    故"走卡片"的用例必须先挂动作。
    """
    attach_web_actions(msg, _Cfg())
    return msg


# ── 1. 渲染器 ────────────────────────────────────────────────────────────────


def test_card_is_news_notice_with_official_required_fields() -> None:
    """卡片满足 `news_notice` 官方必填项（D1；更细的契约见 `test_notification_wecom_card_contract.py`）。"""
    card = WeChatCardRenderer().render_card(_linked(_msg()))
    assert card["card_type"] == "news_notice"
    assert card["main_title"]["title"] == "扫描完成"
    joined = " ".join(it["title"] + it["desc"] for it in card["vertical_content_list"])
    assert "共 10 条" in joined
    # 官方必填：card_image 与 card_action（news_notice）
    assert card["card_image"]["url"]
    assert card["card_action"]["url"]


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
    """地址未配置（降级）⇒ 卡片里不出现 jump_list / card_action（不产生坏链、不发非法卡）。"""
    msg = _msg()
    attach_web_actions(msg, _Cfg(None))
    card = WeChatCardRenderer().render_card(msg)
    assert "jump_list" not in card and "card_action" not in card


def test_card_renders_blocks_into_vertical_content() -> None:
    """结构化块（B1 的失败明细列表）逐行拆进 `vertical_content_list` 的标题/正文。"""
    from pilotstd.core.notification.blocks import ListBlock

    msg = _linked(_msg(body=""))
    msg.blocks = [
        ListBlock(
            title="失败明细",
            items=[{"standard_number": "GB/T 1-2020", "error_type": "not_found"}],
        )
    ]
    card = WeChatCardRenderer().render_card(msg)
    items = card["vertical_content_list"]
    joined = " ".join(it["title"] + it["desc"] for it in items)
    assert "GB/T 1-2020" in joined
    assert all(len(it["desc"]) <= 112 for it in items), "单条正文宽度需受控（官方建议 ≤112）"
    assert all(it["title"] for it in items), "条目 title 是官方必填字段"


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


def test_app_form_defaults_to_mp_text(monkeypatch) -> None:
    """默认（对齐 MoviePilot）：应用形态发 **`msgtype=text`**，标题+正文，主动不带 markdown 源码。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    monkeypatch.delenv("PILOTSTD_WECHAT_APP_FORMAT", raising=False)
    msg = _linked(_msg())
    msg.title = "扫描完成"
    msg.link = f"{BASE}/notification-logs"
    ch = WechatChannel("", "ww123", "1000001", "secret", "", "@all")
    assert ch.send(msg) is True
    payload = sent[0]
    assert payload["msgtype"] == "text"
    assert payload["text"]["content"] == "扫描完成\n共 10 条，全部成功\n点击查看：" + f"{BASE}/notification-logs"
    assert payload["touser"] == "@all" and payload["agentid"] == "1000001"
    # MP 对齐的端点字段
    assert payload["safe"] == 0 and payload["enable_id_trans"] == 0 and payload["enable_duplicate_check"] == 0


def test_app_form_sends_template_card(monkeypatch) -> None:
    """显式启用 card 格式时仍发 `template_card`（保留既有能力，默认不启用）。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    monkeypatch.setenv("PILOTSTD_WECHAT_APP_FORMAT", "card")
    ch = WechatChannel("", "ww123", "1000001", "secret", "", "@all")
    assert ch.send(_linked(_msg())) is True
    assert sent and sent[0]["msgtype"] == "template_card"
    assert sent[0]["touser"] == "@all" and sent[0]["agentid"] == "1000001"
    assert sent[0]["template_card"]["card_type"] == "news_notice"


def test_app_form_degrades_to_markdown_when_card_rejected(monkeypatch) -> None:
    """D3：卡片被平台拒收（errcode≠0）⇒ 降级为 **`msgtype=markdown`**（不是 text 源码）。"""
    monkeypatch.setenv("PILOTSTD_WECHAT_APP_FORMAT", "card")
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
    assert ch.send(_linked(_msg())) is True
    kinds = [p.get("msgtype") for p in sent]
    assert kinds == ["template_card", "markdown"], f"应为卡片失败后降级 markdown，实测 {kinds}"
    assert "共 10 条" in sent[-1]["markdown"]["content"]
    # markdown 源码里的渲染标记是**合法内容**（企微 markdown 消息会解析它们）
    assert "## 扫描完成" in sent[-1]["markdown"]["content"]


def test_app_form_uses_markdown_when_no_legal_card_action(monkeypatch) -> None:
    """D1：无合法跳转 URL ⇒ 不产出/不发送必被拒的卡，直接发 markdown 应用消息。"""
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    monkeypatch.setenv("PILOTSTD_WECHAT_APP_FORMAT", "card")
    ch = WechatChannel("", "ww123", "1000001", "secret")
    assert ch.send(_msg()) is True  # 未挂站内入口动作
    kinds = [p.get("msgtype") for p in sent]
    assert kinds == ["markdown"], f"无合法 card_action 时不得发模板卡片，实测 {kinds}"


def test_app_form_text_is_last_resort_when_markdown_also_fails(monkeypatch) -> None:
    """卡片与 markdown 都失败 ⇒ 最后兜底发 text（绝不静默丢消息）。"""
    monkeypatch.setenv("PILOTSTD_WECHAT_APP_FORMAT", "card")
    sent: list[dict] = []
    state = {"card_failed": False, "md_failed": False}

    def _open(url: str, payload: dict | None = None) -> _Resp:
        if "gettoken" in url:
            return _Resp({"errcode": 0, "access_token": "tok"})
        sent.append(payload or {})
        kind = (payload or {}).get("msgtype")
        if kind == "template_card" and not state["card_failed"]:
            state["card_failed"] = True
            return _Resp({"errcode": 40058, "errmsg": "invalid card"})
        if kind == "markdown" and not state["md_failed"]:
            state["md_failed"] = True
            return _Resp({"errcode": 40058, "errmsg": "invalid markdown"})
        return _Resp({"errcode": 0})

    monkeypatch.setattr(WechatChannel, "_open", lambda self, url, payload=None: _open(url, payload))
    ch = WechatChannel("", "ww123", "1000001", "secret")
    assert ch.send(_linked(_msg())) is True
    kinds = [p.get("msgtype") for p in sent]
    assert kinds == ["template_card", "markdown", "text"], f"兜底顺序不符：{kinds}"
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
    monkeypatch.delenv("PILOTSTD_WECHAT_APP_FORMAT", raising=False)
    ch = WechatChannel("https://hook/x", "ww123", "1000001", "secret")
    assert ch.send(_linked(_msg())) is True
    assert sent[0]["msgtype"] == "text"


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


# ── 4. P1-2：卡片拒收 → 文本降级的**字节**分段（不得按字符截断） ─────────────


def test_app_form_text_fallback_splits_by_wecom_byte_limit(monkeypatch) -> None:
    monkeypatch.setenv("PILOTSTD_WECHAT_APP_FORMAT", "card")
    """P1-2：降级文本必须按 2048 **字节**分段发送，且末段含消息尾部。

    缺陷背景：原实现 `text[:2000]` 按**字符**硬截断——2000 汉字 ≈ 6000 字节，
    超过企微文本 2048 字节上限 ⇒ 降级消息本身仍会被平台拒收，且尾部信息直接丢失。
    判别力：把实现改回 `text[:2000]` ⇒ 本用例 FAIL（只有 1 段，尾部不在）。
    """
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

    # 3000 个汉字 = 9000 UTF-8 字节 ⇒ 至少 5 段；末段必须含结尾标记
    tail = "尾部结束标记"
    body = "长" * 3000 + tail
    ch = WechatChannel("", "ww123", "1000001", "secret")
    assert ch.send(_linked(_msg(body=body))) is True

    texts = [p["markdown"]["content"] for p in sent if p.get("msgtype") == "markdown"]
    assert len(texts) > 1, f"降级消息未按字节分段（字符截断回归）：段数={len(texts)}"
    for seg in texts:
        size = len(seg.encode("utf-8"))
        assert size <= 2048, f"分段超过企微 2048 字节上限：{size}"
    assert tail in texts[-1], f"末段丢失消息尾部：{texts[-1][-30:]!r}"
    # 内容不丢：正文里 3000 个「长」必须全部出现在各段中
    assert sum(seg.count("长") for seg in texts) == 3000, "分段后正文内容丢失"


def test_app_form_short_text_still_sent_as_single_message(monkeypatch) -> None:
    monkeypatch.setenv("PILOTSTD_WECHAT_APP_FORMAT", "card")
    """未超限时 `split_for_channel` 原样返回单段（零行为变更，不多发消息）。"""
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
    assert ch.send(_linked(_msg(body="短消息"))) is True
    texts = [p for p in sent if p.get("msgtype") == "markdown"]
    assert len(texts) == 1
    assert "短消息" in texts[0]["markdown"]["content"]


# ── 3. 信息量对齐（P0-2 级别 / P0-3 详情链接 / P1-1 列表计数） ────────────────


def test_card_renders_level_prefix_exactly_once() -> None:
    """P0-2：warning/error 的级别前缀必须进入卡片（27 个事件此前看不出严重度）。

    「恰好一次」同时锁定**不得重复**：卡片路径只在 `render_card()` 的字段里补一次，
    不得再经 `_render_block()` 叠加（否则降级文本路径会二次前缀）。
    """
    for level in ("warning", "error"):
        msg = _msg()
        msg.level = level
        dumped = json.dumps(WeChatCardRenderer().render_card(msg), ensure_ascii=False)
        prefix = level_prefix(level)
        assert prefix in dumped, f"{level} 级别前缀缺失：{dumped}"
        assert dumped.count(prefix) == 1, f"{level} 级别前缀重复：{dumped}"


def test_card_info_level_has_no_prefix() -> None:
    """info 不加前缀（避免所有企微卡片都出现噪声）。"""
    msg = _msg()
    msg.level = "info"
    dumped = json.dumps(WeChatCardRenderer().render_card(msg), ensure_ascii=False)
    assert level_prefix("info") == ""
    assert "⚠️" not in dumped and "❌" not in dumped


def test_card_degradation_text_has_level_prefix_exactly_once() -> None:
    """降级文本（`render()`）里前缀同样只出现一次（防 `_render_block` 二次前缀）。"""
    msg = _msg()
    msg.level = "warning"
    text = WeChatCardRenderer().render(msg)
    assert text.count(level_prefix("warning")) == 1, text


def test_card_puts_message_link_into_jump_list_and_card_action() -> None:
    """P0-3：`message.link`（标准详情）必须进卡片跳转，且 `card_action` 指向它。"""
    msg = _msg()
    msg.link = "https://std.example.com/standards/GB%201-2020"
    card = WeChatCardRenderer().render_card(msg)
    assert card["jump_list"] == [
        {"type": 1, "url": msg.link, "title": t("notification.renderer.detail")}
    ]
    assert card["card_action"] == {"type": 1, "url": msg.link}


def test_card_keeps_web_actions_after_detail_link() -> None:
    """详情链接是 `jump_list` 首项；既有站内入口动作保留为后续项（不互相顶掉）。"""
    msg = _msg()
    msg.link = "https://std.example.com/standards/GB%201-2020"
    attach_web_actions(msg, _Cfg())
    card = WeChatCardRenderer().render_card(msg)
    urls = [item["url"] for item in card["jump_list"]]
    assert urls[0] == msg.link
    assert f"{BASE}/notification-logs" in urls


def test_card_list_renders_count_and_detail_url() -> None:
    """P1-1：ListBlock 的「共 N 条」与 `detail_url` 不得再丢（5 个事件受影响）。"""
    from pilotstd.core.notification.blocks import ListBlock

    msg = _linked(_msg(body=""))
    msg.blocks = [
        ListBlock(
            title="新登记",
            items=[{"standard_number": "GB/T 1-2020"}],
            total=2,
            detail_url="https://std.example.com/standards?ids=1,2",
        )
    ]
    card = WeChatCardRenderer().render_card(msg)
    joined = " ".join(item["title"] + item["desc"] for item in card["vertical_content_list"])
    assert t("notification.renderer.list_count").format(total=2) in joined
    assert "https://std.example.com/standards?ids=1,2" in joined


def test_app_form_format_switch_to_markdown(monkeypatch) -> None:
    """显式 markdown 选项仍可用（企微内网/富文本场景）。"""
    monkeypatch.setenv("PILOTSTD_WECHAT_APP_FORMAT", "markdown")
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    ch = WechatChannel("", "ww123", "1000001", "secret")
    assert ch.send(_linked(_msg())) is True
    assert sent[0]["msgtype"] == "markdown"
    assert "共 10 条" in sent[0]["markdown"]["content"]


def test_mp_text_collapses_blank_lines_and_appends_link(monkeypatch) -> None:
    """MP 对齐：连续空行折叠 + 链接以「点击查看：」追加在末尾。"""
    monkeypatch.delenv("PILOTSTD_WECHAT_APP_FORMAT", raising=False)
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    msg = NotificationMessage(title="公告抓取完成", body="共 3 条\n\n已入库 3 条")
    msg.link = "https://std.example.com/announce"
    ch = WechatChannel("", "ww123", "1000001", "secret")
    assert ch.send(msg) is True
    content = sent[0]["text"]["content"]
    assert "\n\n" not in content
    assert content.endswith("点击查看：https://std.example.com/announce")


def test_mp_text_link_falls_back_to_web_actions(monkeypatch) -> None:
    """`message.link` 为空时，从 actions（view_detail 的 args.url）取「点击查看」目标。"""
    from pilotstd.core.notification.specs import ActionSpec

    monkeypatch.delenv("PILOTSTD_WECHAT_APP_FORMAT", raising=False)
    sent: list[dict] = []
    _stub_http(monkeypatch, sent)
    msg = NotificationMessage(title="公告抓取完成", body="共 3 条")
    msg.actions = [ActionSpec(action="view_detail", label_key="notification.action.view_detail",
                              args={"url": "http://192.168.1.18:9028/notification-logs"})]
    ch = WechatChannel("", "ww123", "1000001", "secret")
    assert ch.send(msg) is True
    content = sent[0]["text"]["content"]
    assert content.endswith("点击查看：http://192.168.1.18:9028/notification-logs")
