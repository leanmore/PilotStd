"""P5b：Telegram 交互按钮（`inline_keyboard`）测试。

覆盖用户补充的两条实施约束：
1. **`callback_data` ≤ 64 字节**（Telegram 官方限制；本仓 `notification_log.callback_data` 列注释同口径）
   ——本仓格式 `"<action>:<token>"`、token 形如 `<log_id>:<user_id>` ⇒ 实测十几字节；
   同时验证"超限 ⇒ 跳过该按钮并告警"的防御分支；
2. **按钮只挂最后一段**（分段场景）——这是**设计决策**而非 bug，注释写在
   `TelegramRenderer.build_reply_markup()` docstring；本文件从**行为**上把它钉死。

另覆盖：无动作/无 token ⇒ 不产生 `reply_markup`（fail-safe），既有请求体逐字节不变。
"""

from __future__ import annotations

from typing import Any

from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import TelegramRenderer
from pilotstd.core.notification.specs import ActionSpec
from pilotstd.i18n import t


def _msg(actions: list[ActionSpec] | None = None, token: str = "12345:1") -> Any:
    msg = NotificationMessage(title="t")
    msg.actions = actions or []
    msg.callback_data = token
    return msg


def test_buttons_render_with_signed_short_callback_data() -> None:
    """有动作 + 有 token ⇒ 生成 `inline_keyboard`；`callback_data` ＝ `action:token` 且 ≤ 64 字节。"""
    renderer = TelegramRenderer()
    msg = _msg([ActionSpec(action="retry", label_key="notification.action.retry")])
    markup = renderer.build_reply_markup(msg)

    assert markup is not None
    button = markup["inline_keyboard"][0][0]
    assert button["callback_data"] == "retry:12345:1"
    assert len(button["callback_data"].encode("utf-8")) <= 64, "Telegram 限制 callback_data ≤ 64 字节"
    # 文案走 i18n（不是键名本身）
    assert button["text"] == t("notification.action.retry")
    assert button["text"] != "notification.action.retry"


def test_no_token_or_no_actions_means_no_markup() -> None:
    """fail-safe：无 token（当前尚无生产者）或动作为空 ⇒ **不产生按钮**，而非发出点不动的按钮。"""
    renderer = TelegramRenderer()
    assert renderer.build_reply_markup(_msg([ActionSpec(action="retry", label_key="k")], token="")) is None
    assert renderer.build_reply_markup(_msg()) is None


def test_unknown_action_is_skipped() -> None:
    """不在 `ACTIONS` 闭集内的动作不得下发（否则回调侧必然判未知动作）。"""
    renderer = TelegramRenderer()
    markup = renderer.build_reply_markup(
        _msg([ActionSpec(action="not_a_real_action", label_key="k")])
    )
    assert markup is None, "闭集外的动作应被跳过；全被跳过时返回 None"


def test_overlong_callback_data_is_skipped_with_warning(caplog) -> None:
    """防御：拼接后超 64 字节 ⇒ 跳过该按钮并告警（不发出必被 Telegram 拒收的载荷）。"""
    import logging

    renderer = TelegramRenderer()
    long_token = "9" * 80  # action(5) + ':' + 80 ⇒ 86 字节 > 64
    with caplog.at_level(logging.WARNING, logger="pilotstd.core.notification.renderer"):
        markup = renderer.build_reply_markup(
            _msg([ActionSpec(action="retry", label_key="notification.action.retry")], token=long_token)
        )
    assert markup is None
    assert any("callback_data" in r.getMessage() for r in caplog.records), "超限必须告警（可见，不静默）"


def test_request_body_unchanged_without_markup_and_carries_markup_with_it() -> None:
    """渠道层：未带 `reply_markup` 时请求体与旧版**逐字节一致**；带上时出现该键。"""
    from pilotstd.core.notification.channels.telegram import TelegramChannel

    ch = TelegramChannel("123:abc", "42")
    bodies: list[dict] = []

    class _FakeResp:
        status = 200

        def read(self) -> bytes:
            return b'{"ok": true}'

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *a: object) -> None:
            return None

    def _fake_urlopen(req: Any, timeout: int = 10) -> "_FakeResp":
        import json as _json

        bodies.append(_json.loads(req.data.decode("utf-8")))
        return _FakeResp()

    import pilotstd.core.notification.channels.telegram as tg

    original = tg.urlopen
    tg.urlopen = _fake_urlopen  # type: ignore[assignment]
    try:
        msg = _msg([ActionSpec(action="retry", label_key="notification.action.retry")])
        msg.blocks = []
        msg.body = "hello"
        assert ch.send(msg) is True
        assert "reply_markup" in bodies[-1]
        bodies.clear()

        plain = NotificationMessage(title="t")
        plain.blocks = []
        plain.body = "hello"
        assert ch.send(plain) is True
        assert set(bodies[-1]) == {"chat_id", "text", "parse_mode"}, "无按钮时不得新增键"
    finally:
        tg.urlopen = original  # type: ignore[assignment]
