"""时效性检查排除 file_index 中“过期作废”目录下的标准。"""

from pilotstd.core.db import Database
from pilotstd.core.validity_checker import ValidityChecker


def test_due_standards_excludes_expire_folder(tmp_path) -> None:
    db = Database(str(tmp_path / "validity.db"))
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, next_check_at) VALUES (?, ?, ?)",
        ("GB 1-2020", "现行", "2020-01-01T00:00:00"),
    )
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, next_check_at) VALUES (?, ?, ?)",
        ("GB 2-2020", "现行", "2020-01-01T00:00:00"),
    )
    for code, number, path in (
        ("GB", 1, "/standards/GB/过期作废/GB 1-2020.pdf"),
        ("GB", 2, "/standards/GB/GB 2-2020.pdf"),
    ):
        db.execute(
            "INSERT INTO file_index (file_path, logical_code, number, year, scanned_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (path, code, number, 2020, "2020-01-01"),
        )
    checker = ValidityChecker(db)
    due = checker.get_due_standards()
    assert "GB 1-2020" not in due
    assert "GB 2-2020" in due
    db.close()
