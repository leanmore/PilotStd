"""批次一：启动阻断三修（v57 回填幂等 / schema_version 读失败阻断 / 迁移前备份）。

三个缺陷都会在启动期破坏数据或挂死进程，故测试都带看门狗，回归时失败而不是挂住 CI。
"""

import sqlite3
import threading

import pytest

from pilotstd.core.db import Database
from pilotstd.core.db._migrate_v57 import (
    _backfill_announcement_record,
    _backfill_favorite_tables,
)


def _run_with_watchdog(fn, timeout=10):
    """在子线程执行 fn；超时视为失败（防回填死循环把测试挂死）。"""
    result = {}
    done = threading.Event()

    def runner():
        try:
            result["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - 测试需要把异常带回主线程
            result["error"] = exc
        finally:
            done.set()

    threading.Thread(target=runner, daemon=True).start()
    assert done.wait(timeout), "函数未在超时内返回（疑似死循环）"
    if "error" in result:
        raise result["error"]
    return result.get("value")


@pytest.fixture()
def db(tmp_path):
    return Database(str(tmp_path / "t.db"))


def test_backfill_announcement_record_is_idempotent(db):
    """映射不到的 source_site 必须保持 Unknown，第二次执行 affected=0。"""
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, standard_number, fetched_at, standard_type)"
        " VALUES ('announcement_gb','p1','GB 1-2020','2026-01-01','Unknown')"
    )
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, standard_number, fetched_at, standard_type)"
        " VALUES ('announcement_mystery','p2','XX 2-2020','2026-01-01','Unknown')"
    )

    first = _run_with_watchdog(lambda: _backfill_announcement_record(db))
    assert first == 1
    rows = {
        r["source_site"]: r["standard_type"]
        for r in db.fetchall("SELECT source_site, standard_type FROM announcement_record")
    }
    assert rows["announcement_gb"] == "NationalStd"
    assert rows["announcement_mystery"] == "Unknown"

    second = _run_with_watchdog(lambda: _backfill_announcement_record(db))
    assert second == 0


def test_backfill_favorite_tables_terminates_on_unknown_record(db):
    """收藏表关联到的记录仍是 Unknown 时不得写回 Unknown，必须终止。"""
    db.execute(
        "INSERT INTO users (id, username, password_hash, salt) VALUES (1,'u1','x','s')"
    )
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, standard_number, fetched_at, standard_type)"
        " VALUES ('announcement_mystery','p1','XX 1-2020','2026-01-01','Unknown')"
    )
    rec_id = db.fetchone("SELECT id FROM announcement_record")["id"]
    db.execute(
        "INSERT INTO user_favorites (user_id, record_id, standard_type) VALUES (1, ?, 'Unknown')",
        (rec_id,),
    )

    uf, fd, dq = _run_with_watchdog(lambda: _backfill_favorite_tables(db))
    assert (uf, fd, dq) == (0, 0, 0)
    assert db.fetchone("SELECT standard_type FROM user_favorites")["standard_type"] == "Unknown"

    # 关联记录补上具体类型后，收藏行才会被回填一次
    db.execute("UPDATE announcement_record SET standard_type='NationalStd'")
    uf2, _, _ = _run_with_watchdog(lambda: _backfill_favorite_tables(db))
    assert uf2 == 1
    assert db.fetchone("SELECT standard_type FROM user_favorites")["standard_type"] == "NationalStd"
    assert _run_with_watchdog(lambda: _backfill_favorite_tables(db))[0] == 0


def test_schema_version_returns_zero_only_when_table_missing(db):
    db.execute("DROP TABLE _schema_version")
    assert db.schema_version == 0


def test_schema_version_read_error_blocks_startup(tmp_path, monkeypatch):
    """读版本异常必须抛出并阻止启动，不能从 v1 重跑迁移。"""
    from pilotstd.core.db import DatabaseError
    from pilotstd.core.db.database import Database as DBClass

    path = str(tmp_path / "t.db")
    DBClass(path).close()  # 建好库（版本已到 CURRENT_SCHEMA_VERSION）

    original = DBClass.fetchone

    def broken(self, sql, params=()):
        if "_schema_version" in sql:
            raise DatabaseError("模拟读版本失败")
        return original(self, sql, params)

    monkeypatch.setattr(DBClass, "fetchone", broken)
    with pytest.raises(DatabaseError):
        DBClass(path)


def test_migration_backup_created_for_legacy_db_without_schema_table(tmp_path):
    """没有 _schema_version 但已有业务表的旧库：迁移前必须留下备份。"""
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE legacy_probe (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()

    Database(str(path)).close()

    backups = list((tmp_path / "backups").glob("pre_migration_v0_to_*.bak"))
    assert backups, "旧库（current=0 但非空）迁移前必须备份"
    assert backups[0].stat().st_size > 0


def test_migration_aborts_when_backup_fails(tmp_path, monkeypatch):
    """备份失败必须中止迁移，而不是无备份继续改 schema。"""
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE legacy_probe (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()

    from pilotstd.core.db import DatabaseError as DBErr
    from pilotstd.core.db.database import Database as DBClass

    monkeypatch.setattr(DBClass, "backup", lambda self, p=None: "")
    with pytest.raises(DBErr):
        DBClass(str(path))


def test_no_backup_for_fresh_empty_db(tmp_path):
    """全新空库不应产生 v0 备份（无数据可回滚）。"""
    Database(str(tmp_path / "fresh.db")).close()
    assert not (tmp_path / "backups").exists()


def test_v57_registered_function_checksum_pinned():
    """守卫：可回填 helper 可改，但已注册的 v57 迁移函数源码不得变（P-106）。"""
    from pilotstd.core.db._constants import MIGRATIONS
    from pilotstd.core.db._migration_checksum import norm_checksum

    assert (
        norm_checksum(MIGRATIONS[57])
        == "3ecf0b3e1c83c5edfb5abcb2a4ef57aba54ed4864cffc2f581fe6d2c7167952a"
    )
