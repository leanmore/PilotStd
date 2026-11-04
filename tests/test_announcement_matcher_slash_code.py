"""公告↔本地库交叉比对：代号双向兼容 + 同号多版本按年代号（D4-1 / D4-2）。

背景（2026-11-04 生产实测）：`parse_std_number` 的 `code` 已去掉斜杠（`GBT`），
而 `file_index.logical_code` 存的是 `GB/T` ⇒ 含斜杠公告 201,499 条只命中 1 条。
"""

import json

from pilotstd.announcement.matcher import AnnouncementMatcher
from pilotstd.core.db import Database
from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser


def _db(tmp_path):
    return Database(str(tmp_path / "m.db"))


def _insert_fi(db, path, code, number, year, name="本地标准", part=-1):
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name,"
        " file_hash, status, scanned_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (path, code, number, year, part, name, "h" + path, "现行", "2026-01-01"),
    )


def _announce(std_code, year, name="新版标准", impl="2026-06-01", replaces=""):
    return {
        "std_code": std_code,
        "std_name": name,
        "announce_no": "2026年第1号",
        "_pid": "p1",
        "publish_date": "2026-01-01",
        "implementation_date": impl,
        "announcement_title": "关于批准发布…的公告",
        "replaces_code": replaces or f"{std_code.rsplit('-', 1)[0]}-{year - 10}",
    }


def test_slash_code_matches_slash_index(tmp_path):
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GB_T 1234-2020.pdf", "GB/T", 1234, 2020)
    res = AnnouncementMatcher(db).match_and_update(
        [_announce("GB/T 1234-2020", 2020)], source_site="announcement_gb"
    )
    assert res["matched"] == 1
    assert db.fetchone("SELECT COUNT(*) AS c FROM announcement_match")["c"] == 1


def test_slash_code_matches_legacy_no_slash_index(tmp_path):
    """历史行可能存 `GBT`，公告是 `GB/T`，必须双向兼容。"""
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GBT 1234-2020.pdf", "GBT", 1234, 2020)
    res = AnnouncementMatcher(db).match_and_update(
        [_announce("GB/T 1234-2020", 2020)], source_site="announcement_gb"
    )
    assert res["matched"] == 1


def test_scan_naming_convention_matches_announcement(tmp_path):
    """回归：`GBT 1234-2020.pdf` 扫描入库后，能与公告 `GB/T 1234-2020` 匹配。"""
    parser = StandardParser(build_code_mapping())
    info = parser.parse("GBT 1234-2020.pdf")
    assert info is not None
    assert info.logical_code == "GB/T"  # 入库代号统一为带斜杠形态
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GBT 1234-2020.pdf", info.logical_code, info.number, info.year)
    res = AnnouncementMatcher(db).match_and_update(
        [_announce("GB/T 1234-2020", 2020)], source_site="announcement_gb"
    )
    assert res["matched"] == 1


def test_new_version_does_not_overwrite_old(tmp_path):
    """本地 2010、公告 2020：写 2020 的“发现新版”行，旧版状态保持不变。"""
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GB_T 1234-2010.pdf", "GB/T", 1234, 2010, "旧版标准")
    db.execute(
        "INSERT INTO announcement_match (standard_number, source_site, result_json, cached_at)"
        " VALUES ('GB/T 1234-2010','announcement_gb',?, '2026-01-01')",
        (json.dumps({"status": "现行", "standard_name": "旧版标准", "match_status": "exact"}, ensure_ascii=False),),
    )
    res = AnnouncementMatcher(db).match_and_update(
        [_announce("GB/T 1234-2020", 2020)], source_site="announcement_gb"
    )
    assert res["matched"] == 1
    assert "GB/T 1234-2020" in res["new_versions"]

    old = json.loads(
        db.fetchone("SELECT result_json FROM announcement_match WHERE standard_number='GB/T 1234-2010'")[
            "result_json"
        ]
    )
    new = json.loads(
        db.fetchone("SELECT result_json FROM announcement_match WHERE standard_number='GB/T 1234-2020'")[
            "result_json"
        ]
    )
    assert old["standard_name"] == "旧版标准"
    assert old["status"] == "现行"
    assert new["is_new_version"] is True
    assert new["local_year"] == 2010
    assert new["match_status"] == "new_version"
    assert new["standard_name"] == "新版标准"


def test_old_announcement_does_not_downgrade_new_file(tmp_path):
    """重抓历史公告（2010）不得覆盖本地新版（2020）缓存。"""
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GB_T 1234-2020.pdf", "GB/T", 1234, 2020, "新版标准")
    res = AnnouncementMatcher(db).match_and_update(
        [_announce("GB/T 1234-2010", 2010)], source_site="announcement_gb"
    )
    assert res["updated"] == 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM announcement_match")["c"] == 0


def test_same_year_updates_in_place(tmp_path):
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GB_T 1234-2020.pdf", "GB/T", 1234, 2020)
    res = AnnouncementMatcher(db).match_and_update(
        [_announce("GB/T 1234-2020", 2020)], source_site="announcement_gb"
    )
    assert res["updated"] == 1
    assert res["new_versions"] == []
    row = db.fetchone("SELECT standard_number FROM announcement_match")
    assert row["standard_number"] == "GB/T 1234-2020"


def test_replaced_match_keeps_old_key(tmp_path):
    """被代替匹配的是旧标准：不得用新标准年代号改写缓存键（审计 P0）。"""
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GB_T 5678-2010.pdf", "GB/T", 5678, 2010, "旧标准")
    item = {
        "std_code": "GB/T 1234-2020",
        "std_name": "新标准",
        "announce_no": "2026年第1号",
        "_pid": "p1",
        "publish_date": "2026-01-01",
        "implementation_date": "2026-06-01",
        "announcement_title": "公告",
        "replaces_code": "GB/T 5678-2010",
    }
    res = AnnouncementMatcher(db).match_and_update([item], source_site="announcement_gb")

    rows = db.fetchall("SELECT standard_number, result_json FROM announcement_match")
    assert len(rows) == 1
    assert rows[0]["standard_number"] == "GB/T 5678-2010"
    assert json.loads(rows[0]["result_json"])["status"] == "被代替"
    assert res["new_versions"] == []


def test_part_standard_cache_key_includes_part(tmp_path):
    """分部标准的缓存键必须带 .part，否则 get_full_info 的精确 JOIN 匹配不上。"""
    db = _db(tmp_path)
    _insert_fi(db, "/lib/GB_T 1234.1-2020.pdf", "GB/T", 1234, 2020, "一分部", part=1)
    res = AnnouncementMatcher(db).match_and_update(
        [_announce("GB/T 1234.1-2020", 2020)], source_site="announcement_gb"
    )
    assert res["matched"] == 1
    row = db.fetchone("SELECT standard_number FROM announcement_match")
    assert row["standard_number"] == "GB/T 1234.1-2020"
