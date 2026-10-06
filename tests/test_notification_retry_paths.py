"""阶段 3 收尾：`callback_service._retry` 的**失败口径**单测。

成功路径（真发 + 结果回写）由端到端用例覆盖（`test_notification_phase3_e2e_loop.py`）；
本文件专攻"发不出去时的如实性"——这是收尾时最容易写成"假装成功"的地方：
1. **行不存在** ⇒ `False`（调用方回 403），不得写任何状态；
2. **凭证不全/渠道停用** ⇒ `False` + 告警，**不**把没发出去记成成功；
3. **发送失败** ⇒ 写回 `status='failed'` + 渠道 `last_error`；
4. **渠道抛异常** ⇒ 写回 `failed` + 异常文本，**不得**让异常冒到端点层（否则回调 500）。
"""

from __future__ import annotations

from typing import Any

from pilotstd.core.notification.callback_service import _retry


class _Db:
    """最小库替身：记录 UPDATE，返回预设的日志行。"""

    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self._row = row
        self.updates: list[tuple[str, tuple]] = []

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return [self._row] if self._row is not None else []

    def fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        return None

    def execute(self, sql: str, params: tuple = ()) -> Any:
        self.updates.append((sql, params))
        return type("_C", (), {"rowcount": 1, "lastrowid": 1})()


def _row() -> dict[str, Any]:
    return {"title": "扫描完成", "body": "正文", "event_type": "scan_complete"}


def test_missing_row_returns_false_without_writes() -> None:
    """行不存在（日志已清理）⇒ `False`，且**不写任何状态**（不留半截痕迹）。"""
    db = _Db(None)
    assert _retry(db, 999, "telegram", {"bot_token": "1:x", "chat_id": "42"}) is False
    assert db.updates == []


def test_incomplete_credentials_skips_and_warns(caplog) -> None:
    """凭证不全（缺 `ctor_required`）⇒ `False` + 告警；只留 `retry_requested` 的如实记录。"""
    import logging

    db = _Db(_row())
    with caplog.at_level(logging.WARNING, logger="pilotstd.core.notification.callback_service"):
        assert _retry(db, 7, "telegram", {"secret": "s"}) is False
    assert any("retry skipped" in r.getMessage() for r in caplog.records)
    kinds = [sql for sql, _ in db.updates]
    assert any("ack_status" in sql for sql in kinds), "请求动作本身应如实记录"
    assert not any("SET status = ?" in sql for sql in kinds), "没发出去就不得改写 status"


def test_disabled_channel_skips() -> None:
    """渠道显式停用（`enabled=false`）⇒ `False`，同样不写 status。"""
    db = _Db(_row())
    creds = {"bot_token": "1:x", "chat_id": "42", "enabled": "false"}
    assert _retry(db, 7, "telegram", creds) is False
    assert not any("SET status = ?" in sql for sql, _ in db.updates)


def test_send_failure_records_last_error(monkeypatch) -> None:
    """真发失败 ⇒ `status='failed'` 且写回渠道 `last_error`（不谎报成功）。"""
    from pilotstd.core.notification import channel_spec

    class _Failing:
        last_error = "HTTP 404: Not Found"

        def __init__(self, *args: object) -> None:
            pass

        def send(self, msg: object) -> bool:
            return False

    monkeypatch.setattr(channel_spec, "channel_class", lambda spec: _Failing)
    db = _Db(_row())
    assert _retry(db, 7, "telegram", {"bot_token": "1:x", "chat_id": "42"}) is False
    final = [params for sql, params in db.updates if "SET status = ?" in sql][-1]
    assert final[0] == "failed"
    assert final[1] == "HTTP 404: Not Found"


def test_channel_exception_is_contained(monkeypatch) -> None:
    """渠道抛异常 ⇒ 写回 `failed` + 异常文本；**异常不得冒到端点**（否则回调 500）。"""
    from pilotstd.core.notification import channel_spec

    class _Raising:
        last_error = ""

        def __init__(self, *args: object) -> None:
            pass

        def send(self, msg: object) -> bool:
            raise RuntimeError("boom")

    monkeypatch.setattr(channel_spec, "channel_class", lambda spec: _Raising)
    db = _Db(_row())
    assert _retry(db, 7, "telegram", {"bot_token": "1:x", "chat_id": "42"}) is False
    final = [params for sql, params in db.updates if "SET status = ?" in sql][-1]
    assert final[0] == "failed"
    assert "boom" in str(final[1])
