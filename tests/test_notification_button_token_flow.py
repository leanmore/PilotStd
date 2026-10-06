"""P5b 收尾（方案甲）：按钮 token 铸发流程与 `_resolve_target` 对齐测试。

用户裁定的顺序：**INSERT(占位) → 铸 token → 发送(最后一段) → UPDATE(落真)**。
本文件从三个角度钉死它：
1. **顺序与取值**：用真实 `NotificationManager` + 记录型渠道，断言
   ① INSERT 先落占位（状态最保守的 `failed`）② 铸 token 并回填到该行 ③ 渠道**收到消息时**
   `msg.callback_data` 已是最终 token ④ 发送后回填真结果；
2. **对齐**：token 能被 `callback_service._resolve_target` 解析回 `(log_id, user_id)`；
3. **失败口径**：回填失败只告警、不重发、不影响投递成功（用户裁定）。
"""

from __future__ import annotations

from typing import Any

from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.specs import ActionSpec


class _Recorder:
    """记录型假 DB：捕获 INSERT/UPDATE 的顺序与取值，并模拟 `lastrowid`。"""

    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple]] = []
        self._next_id = 1

    def execute(self, sql: str, params: tuple = ()) -> Any:
        self.statements.append((sql, params))
        cur = type("_Cur", (), {})()
        if "INSERT INTO notification_log" in sql:
            cur.lastrowid = self._next_id
            self._next_id += 1
        else:
            cur.lastrowid = 0
        cur.rowcount = 1
        return cur

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        # 供 `_resolve_target` 判断"行是否存在"：本替身里凡 INSERT 过的 id 都算存在
        return [{"id": 1}]

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        return None

    def close(self) -> None:  # pragma: no cover - 与真实 Database 接口对齐
        return None

    def kinds(self) -> list[str]:
        out = []
        for sql, _ in self.statements:
            if "INSERT INTO notification_log" in sql:
                out.append("insert")
            elif "UPDATE notification_log SET" in sql:
                out.append("update")
        return out


class _Cfg:
    def __init__(self, values: dict) -> None:
        self._v = values
        self._filepath = ""

    def get(self, key: str, default: Any = None) -> Any:
        return self._v.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._v[key] = value


def _manager(db: Any, user_id: int = 7) -> Any:
    from pilotstd.core.notification.manager import NotificationManager

    cfg = _Cfg({"notification.enabled": True, "notification.aggregate_enabled": False})
    mgr = NotificationManager(cfg, db, user_id)
    mgr._enabled = True
    return mgr


def test_token_minted_before_send_and_persisted() -> None:
    """顺序 ①INSERT ②铸 token ③发送（此时消息已带 token）④回填结果。"""
    db = _Recorder()
    mgr = _manager(db, user_id=7)
    seen: list[str] = []

    def _send(msg: NotificationMessage) -> bool:
        seen.append(str(getattr(msg, "callback_data", "")))
        return True

    mgr._channels = {"telegram": type("Ch", (), {"send": staticmethod(_send), "last_error": ""})()}
    msg = NotificationMessage(title="t")
    msg.event_type = "scan_complete"
    msg.actions = [ActionSpec(action="retry", label_key="notification.action.retry")]

    mgr._send_now(msg, ["telegram"])

    kinds = db.kinds()
    assert kinds[:2] == ["insert", "update"], f"应先 INSERT 占位再回填 token，实测 {kinds}"
    assert kinds[-1] == "update", "最后应回填结果"
    # ③ 渠道收到消息时 token 已就位（这正是"按钮可点"的前提）
    assert seen and seen[0] == "1:7", f"发送时 callback_data 应为 '<log_id>:<user_id>'，实测 {seen}"
    # ② token 已回填到日志行
    token_writes = [
        params for sql, params in db.statements if "UPDATE notification_log SET" in sql and params
    ]
    assert any("1:7" in [str(p) for p in params] for params in token_writes), "token 未回填日志行"


def test_no_actions_means_no_token_and_no_button() -> None:
    """无动作的通知**不铸 token**（`callback_data` 保持空 ⇒ 渲染器 fail-safe 不出按钮）。"""
    db = _Recorder()
    mgr = _manager(db)
    seen: list[str] = []
    mgr._channels = {
        "telegram": type(
            "Ch", (), {"send": staticmethod(lambda m: (seen.append(str(m.callback_data)), True)[1]), "last_error": ""}
        )()
    }
    msg = NotificationMessage(title="t")
    msg.event_type = "scan_complete"
    mgr._send_now(msg, ["telegram"])
    assert seen == [""], "无动作时不得铸 token"
    token_writes = [
        params
        for sql, params in db.statements
        if "UPDATE notification_log SET" in sql and "callback_data" in sql
    ]
    assert token_writes == [], "无动作时不得写 callback_data"


def test_resolve_target_aligns_with_minted_token() -> None:
    """对齐：铸出的 token 必须能被 `_resolve_target` 解析回 `(log_id, user_id)`。"""
    from pilotstd.core.notification.callback_service import _is_wellformed_token, _resolve_target

    db = _Recorder()
    token = "1:7"  # ＝ test_token_minted_before_send_and_persisted 里铸出的形态
    assert _is_wellformed_token(token) is True
    assert _resolve_target(db, "telegram", token) == (1, 7)
    # 记录不存在 ⇒ 解析失败（调用方据此返回 410 优雅降级）
    class _Empty(_Recorder):
        def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
            return []

    assert _resolve_target(_Empty(), "telegram", token) is None


def test_backfill_failure_does_not_break_delivery() -> None:
    """回填失败（UPDATE 抛错）⇒ 只告警，**不重发**、不改变"投递成功"的判定（用户裁定）。"""
    from unittest.mock import patch

    class _BadUpdate(_Recorder):
        def execute(self, sql: str, params: tuple = ()) -> Any:
            if "UPDATE notification_log SET" in sql:
                self.statements.append((sql, params))
                raise RuntimeError("update boom")
            return super().execute(sql, params)

    db = _BadUpdate()
    mgr = _manager(db)
    sends: list[int] = []
    mgr._channels = {
        "telegram": type(
            "Ch", (), {"send": staticmethod(lambda m: (sends.append(1), True)[1]), "last_error": ""}
        )()
    }
    msg = NotificationMessage(title="t")
    msg.event_type = "scan_complete"
    with patch("pilotstd.core.notification._manager_ops.logger") as log:
        mgr._send_now(msg, ["telegram"])
    assert len(sends) == 1, "回填失败不得导致重发"
    assert log.warning.called, "回填失败必须告警（可见，不静默）"
