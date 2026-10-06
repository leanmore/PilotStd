"""阶段 3 · Step 1：站内入口（`view_detail` / `open_logs`）接线与 **URL 降级策略** 测试。

背景（实测缺口）：这两个动作此前只有词表与三语文案，**全库无生产者** ⇒ 任何渠道都不出现入口。
现按用户裁定实现：**TG/飞书渲染为按钮**、**企微 webhook（及钉钉 webhook）渲染为 Markdown 链接**；
站内地址从系统配置 `notification.web_base_url` 读取，**未配置/不可用必须优雅降级**——
"绝不能生成 `http://localhost` 这种无效链接"。

本文件按四组断言组织：
1. **取址**（`resolve_web_base`）：合法 / 去尾斜杠 / 非绝对地址拒绝 / **回环拒绝** / 空值；
2. **挂载**（`attach_web_actions`）：常态挂 `view_detail`；**仅当有失败明细**时另挂 `open_logs`；
   地址不可用 ⇒ **不挂动作**、改为纯文本提示；幂等；不覆盖既有业务动作；
3. **渲染**（四渠道）：TG `url` 按钮（且**无** `callback_data`）、飞书 `action` 元素、Markdown 链接、
   钉钉卡片 `content` 内链接；降级时 TG **不出按钮**；
4. **接线**（`_dispatcher.send_now`）：确认发送路径**确实调用**了挂载函数。
"""

from __future__ import annotations

from typing import Any

import pytest

from pilotstd.core.notification._links import (
    attach_web_actions,
    logs_url,
    resolve_web_base,
)
from pilotstd.core.notification.blocks import TextBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import (
    DingTalkCardRenderer,
    FeishuCardRenderer,
    MarkdownRenderer,
    TelegramRenderer,
)
from pilotstd.core.notification.specs import ActionSpec

BASE = "https://std.example.com"
KEY = "notification.web_base_url"


class _Cfg:
    def __init__(self, value: str | None = BASE) -> None:
        self._v: dict[str, Any] = {} if value is None else {KEY: value}

    def get(self, key: str, default: Any = None) -> Any:
        return self._v.get(key, default)


def _msg(failed: bool = False) -> NotificationMessage:
    msg = NotificationMessage(title="扫描完成")
    msg.body = "正文"
    if failed:
        msg.failed_items = [
            {
                "standard_number": "GB/T 1-2020",
                "standard_name": "甲",
                "error_type": "not_found",
                "error_message": "缺失",
            }
        ]
    return msg


# ── 1. 取址 ──────────────────────────────────────────────────────────────────


def test_resolve_web_base_accepts_absolute_and_strips_slash() -> None:
    assert resolve_web_base(_Cfg("https://std.example.com/")) == BASE
    assert resolve_web_base(_Cfg("http://10.0.0.5:9028")) == "http://10.0.0.5:9028"


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "std.example.com", "/notification-logs", "ftp://x", "javascript:alert(1)"],
)
def test_resolve_web_base_rejects_non_absolute(bad: str) -> None:
    assert resolve_web_base(_Cfg(bad)) == ""


@pytest.mark.parametrize(
    "loopback",
    [
        "http://localhost:9028",
        "http://localhost",
        "http://127.0.0.1:9028",
        "http://127.0.0.1",
        "http://0.0.0.0:9028",
        "http://[::1]:9028",
    ],
)
def test_resolve_web_base_rejects_loopback(loopback: str) -> None:
    """**核心约束**：聊天接收方在别的机器上 ⇒ 回环地址点不开，必须拒绝（不得生成无效链接）。"""
    assert resolve_web_base(_Cfg(loopback)) == ""


def test_logs_url() -> None:
    assert logs_url(BASE) == f"{BASE}/notification-logs"
    assert logs_url("") == ""


# ── 2. 挂载与降级 ────────────────────────────────────────────────────────────


def test_attach_view_detail_by_default() -> None:
    msg = _msg()
    assert attach_web_actions(msg, _Cfg()) is True
    assert [a.action for a in msg.actions] == ["view_detail"]
    assert msg.actions[0].args["url"] == f"{BASE}/notification-logs"


def test_attach_open_logs_only_when_failed_items_present() -> None:
    """`open_logs` 只在**有失败明细**时另挂：那一步的下一步才是"去日志页看细节"。"""
    plain = _msg()
    attach_web_actions(plain, _Cfg())
    assert "open_logs" not in [a.action for a in plain.actions]

    failed = _msg(failed=True)
    attach_web_actions(failed, _Cfg())
    assert [a.action for a in failed.actions] == ["view_detail", "open_logs"]
    assert all(a.args["url"] == f"{BASE}/notification-logs" for a in failed.actions)


