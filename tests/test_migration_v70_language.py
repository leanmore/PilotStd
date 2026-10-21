"""v70：公告记录语种/外文名 + 同标准号多语种共存。"""

from __future__ import annotations

import pytest


@pytest.fixture()
def db(tmp_path):
    from pilotstd.core.db import Database

    database = Database(str(tmp_path / "v70.db"))
    yield database
    database.close()


def _insert(db, language: str, name: str) -> None:
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name, fetched_at,"
        "  language, foreign_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("announcement_gb", "p1", "2026年第29号", "GB/T 29548-2024", name, "2026-10-21", language, name),
    )


def test_same_standard_different_languages_coexist(db) -> None:
    _insert(db, "英文", "English")
    _insert(db, "德文", "Deutsch")
    rows = db.fetchall("SELECT language FROM announcement_record ORDER BY language")
    assert [r["language"] for r in rows] == ["德文", "英文"]


def test_schema_has_language_and_foreign_name(db) -> None:
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(announcement_record)")}
    assert {"language", "foreign_name"} <= cols


def test_matcher_keeps_both_language_rows(db) -> None:
    from pilotstd.announcement.matcher import AnnouncementMatcher

    items = [
        {
            "_pid": "p1",
            "announce_no": "2026年第29号",
            "std_code": "GB/T 29548-2024",
            "std_name": "中文名",
            "language": "英文",
            "foreign_name": "English",
        },
        {
            "_pid": "p1",
            "announce_no": "2026年第29号",
            "std_code": "GB/T 29548-2024",
            "std_name": "中文名",
            "language": "德文",
            "foreign_name": "Deutsch",
        },
    ]
    AnnouncementMatcher(db).match_and_update(items, source_site="announcement_gb", standard_category="NationalStd")
    rows = db.fetchall("SELECT language FROM announcement_record ORDER BY language")
    assert [r["language"] for r in rows] == ["德文", "英文"]
