"""阶段 3 · Step 4 ③：飞书**企业应用形态**测试（发送 + `message_id` 留存 + `PATCH` 编辑）。

现状背景（实测）：飞书渠道此前**只有机器人 Webhook**（发卡片但**拿不到 `message_id`** ⇒ 不能编辑）；
`channel_spec` 里也没有应用形态字段。本批按第三方实证（`larkmessager/client.py`）补齐：

| 端点 | 用途 |
|---|---|
| `POST /open-apis/auth/v3/tenant_access_token/internal` | 取应用 token（`app_id`/`app_secret`） |
| `POST /open-apis/im/v1/messages?receive_id_type=…` | 发卡片；`content` 必须是 **JSON 字符串** |
| `PATCH /open-apis/im/v1/messages/{message_id}` | 编辑已发消息（`code==0` 为成功） |

另覆盖：两形态选择与优先级（应用优先）、`message_id` 写进 `channel_message_ids["feishu"]`、
编辑在 Webhook 形态下如实拒绝、token 失败与接口报错的如实报错。
"""

from __future__ import annotations

import json
from typing import Any

from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.channels.feishu import FeishuChannel
from pilotstd.core.notification.interaction import ANCHOR_MESSAGE_ID, MessageHandle

CARD = {"header": {"title": {"tag": "plain_text", "content": "t"}}, "elements": []}


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


def _msg() -> NotificationMessage:
    msg = NotificationMessage(title="扫描完成")
    msg.body = "共 10 条，全部成功"
    return msg


def _stub(monkeypatch: Any, captured: list[tuple[str, str, dict]], *, token_ok: bool = True,
          send_code: int = 0, patch_code: int = 0) -> None:
    """打桩 `urlopen`：记录 (method, url, body)，按端点返回可控响应。"""

    def _fake(req: Any, timeout: int = 10) -> _Resp:
        url = req.full_url
        body = json.loads(req.data.decode("utf-8")) if req.data else {}
        captured.append((req.get_method(), url, body))
        if "tenant_access_token" in url:
            return _Resp(
                {"code": 0, "tenant_access_token": "tok"} if token_ok else {"code": 99, "msg": "bad app"}
            )
        if req.get_method() == "PATCH":
            return _Resp({"code": patch_code, "msg": "patch fail" if patch_code else ""})
        return _Resp(
            {"code": send_code, "msg": "send fail" if send_code else "",
             "data": {"message_id": "om_123"}}
        )

    import pilotstd.core.notification.channels.feishu as feishu_mod

    monkeypatch.setattr(feishu_mod, "urlopen", _fake)


def test_app_form_sends_card_and_keeps_message_id(monkeypatch) -> None:
    """应用形态：走应用端点发卡片，`content` 为 **JSON 字符串**，并留存 `message_id`。"""
    calls: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls)
    ch = FeishuChannel("", "", "cli_x", "sec", "ou_user", "open_id")
    msg = _msg()
    assert ch.send(msg) is True

    send_calls = [c for c in calls if "/im/v1/messages?" in c[1]]
    assert send_calls, f"应经应用端点发送，实测调用：{[c[1] for c in calls]}"
    method, url, body = send_calls[0]
    assert method == "POST" and "receive_id_type=open_id" in url
    assert body["receive_id"] == "ou_user" and body["msg_type"] == "interactive"
    assert isinstance(body["content"], str), "`content` 必须是 JSON 字符串（不是对象）"
    assert json.loads(body["content"])["header"]["title"]["content"] == "扫描完成"
    # `message_id` 写进消息（渠道→ID 映射），供后续编辑使用
    assert msg.channel_message_ids.get("feishu") == "om_123"


