"""v73：历史裸时间字符串补齐时区偏移；已带偏移的行保持不变。"""

from pilotstd.core.db import Database
from pilotstd.core.db._migrate_v73_normalize_timestamps import (
    _migrate_v73_normalize_timestamps,
    _offset,
)


def test_v73_normalizes_bare_timestamps(tmp_path):
    db = Database(str(tmp_path / "v73.db"))
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status, scanned_at)"
        " VALUES ('/x.pdf','GB/T',1,2020,-1,'x','现行','2026-11-06 14:30:00')"
    )
    db.execute(
        "INSERT INTO audit_logs (action, resource, detail, user_id, timestamp)"
        " VALUES ('T','r','{}',1,'2026-11-06T14:30:00')"
    )
    db.execute(
        "INSERT INTO audit_logs (action, resource, detail, user_id, timestamp)"
        " VALUES ('T2','r','{}',1,'2026-11-06T14:30:00+00:00')"
    )
    _migrate_v73_normalize_timestamps(db)
    scanned = db.fetchone("SELECT scanned_at FROM file_index")["scanned_at"]
    assert scanned == f"2026-11-06T14:30:00{_offset()}"
    rows = db.fetchall("SELECT timestamp FROM audit_logs ORDER BY id")
    assert rows[0]["timestamp"] == f"2026-11-06T14:30:00{_offset()}"
    assert rows[1]["timestamp"] == "2026-11-06T14:30:00+00:00"
    db.close()


def test_v73_is_idempotent(tmp_path):
    db = Database(str(tmp_path / "v73b.db"))
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status, scanned_at)"
        " VALUES ('/x.pdf','GB/T',1,2020,-1,'x','现行','2026-11-06 14:30:00')"
    )
    _migrate_v73_normalize_timestamps(db)
    _migrate_v73_normalize_timestamps(db)
    assert db.fetchone("SELECT scanned_at FROM file_index")["scanned_at"] == f"2026-11-06T14:30:00{_offset()}"
    db.close()
