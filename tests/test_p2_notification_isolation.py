"""P2 集成验证：通知队列 / 聚合必须按用户隔离（2026-11-14 多用户主线）。

不碰生产：每个用例用临时 SQLite 库跑完整迁移链，构造真实 `NotificationManager`。
生产环境（`docker/manager.py`）是进程内**单例** StandardManager ⇒ 多用户共享同一个
manager、同一个 `NotificationAggregator` 与 `notification_queue`，故本文件只建一个
manager，用 `NotificationContext` 区分触发者（user 1 / user 2 / system）。

P2 完成判据（docs/plans/2026-11-14-multiuser-mainline.md §P2）：
1. `notification_queue` 行的 `user_id` 与 `event_data.user_id` 均等于触发者，system=0；
2. 聚合分组键含用户维度：不同用户同 event_type 不得进同一缓冲组、不得生成跨用户摘要；
3. system(0) 自成一户；队列补发按队列行的 owner 选择该用户渠道。

本文件只新增测试，不改生产代码；断言失败即暴露跨用户缺陷（失败消息内附实测数据）。
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest

from pilotstd.core.db import Database
from pilotstd.core.notification.context import NotificationContext
from pilotstd.core.notification.manager import NotificationManager

EVENT_TYPE = "archive_complete"  # notify_event=batch_summary，P1 已实测的用户触发事件


class _Cfg:
    """最小配置对象（与项目 ConfigManager 的点分隔 get 接口一致）。"""

    def __init__(self, path: str, data: dict[str, object]):
        self._filepath = path
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


class _Policy:
    """策略桩：所有用户/事件都订阅 web 渠道。"""

    def get_channels_for_event(self, user_id, event_type, event_data):
        return ["web"]


class _Channel:
    """渠道桩：记录实际收到的消息。"""

    name = "web"

    def __init__(self):
        self.sent: list = []

    def send(self, msg) -> bool:
        self.sent.append(msg)
        return True


def _quiet_hours_window() -> tuple[str, str]:
    """构造一个必然包含“当前时刻”的静音窗口（±2h，支持跨零点）。"""
    now = datetime.now()
    return (
        (now - timedelta(hours=2)).strftime("%H:%M"),
        (now + timedelta(hours=2)).strftime("%H:%M"),
    )


@pytest.fixture()
def env(tmp_path):
    """构造临时库 + 真实 manager；返回 `(db, manager, {user_id: channel})`。"""
    managers: list[NotificationManager] = []
    databases: list[Database] = []

    def build(*, quiet_hours: bool, window_seconds: float = 60.0):
        db = Database(str(tmp_path / "p2_isolation.db"))
        databases.append(db)
        for uid, role in ((1, "admin"), (2, "user")):
            db.execute(
                "INSERT INTO users (id, username, password_hash, salt, role) VALUES (?,?,?,?,?)",
                (uid, f"u{uid}", "h", "s", role),
            )

        quiet_start, quiet_end = _quiet_hours_window()
        cfg = _Cfg(
            str(tmp_path / "config.json"),
            {
                # 先按“未启用”构造，避免 _init_channels 去读真实凭证；随后显式打开投递。
                "notification.enabled": False,
                "notification.aggregate_enabled": True,
                "notification.aggregate_window_seconds": window_seconds,
                "notification.aggregate_max_events": 50,
                "notification.quiet_hours_enabled": quiet_hours,
                "notification.quiet_hours_start": quiet_start,
                "notification.quiet_hours_end": quiet_end,
                "notification.queue_expire_hours": 72,
                "notification.release_max_per_tick": 100,
            },
        )
        mgr = NotificationManager(cfg, db, user_id=1)
        mgr._enabled = True
        mgr._system_enabled = True
        mgr._policy = _Policy()

        channels = {1: _Channel(), 2: _Channel()}
        mgr._channels = {"web": channels[1]}
        mgr.channels_for = lambda uid: {"web": channels[uid if uid in channels else 1]}
        managers.append(mgr)
        return db, mgr, channels

    yield build

    for mgr in managers:
        try:
            if mgr.aggregator is not None:
                mgr.aggregator.shutdown()
        except Exception:
            pass
    for db in databases:
        db.close()


def _user(uid: int) -> NotificationContext:
    return NotificationContext(scope="admin", user_id=uid)


def _system() -> NotificationContext:
    return NotificationContext(scope="system")


def _send_concurrently(mgr: NotificationManager, contexts: list[NotificationContext]) -> None:
    """所有用户在同一屏障后并发触发同一 event_type（真实线程并发）。"""
    barrier = threading.Barrier(len(contexts))

    def worker(ctx: NotificationContext) -> None:
        barrier.wait(timeout=10)
        mgr.send_event(EVENT_TYPE, {"count": 1}, context=ctx)

    with ThreadPoolExecutor(max_workers=len(contexts)) as pool:
        list(pool.map(worker, contexts))


def _queue_rows(db: Database) -> list[dict]:
    rows = [dict(r) for r in db.fetchall(
        "SELECT id, user_id, event_type, event_data, status FROM notification_queue ORDER BY id"
    )]
    observed = []
    for row in rows:
        payload = json.loads(row["event_data"] or "{}")
        observed.append(
            {
                "id": row["id"],
                "db_user_id": row["user_id"],
                "payload_user_id": payload.get("user_id"),
                "event_type": row["event_type"],
                "status": row["status"],
            }
        )
    return observed


def _log_rows(db: Database) -> list[dict]:
    return [dict(r) for r in db.fetchall(
        "SELECT id, user_id, event_type, aggregated_count, notify_event "
        "FROM notification_log ORDER BY id"
    )]


def test_queue_rows_keep_per_user_owner(env):
    """队列行归属：user1→1、user2→2、system→0，列与 event_data 不得互相错位。"""
    db, mgr, _channels = env(quiet_hours=True)
    _send_concurrently(mgr, [_user(1), _user(2), _system()])

    observed = _queue_rows(db)
    assert len(observed) == 3, f"静音期每个触发者应各入队一行；observed={observed}"

    mismatched = [
        (row["db_user_id"], row["payload_user_id"])
        for row in observed
        if row["db_user_id"] != row["payload_user_id"]
    ]
    assert not mismatched, (
        "notification_queue.user_id 与 event_data.user_id 错位（system=0 被改成 1）；"
        f"mismatches={mismatched}; observed={observed}"
    )
    assert sorted(row["db_user_id"] for row in observed) == [0, 1, 2], (
        f"队列行的用户归属应恰为 system(0)/user1/user2；observed={observed}"
    )
    assert all(row["event_type"] == EVENT_TYPE for row in observed), observed


def test_aggregation_never_merges_users(env):
    """聚合隔离：同 event_type 的两个用户 + system 不得共享分组；刷新后各一条日志。"""
    db, mgr, _channels = env(quiet_hours=False, window_seconds=60.0)
    assert mgr.aggregator is not None, "本用例需要启用聚合器"

    _send_concurrently(mgr, [_user(1), _user(2), _system()])

    # 窗口 60s 内不会触发定时器；此处快照缓冲分组后再强制刷新。
    buffers = {
        key: [entry[0].user_id for entry in entries]
        for key, entries in mgr.aggregator._buffers.items()
    }
    mgr.aggregator.flush_all()
    logs = _log_rows(db)
    observed = {"buffer_owners": buffers, "log_rows": logs}

    mixed = {key: owners for key, owners in buffers.items() if len(set(owners)) > 1}
    assert not mixed, (
        "聚合缓冲把不同用户（含 system=0）并进同一分组，合并消息会只归属首条消息的用户；"
        f"mixed={mixed}; observed={observed}"
    )
    assert sorted(row["user_id"] for row in logs) == [0, 1, 2], (
        f"刷新后应各用户一条日志，不得跨用户合并成一条；observed={observed}"
    )
    assert all(row["aggregated_count"] == 1 for row in logs), (
        f"任何一条日志都不得代表多个用户的事件；observed={observed}"
    )


def test_queue_release_routes_to_queue_owner(env):
    """补发归属：user2 的静音消息必须走 user2 的渠道，不能落到 manager 默认用户。"""
    db, mgr, channels = env(quiet_hours=True)
    _send_concurrently(mgr, [_user(1), _user(2)])

    queued = _queue_rows(db)
    assert sorted(row["db_user_id"] for row in queued) == [1, 2], queued

    # 让两条排队消息立即到期（不改 created_at，避免被 expire 判过期）。
    db.execute(
        "UPDATE notification_queue SET scheduled_time='2000-01-01T00:00:00' WHERE status='suppressed'"
    )
    assert mgr.release_suppressed_notifications() == 2

    observed = {
        "user1_channel": [(m.user_id, m.delivery_user_id) for m in channels[1].sent],
        "user2_channel": [(m.user_id, m.delivery_user_id) for m in channels[2].sent],
        "log_rows": _log_rows(db),
    }
    assert sorted(m.user_id for m in channels[2].sent) == [2], (
        "user2 的静音消息未被投递到 user2 的渠道（补发丢失 delivery owner，落回 manager 默认用户）；"
        f"observed={observed}"
    )
    assert sorted(m.user_id for m in channels[1].sent) == [1], (
        f"user1 的渠道不应收到其他用户的消息；observed={observed}"
    )
    assert all(
        m.delivery_user_id == m.user_id for m in [*channels[1].sent, *channels[2].sent]
    ), f"补发消息的 delivery_user_id 应等于队列行的 user_id；observed={observed}"
