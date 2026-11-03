"""公告单条重解析：修复历史解析缺口（HTML/附件通用）。"""

from __future__ import annotations

from unittest.mock import MagicMock

from pilotstd.announce.crawler_service import AnnounceCrawler


class _Adapter:
    source_site = "announcement_hb"
    standard_category = "IndustryStd"

    def _process_one_detail(self, ann, ocr, bump):
        assert ann["pid"] == "p1"
        return [{"std_code": "SJ/T 11460.6.1-2025", "std_name": "x", "_pid": "p1"}]


class _Engine:
    adapters = [_Adapter()]
    matcher = MagicMock()


def test_reparse_replaces_records_after_successful_parse() -> None:
    crawler = object.__new__(AnnounceCrawler)
    crawler._file_index = MagicMock()
    crawler._file_index._db.fetchone.side_effect = [
        {
            "id": 1,
            "pid": "p1",
            "announce_no": "2026年第7号(总第315号)",
            "title": "t",
            "publish_date": "2026-08-01",
            "source_site": "announcement_hb",
        },
        {"c": 0},
    ]
    crawler._engine = _Engine()
    crawler._ocr_config = None
    crawler._ocr_provider = None
    crawler._file_index._db.fetchall.return_value = []

    result = crawler.reparse_from_source("2026年第7号(总第315号)")

    assert result == {"status": "reparsed", "announce_no": "2026年第7号(总第315号)", "records": 1}
    db = crawler._file_index._db
    # 解析成功后才动数据：先原地 upsert（保留 row id，收藏外键不断），再清理未解析旧行
    assert crawler._engine.matcher.match_and_update.call_args.kwargs["update_existing"] is True
    sqls = [c.args[0] for c in db.execute.call_args_list]
    assert sqls[-1].startswith("UPDATE announcements SET parse_status")
    assert not any(s.startswith("DELETE FROM announcement_record") for s in sqls)


def test_reparse_does_not_delete_when_parse_empty() -> None:
    crawler = object.__new__(AnnounceCrawler)
    crawler._file_index = MagicMock()
    crawler._file_index._db.fetchone.return_value = {
        "id": 1,
        "pid": "p1",
        "announce_no": "n",
        "title": "t",
        "publish_date": "2026-08-01",
        "source_site": "announcement_hb",
    }

    class EmptyAdapter(_Adapter):
        def _process_one_detail(self, ann, ocr, bump):
            return []

    engine = _Engine()
    engine.adapters = [EmptyAdapter()]
    crawler._engine = engine
    crawler._ocr_config = None
    crawler._ocr_provider = None

    try:
        crawler.reparse_from_source("n")
    except ValueError as exc:
        assert "no records" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    crawler._file_index._db.execute.assert_not_called()
