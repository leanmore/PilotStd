"""时效性检查新增路径：排除过期目录、替代标准入队、批量变更。"""

from datetime import datetime, timedelta, timezone

from pilotstd.core._validity_pipeline import _enqueue_gb_replacement, _process_validity_batch
from pilotstd.core.db import Database
from pilotstd.core.validity_checker import ValidityChecker


def test_file_index_exists_and_exclude_sql(tmp_path) -> None:
    db = Database(str(tmp_path / "v.db"))
    checker = ValidityChecker(db)
    assert checker._file_index_exists() is True
    clause, pattern = checker._exclude_expired_sql()
    assert "file_index" in clause
    assert pattern == "%/过期作废/%"
    db.close()


def test_count_and_random_due(tmp_path) -> None:
    db = Database(str(tmp_path / "v.db"))
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    for i in range(3):
        db.execute(
            "INSERT INTO standard_validity (standard_number, status, next_check_at) VALUES (?, ?, ?)",
            (f"GB {i}-2020", "现行", past),
        )
    checker = ValidityChecker(db)
    assert checker.count_due_standards() == 3
    assert len(checker.get_due_standards_random(2)) == 2
    db.close()


def test_enqueue_gb_replacement(tmp_path) -> None:
    db = Database(str(tmp_path / "v.db"))
    _enqueue_gb_replacement(db, "GB/T 1-2024", "新标准")
    row = db.fetchone("SELECT standard_number, status FROM download_queue")
    assert row is not None and row["standard_number"] == "GB/T 1-2024"
    db.close()


class _Checker:
    def check_standard(self, std):
        return {"status": "已废止", "new_standard": "GB/T 1-2024", "new_standard_name": "新标准"}

    def update_status(self, *args):
        return None


class _Notify:
    def __init__(self):
        self.events = []

    def send_event(self, event, data):
        self.events.append((event, data))


def test_process_batch_reports_replacement(tmp_path) -> None:
    db = Database(str(tmp_path / "v.db"))
    db.execute("INSERT INTO standard_validity (standard_number, status) VALUES ('GB 1-2020', '现行')")
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, standard_number, std_name, superseded_by, fetched_at)"
        " VALUES ('test', 'p1', 'GB 1-2020', '旧标准', 'GB/T 1-2024', '2020-01-01')"
    )
    changed, changed_list, failed, detail = _process_validity_batch(
        ["GB 1-2020"], _Checker(), db, _Notify(), 10, 0
    )
    assert changed == 1 and changed_list == ["GB 1-2020"]
    assert detail[0]["new_standard"] == "GB/T 1-2024"
    db.close()


def test_status_notification_includes_new_standard_name() -> None:
    from pilotstd.core.notification._builders_validity import _build_standard_status_changed_message

    msg = _build_standard_status_changed_message(
        {
            "standard_number": "GB 1-2020",
            "old_status": "现行",
            "new_status": "已废止",
            "is_expired": True,
            "new_standard": "GB/T 1-2024",
            "new_standard_name": "新标准名称",
        }
    )
    texts = [getattr(b, "text", "") for b in msg.blocks]
    assert any("GB/T 1-2024" in x and "新标准名称" in x for x in texts)
