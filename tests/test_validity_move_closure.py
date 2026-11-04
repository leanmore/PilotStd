"""废止搬家闭环（D3-1/D3-3/D3-4）：先搬后写库、分 part、回写 file_index。"""

import os

import pytest

from pilotstd.core.db import Database
from pilotstd.core.validity_checker import ValidityChecker


def _db(tmp_path):
    return Database(str(tmp_path / "v.db"))


def _make_file(root, name, content=b"%PDF-1.4 body"):
    path = root / name
    path.write_bytes(content)
    return str(path)


def test_move_expired_is_part_scoped(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    monkeypatch.setenv("STANDARD_ROOT", str(lib))
    db = _db(tmp_path)
    p1 = _make_file(lib, "GBT 1234.1-2020 标准一.pdf")
    p2 = _make_file(lib, "GBT 1234.2-2020 标准二.pdf")
    for path, part in ((p1, 1), (p2, 2)):
        db.execute(
            "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name,"
            " file_hash, status, scanned_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (path, "GB/T", 1234, 2020, part, os.path.basename(path), "h", "现行", "2026-01-01"),
        )

    checker = ValidityChecker(db)
    moved = checker._move_expired_file("GB/T 1234.1-2020", "已废止")

    assert moved is not None
    assert len(moved) == 1
    old, new = moved[0]
    assert old == p1
    assert "过期作废" in new.replace("\\", "/")
    assert os.path.exists(new)
    assert not os.path.exists(p1)
    assert os.path.exists(p2), "同号其它分部不得被搬走"


def test_amendment_file_is_not_moved(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    monkeypatch.setenv("STANDARD_ROOT", str(lib))
    db = _db(tmp_path)
    base = _make_file(lib, "GBT 1234-2020 标准.pdf")
    amend = _make_file(lib, "GBT 1234-2020 第1号修改单.pdf")
    for path, name in ((base, "标准"), (amend, "标准 第1号修改单")):
        db.execute(
            "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name,"
            " file_hash, status, scanned_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (path, "GB/T", 1234, 2020, -1, name, "h", "现行", "2026-01-01"),
        )

    moved = ValidityChecker(db)._move_expired_file("GB/T 1234-2020", "已废止")

    assert moved is not None
    assert [old for old, _ in moved] == [base]
    assert os.path.exists(amend)


def test_update_status_rolls_forward_only_after_move(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    monkeypatch.setenv("STANDARD_ROOT", str(lib))
    db = _db(tmp_path)
    src = _make_file(lib, "GBT 1234-2020 标准.pdf")
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name,"
        " file_hash, status, scanned_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (src, "GB/T", 1234, 2020, -1, "标准", "h", "现行", "2026-01-01"),
    )
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_checked_at, next_check_at,"
        " check_count, created_at, updated_at) VALUES ('GB/T 1234-2020','现行','2026-01-01',"
        " '2026-01-01',1,'2026-01-01','2026-01-01')"
    )
    checker = ValidityChecker(db)
    monkeypatch.setattr(checker, "should_apply_side_effects", lambda evidence: True)

    checker.update_status("GB/T 1234-2020", "已废止", evidence="L2")

    assert db.fetchone("SELECT status FROM standard_validity")["status"] == "已废止"
    new_path = db.fetchone("SELECT file_path FROM file_index")["file_path"]
    assert os.path.exists(new_path) and "过期作废" in new_path.replace("\\", "/")


def test_update_status_keeps_state_when_move_fails(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    monkeypatch.setenv("STANDARD_ROOT", str(lib))
    db = _db(tmp_path)
    src = _make_file(lib, "GBT 1234-2020 标准.pdf")
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name,"
        " file_hash, status, scanned_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (src, "GB/T", 1234, 2020, -1, "标准", "h", "现行", "2026-01-01"),
    )
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_checked_at, next_check_at,"
        " check_count, created_at, updated_at) VALUES ('GB/T 1234-2020','现行','2026-01-01',"
        " '2026-01-01',1,'2026-01-01','2026-01-01')"
    )
    checker = ValidityChecker(db)
    monkeypatch.setattr(checker, "should_apply_side_effects", lambda evidence: True)
    monkeypatch.setattr(checker, "_move_expired_file", lambda *a, **k: None)

    checker.update_status("GB/T 1234-2020", "已废止", evidence="L2")

    assert db.fetchone("SELECT status FROM standard_validity")["status"] == "现行"
    assert os.path.exists(src)


@pytest.mark.parametrize("status", ["已废止", "被代替", "作废"])
def test_abolished_statuses_trigger_move(tmp_path, monkeypatch, status):
    lib = tmp_path / "lib"
    lib.mkdir()
    monkeypatch.setenv("STANDARD_ROOT", str(lib))
    db = _db(tmp_path)
    src = _make_file(lib, "GBT 1234-2020 标准.pdf")
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name,"
        " file_hash, status, scanned_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (src, "GB/T", 1234, 2020, -1, "标准", "h", "现行", "2026-01-01"),
    )
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_checked_at, next_check_at,"
        " check_count, created_at, updated_at) VALUES ('GB/T 1234-2020','现行','2026-01-01',"
        " '2026-01-01',1,'2026-01-01','2026-01-01')"
    )
    checker = ValidityChecker(db)
    monkeypatch.setattr(checker, "should_apply_side_effects", lambda evidence: True)

    checker.update_status("GB/T 1234-2020", status, evidence="L2")

    assert db.fetchone("SELECT status FROM standard_validity")["status"] == status
    assert "过期作废" in db.fetchone("SELECT file_path FROM file_index")["file_path"].replace("\\", "/")
