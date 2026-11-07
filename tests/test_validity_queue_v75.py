"""v75：validity_check_queue 建表、入队、消费与失败回写。"""

from types import SimpleNamespace

from pilotstd.core.db import Database
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.manager.validity_service import ValidityService


class _Checker:
    def __init__(self):
        self.seen = []

    def check_standard(self, standard_number, query_engine=None):
        self.seen.append(standard_number)
        return {"status": "现行", "previous": None, "evidence": "test"}


def _manager(db, checker=None):
    return SimpleNamespace(db=db, validity_checker=checker, query_engine=None)


def test_enqueue_and_process_pending(tmp_path):
    db = Database(str(tmp_path / "queue.db"))
    path = "/standards/GB 19001-2016.pdf"
    FileIndexRepository(db).upsert(path, "GB/T", 19001, 2016)
    checker = _Checker()
    svc = ValidityService(_manager(db, checker))

    assert svc.enqueue_files([path])["enqueued"] == 1
    assert db.fetchone("SELECT status FROM validity_check_queue WHERE file_path=?", (path,))["status"] == "pending"

    result = svc.process_pending()
    assert result == {"processed": 1, "success": 1, "failed": 0, "skipped": 0}
    assert checker.seen == ["GB/T 19001-2016"]
    assert db.fetchone("SELECT status, error FROM validity_check_queue WHERE file_path=?", (path,)) == {
        "status": "success",
        "error": "",
    }
    db.close()


def test_enqueue_duplicate_pending_is_idempotent(tmp_path):
    db = Database(str(tmp_path / "queue2.db"))
    path = "/standards/GB 19001-2016.pdf"
    FileIndexRepository(db).upsert(path, "GB/T", 19001, 2016)
    svc = ValidityService(_manager(db, _Checker()))

    assert svc.enqueue_files([path])["enqueued"] == 1
    second = svc.enqueue_files([path])
    assert second["enqueued"] == 0
    assert second["ok"] is True
    db.close()


def test_unindexed_file_is_failed(tmp_path):
    db = Database(str(tmp_path / "queue3.db"))
    svc = ValidityService(_manager(db, _Checker()))

    assert svc.enqueue_files(["/standards/missing.pdf"])["enqueued"] == 1
    result = svc.process_pending()
    assert result["failed"] == 1
    row = db.fetchone("SELECT status, error FROM validity_check_queue WHERE file_path=?", ("/standards/missing.pdf",))
    assert row["status"] == "failed"
    assert "未索引" in row["error"]
    db.close()


def test_queue_table_exists(tmp_path):
    db = Database(str(tmp_path / "queue4.db"))
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='validity_check_queue'")
    assert row is not None
    db.close()