def test_edit_message_uses_patch(monkeypatch) -> None:
    """编辑：`PATCH /im/v1/messages/{message_id}`，`content` 同样是 JSON 字符串。"""
    calls: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls)
    ch = FeishuChannel("", "", "cli_x", "sec", "ou_user")
    assert ch.edit_message(MessageHandle("feishu", ANCHOR_MESSAGE_ID, "om_123"), _msg()) is True
    patch_calls = [c for c in calls if c[0] == "PATCH"]
    assert patch_calls and patch_calls[0][1].endswith("/im/v1/messages/om_123")
    assert isinstance(patch_calls[0][2]["content"], str)


def test_edit_requires_app_form_and_message_id(monkeypatch) -> None:
    """Webhook 形态（无应用凭证）或缺 `message_id` ⇒ **如实拒绝**（不假装成功）。"""
    calls: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls)
    webhook_only = FeishuChannel("https://open.feishu.cn/open-apis/bot/v2/hook/x")
    assert webhook_only.edit_message(MessageHandle("feishu", ANCHOR_MESSAGE_ID, "om_123"), _msg()) is False
    assert webhook_only.last_error

    app = FeishuChannel("", "", "cli_x", "sec", "ou_user")
    assert app.edit_message(MessageHandle("feishu", ANCHOR_MESSAGE_ID, ""), _msg()) is False
    assert app.last_error


def test_webhook_form_unchanged(monkeypatch) -> None:
    """仅配 Webhook ⇒ 仍走机器人 Webhook（`card` 直接给对象，不取 token）。"""
    calls: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls)
    ch = FeishuChannel("https://open.feishu.cn/open-apis/bot/v2/hook/x")
    assert ch.send(_msg()) is True
    assert all("tenant_access_token" not in c[1] for c in calls), "Webhook 形态不得取应用 token"
    hook_calls = [c for c in calls if "bot/v2/hook" in c[1]]
    assert hook_calls and hook_calls[0][2]["msg_type"] == "interactive"
    assert isinstance(hook_calls[0][2]["card"], dict), "Webhook 形态的 card 是对象"


def test_app_form_takes_precedence(monkeypatch) -> None:
    """两形态都配好 ⇒ **优先应用形态**（与 `status_rule` 分支序一致）。"""
    calls: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls)
    ch = FeishuChannel("https://open.feishu.cn/open-apis/bot/v2/hook/x", "", "cli_x", "sec", "ou_user")
    assert ch.send(_msg()) is True
    assert any("tenant_access_token" in c[1] for c in calls), "应走应用形态"
    assert not any("bot/v2/hook" in c[1] for c in calls), "不应同时打 Webhook"


def test_token_failure_and_api_error_are_reported(monkeypatch) -> None:
    """token 失败 / 接口返回非 0 ⇒ 失败且记录原因（不静默）。"""
    calls: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls, token_ok=False)
    ch = FeishuChannel("", "", "cli_x", "bad", "ou_user")
    assert ch.send(_msg()) is False
    assert ch.last_error

    calls2: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls2, send_code=10002)
    ch2 = FeishuChannel("", "", "cli_x", "sec", "ou_user")
    assert ch2.send(_msg()) is False
    assert ch2.last_error


def test_edit_failure_is_reported(monkeypatch) -> None:
    """编辑接口返回非 0 ⇒ 失败且记录原因。"""
    calls: list[tuple[str, str, dict]] = []
    _stub(monkeypatch, calls, patch_code=10003)
    ch = FeishuChannel("", "", "cli_x", "sec", "ou_user")
    assert ch.edit_message(MessageHandle("feishu", ANCHOR_MESSAGE_ID, "om_123"), _msg()) is False
    assert ch.last_error


def test_channel_spec_declares_both_forms() -> None:
    """规格与实现同源：应用形态的必需字段必须与 `_app_configured` 判据一致。"""
    from pilotstd.core.notification.channel_spec import spec_for

    spec = spec_for("feishu")
    app_form = next(f for f in spec.forms if f.key == "app")
    assert set(app_form.required) == {"app_id", "app_secret", "receive_id"}
    # 分支序：应用优先
    assert spec.status_rule.branches[0].all_of == ("app_id", "app_secret", "receive_id")
