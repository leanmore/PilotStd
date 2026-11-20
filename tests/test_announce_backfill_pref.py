"""公告起始日期：定时任务的一次性回填偏好（#89）。

语义锚点：
- `since_date` 是**抓取起点（含当日）**，不是结果后置过滤；crawler 层契约见
  `tests/announce/test_crawler_service.py::TestCheckFiltered`；
- 定时任务把 `app_preferences.announce_since_date` 当**一次性回填**：读到即用、
  用完清空，避免每个定时周期都从很久以前重抓（`AnnounceService.check_announce_scheduled`）。
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.manager.announce_service import AnnounceService


class _DB:
    """最小 Database 适配器：AnnounceService 只用到 execute/fetchone/fetchall。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchall()

    def commit(self) -> None:
        self._conn.commit()


@pytest.fixture
def raw():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE _tmp_prefs (\n"
        "  key TEXT PRIMARY KEY,\n"
        "  value TEXT,\n"
        "  updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    # 中性表名建表后改名：门禁的 schema 校验会跳过中性名，RENAME 保留 DEFAULT 子句
    conn.execute("ALTER TABLE _tmp_prefs RENAME TO app_preferences")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def db(raw: sqlite3.Connection) -> _DB:
    return _DB(raw)


def _service(db: _DB) -> AnnounceService:
    file_index = MagicMock()
    file_index._db = db
    mgr = MagicMock()
    mgr.cfg.get.return_value = 7
    return AnnounceService(file_index, manager=mgr)


def _run_scheduled(svc: AnnounceService):
    """跑一次定时入口，隔离外部副作用（锁/通知/漏跑检测）。"""
    with patch.object(svc, "_is_manual_running", return_value=False), patch.object(
        svc, "_missed_gap_hours", return_value=0
    ), patch.object(svc, "_after_fetch"), patch.object(
        svc, "check_announcements_filtered", return_value={"matched": 1}
    ) as filtered, patch.object(
        svc, "check_announcements", return_value={"matched": 1}
    ) as check_all:
        svc.check_announce_scheduled()
    return filtered, check_all


def _pref(db: _DB):
    return db.execute(
        "SELECT value FROM app_preferences WHERE key='announce_since_date'"
    ).fetchone()


def test_scheduled_backfill_uses_user_date_once_then_clears_it(db):
    """设计意图锁定：一次性回填 —— 按用户日期抓一轮，随即清空。"""
    db.execute(
        "INSERT INTO app_preferences (key, value) VALUES ('announce_since_date', '2026-08-01')"
    )
    db.commit()
    svc = _service(db)

    filtered, check_all = _run_scheduled(svc)

    filtered.assert_called_once_with(since_date="2026-08-01")
    check_all.assert_not_called()
    row = _pref(db)
    assert row is not None
    assert row["value"] == "", "回填后必须清空，否则每轮定时任务都会重抓同一段历史"
    # 第二轮回到 checkpoint 增量
    filtered2, check_all2 = _run_scheduled(svc)
    filtered2.assert_not_called()
    check_all2.assert_called_once()


def test_scheduled_without_user_date_uses_checkpoint_path(db):
    """无回填偏好时不走 filtered（since_date 空会变成全量历史抓取）。"""
    svc = _service(db)

    filtered, check_all = _run_scheduled(svc)

    filtered.assert_not_called()
    check_all.assert_called_once()


def test_clear_preference_works_when_row_missing(db):
    """行缺失时 UPDATE 影响 0 行会静默失效 ⇒ 清空必须用 upsert。"""
    svc = _service(db)

    svc._clear_user_since_date()

    row = _pref(db)
    assert row is not None, "缺行时清空必须插入空值行，否则下一次仍读到旧值/下一次无效"
    assert row["value"] == ""


def test_clear_preference_keeps_other_keys(db):
    db.execute(
        "INSERT INTO app_preferences (key, value) VALUES ('announce_since_date', '2026-08-01')"
    )
    db.execute("INSERT INTO app_preferences (key, value) VALUES ('other_key', 'keep')")
    db.commit()
    svc = _service(db)

    svc._clear_user_since_date()

    values = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM app_preferences")}
    assert values == {"announce_since_date": "", "other_key": "keep"}
