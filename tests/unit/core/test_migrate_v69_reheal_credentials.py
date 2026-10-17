"""v69 自愈通知渠道凭据的受控测试（体检 D-5，2026-10-17）。

背景：v37+ 的迁移在「config.json 的 channels → user_credentials」失败时吞掉异常、却仍把
`notification._migrated_to_db` 置 True ⇒ 凭据永久丢失且无日志。v69 负责在"标记为真但 DB 缺渠道"
时重做一次。本文件按**行为**断言（D-15 的教训：只测"函数被注册"等于没测）。
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from cryptography.fernet import Fernet

from pilotstd.core.db._migrate_v69_reheal_notification_credentials import (
    _migrate_v69_reheal_notification_credentials as migrate_v69,
)

USER_ID = 1


class _Db:
    """最小 DB 替身：只实现本迁移用到的 fetchall/execute（行对象按列名取值）。"""

    def __init__(self, existing: dict[str, str] | None = None) -> None:
        self.rows: dict[str, str] = dict(existing or {})

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        assert "user_credentials" in sql
        return [{"channel": channel} for channel in self.rows]

    def execute(self, sql: str, params: tuple = ()) -> None:
        assert "user_credentials" in sql
        _user_id, channel, credentials = params
        self.rows[str(channel)] = str(credentials)


class _Cfg:
    """ConfigManager 替身：只暴露迁移用到的 `_data` 与 `_filepath`。"""

    def __init__(self, notification: dict[str, Any], filepath: str = "C:/tmp/config.json") -> None:
        self._data = {"notification": notification}
        self._filepath = filepath


@pytest.fixture()
def fernet(monkeypatch) -> Fernet:
    """把 `_get_fernet` 换成一次性密钥（不落盘、不碰真实 config 目录）。"""
    key = Fernet.generate_key()
    monkeypatch.setattr(
        "pilotstd.core.config.crypto._get_fernet", lambda _dir: Fernet(key), raising=True
    )
    return Fernet(key)


def _patch_cfg(monkeypatch, cfg: _Cfg) -> None:
    monkeypatch.setattr("pilotstd.core.config.ConfigManager", lambda: cfg, raising=True)


def test_restores_missing_channels_when_flag_says_migrated(monkeypatch, fernet) -> None:
    """核心场景：标记=True + config 有 channels + DB 为空 ⇒ 补齐且可解密。"""
    _patch_cfg(monkeypatch, _Cfg({"_migrated_to_db": True, "channels": {"telegram": {"bot_token": "t"}}}))
    db = _Db()

    migrate_v69(db)

    assert set(db.rows) == {"telegram"}
    assert fernet.decrypt(db.rows["telegram"].encode()).decode() == json.dumps(
        {"bot_token": "t"}, ensure_ascii=False
    )


def test_noop_when_flag_is_false(monkeypatch, fernet) -> None:
    """旧迁移没声称做完 ⇒ 不动作（避免与正常迁移路径抢跑）。"""
    _patch_cfg(monkeypatch, _Cfg({"channels": {"telegram": {"bot_token": "t"}}}))
    db = _Db()

    migrate_v69(db)

    assert db.rows == {}


def test_noop_when_db_already_has_channel(monkeypatch, fernet) -> None:
    """DB 是 SSOT：已存在的渠道不得被 config.json 覆盖。"""
    _patch_cfg(monkeypatch, _Cfg({"_migrated_to_db": True, "channels": {"telegram": {"bot_token": "new"}}}))
    db = _Db({"telegram": "already-in-db"})

    migrate_v69(db)

    assert db.rows == {"telegram": "already-in-db"}


def test_failure_is_logged_not_raised(monkeypatch, caplog) -> None:
    """取密钥失败等确定性错误**不得**抛出（否则每次启动都重试、拖垮启动），但必须可见。"""
    _patch_cfg(monkeypatch, _Cfg({"_migrated_to_db": True, "channels": {"telegram": {"bot_token": "t"}}}))

    def _boom(_dir: str) -> Any:
        raise RuntimeError("key unavailable")

    monkeypatch.setattr("pilotstd.core.config.crypto._get_fernet", _boom, raising=True)
    db = _Db()

    with caplog.at_level("WARNING"):
        migrate_v69(db)

    assert db.rows == {}
    assert any("v69 self-heal failed" in record.message for record in caplog.records)


def test_empty_channels_is_noop(monkeypatch, fernet) -> None:
    """config 里没有渠道 ⇒ 不动（健康路径，含"从没用过通知"的部署）。"""
    _patch_cfg(monkeypatch, _Cfg({"_migrated_to_db": True, "channels": {}}))
    db = _Db()

    migrate_v69(db)

    assert db.rows == {}