def test_attach_is_idempotent_and_keeps_business_actions() -> None:
    """重复调用不产生重复按钮；既有业务动作（回调型）不被覆盖。"""
    msg = _msg()
    msg.actions = [ActionSpec(action="retry", label_key="notification.action.retry")]
    attach_web_actions(msg, _Cfg())
    attach_web_actions(msg, _Cfg())
    assert [a.action for a in msg.actions] == ["retry", "view_detail"]


def test_degrade_appends_hint_and_no_actions() -> None:
    """地址不可用 ⇒ **不挂动作**，改为追加纯文本提示（按钮变提示的降级）。"""
    msg = _msg()
    assert attach_web_actions(msg, _Cfg(None)) is False
    assert msg.actions == []
    assert msg.blocks and isinstance(msg.blocks[-1], TextBlock)
    assert "Web" in msg.blocks[-1].text


def test_degrade_also_for_loopback_config() -> None:
    msg = _msg()
    assert attach_web_actions(msg, _Cfg("http://localhost:9028")) is False
    assert msg.actions == []


# ── 3. 四渠道渲染 ────────────────────────────────────────────────────────────


def test_telegram_renders_url_button_without_callback_data() -> None:
    msg = _msg()
    attach_web_actions(msg, _Cfg())
    markup = TelegramRenderer().build_reply_markup(msg)
    assert markup is not None
    button = markup["inline_keyboard"][0][0]
    assert button["url"] == f"{BASE}/notification-logs"
    assert "callback_data" not in button, "链接型动作不得携带回调载荷"


def test_feishu_renders_action_element_with_url_button() -> None:
    msg = _msg()
    attach_web_actions(msg, _Cfg())
    card = FeishuCardRenderer().render(msg)
    last = card["elements"][-1]
    assert last["tag"] == "action"
    assert last["actions"][0]["url"] == f"{BASE}/notification-logs"
    assert last["actions"][0]["text"]["content"] == "查看详情"


def test_markdown_renderer_emits_link_line() -> None:
    """企微 webhook（及钉钉 webhook）只能发 markdown ⇒ 站内入口以链接呈现。"""
    msg = _msg()
    attach_web_actions(msg, _Cfg())
    text = MarkdownRenderer().render(msg)
    assert f"[查看详情]({BASE}/notification-logs)" in text


def test_dingtalk_card_puts_link_in_content() -> None:
    msg = _msg()
    attach_web_actions(msg, _Cfg())
    content = DingTalkCardRenderer().render_card(msg)["cardParamMap"]["content"]
    assert f"[查看详情]({BASE}/notification-logs)" in content


def test_degraded_message_has_no_buttons_on_any_channel() -> None:
    msg = _msg()
    attach_web_actions(msg, _Cfg(None))
    assert TelegramRenderer().build_reply_markup(msg) is None
    card = FeishuCardRenderer().render(msg)
    assert all(el.get("tag") != "action" for el in card["elements"])
    assert "Web" in MarkdownRenderer().render(msg)


# ── 4. 接线证明 ──────────────────────────────────────────────────────────────


def test_send_now_calls_attach_web_actions(monkeypatch) -> None:
    """发送路径**确实**调用挂载函数（防"实现了但没接线"的老问题复发）。"""
    from pilotstd.core.notification import _dispatcher

    calls: list[Any] = []

    def _spy(msg: Any, cfg: Any) -> bool:
        calls.append((msg, cfg))
        return True

    monkeypatch.setattr(_dispatcher, "attach_web_actions", _spy)

    class _Ch:
        last_error = ""

        def send(self, msg: Any) -> bool:
            return True

    class _Ops:
        def update_log_fields(self, *a: Any, **k: Any) -> bool:
            return True

    class _Host:
        _user_id = 1
        _cfg = _Cfg()

        def __init__(self) -> None:
            self._channels = {"telegram": _Ch()}
            self.ops = _Ops()
            self.logged = 0

        def _log(self, *a: Any, **k: Any) -> int:
            self.logged += 1
            return self.logged

        def _record_delivery(self, channel: str, ok: bool) -> None:
            return None

    host = _Host()
    _dispatcher.send_now(host, _msg(), ["telegram"])
    assert calls, "send_now 必须调用 attach_web_actions（否则站内入口永不出现）"
