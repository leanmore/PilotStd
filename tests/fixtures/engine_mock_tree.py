"""Engine/DB/Channel Mock 基础设施 — 供扫射补测使用。

提供三个桩对象，均支持上下文管理器自动清理：

    with EngineCoreMock() as core:
        handler = MiniBucketHandler(core, routing, single)
        ...

    with MemoryDB() as db:
        db.execute("CREATE TABLE ...")
        ...

    with ChannelStub("telegram") as ch:
        NotificationManager(config, db, user_id)._channels["telegram"] = ch

Runtime Protocol 校验确保桩接口与真实对象一致。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Callable
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════
# EngineCore 桩 — 提供 _mini_bucket 等查询引擎模块所需的注入点
# ═══════════════════════════════════════════════════════════════

class EngineCoreMock:
    """模拟 EngineCore，提供 rotator/db/ctx 和线程安全锁。

    使用方式:
        with EngineCoreMock() as core:
            core.rotator._sites["test"] = site_state
            handler = SomeHandler(core, routing, single)
    """

    def __init__(self, rotator_sites: dict[str, Any] | None = None):
        self.rotator = MagicMock()
        self.rotator._sites = rotator_sites or {}
        self.rotator.get_cooldown_remaining = lambda name: max(
            0, (self.rotator._sites[name].cooldown_until - __import__("time").time())
            if name in self.rotator._sites and self.rotator._sites[name].cooldown_until > 0
            else 0
        )
        self.rotator.record_success = MagicMock()
        self.rotator.record_error = MagicMock()
        self.rotator._save = MagicMock()

        self.db = MagicMock()
        self._lock = threading.Lock()
        self.ctx: dict[str, Any] = {"metrics": MagicMock()}

        # 模拟 _batch_dispatch 需要的属性
        self.dispatch = MagicMock()
        self.DEFAULT_TIMEOUT = 30
        self.MAX_RETRIES = 3
        self.MIN_BATCH_SIZE = 10

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ═══════════════════════════════════════════════════════════════
# 内存 DB 工厂 — SQLite :memory: 连接 + schema 初始化
# ═══════════════════════════════════════════════════════════════

NOTIFICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    title TEXT,
    body TEXT,
    standard_number TEXT,
    status TEXT NOT NULL DEFAULT 'success',
    error_msg TEXT,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_read INTEGER DEFAULT 0,
    aggregated_count INTEGER DEFAULT 1,
    link TEXT,
    icon TEXT
);

CREATE TABLE IF NOT EXISTS notification_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    scheduled_time TEXT,
    error_msg TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_policy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    channel TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    events TEXT NOT NULL DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, channel)
);

CREATE TABLE IF NOT EXISTS user_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    record_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    local_path TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    publish_date TEXT,
    last_archive_attempt TEXT,
    archive_retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (record_id) REFERENCES announcement_record(id),
    UNIQUE(user_id, record_id)
);

CREATE TABLE IF NOT EXISTS favorite_downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    favorite_id INTEGER NOT NULL,
    record_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    local_path TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (favorite_id) REFERENCES user_favorites(id) ON DELETE CASCADE,
    FOREIGN KEY (record_id) REFERENCES announcement_record(id),
    UNIQUE(favorite_id, record_id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, preference_key)
);

CREATE TABLE IF NOT EXISTS user_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    credentials TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, channel)
);
"""


class MemoryDB:
    """SQLite :memory: 连接工厂，自动建表并支持上下文管理。

    使用方式:
        with MemoryDB() as db:
            db.execute("INSERT INTO ...")
            rows = db.fetchall("SELECT * FROM ...")
    """

    def __init__(self):
        self.conn: sqlite3.Connection | None = None

    def __enter__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(NOTIFICATION_SCHEMA)
        self.conn.commit()
        return self

    def __exit__(self, *args):
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute(self, sql: str, params: tuple | None = None) -> sqlite3.Cursor:
        if params:
            return self.conn.execute(sql, params)
        return self.conn.execute(sql)

    def fetchone(self, sql: str, params: tuple | None = None):
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql: str, params: tuple | None = None):
        cur = self.execute(sql, params)
        return cur.fetchall()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


# ═══════════════════════════════════════════════════════════════
# Notification Channel 桩 — 模拟渠道实例，记录 send 调用
# ═══════════════════════════════════════════════════════════════

class ChannelStub:
    """模拟通知渠道，send() 记录调用历史，成功/失败可配置。

    使用方式:
        ch = ChannelStub("telegram", should_succeed=True)
        assert ch.send(msg) is True
        assert len(ch.sent) == 1
    """

    def __init__(self, name: str = "stub", should_succeed: bool = True):
        self.name = name
        self.should_succeed = should_succeed
        self.sent: list[Any] = []

    def send(self, message: Any) -> bool:
        self.sent.append(message)
        return self.should_succeed

    @staticmethod
    def validate_config(config: dict) -> bool:
        return bool(config)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ═══════════════════════════════════════════════════════════════
# Config 桩 — 模拟配置对象，支持多层 key 访问
# ═══════════════════════════════════════════════════════════════

class ConfigStub:
    """模拟配置对象，支持点号分隔的多层 key。

    使用方式:
        cfg = ConfigStub({"notification.enabled": True, "notification.channels": ["telegram"]})
        assert cfg.get("notification.enabled") is True
    """

    def __init__(self, defaults: dict[str, Any] | None = None):
        self._data: dict[str, Any] = defaults or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ═══════════════════════════════════════════════════════════════
# MiniBucketHandler Mock Tree — 完整的 EngineCore+Routing+Single
# ═══════════════════════════════════════════════════════════════

@contextmanager
def mini_bucket_mock_tree(sites_config: dict | None = None):
    """构建 MiniBucketHandler 所需的完整 Mock 树。

    Yields: (core, routing, single) 三元组，可直接注入 MiniBucketHandler。
    """
    from dataclasses import dataclass, field

    @dataclass
    class SiteState:
        name: str = ""
        base_url: str = ""
        max_requests: int = 200
        daily_limit: int = 800
        cooldown_seconds: int = 600
        request_interval: float = 0.5
        request_count: int = 0
        daily_count: int = 0
        daily_date: str = ""
        cooldown_until: float = 0.0
        consecutive_errors: int = 0
        active_url: str = ""
        fallback_urls: list = field(default_factory=list)

    core = EngineCoreMock()
    if sites_config:
        for name, cfg in sites_config.items():
            site = SiteState(name=name, **cfg)
            core.rotator._sites[name] = site

    routing = MagicMock()
    single = MagicMock()

    try:
        yield core, routing, single
    finally:
        pass
