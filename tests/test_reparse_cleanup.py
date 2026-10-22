"""公告 reparse 必须清理同一公告号的旧 pid 残留，否则 reconcile 永远对不上。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from pilotstd.announce.crawler_service import AnnounceCrawler


def test_reparse_deletes_by_source_and_announce_no() -> None:
    db = MagicMock()
    db.fetchone.return_value = {
        "id": 1,
        "pid": "new-pid",
        "announce_no": "2014年第4号(总第172号)",
        "title": "测试",
        "publish_date": "2014-05-16",
        "source_site": "announcement_hb",
    }
    adapter = MagicMock()
    adapter.source_site = "announcement_hb"
    adapter.standard_category = "hb"
    adapter._process_one_detail.return_value = [{"std_code": "GA/T 1018-2013", "std_name": "测试"}]
    matcher = MagicMock()
    crawler = AnnounceCrawler.__new__(AnnounceCrawler)
    crawler._file_index = SimpleNamespace(_db=db)
    crawler._persistence = MagicMock()
    crawler._ocr_config = {}
    crawler._ocr_provider = None
    crawler._engine = SimpleNamespace(adapters=[adapter], matcher=matcher)

    result = crawler.reparse_from_source("2014年第4号(总第172号)")

    assert result["records"] == 1
    sql, params = db.execute.call_args_list[0].args
    assert "announce_no" in sql
    assert params[0] == "announcement_hb"
    assert params[2] == "2014年第4号(总第172号)"
