"""C-2：启动期归档对账（悬空路径回填 + 过期目录孤儿清理）。"""


from pilotstd.core.archive_reconcile import reconcile_archive
from pilotstd.core.db import Database


def _insert(db, path: str) -> None:
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status)"
        " VALUES (?, 'GB/T', 1, 2020, -1, '测试标准', '现行')",
        (path,),
    )


def test_reconcile_repairs_moved_file_and_cleans_orphan(tmp_path) -> None:
    db = Database(str(tmp_path / "db.sqlite"))
    root = tmp_path / "standards"
    expire = root / "过期作废"
    expire.mkdir(parents=True)

    moved = expire / "GBT 1-2020.pdf"
    moved.write_bytes(b"%PDF-1.7")
    old_path = str(root / "归档" / "GBT 1-2020.pdf")
    _insert(db, old_path)

    existing = root / "existing.pdf"
    existing.write_bytes(b"%PDF-1.7")
    _insert(db, str(existing))

    orphan = expire / "orphan.pdf"
    orphan.write_bytes(b"%PDF-1.7")

    stats = reconcile_archive(db, str(root))
    assert stats["checked"] == 2
    assert stats["repaired"] == 1
    assert stats["orphans"] == 1
    row = db.fetchone("SELECT file_path FROM file_index WHERE file_path LIKE '%GBT 1-2020.pdf'")
    assert row["file_path"] == str(moved)
    assert not orphan.exists()
    recycled = list((root / ".recycle" / "expired_orphans").rglob("orphan.pdf"))
    assert len(recycled) == 1
    db.close()


def test_reconcile_warns_when_file_really_lost(tmp_path) -> None:
    db = Database(str(tmp_path / "db.sqlite"))
    root = tmp_path / "standards"
    root.mkdir()
    _insert(db, str(root / "lost.pdf"))
    stats = reconcile_archive(db, str(root))
    assert stats["missing"] == 1
    assert stats["repaired"] == 0
    db.close()


def test_reconcile_missing_root_is_noop(tmp_path) -> None:
    db = Database(str(tmp_path / "db.sqlite"))
    stats = reconcile_archive(db, str(tmp_path / "nope"))
    assert stats == {"checked": 0, "repaired": 0, "missing": 0, "orphans": 0}
    db.close()
