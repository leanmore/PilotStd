"""批次二：公告入库按归一化标准号去重（v72 迁移 + matcher 入库键）。"""

import pytest

from pilotstd.core.db import Database
from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION
from pilotstd.core.db._migrate_v72_announcement_dedupe import _migrate_v72_announcement_dedupe


@pytest.fixture()
def db(tmp_path):
    return Database(str(tmp_path / "t.db"))


def _insert(db, code, name="", announce_no="2026年第45号", count=42, lang=""):
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name, fetched_at,"
        "  standard_count, language)"
        " VALUES ('announcement_gb','p1',?,?,?,'2026-01-01',?,?)",
        (announce_no, code, name, count, lang),
    )


def test_schema_reaches_v72(db):
    assert db.schema_version == CURRENT_SCHEMA_VERSION
    assert CURRENT_SCHEMA_VERSION >= 72


def test_v72_merges_only_when_all_fields_equal(db):
    """破折号不同但全字段一致 → 合并为 1 行，standard_count 重算为 1。"""
    _insert(db, "GB 11887-2026", "首饰 贵金属纯度")
    _insert(db, "GB 11887—2026", "首饰 贵金属纯度")
    assert db.fetchone("SELECT COUNT(*) AS c FROM announcement_record")["c"] == 2

    _migrate_v72_announcement_dedupe(db)

    rows = db.fetchall("SELECT standard_number, std_name, standard_count FROM announcement_record")
    assert len(rows) == 1
    assert rows[0]["standard_number"] == "GB 11887-2026"
    assert rows[0]["standard_count"] == 1


def test_v72_keeps_both_when_any_field_differs(db):
    """归一化后撞键但名称不同 → 严禁合并，两行都保留。"""
    _insert(db, "GB 2-2020", "")
    _insert(db, "GB 2—2020", "有名称的那行")
    _migrate_v72_announcement_dedupe(db)

    rows = db.fetchall("SELECT standard_number, std_name FROM announcement_record ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["standard_number"] == "GB 2-2020"
    assert rows[1]["standard_number"] == "GB 2—2020"


def test_v72_is_idempotent(db):
    _insert(db, "GB 1-2020", "标准一")
    _insert(db, "GB 1—2020", "标准一")
    _migrate_v72_announcement_dedupe(db)

    before = db.fetchall("SELECT id, standard_number, standard_count FROM announcement_record")
    _migrate_v72_announcement_dedupe(db)
    after = db.fetchall("SELECT id, standard_number, standard_count FROM announcement_record")
    assert before == after


def test_match_cache_unique_index_comes_from_v5(db):
    """announcement_match 的唯一索引沿用 v5（v72 不重复建）。"""
    row = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_announcement_match_lookup'"
    )
    assert row is not None
    db.execute(
        "INSERT INTO announcement_match (standard_number, source_site, result_json, cached_at)"
        " VALUES ('GB 3-2020','announcement_gb','{\"x\":0}','2026-01-01')"
    )
    db.execute(
        "INSERT OR REPLACE INTO announcement_match (standard_number, source_site, result_json, cached_at)"
        " VALUES ('GB 3-2020','announcement_gb','{\"x\":1}','2026-02-01')"
    )
    rows = db.fetchall("SELECT result_json FROM announcement_match")
    assert len(rows) == 1
    assert '"x":1' in rows[0]["result_json"]


def test_matcher_stores_normalized_code_once(db):
    """同一公告 HTML/附件两种写法 → announcement_record 只落一行。"""
    from pilotstd.announcement.matcher import AnnouncementMatcher

    matcher = AnnouncementMatcher(db)
    items = [
        {
            "std_code": "GB 11887-2026",
            "std_name": "首饰 贵金属纯度",
            "announce_no": "2026年第45号",
            "_pid": "p1",
            "publish_date": "2026-01-01",
        },
        {
            "std_code": "GB 11887—2026",
            "std_name": "首饰 贵金属纯度",
            "announce_no": "2026年第45号",
            "_pid": "p1",
            "publish_date": "2026-01-01",
        },
    ]
    result = matcher.match_and_update(items, source_site="announcement_gb")

    rows = db.fetchall("SELECT standard_number FROM announcement_record")
    assert len(rows) == 1
    assert rows[0]["standard_number"] == "GB 11887-2026"
    assert result["inserted"] == 1
    assert result["duplicates"] == 1
