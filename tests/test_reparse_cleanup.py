"""公告 reparse：原地 upsert + 清理旧 pid 残留（且不得撞收藏外键）。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from pilotstd.announce.crawler_service import AnnounceCrawler
from pilotstd.announcement.matcher import AnnouncementMatcher
from pilotstd.core.db import Database


def _crawler(db, adapter, matcher):
    crawler = AnnounceCrawler.__new__(AnnounceCrawler)
    crawler._file_index = SimpleNamespace(_db=db)
    crawler._persistence = MagicMock()
    crawler._ocr_config = {}
    crawler._ocr_provider = None
    crawler._engine = SimpleNamespace(adapters=[adapter], matcher=matcher)
    return crawler


def test_reparse_upserts_before_cleanup() -> None:
    """重解析不得先 DELETE：必须 upsert（update_existing=True）后再清理残留。"""
    db = MagicMock()
    db.fetchone.side_effect = [
        {
            "id": 1,
            "pid": "new-pid",
            "announce_no": "2014年第4号(总第172号)",
            "title": "测试",
            "publish_date": "2014-05-16",
            "source_site": "announcement_hb",
        },
        {"c": 0},  # blocked 统计
    ]
    db.fetchall.return_value = []
    adapter = MagicMock()
    adapter.source_site = "announcement_hb"
    adapter.standard_category = "hb"
    adapter._process_one_detail.return_value = [{"std_code": "GA/T 1018-2013", "std_name": "测试"}]
    matcher = MagicMock()

    result = _crawler(db, adapter, matcher).reparse_from_source("2014年第4号(总第172号)")

    assert result["records"] == 1
    assert matcher.match_and_update.call_args.kwargs["update_existing"] is True
    # 第一条写语句应是 announcements 状态回写，而不是按公告号删记录
    sql, _params = db.execute.call_args_list[0].args
    assert "UPDATE announcements" in sql
    assert "DELETE FROM announcement_record" not in sql


def test_reparse_keeps_rows_referenced_by_favorites(tmp_path) -> None:
    """收藏引用某条记录时，重解析必须原地更新该行（id 不变），不能删。"""
    db = Database(str(tmp_path / "t.db"))
    db.execute("INSERT INTO users (id, username, password_hash, salt) VALUES (1,'u1','x','s')")
    db.execute(
        "INSERT INTO announcements (source_site, pid, announce_no, title, publish_date)"
        " VALUES ('announcement_gb','p1','2026年第99号','测试公告','2026-01-01')"
    )
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name, fetched_at)"
        " VALUES ('announcement_gb','p1','2026年第99号','GB 1-2020','旧名称','2026-01-01')"
    )
    rec_id = db.fetchone("SELECT id FROM announcement_record")["id"]
    db.execute("INSERT INTO user_favorites (user_id, record_id) VALUES (1, ?)", (rec_id,))

    adapter = MagicMock()
    adapter.source_site = "announcement_gb"
    adapter.standard_category = "NationalStd"
    adapter._process_one_detail.return_value = [
        {
            "std_code": "GB 1—2020",
            "std_name": "新名称",
            "announce_no": "2026年第99号",
            "_pid": "p1",
            "publish_date": "2026-01-01",
        }
    ]

    result = _crawler(db, adapter, AnnouncementMatcher(db)).reparse_from_source("2026年第99号")

    assert result["records"] == 1
    rows = db.fetchall("SELECT id, standard_number, std_name FROM announcement_record")
    assert len(rows) == 1
    assert rows[0]["id"] == rec_id, "原地 upsert 必须保留 row id（收藏外键指着它）"
    assert rows[0]["standard_number"] == "GB 1-2020"
    assert rows[0]["std_name"] == "新名称"
    assert db.fetchone("SELECT COUNT(*) AS c FROM user_favorites")["c"] == 1


def test_matcher_update_existing_preserves_id(tmp_path) -> None:
    db = Database(str(tmp_path / "m.db"))
    matcher = AnnouncementMatcher(db)
    item = {
        "std_code": "GB 2-2020",
        "std_name": "旧",
        "announce_no": "2026年第98号",
        "_pid": "p1",
        "publish_date": "2026-01-01",
    }
    matcher.match_and_update([dict(item)], source_site="announcement_gb")
    first = db.fetchone("SELECT id FROM announcement_record")

    matcher.match_and_update(
        [dict(item, std_name="新")], source_site="announcement_gb", update_existing=True
    )

    rows = db.fetchall("SELECT id, std_name FROM announcement_record")
    assert len(rows) == 1
    assert rows[0]["id"] == first["id"]
    assert rows[0]["std_name"] == "新"


def test_update_existing_keeps_announcement_scope(tmp_path) -> None:
    """唯一键含 pid：同一标准出现在不同公告里是两行，upsert 不得跨公告合并。"""
    db = Database(str(tmp_path / "o.db"))
    matcher = AnnouncementMatcher(db)
    base = {"std_code": "GB 3-2020", "std_name": "A", "publish_date": "2026-01-01"}
    matcher.match_and_update(
        [dict(base, announce_no="2026年第1号", _pid="p1")], source_site="announcement_gb"
    )
    matcher.match_and_update(
        [dict(base, announce_no="2026年第2号", _pid="p2", std_name="B")],
        source_site="announcement_gb",
        update_existing=True,
    )
    rows = db.fetchall("SELECT announce_no, std_name FROM announcement_record ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["announce_no"] == "2026年第1号"
    assert rows[1]["announce_no"] == "2026年第2号"


def test_reparse_removes_stale_rows_not_rewritten(tmp_path) -> None:
    """历史残留行（同号不同 language、fetched_at 早于本次）必须清掉；被引用的保留。"""
    db = Database(str(tmp_path / "stale.db"))
    db.execute("INSERT INTO users (id, username, password_hash, salt) VALUES (1,'u1','x','s')")
    db.execute(
        "INSERT INTO announcements (source_site, pid, announce_no, title, publish_date)"
        " VALUES ('announcement_gb','p1','2026年第8号','测试','2026-01-01')"
    )
    rows = [
        ("", "2020-01-01"),  # 会被 upsert 命中并刷新
        ("英文", "2020-01-01"),  # 同号不同键的历史残留 → 应删除
        ("日文", "2020-01-01"),  # 被收藏引用 → 必须保留
    ]
    ids = {}
    for lang, fetched in rows:
        db.execute(
            "INSERT INTO announcement_record (source_site, pid, announce_no, standard_number,"
            " std_name, fetched_at, language) VALUES ('announcement_gb','p1','2026年第8号',"
            " 'GB/T 1-2020','标准',?,?)",
            (fetched, lang),
        )
        ids[lang] = db.fetchone("SELECT MAX(id) AS id FROM announcement_record")["id"]
    db.execute("INSERT INTO user_favorites (user_id, record_id) VALUES (1, ?)", (ids["日文"],))

    adapter = MagicMock()
    adapter.source_site = "announcement_gb"
    adapter.standard_category = "NationalStd"
    adapter._process_one_detail.return_value = [
        {"std_code": "GB/T 1-2020", "std_name": "标准", "announce_no": "2026年第8号", "_pid": "p1"}
    ]
    result = _crawler(db, adapter, AnnouncementMatcher(db)).reparse_from_source("2026年第8号")

    assert result["records"] == 1
    langs = [r["language"] for r in db.fetchall("SELECT language FROM announcement_record")]
    assert "英文" not in langs, "未重写的旧版本行应被清理"
    assert "日文" in langs, "被收藏引用的行必须保留"
