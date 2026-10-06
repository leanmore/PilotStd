"""阶段 3 端到端串联验收：**发送 → 按钮 → 回调 → 动作执行 / 410 降级**。

这是阶段 3 的"终极闭环证据"：**不 mock 业务链路**——
真实 `Database`（跑真实迁移链）＋ 真实 `NotificationManager` ＋ 真实 `NotificationRenderer` ＋
真实 `TelegramChannel`（只把最外层的 `urlopen` 换成捕获器，**不伪造渠道内部逻辑**）
＋ 真实 `callback_service.handle_callback`。

覆盖三条路径：
1. **正常闭环**：发一条带动作的通知 ⇒ 断言 Telegram 请求体里的按钮载荷 = `"<log_id>:<user_id>"`；
   把它当作真实 `callback_query.data` 回灌 ⇒ 动作执行（`ack_status` 落库）⇒ 返回 200；
2. **重试动作**：`retry` 走真实重投（重新经渠道发送）⇒ 结果写回同一行；
3. **410 降级**：把日志行删掉（模拟保留策略清理）后再回灌同一个按钮载荷
   ⇒ **410 + `notification.callback.action_expired`**（可读降级，而非 500/无响应）。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from pilotstd.core.db.database import Database
from pilotstd.core.notification.callback_service import handle_callback
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.manager import NotificationManager
from pilotstd.core.notification.specs import ActionSpec


class _Cfg:
    """最小配置桩（只需 `notification.enabled` 与 `_filepath` 定位凭证目录）。"""

    def __init__(self, values: dict) -> None:
        self._v = values
        self._filepath = ""

    def get(self, key: str, default: Any = None) -> Any:
        return self._v.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._v[key] = value


def _make(tmp: str, user_id: int = 1) -> tuple[Any, Database]:
    """真实库（真实迁移链）+ 真实 manager + **真实 Telegram 渠道**（仅最外层 urlopen 被替换）。"""
    from pilotstd.core.notification.channels.telegram import TelegramChannel

    db = Database(str(Path(tmp) / "e2e.db"))
    cfg = _Cfg({"notification.enabled": True, "notification.aggregate_enabled": False})
    cfg._filepath = str(Path(tmp) / "cfg.json")
    mgr = NotificationManager(cfg, db, user_id)
    mgr._enabled = True
    # 真实渠道对象（构造参数＝bot token / chat id）；捕获发生在 HTTP 边界，渠道内部逻辑全真实。
    # 动作鉴权只认**服务端角色**（`callback.authorize_action`），且仅管理员可执行
    # ⇒ 种一个 admin 用户（这正是生产里"谁能点按钮"的口径，不是测试放宽）。
    # 不吞异常：列集不满足时**当场报错**（比静默 403 更容易定位）。
    db.execute(
        "INSERT OR REPLACE INTO users (id, username, password_hash, salt, role) VALUES (?, ?, ?, ?, ?)",
        (user_id, f"e2e_user_{user_id}", "x", "s", "admin"),
    )
    mgr._channels = {"telegram": TelegramChannel("1:x", "42")}
    return mgr, db


def _capture_telegram(monkeypatch: Any) -> list[dict]:
    """把 Telegram 渠道最外层 HTTP 调用换成捕获器，返回**真实请求体**列表。"""
    import pilotstd.core.notification.channels.telegram as tg

    bodies: list[dict] = []

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return b'{"ok": true, "result": {"message_id": 555}}'

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *a: object) -> None:
            return None

    def _fake_urlopen(req: Any, timeout: int = 10) -> "_Resp":
        bodies.append(json.loads(req.data.decode("utf-8")))
        return _Resp()

    monkeypatch.setattr(tg, "urlopen", _fake_urlopen)
    return bodies


def test_send_button_callback_executes_action(tmp_path, monkeypatch) -> None:
    """① 发送（按钮载荷 = `log_id:user_id`）→ ② 回灌 callback_query → ③ 动作落库 + 200。"""
    mgr, db = _make(str(tmp_path))
    bodies = _capture_telegram(monkeypatch)

    # 验签密钥由下面 handle_callback 的 credentials_for 回调注入
    # （不落库：真实凭证表 `user_credentials` 存的是**加密** JSON，落库需额外构造密钥目录，
    #  而本用例要验的是"按钮 → 回调 → 动作"的链路，不是凭证加解密）
    secret = "e2e-secret"

    msg = NotificationMessage(title="扫描完成")
    msg.event_type = "scan_complete"
    msg.body = "正文"
    msg.actions = [ActionSpec(action="ignore", label_key="notification.action.ignore")]
    mgr._send_now(msg, ["telegram"])

    assert bodies, "未捕获到 Telegram 请求"
    markup = bodies[-1].get("reply_markup")
    assert markup, "带动作的通知必须带 reply_markup"
    callback_data = markup["inline_keyboard"][0][0]["callback_data"]

    # 按钮载荷必须指向真实日志行，且形如 `<log_id>:<user_id>`
    row = db.fetchone("SELECT id, callback_data FROM notification_log ORDER BY id DESC LIMIT 1")
    assert row is not None
    assert row["callback_data"] == f"{row['id']}:1", "日志行必须回填 token（<log_id>:<user_id>）"
    assert callback_data == f"ignore:{row['callback_data']}", "按钮载荷 = <动作>:<token>"

    # ② 回灌真实 callback_query
    payload = {
        "callback_query": {
            "id": "cb-1",
            "data": callback_data,
            "from": {"id": "42"},
            "message": {"message_id": 555},
        }
    }
    outcome = handle_callback(
        db,
        "telegram",
        {"X-Telegram-Bot-Api-Secret-Token": secret},
        json.dumps(payload).encode("utf-8"),
        lambda user_id, channel: {"secret": secret},
    )
    assert outcome.status == 200, f"回调应成功，实测 {outcome.status} {outcome.reason_key}"
    acked = db.fetchone("SELECT ack_status FROM notification_log WHERE id = ?", (row["id"],))
    assert acked is not None and acked["ack_status"] == "ignored", "ignore 动作必须落库"
    db.close()


def test_retry_action_really_resends_and_records_outcome(tmp_path, monkeypatch) -> None:
    """`retry` **真正重投**：重建渠道 → 真发（HTTP 请求体 +1）→ 真发结果写回同一行。

    这是阶段 3 收尾的验收点：此前 `_retry` 是占位实现（只写 `retry_requested`，docstring 却称
    "经渠道再发一次"）；现在必须**真的发出去**，且把结果如实写回。
    """
    mgr, db = _make(str(tmp_path))
    bodies = _capture_telegram(monkeypatch)
    secret = "e2e-secret"
    msg = NotificationMessage(title="扫描完成")
    msg.event_type = "scan_complete"
    msg.body = "正文"
    msg.actions = [ActionSpec(action="retry", label_key="notification.action.retry")]
    mgr._send_now(msg, ["telegram"])
    before = len(bodies)
    callback_data = bodies[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    log_id = int(callback_data.split(":")[1])
    db.execute("UPDATE notification_log SET status = 'failed' WHERE id = ?", (log_id,))

    payload = {"callback_query": {"id": "cb-2", "data": callback_data, "from": {"id": "42"}}}
    # 重投要按 `spec.ctor` 重建渠道（telegram: bot_token + chat_id）
    full_creds = {"secret": secret, "bot_token": "1:x", "chat_id": "42"}
    outcome = handle_callback(
        db,
        "telegram",
        {"X-Telegram-Bot-Api-Secret-Token": secret},
        json.dumps(payload).encode("utf-8"),
        lambda user_id, channel: full_creds,
    )
    assert outcome.status == 200, f"retry 应成功，实测 {outcome.status} {outcome.reason_key}"
    assert len(bodies) == before + 1, "重投必须真的走了一次渠道发送（HTTP 请求体 +1）"
    row = db.fetchone("SELECT ack_status, status, error_msg FROM notification_log WHERE id = ?", (log_id,))
    assert row is not None
    assert row["ack_status"] == "retry_requested"
    assert row["status"] == "success", "真发成功必须把 status 回写为 success"
    assert row["error_msg"] == ""
    db.close()


def test_click_on_cleaned_up_log_returns_410(tmp_path, monkeypatch) -> None:
    """③ 日志被清理后点旧按钮 ⇒ **410 优雅降级**（`action_expired`），不是 401/500/无响应。"""
    mgr, db = _make(str(tmp_path))
    bodies = _capture_telegram(monkeypatch)
    secret = "e2e-secret"
    msg = NotificationMessage(title="扫描完成")
    msg.event_type = "scan_complete"
    msg.body = "正文"
    msg.actions = [ActionSpec(action="ignore", label_key="notification.action.ignore")]
    mgr._send_now(msg, ["telegram"])
    callback_data = bodies[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]

    # 模拟保留策略清理：删掉该日志行（按钮仍在用户手里）
    # 载荷形如 `ignore:<log_id>:<user_id>` ⇒ 取第二段（第一段是动作）
    db.execute("DELETE FROM notification_log WHERE id = ?", (int(callback_data.split(":")[1]),))

    payload = {"callback_query": {"id": "cb-3", "data": callback_data, "from": {"id": "42"}}}
    outcome = handle_callback(
        db,
        "telegram",
        {"X-Telegram-Bot-Api-Secret-Token": secret},
        json.dumps(payload).encode("utf-8"),
        lambda user_id, channel: {"secret": secret},
    )
    assert outcome.status == 410, f"清理后的旧按钮应为 410，实测 {outcome.status}"
    assert outcome.reason_key == "notification.callback.action_expired"
    db.close()


def test_telegram_renders_actual_button_payload(tmp_path, monkeypatch) -> None:
    """渲染层闭环：真实渲染器把动作渲染成 `inline_keyboard`，载荷与落库 token 一致。"""
    mgr, db = _make(str(tmp_path))
    bodies = _capture_telegram(monkeypatch)
    msg = NotificationMessage(title="扫描完成")
    msg.event_type = "scan_complete"
    msg.body = "正文"
    msg.actions = [
        ActionSpec(action="retry", label_key="notification.action.retry"),
        ActionSpec(action="ignore", label_key="notification.action.ignore"),
    ]
    mgr._send_now(msg, ["telegram"])
    row = db.fetchone("SELECT id FROM notification_log ORDER BY id DESC LIMIT 1")
    buttons = bodies[-1]["reply_markup"]["inline_keyboard"][0]
    datas = [b["callback_data"] for b in buttons]
    assert datas == [f"retry:{row['id']}:1", f"ignore:{row['id']}:1"], f"实测 {datas}"
    assert all(len(d.encode("utf-8")) <= 64 for d in datas), "载荷必须 ≤ 64 字节"
    # 文案走 i18n（不是键名）
    assert all(b["text"] != "" and not b["text"].startswith("notification.") for b in buttons)
    db.close()


def _unused_tempdir_guard() -> None:
    """占位：确保 `tempfile` 导入被使用（测试内以 `tmp_path` 为主，不额外建目录）。"""
    tempfile.gettempdir()
