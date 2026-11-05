"""空白库全量迁移：v1→v72 不得出现任何 OperationalError / SQL 执行失败日志。"""

import logging

from pilotstd.core.db import Database
from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION


def test_blank_db_migration_has_no_operational_error(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger="pilotstd.db")
    db_path = tmp_path / "blank.db"
    db = Database(str(db_path))
    try:
        assert db.schema_version == CURRENT_SCHEMA_VERSION
        cache_cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
        assert {"source_version", "data_state", "last_accessed_at"} <= cache_cols
        policy_cols = {r["name"] for r in db.fetchall("PRAGMA table_info(notification_policy)")}
        assert "user_id" in policy_cols
    finally:
        db.close()

    assert "OperationalError" not in caplog.text, caplog.text
    assert "SQL执行失败" not in caplog.text, caplog.text
