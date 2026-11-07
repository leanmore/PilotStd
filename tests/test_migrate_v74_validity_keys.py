"""v74：修复 standard_validity 前导空格/缺代号键；冲突合并、无匹配保留、幂等。"""

from pilotstd.core.db import Database
from pilotstd.core.db._migrate_v74_repair_validity_keys import _migrate_v74_repair_validity_keys
from pilotstd.core.file_index import FileIndexRepository


def _validity(db, number, **kwargs):
    cols = ["standard_number", *kwargs.keys()]
    sql = f"INSERT INTO standard_validity ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    db.execute(sql, (number, *kwargs.values()))


def test_v74_renames_unique_and_merges_collision_and_keeps_unresolved(tmp_path):
    db = Database(str(tmp_path / "v74.db"))
    repo = FileIndexRepository(db)
    repo.upsert("/standards/GB/T 11120-2011.pdf", "GB/T", 11120, 2011)
    repo.upsert("/standards/NB/T 47014-2011.pdf", "NB/T", 47014, 2011)
    # 唯一可还原
    _validity(db, " 11120-2011", status="未知", check_count=1)
    # 冲突：规范行 + 畸形行
    _validity(db, "NB/T 47014-2011", status="未知", check_count=0)
    _validity(db, " 47014-2011", status="未知", check_count=2, last_checked_at="2026-11-01T00:00:00+08:00")
    # 无匹配
    _validity(db, " 19001-2020", status="未知", check_count=1)

    _migrate_v74_repair_validity_keys(db)

    keys = {r["standard_number"] for r in db.fetchall("SELECT standard_number FROM standard_validity")}
    assert "GB/T 11120-2011" in keys
    assert "NB/T 47014-2011" in keys
    assert " 11120-2011" not in keys
    assert " 47014-2011" not in keys
    assert " 19001-2020" in keys

    merged = db.fetchone(
        "SELECT check_count, last_checked_at FROM standard_validity WHERE standard_number='NB/T 47014-2011'"
    )
    assert merged["check_count"] == 2
    assert merged["last_checked_at"] == "2026-11-01T00:00:00+08:00"

    # 幂等
    _migrate_v74_repair_validity_keys(db)
    assert db.fetchone("SELECT COUNT(*) AS c FROM standard_validity")["c"] == 3
    db.close()
