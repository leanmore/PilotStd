"""A-21 v71：加列/回填/索引/幂等/缺表跳过。"""

from pilotstd.core.db._migrate_v71_notification_user_id import _migrate_v71_notification_user_id


class FakeDB:
    def __init__(self):
        self.columns = {"notification_log": {"id"}, "notification_queue": {"id"}}
        self.sql = []

    def fetchall(self, sql, params=()):
        table = "notification_log" if "notification_log" in sql else "notification_queue"
        return [{"name": c} for c in self.columns[table]]

    def execute(self, sql, params=()):
        self.sql.append(sql)
        table = "notification_log" if "notification_log" in sql else "notification_queue"
        if sql.startswith("ALTER TABLE"):
            self.columns[table].add("user_id")


def test_adds_columns_and_indexes():
    db = FakeDB()
    _migrate_v71_notification_user_id(db)
    assert "user_id" in db.columns["notification_log"]
    assert "user_id" in db.columns["notification_queue"]
    assert any("idx_nl_user_sent" in s for s in db.sql)
    assert any("idx_nq_user_status" in s for s in db.sql)


def test_backfill_sets_one():
    db = FakeDB()
    _migrate_v71_notification_user_id(db)
    assert sum("SET user_id = 1" in s for s in db.sql) == 2


def test_idempotent_no_duplicate_alter():
    db = FakeDB()
    _migrate_v71_notification_user_id(db)
    first = len([s for s in db.sql if s.startswith("ALTER TABLE")])
    _migrate_v71_notification_user_id(db)
    assert len([s for s in db.sql if s.startswith("ALTER TABLE")]) == first == 2


def test_missing_table_skipped():
    class EmptyDB(FakeDB):
        def fetchall(self, sql, params=()):
            return []

    db = EmptyDB()
    _migrate_v71_notification_user_id(db)
    assert not [s for s in db.sql if s.startswith("ALTER TABLE")]
