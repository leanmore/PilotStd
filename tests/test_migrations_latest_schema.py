"""最新 schema 的结果断言（体检 D-15，2026-10-17）。

体检发现：`tests/test_migrations_full.py` 只到 v38，v39~v69 仅有"函数已注册"检查，
**没有 schema 结果断言**——迁移函数写错列名/漏建表时，注册检查照样通过。

本文件在**空库**上跑完整迁移链（v2~v69），断言最终 schema 的关键表/列/索引/默认值。
不替代逐函数单测，只兜住"迁移链跑完是错的"这类整体性缺陷。
"""

from __future__ import annotations

import pytest

from pilotstd.core.db import CURRENT_SCHEMA_VERSION, MIGRATIONS, Database


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    """空库跑完整迁移链（只建一次，模块内共享）。"""
    path = tmp_path_factory.mktemp("mig_latest") / "fresh.db"
    db = Database(str(path))
    yield db
    db.close()


def _columns(db: Database, table: str) -> set[str]:
    return {row["name"] for row in db.fetchall(f"PRAGMA table_info({table})")}


def test_schema_version_reaches_current(fresh_db: Database) -> None:
    row = fresh_db.fetchone("SELECT MAX(version) AS v FROM _schema_version")
    assert row is not None
    # 不写死具体版本号（tests/test_notification_stage1b_fields.py 明令禁止，
    # 否则每加一条迁移就要改这里）；下限 69 只用于防"迁移链提前截断"
    assert row["v"] == CURRENT_SCHEMA_VERSION
    assert CURRENT_SCHEMA_VERSION >= 69


def test_all_migrations_registered_and_contiguous() -> None:
    """v2~v69 连续注册（v1 为建库基线，无迁移函数）。"""
    assert sorted(MIGRATIONS) == list(range(2, CURRENT_SCHEMA_VERSION + 1))


@pytest.mark.parametrize(
    "table",
    ["user_preferences", "user_favorites", "app_preferences", "favorite_downloads"],
)
def test_tables_introduced_after_v38_exist(fresh_db: Database, table: str) -> None:
    row = fresh_db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    assert row is not None, f"{table} 未建（v44/v50/v52/v58 迁移链结果缺失）"


@pytest.mark.parametrize(
    ("table", "column"),
    [
        # v51：适配器健康探测
        ("adapter_state", "last_health_check"),
        ("adapter_state", "health_status"),
        # v62：通知身份
        ("notification_log", "message_id"),
        ("notification_log", "correlation_id"),
        ("notification_log", "delivery_status"),
        ("notification_log", "ack_status"),
        # v63：任务视角
        ("notification_log", "task_id"),
        ("notification_log", "notify_event"),
        ("notification_log", "content_type"),
        ("notification_log", "task_context"),
        # v64：交互能力
        ("notification_log", "actions"),
        ("notification_log", "callback_data"),
        ("notification_log", "attachments"),
        ("notification_log", "channel_message_ids"),
        # v65~v68
        ("notification_log", "task_kind"),
        ("notification_log", "failed_items"),
        ("announcement_record", "final_name"),
        ("notification_policy", "event_classes"),
    ],
)
def test_columns_introduced_after_v38_exist(fresh_db: Database, table: str, column: str) -> None:
    assert column in _columns(fresh_db, table), f"{table}.{column} 缺失"


def test_v62_defaults_are_contract_values(fresh_db: Database) -> None:
    """v62 的两个状态列默认值是读取方契约（pending/none），必须与代码默认一致。"""
    defaults = {
        row["name"]: row["dflt_value"]
        for row in fresh_db.fetchall("PRAGMA table_info(notification_log)")
    }
    assert defaults["delivery_status"] == "'pending'"
    assert defaults["ack_status"] == "'none'"


def test_v53_composite_index_exists(fresh_db: Database) -> None:
    row = fresh_db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='index'"
        " AND name='idx_announcement_record_announce_no_std'"
    )
    assert row is not None, "v53 分页复合索引未创建"
